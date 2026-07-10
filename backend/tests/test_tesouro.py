"""Testes offline do conector Tesouro Direto (app.services.tesouro).

Sem rede/DB reais: httpx.MockTransport + fixtures CSV inline latin-1 com o
header REAL da STN, e sessões fake para o upsert. Cobre os deltas 5 da
reconciliação: CSV NÃO cronológico (max Data Base), mapa completo sigla<->tipo,
ambiguidade de vencimento abstém, staleness 30d e janela diária+amostra mensal.
"""

from __future__ import annotations

import datetime as dt
import inspect
import uuid
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from app.services import http_client, tesouro
from app.services.dados import DadoNaoEncontrado
from app.services.tesouro import (
    _MAX_CSV_BYTES,
    STALENESS_DIAS,
    TIPO_POR_FAMILIA,
    URL_CSV,
    _recuar_meses,
    escolher_atual,
    ingest_titulo,
    parse_csv_tesouro,
    resolver_vencimento,
    selecionar_janela,
    titulo_atual,
)

_HEADER = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;"
    "PU Compra Manha;PU Venda Manha;PU Base Manha\n"
)

# Fixture principal: Data Base FORA de ordem cronológica (05/07, 07/07, 06/07)
# — prova que a leitura "atual" usa max(Data Base), nunca "última linha".
# Inclui 'Tesouro IPCA+ com Juros Semestrais' com o MESMO vencimento/ano para
# provar que o casamento do tipo é por igualdade exata (IPCA não puxa IPCAJ).
_CSV_BASE = (
    _HEADER + "Tesouro IPCA+;15/05/2035;05/07/2026;7,60;7,66;2.100,00;2.095,00;2.098,00\n"
    "Tesouro IPCA+;15/05/2035;07/07/2026;7,55;7,61;2.110,50;2.105,10;2.108,00\n"
    "Tesouro IPCA+;15/05/2035;06/07/2026;7,58;7,63;2.105,00;2.100,00;2.102,00\n"
    "Tesouro IPCA+ com Juros Semestrais;15/05/2035;07/07/2026;"
    "7,40;7,46;4.100,00;4.090,00;4.095,00\n"
    "Tesouro Prefixado;01/01/2029;07/07/2026;13,52;13,64;720,10;715,30;718,00\n"
    "Tesouro Selic;01/03/2031;07/07/2026;0,05;0,09;16.500,00;16.480,00;16.490,00\n"
).encode("latin-1")

_HOJE = dt.date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Parse: decimal vírgula, DD/MM/AAAA, linhas inválidas descartadas
# ---------------------------------------------------------------------------
def test_parse_decimal_virgula_e_data_br() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE)
    pre = next(ln for ln in linhas if ln["tipo"] == "Tesouro Prefixado")
    assert pre["taxa_compra"] == 13.52  # '13,52' -> 13.52
    assert pre["data_vencimento"] == dt.date(2029, 1, 1)  # '01/01/2029' -> date
    ipca = next(ln for ln in linhas if ln["data_base"] == dt.date(2026, 7, 7))
    assert ipca["pu_compra"] == 2110.50  # '2.110,50' (milhar com ponto) -> 2110.5


def test_parse_data_vencimento_dd_mm_aaaa() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE)
    assert any(ln["data_vencimento"] == dt.date(2035, 5, 15) for ln in linhas)


def test_parse_descarta_linha_sem_data_valida() -> None:
    csv_ruim = (
        _HEADER + "Tesouro Prefixado;01/01/2029;;13,52;13,64;720,10;715,30;718,00\n"
        "Tesouro Prefixado;01/01/2029;07/07/2026;13,52;13,64;720,10;715,30;718,00\n"
        ";15/05/2035;07/07/2026;7,55;7,61;1,00;1,00;1,00\n"
    ).encode("latin-1")
    linhas = parse_csv_tesouro(csv_ruim)
    assert len(linhas) == 1  # sem Data Base OU sem tipo -> fora (nunca inventa)


