"""Testes offline do conector IF.data (app.services.ifdata).

Sem rede real (httpx.MockTransport pula a allowlist — padrão de
test_anbima_ettj.py) e sem Postgres (SQLite em memória). Fixtures congeladas
por sonda ao vivo em 2026-07-10 (tests/fixtures/ifdata/), CURADAS para os 6
conglomerados prudenciais alvo + agregado e=0: listagem `relatorios.json`
(datas-base 202503..202603), `info202603.json` (conceitos id->lid/arquivo),
`cadastro202603_1009.json` (inclui BB - PRUDENCIAL, código 1000080329,
descoberto no cadastro) e `dados202603_{1,3,5}.json`.

Ground truth validado na sonda contra a ordem de grandeza pública:
PL Itaú 1T2026 = R$232,45 bi; Basileia Itaú = 14,77% (fração 0,147697 no REST).
Arquivo desconhecido no REST = HTTP 200 com corpo "Erro interno - Internal
error" (comportamento real) — coberto como alarme de schema.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import Session

from app.models.models import BancoIndicador, Fonte
from app.services import ifdata
from app.services.dados import DadoNaoEncontrado
from app.services.ifdata import (
    IFDATA_CODIGO_CAIXA,
    IFDATA_RELATORIOS_URL,
    IFDATA_REST_BASE,
    INDICADORES,
    MAPA_CVM_IFDATA,
    _fim_do_mes,
    _regra_anualizacao,
    ensure_indicadores_banco,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ifdata"

CD_CVM_ITAU = 19348
CD_CVM_BB = 1023
HOJE = dt.date(2026, 7, 10)  # data da sonda que congelou as fixtures
DT_REF_202603 = dt.date(2026, 3, 31)

# Ground truth de dados202603_{1,3,5}.json (conferido manualmente na sonda).
ITAU_BASILEIA_FRACAO = 0.147697088305565
ITAU_PR = 230527362409.73
ITAU_RWA = 1560811828143.83
ITAU_CARTEIRA = 1221119970501.64
ITAU_ATIVOS_PROBLEMATICOS = 43682386342.31
ITAU_LL_1T2026 = 12150492100.62  # acumulado jan-mar -> anualizado x4
BB_BASILEIA_FRACAO = 0.142286687375203

ERRO_INTERNO = b"Erro interno - Internal error"  # resposta REAL p/ arquivo desconhecido


# --- Transporte fake: roteia pelo nomeArquivo e serve as fixturas ------------
def _transport(
    overrides: dict[str, bytes | int] | None = None,
    chamadas: list[str] | None = None,
) -> httpx.MockTransport:
    """Serve fixtures por nome-base do arquivo; `overrides[nome]` substitui
    (bytes -> corpo 200; int -> status). Chave 'relatorios' cobre a listagem."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        url = str(request.url)
        if url == IFDATA_RELATORIOS_URL:
            nome = "relatorios"
            arquivo_fixture = "relatorios.json"
        else:
            assert url.startswith(f"{IFDATA_REST_BASE}/arquivos?")
            nome_arquivo = parse_qs(urlsplit(url).query)["nomeArquivo"][0]
            # Caminho VERBATIM da listagem (nunca fabricado pelo conector).
            assert nome_arquivo.startswith("ifdata_2025_2030//")
            nome = nome_arquivo.rsplit("/", 1)[-1]
            arquivo_fixture = nome
        if chamadas is not None:
            chamadas.append(nome)
        if overrides is not None and nome in overrides:
            resposta = overrides[nome]
            if isinstance(resposta, int):
                return httpx.Response(resposta, text="erro")
            return httpx.Response(200, content=resposta)
        caminho = FIXTURES / arquivo_fixture
        if not caminho.exists():  # comportamento real do REST p/ arquivo desconhecido
            return httpx.Response(200, content=ERRO_INTERNO)
        return httpx.Response(200, content=caminho.read_bytes())

    return httpx.MockTransport(handler)