def test_parse_filtra_por_tipo_quando_pedido() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE, tipos={"Tesouro IPCA+"})
    assert {ln["tipo"] for ln in linhas} == {"Tesouro IPCA+"}
    assert len(linhas) == 3  # IPCAJ (mesmo prefixo) NÃO entra — igualdade exata


# ---------------------------------------------------------------------------
# Mapa sigla <-> 'Tipo Titulo' (delta 5 — completo e exato)
# ---------------------------------------------------------------------------
def test_mapa_familia_tipo_completo() -> None:
    assert TIPO_POR_FAMILIA == {
        "PRE": "Tesouro Prefixado",
        "PREJ": "Tesouro Prefixado com Juros Semestrais",
        "SELIC": "Tesouro Selic",
        "IPCA": "Tesouro IPCA+",
        "IPCAJ": "Tesouro IPCA+ com Juros Semestrais",
        "IGPMJ": "Tesouro IGPM+ com Juros Semestrais",
        "RENDA": "Tesouro Renda+ Aposentadoria Extra",
        "EDUCA": "Tesouro Educa+",
    }


# ---------------------------------------------------------------------------
# resolver_vencimento — DISTINCT, nunca contagem de linhas
# ---------------------------------------------------------------------------
def test_resolver_um_vencimento_com_n_data_bases_resolve() -> None:
    # 3 data_bases do MESMO vencimento não são ambiguidade (DISTINCT, não count).
    linhas = parse_csv_tesouro(_CSV_BASE)
    assert resolver_vencimento(linhas, "IPCA", 2035) == dt.date(2035, 5, 15)


def test_resolver_ipca_nao_casa_ipca_com_juros() -> None:
    # Só a linha IPCAJ tem taxa 7,40; se IPCA a puxasse, haveria contaminação.
    linhas = parse_csv_tesouro(_CSV_BASE)
    venc = resolver_vencimento(linhas, "IPCAJ", 2035)
    assert venc == dt.date(2035, 5, 15)
    do_ipcaj = [ln for ln in linhas if ln["tipo"] == "Tesouro IPCA+ com Juros Semestrais"]
    assert len(do_ipcaj) == 1 and do_ipcaj[0]["taxa_compra"] == 7.40


def test_resolver_sem_vencimento_no_ano_abstem() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE)
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        resolver_vencimento(linhas, "EDUCA", 2035)


def test_resolver_familia_desconhecida_abstem() -> None:
    with pytest.raises(DadoNaoEncontrado, match="família"):
        resolver_vencimento([], "XPTO", 2035)


def test_resolver_dois_vencimentos_distintos_no_ano_abstem() -> None:
    # Guarda da premissa NTN-B (15/05 e 15/08 no mesmo ano): 2+ DISTINTOS -> abstém.
    csv_ambiguo = (
        _HEADER + "Tesouro IPCA+;15/05/2035;07/07/2026;7,55;7,61;2.110,50;2.105,10;2.108,00\n"
        "Tesouro IPCA+;15/08/2035;07/07/2026;7,50;7,56;2.050,00;2.045,00;2.048,00\n"
    ).encode("latin-1")
    with pytest.raises(DadoNaoEncontrado, match="ambíguo"):
        resolver_vencimento(parse_csv_tesouro(csv_ambiguo), "IPCA", 2035)


# ---------------------------------------------------------------------------
# escolher_atual — max(Data Base) em CSV fora de ordem + staleness 30d
# ---------------------------------------------------------------------------
def test_escolher_atual_usa_max_data_base_nao_ultima_linha() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE)
    atual = escolher_atual(linhas, "IPCA", 2035, _HOJE)
    assert atual is not None
    assert atual["data_base"] == dt.date(2026, 7, 7)  # max, embora a última linha seja 06/07
    assert atual["taxa_compra"] == 7.55
    assert atual["codigo"] == "TD-IPCA-2035"


def test_escolher_atual_staleness_31_dias_abstem_com_none() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE)  # max Data Base = 2026-07-07
    hoje = dt.date(2026, 7, 7) + dt.timedelta(days=STALENESS_DIAS + 1)
    assert escolher_atual(linhas, "IPCA", 2035, hoje) is None


def test_escolher_atual_exatamente_30_dias_ainda_serve() -> None:
    linhas = parse_csv_tesouro(_CSV_BASE)
    hoje = dt.date(2026, 7, 7) + dt.timedelta(days=STALENESS_DIAS)
    atual = escolher_atual(linhas, "IPCA", 2035, hoje)
    assert atual is not None and atual["data_base"] == dt.date(2026, 7, 7)


def test_escolher_atual_zero_e_nao_ofertado_vira_ausencia() -> None:
    # Achado M1 (red-team fase 2): convenção STN — taxa/PU = 0 no CSV significa
    # título fora da janela de compra/venda ("não ofertado"), nunca taxa 0,00%
    # nem PU R$ 0,00. Campo zerado abstém; os não-zero seguem.
    csv_zero = (
        _HEADER + "Tesouro IPCA+;15/05/2035;07/07/2026;0,00;7,61;0,00;2.105,10;2.108,00\n"
    ).encode("latin-1")
    atual = escolher_atual(parse_csv_tesouro(csv_zero), "IPCA", 2035, _HOJE)
    assert atual is not None
    assert atual["taxa_compra"] is None  # 0 -> ausência (abstém só este campo)
    assert atual["pu_compra"] is None
    assert atual["taxa_venda"] == 7.61  # campos não-zero seguem servindo
    assert atual["pu_venda"] == 2105.10


def test_parse_da_serie_mantem_zero_cru() -> None:
    # A regra M1 vale só na LEITURA atual/derivadas: o parse da série NÃO
    # reescreve o 0 (o valor cru fica no banco; 0 legítimo de outros parsers
    # nunca é tocado por esta regra).
    csv_zero = (
        _HEADER + "Tesouro IPCA+;15/05/2035;07/07/2026;0,00;7,61;0,00;2.105,10;2.108,00\n"
    ).encode("latin-1")
    linha = parse_csv_tesouro(csv_zero)[0]
    assert linha["taxa_compra"] == 0.0
    assert linha["pu_compra"] == 0.0


# ---------------------------------------------------------------------------
# Janela: diária (24 meses) + amostra mensal (primeira Data Base) até 5 anos
# ---------------------------------------------------------------------------
def _linha(base: dt.date) -> dict:
    return {
        "tipo": "Tesouro IPCA+",
        "data_vencimento": dt.date(2035, 5, 15),
        "data_base": base,
        "taxa_compra": 7.5,
        "taxa_venda": 7.56,
        "pu_compra": 2000.0,
        "pu_venda": 1995.0,
        "pu_base": 1998.0,
    }


def test_selecionar_janela_diaria_mensal_e_corte_de_5_anos() -> None:
    linhas = [
        _linha(dt.date(2026, 7, 7)),  # diária (dentro de 24m)
        _linha(dt.date(2026, 7, 6)),  # diária
        _linha(dt.date(2025, 1, 10)),  # diária (ainda dentro de 24m de 2026-07-08)
        _linha(dt.date(2025, 1, 11)),  # diária — mês repetido NÃO é amostrado aqui
        _linha(dt.date(2023, 3, 20)),  # histórico: mesmo mês...
        _linha(dt.date(2023, 3, 5)),  # ...só a PRIMEIRA Data Base do mês entra
        _linha(dt.date(2016, 5, 15)),  # mais velho que 5 anos -> descartado
    ]
    selecao = selecionar_janela(linhas, _HOJE)
    assert [ln["data_base"] for ln in selecao] == [
        dt.date(2023, 3, 5),
        dt.date(2025, 1, 10),
        dt.date(2025, 1, 11),
        dt.date(2026, 7, 6),
        dt.date(2026, 7, 7),
    ]


def test_recuar_meses_cruza_ano_e_clampa_dia() -> None:
    assert _recuar_meses(dt.date(2026, 7, 8), 24) == dt.date(2024, 7, 8)
    assert _recuar_meses(dt.date(2026, 1, 31), 1) == dt.date(2025, 12, 28)  # clamp 28