def _transport_rede_fora() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("rede indisponível", request=request)

    return httpx.MockTransport(handler)


# --- Sessão SQLite em memória (padrão de test_anbima_ettj.py) ----------------
def _make_sessao(tabelas: tuple) -> Iterator[Session]:
    engine = create_engine("sqlite://")
    meta = MetaData()
    for tabela in tabelas:
        copia = tabela.to_metadata(meta)
        for col in copia.columns:
            col.server_default = None  # gen_random_uuid()/now() não existem no SQLite
    meta.create_all(engine)
    with Session(engine) as s:

        @event.listens_for(s, "before_flush")
        def _defaults(sess, _ctx, _instances) -> None:
            for obj in sess.new:
                if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()
                if hasattr(obj, "criado_em") and getattr(obj, "criado_em", None) is None:
                    obj.criado_em = dt.datetime.now(dt.UTC)

        yield s
    engine.dispose()


@pytest.fixture()
def sessao() -> Iterator[Session]:
    yield from _make_sessao((Fonte.__table__, BancoIndicador.__table__))


@pytest.fixture()
def sessao_sem_tabela() -> Iterator[Session]:
    """Banco SEM banco_indicadores — simula deploy antes da migração 0006 (A13)."""
    yield from _make_sessao((Fonte.__table__,))


def _linhas(sessao: Session) -> list[BancoIndicador]:
    return list(
        sessao.execute(select(BancoIndicador).order_by(BancoIndicador.indicador)).scalars().all()
    )


def _fontes(sessao: Session) -> list[Fonte]:
    return list(sessao.execute(select(Fonte)).scalars().all())


def _fixture_json(nome: str) -> object:
    return json.loads((FIXTURES / nome).read_bytes())


# ---------------------------------------------------------------------------
# Helpers puros — regra de anualização e fim do mês
# ---------------------------------------------------------------------------
def test_regra_anualizacao_segue_a_apuracao_semestral() -> None:
    # Lei 4.595 (nota do relatório 116): mar/set = 1º trimestre do semestre.
    assert _regra_anualizacao(202603) == (4, "jan-mar")
    assert _regra_anualizacao(202606) == (2, "jan-jun")
    assert _regra_anualizacao(202609) == (4, "jul-set")
    assert _regra_anualizacao(202612) == (2, "jul-dez")


def test_regra_anualizacao_mes_fora_do_calendario_alarma() -> None:
    with pytest.raises(DadoNaoEncontrado, match="calendário trimestral"):
        _regra_anualizacao(202601)


def test_fim_do_mes_da_data_base() -> None:
    assert _fim_do_mes(202603) == dt.date(2026, 3, 31)
    assert _fim_do_mes(202606) == dt.date(2026, 6, 30)
    assert _fim_do_mes(202612) == dt.date(2026, 12, 31)