# ---------------------------------------------------------------------------
# ingest_titulo — MockTransport + sessão fake; idempotência e janela medidas
# ---------------------------------------------------------------------------
class _SessaoTitulos:
    """Upsert em memória chaveado por (tipo, data_vencimento, data_base)."""

    def __init__(self) -> None:
        self.titulos: dict[tuple, object] = {}

    def execute(self, stmt):
        params = stmt.compile().params
        chave = (params["tipo_1"], params["data_vencimento_1"], params["data_base_1"])
        obj = self.titulos.get(chave)
        return SimpleNamespace(scalar_one_or_none=lambda o=obj: o)

    def add(self, titulo) -> None:
        self.titulos[(titulo.tipo, titulo.data_vencimento, titulo.data_base)] = titulo


def _transport_csv(conteudo: bytes) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "tesourotransparente.gov.br" in request.url.host
        return httpx.Response(200, content=conteudo, headers={"Content-Type": "text/csv"})

    return httpx.MockTransport(handler)


def _stub_fontes(monkeypatch) -> list[tuple[str, dt.date]]:
    chamadas: list[tuple[str, dt.date]] = []

    def _fake(session, *, url, descricao, dt_referencia=None):
        chamadas.append((descricao, dt_referencia))
        assert url == URL_CSV
        return uuid.uuid4()

    monkeypatch.setattr(tesouro, "get_or_create_fonte", _fake)
    return chamadas


def test_ingest_persiste_so_o_titulo_resolvido_com_fonte_stn(monkeypatch) -> None:
    chamadas = _stub_fontes(monkeypatch)
    sess = _SessaoTitulos()
    gravados = ingest_titulo(sess, "IPCA", 2035, hoje=_HOJE, transport=_transport_csv(_CSV_BASE))
    assert len(gravados) == 3  # só as 3 Data Bases do Tesouro IPCA+ 15/05/2035
    assert len(sess.titulos) == 3
    assert all(t.tipo == "Tesouro IPCA+" for t in sess.titulos.values())  # PRE/SELIC/IPCAJ fora
    # Fonte por Data Base, com 'STN' na descrição (autorização comercial com citação).
    assert {dt_ref for _, dt_ref in chamadas} == {
        dt.date(2026, 7, 5),
        dt.date(2026, 7, 6),
        dt.date(2026, 7, 7),
    }
    assert all("STN" in descricao for descricao, _ in chamadas)


def test_ingest_e_idempotente_no_refresh(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    sess = _SessaoTitulos()
    transport = _transport_csv(_CSV_BASE)
    ingest_titulo(sess, "IPCA", 2035, hoje=_HOJE, transport=transport)
    antes = dict(sess.titulos)
    de_novo = ingest_titulo(sess, "IPCA", 2035, hoje=_HOJE, transport=transport)
    assert len(sess.titulos) == 3  # refresh não duplica
    assert all(sess.titulos[k] is antes[k] for k in antes)  # atualiza os MESMOS objetos
    assert all(t in sess.titulos.values() for t in de_novo)


def test_ingest_aplica_janela_diaria_e_amostra_mensal(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    corpo = (
        _HEADER + "Tesouro IPCA+;15/05/2035;07/07/2026;7,55;7,61;2.110,50;2.105,10;2.108,00\n"
        "Tesouro IPCA+;15/05/2035;06/07/2026;7,58;7,63;2.105,00;2.100,00;2.102,00\n"
        "Tesouro IPCA+;15/05/2035;20/03/2023;6,10;6,16;1.800,00;1.795,00;1.798,00\n"
        "Tesouro IPCA+;15/05/2035;10/03/2023;6,20;6,26;1.790,00;1.785,00;1.788,00\n"
        "Tesouro IPCA+;15/05/2035;15/05/2016;6,50;6,56;1.500,00;1.495,00;1.498,00\n"
    ).encode("latin-1")
    sess = _SessaoTitulos()
    gravados = ingest_titulo(sess, "IPCA", 2035, hoje=_HOJE, transport=_transport_csv(corpo))
    bases = sorted(t.data_base for t in gravados)
    # 2016 fora (>5 anos); mar/2023 amostrado pela PRIMEIRA Data Base (10/03).
    assert bases == [dt.date(2023, 3, 10), dt.date(2026, 7, 6), dt.date(2026, 7, 7)]


def test_ingest_dois_vencimentos_no_ano_abstem_sem_persistir(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    corpo = (
        _HEADER + "Tesouro IPCA+;15/05/2035;07/07/2026;7,55;7,61;2.110,50;2.105,10;2.108,00\n"
        "Tesouro IPCA+;15/08/2035;07/07/2026;7,50;7,56;2.050,00;2.045,00;2.048,00\n"
    ).encode("latin-1")
    sess = _SessaoTitulos()
    with pytest.raises(DadoNaoEncontrado, match="ambíguo"):
        ingest_titulo(sess, "IPCA", 2035, hoje=_HOJE, transport=_transport_csv(corpo))
    assert sess.titulos == {}  # nada persistido em abstenção


# ---------------------------------------------------------------------------
# titulo_atual — leitura do banco (fake) com conversão Decimal -> float
# ---------------------------------------------------------------------------
class _SessaoLeitura:
    def __init__(self, titulos: list) -> None:
        self._titulos = titulos

    def execute(self, stmt):
        titulos = self._titulos
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: titulos))


def _titulo_db(base: dt.date, taxa: str) -> SimpleNamespace:
    return SimpleNamespace(
        tipo="Tesouro IPCA+",
        data_vencimento=dt.date(2035, 5, 15),
        data_base=base,
        taxa_compra=Decimal(taxa),
        taxa_venda=Decimal("7.61"),
        pu_compra=Decimal("2110.50"),
        pu_venda=Decimal("2105.10"),
        pu_base=Decimal("2108.00"),
        fonte_id=uuid.uuid4(),
    )


def test_titulo_atual_max_data_base_e_floats() -> None:
    sess = _SessaoLeitura(
        [
            _titulo_db(dt.date(2026, 7, 5), "7.60"),
            _titulo_db(dt.date(2026, 7, 7), "7.55"),
            _titulo_db(dt.date(2026, 7, 6), "7.58"),  # fora de ordem também no banco
        ]
    )
    atual = titulo_atual(sess, "IPCA", 2035, hoje=_HOJE)
    assert atual is not None
    assert atual["data_base"] == dt.date(2026, 7, 7)
    assert atual["taxa_compra"] == 7.55 and isinstance(atual["taxa_compra"], float)
    assert atual["codigo"] == "TD-IPCA-2035"
    assert atual["fonte_id"] is not None  # sem fonte não é fato


def test_titulo_atual_stale_devolve_none() -> None:
    sess = _SessaoLeitura([_titulo_db(dt.date(2016, 5, 13), "6.50")])
    # Caso REAL do ground truth: 'Tesouro IPCA+ 15/05/2035' com série antiga
    # encerrada em 2016 jamais pode sair como taxa atual.
    hoje_2035 = dt.date(2026, 7, 8)
    assert titulo_atual(sess, "IPCA", 2035, hoje=hoje_2035) is None


def test_titulo_atual_sem_linhas_abstem() -> None:
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        titulo_atual(_SessaoLeitura([]), "IPCA", 2035, hoje=_HOJE)


# ---------------------------------------------------------------------------
# URL, allowlist e teto de bytes
# ---------------------------------------------------------------------------
def test_url_csv_oficial_e_host_allowlisted() -> None:
    assert URL_CSV.endswith("precotaxatesourodireto.csv")
    assert http_client._host_permitido("www.tesourotransparente.gov.br")
    assert not http_client._host_permitido("evil.example.com")


def test_ingest_usa_teto_de_bytes_de_50mb() -> None:
    assert _MAX_CSV_BYTES == 50 * 1024 * 1024
    assert "_MAX_CSV_BYTES" in inspect.getsource(tesouro.ingest_titulo)


def test_download_acima_do_teto_aborta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        resp = httpx.Response(200, content=b"x")
        resp.headers["Content-Length"] = str(_MAX_CSV_BYTES + 1)
        return resp

    with pytest.raises(http_client.RespostaGrandeDemais):
        http_client.download_zip(
            URL_CSV, transport=httpx.MockTransport(handler), max_bytes=_MAX_CSV_BYTES
        )