# ---------------------------------------------------------------------------
# ensure_indicadores_banco — colheita real (fixtures congeladas)
# ---------------------------------------------------------------------------
def test_ensure_persiste_os_seis_indicadores_do_itau(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    assert set(resultado) == set(INDICADORES)
    # Ordem de grandeza validada na sonda (PL Itaú ~R$232 bi; Basileia ~14,77%).
    assert float(resultado["BASILEIA"].valor) == pytest.approx(ITAU_BASILEIA_FRACAO * 100)
    assert float(resultado["PR"].valor) == pytest.approx(ITAU_PR)
    assert float(resultado["RWA"].valor) == pytest.approx(ITAU_RWA)
    assert float(resultado["CARTEIRA_CREDITO"].valor) == pytest.approx(ITAU_CARTEIRA)
    assert float(resultado["ATIVOS_PROBLEMATICOS"].valor) == pytest.approx(
        ITAU_ATIVOS_PROBLEMATICOS
    )
    assert float(resultado["LL_ANUALIZADO"].valor) == pytest.approx(ITAU_LL_1T2026 * 4)
    assert len(_linhas(sessao)) == len(INDICADORES)


def test_ensure_dt_referencia_e_base_prudencial(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    for linha in resultado.values():
        assert linha.cd_cvm == CD_CVM_ITAU
        assert linha.dt_referencia == DT_REF_202603  # fim do mês da data-base
        assert linha.base == "prudencial"


def test_ensure_basileia_em_pct_e_monetarios_em_brl(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    assert resultado["BASILEIA"].unidade == "PCT"
    assert 10 < float(resultado["BASILEIA"].valor) < 20  # %, não fração
    for indicador in ("PR", "RWA", "CARTEIRA_CREDITO", "ATIVOS_PROBLEMATICOS", "LL_ANUALIZADO"):
        assert resultado[indicador].unidade == "BRL"


def test_metodologia_declarada_por_indicador(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    for linha in resultado.values():  # base prudencial + Res. 4966 em TODOS
        assert "prudencial" in linha.metodologia
        assert "4.966" in linha.metodologia
        assert "data-base 202603" in linha.metodologia
    assert "×100" in resultado["BASILEIA"].metodologia  # conversão fração -> %
    ll = resultado["LL_ANUALIZADO"].metodologia
    assert "×4" in ll and "jan-mar" in ll  # regra de anualização declarada
    assert "Lei 4.595" in ll


def test_fonte_ifdata_com_data_base_e_data_de_extracao(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    fontes = _fontes(sessao)
    assert len(fontes) == 3  # um arquivo de dados por relatório: dados 1, 3 e 5
    for fonte in fontes:
        assert "BCB IF.data" in fonte.descricao
        assert "data-base 202603" in fonte.descricao
        assert "2026-07-10" in fonte.descricao  # data de extração
        assert fonte.dt_referencia == HOJE  # staleness ancorada na extração
        assert fonte.url.startswith(f"{IFDATA_REST_BASE}/arquivos?")
    assert all(linha.fonte_id is not None for linha in resultado.values())  # sem fonte não é fato


def test_ensure_idempotente_nao_duplica(sessao: Session) -> None:
    ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    # staleness_dias=-1 força nova colheita mesmo com extração de hoje.
    ensure_indicadores_banco(
        sessao, CD_CVM_ITAU, hoje=HOJE, staleness_dias=-1, transport=_transport()
    )
    assert len(_linhas(sessao)) == len(INDICADORES)
    assert len(_fontes(sessao)) == 3


def test_bb_descoberto_no_cadastro_prudencial(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(sessao, CD_CVM_BB, hoje=HOJE, transport=_transport())
    assert MAPA_CVM_IFDATA[CD_CVM_BB][0] == 1000080329  # "BB - PRUDENCIAL" no cadastro
    assert float(resultado["BASILEIA"].valor) == pytest.approx(BB_BASILEIA_FRACAO * 100)


def test_data_base_explicita_e_respeitada(sessao: Session) -> None:
    resultado = ensure_indicadores_banco(
        sessao, CD_CVM_ITAU, data_base=202603, hoje=HOJE, transport=_transport()
    )
    assert all(linha.dt_referencia == DT_REF_202603 for linha in resultado.values())


def test_data_base_nao_publicada_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="não publicada"):
        ensure_indicadores_banco(
            sessao, CD_CVM_ITAU, data_base=209912, hoje=HOJE, transport=_transport()
        )
    assert _linhas(sessao) == []


# ---------------------------------------------------------------------------
# Mapa curado — lacuna honesta v1
# ---------------------------------------------------------------------------
def test_fora_do_mapa_abstem_sem_tocar_a_rede(sessao: Session) -> None:
    chamadas: list[str] = []
    with pytest.raises(DadoNaoEncontrado, match="mapa curado"):
        ensure_indicadores_banco(
            sessao, 9512, hoje=HOJE, transport=_transport(chamadas=chamadas)  # Petrobras
        )
    assert chamadas == []
    assert _linhas(sessao) == []


def test_caixa_sem_registro_cvm_fica_fora_do_mapa_documentada() -> None:
    # Caixa não tem cd_cvm (sonda cad_cia_aberta 2026-07-10): inventar chave
    # violaria "nunca inventar dado". O código IF.data fica exportado p/ futuro.
    assert IFDATA_CODIGO_CAIXA == 1000080738
    assert IFDATA_CODIGO_CAIXA not in {codigo for codigo, _ in MAPA_CVM_IFDATA.values()}
    assert "Caixa" in (ifdata.__doc__ or "")
    assert set(MAPA_CVM_IFDATA) == {19348, 906, 20532, 1023, 22616}


# ---------------------------------------------------------------------------
# Staleness — consulta fresca não toca a rede; stale rebusca
# ---------------------------------------------------------------------------
def test_cache_fresco_nao_toca_a_rede(sessao: Session) -> None:
    ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    chamadas: list[str] = []
    resultado = ensure_indicadores_banco(
        sessao,
        CD_CVM_ITAU,
        hoje=HOJE + dt.timedelta(days=10),
        transport=_transport(chamadas=chamadas),
    )
    assert chamadas == []  # dentro da janela de 30 dias: nada de rede
    assert set(resultado) == set(INDICADORES)


def test_extracao_stale_rebusca_na_fonte(sessao: Session) -> None:
    ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    chamadas: list[str] = []
    depois = HOJE + dt.timedelta(days=40)
    ensure_indicadores_banco(
        sessao, CD_CVM_ITAU, hoje=depois, transport=_transport(chamadas=chamadas)
    )
    assert "relatorios" in chamadas  # janela vencida: consultou a fonte
    # Nova extração registra Fonte nova (data de extração distinta), sem duplicar linhas.
    assert depois in {fonte.dt_referencia for fonte in _fontes(sessao)}
    assert len(_linhas(sessao)) == len(INDICADORES)


def test_fonte_indisponivel_serve_o_persistido_stale(sessao: Session) -> None:
    ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    resultado = ensure_indicadores_banco(
        sessao,
        CD_CVM_ITAU,
        hoje=HOJE + dt.timedelta(days=60),
        transport=_transport_rede_fora(),
    )
    # Defasagem honesta: devolve o persistido, rotulado pelo dt_referencia.
    assert set(resultado) == set(INDICADORES)
    assert all(linha.dt_referencia == DT_REF_202603 for linha in resultado.values())


def test_fonte_indisponivel_sem_persistido_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="falha HTTP"):
        ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport_rede_fora())
    assert _linhas(sessao) == []


# ---------------------------------------------------------------------------
# Alarmes de schema — endpoint interno não documentado pode mudar
# ---------------------------------------------------------------------------
def test_erro_interno_do_rest_e_alarme_de_schema(sessao: Session) -> None:
    # Forma REAL de "arquivo desconhecido": HTTP 200 com corpo de erro não-JSON.
    with pytest.raises(DadoNaoEncontrado, match="não-JSON"):
        ensure_indicadores_banco(
            sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport({"relatorios": ERRO_INTERNO})
        )


def test_arquivo_ausente_da_listagem_alarma(sessao: Session) -> None:
    listagem = _fixture_json("relatorios.json")
    for item in listagem:
        item["files"] = [f for f in item["files"] if not f["f"].endswith("dados202603_5.json")]
    with pytest.raises(DadoNaoEncontrado, match="ausente da listagem"):
        ensure_indicadores_banco(
            sessao,
            CD_CVM_ITAU,
            hoje=HOJE,
            transport=_transport({"relatorios": json.dumps(listagem).encode()}),
        )


def test_conceito_ausente_do_info_alarma(sessao: Session) -> None:
    info = [e for e in _fixture_json("info202603.json") if e.get("id") != 79664]  # some Basileia
    with pytest.raises(DadoNaoEncontrado, match="ausente do info"):
        ensure_indicadores_banco(
            sessao,
            CD_CVM_ITAU,
            hoje=HOJE,
            transport=_transport({"info202603.json": json.dumps(info).encode()}),
        )


def test_conceito_com_nome_divergente_alarma(sessao: Session) -> None:
    # id remapeado para OUTRO conceito viraria número errado COM fonte.
    info = _fixture_json("info202603.json")
    for entrada in info:
        if entrada.get("id") == 79664:
            entrada["n"] = "Índice de Cobertura de Liquidez"
    with pytest.raises(DadoNaoEncontrado, match="nome divergente"):
        ensure_indicadores_banco(
            sessao,
            CD_CVM_ITAU,
            hoje=HOJE,
            transport=_transport({"info202603.json": json.dumps(info).encode()}),
        )


def test_codigo_ausente_do_cadastro_alarma(sessao: Session) -> None:
    cadastro = [e for e in _fixture_json("cadastro202603_1009.json") if e["c0"] != "1000080099"]
    with pytest.raises(DadoNaoEncontrado, match="ausente do cadastro"):
        ensure_indicadores_banco(
            sessao,
            CD_CVM_ITAU,
            hoje=HOJE,
            transport=_transport({"cadastro202603_1009.json": json.dumps(cadastro).encode()}),
        )


def test_codigo_remapeado_para_outra_instituicao_alarma(sessao: Session) -> None:
    cadastro = _fixture_json("cadastro202603_1009.json")
    for entrada in cadastro:
        if entrada["c0"] == "1000080099":
            entrada["c2"] = "BANCO XPTO - PRUDENCIAL"
    with pytest.raises(DadoNaoEncontrado, match="não corresponde ao rótulo"):
        ensure_indicadores_banco(
            sessao,
            CD_CVM_ITAU,
            hoje=HOJE,
            transport=_transport({"cadastro202603_1009.json": json.dumps(cadastro).encode()}),
        )


# ---------------------------------------------------------------------------
# Abstenção parcial — indicador sem valor fica fora; nenhum valor = abstenção
# ---------------------------------------------------------------------------
def test_instituicao_sem_bloco_num_arquivo_e_abstencao_parcial(sessao: Session) -> None:
    # Sem dados202603_1 (Resumo/DRE): caem CARTEIRA_CREDITO e LL_ANUALIZADO;
    # os indicadores de capital (dados 5) e ativos problemáticos (dados 3) ficam.
    resultado = ensure_indicadores_banco(
        sessao,
        CD_CVM_ITAU,
        hoje=HOJE,
        transport=_transport({"dados202603_1.json": b'{"id":1,"values":[]}'}),
    )
    assert set(resultado) == {"BASILEIA", "PR", "RWA", "ATIVOS_PROBLEMATICOS"}
    assert len(_linhas(sessao)) == 4  # nada é inventado para os ausentes


def test_nenhum_valor_em_nenhum_arquivo_abstem(sessao: Session) -> None:
    vazios: dict[str, bytes | int] = {
        f"dados202603_{n}.json": json.dumps({"id": n, "values": []}).encode() for n in (1, 3, 5)
    }
    with pytest.raises(DadoNaoEncontrado, match="sem nenhum indicador"):
        ensure_indicadores_banco(sessao, CD_CVM_ITAU, hoje=HOJE, transport=_transport(vazios))
    assert _linhas(sessao) == []


# ---------------------------------------------------------------------------
# Degradação sem tabela (correção A13) — abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
def test_sem_tabela_banco_indicadores_degrada_para_abstencao(
    sessao_sem_tabela: Session,
) -> None:
    with pytest.raises(DadoNaoEncontrado, match="banco_indicadores"):
        ensure_indicadores_banco(sessao_sem_tabela, CD_CVM_ITAU, hoje=HOJE, transport=_transport())
    # A transação externa segue utilizável: nenhuma Fonte órfã persistida.
    assert list(sessao_sem_tabela.execute(select(Fonte)).scalars().all()) == []
