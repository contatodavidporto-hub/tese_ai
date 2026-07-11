"""Testes offline do conector de proventos B3 (app.services.proventos_b3).

Sem rede real (httpx.MockTransport pula a allowlist — padrão de
test_anbima_ettj.py) e sem Postgres (SQLite em memória). Fixtures congeladas de
sondas ao vivo em 2026-07-10 (tests/fixtures/proventos_b3/):

- fundsproxy_hglg11.json — HGLG11 (FII): 20 cashDividends, 12 do ISIN do fundo
  (BRHGLGCTF004) + 8 de recibos de subscrição (BRHGLGR*) que devem ficar FORA.
- companyproxy_itub.json — ITUB (ação): 34 itens (17 ON + 17 PN, JCP mensal +
  dividendos); ITUB4 = espécie ACNPR.
- companyproxy_taee.json — TAEE: 21 itens nas 3 espécies; a unit TAEE11 (CDAM)
  paga exatamente 3x a ON e teve 2 DIVIDENDOs na MESMA data-com (29/04/2026),
  que o conector SOMA.

O transporte roteia por URL EXATA reconstruída independentemente no teste
(payload JSON -> base64) — qualquer divergência no payload server-side derruba
o teste com 404. Cobre também o alarme de schema (endpoint não documentado) e
a degradação sem tabela da correção A13.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.models import FiiCadastro, Fonte, Provento
from app.services.dados import DadoNaoEncontrado
from app.services.proventos_b3 import (
    B3_COMPANY_URL,
    B3_FUNDS_URL,
    _consolidar,
    _data_br,
    _decimal_ptbr,
    _payload_b64,
    ensure_proventos,
)

FIXTURES = Path(__file__).parent / "fixtures" / "proventos_b3"
FUNDS_HGLG = (FIXTURES / "fundsproxy_hglg11.json").read_bytes()
COMPANY_ITUB = (FIXTURES / "companyproxy_itub.json").read_bytes()
COMPANY_TAEE = (FIXTURES / "companyproxy_taee.json").read_bytes()

HOJE = dt.date(2026, 7, 10)  # data das sondas que congelaram as fixtures

# CNPJ sintético do cadastro de teste; ISIN real do fundo (presente na fixture).
CNPJ_HGLG = "11.222.333/0001-44"
ISIN_HGLG = "BRHGLGCTF004"


def _b64(payload: dict) -> str:
    """Reconstrução INDEPENDENTE do payload esperado (contrato do endpoint)."""
    return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("ascii")).decode()


URL_HGLG = B3_FUNDS_URL.format(
    payload=_b64({"cnpj": "11222333000144", "identifierFund": "HGLG", "typeFund": 7})
)
URL_ITUB = B3_COMPANY_URL.format(payload=_b64({"issuingCompany": "ITUB", "language": "pt-br"}))
URL_TAEE = B3_COMPANY_URL.format(payload=_b64({"issuingCompany": "TAEE", "language": "pt-br"}))


# --- Transporte fake: roteia por URL exata; fora do mapa -> 404 ---------------
def _transport(
    respostas: dict[str, bytes | int], chamadas: list[str] | None = None
) -> httpx.MockTransport:
    """Serve `respostas[url]` (bytes -> 200; int -> status); ausente -> 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        url = str(request.url)
        if chamadas is not None:
            chamadas.append(url)
        resposta = respostas.get(url)
        if resposta is None:
            return httpx.Response(404, text="not found")
        if isinstance(resposta, int):
            return httpx.Response(resposta, text="erro")
        return httpx.Response(200, content=resposta, headers={"content-type": "application/json"})

    return httpx.MockTransport(handler)


# --- Sessão SQLite em memória (padrão de test_anbima_ettj.py) -----------------
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
    yield from _make_sessao((Fonte.__table__, FiiCadastro.__table__, Provento.__table__))


@pytest.fixture()
def sessao_sem_tabela() -> Iterator[Session]:
    """Banco SEM a tabela `proventos` — simula deploy antes da migração 0006 (A13)."""
    yield from _make_sessao((Fonte.__table__, FiiCadastro.__table__))


def _cadastrar_fii(sessao: Session, *, isin: str | None = ISIN_HGLG, cnpj: str = CNPJ_HGLG) -> None:
    sessao.add(FiiCadastro(cnpj=cnpj, nome="CSHG LOGISTICA FII", ticker="HGLG11", isin=isin))
    sessao.flush()


def _valor(proventos: list[Provento], tipo: str, data_com: dt.date) -> Decimal:
    (unico,) = [p for p in proventos if p.tipo == tipo and p.data_com == data_com]
    return Decimal(str(unico.valor))


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------
def test_decimal_ptbr_virgula_decimal_vira_decimal_exato() -> None:
    assert _decimal_ptbr("1,10000000000") == Decimal("1.10000000000")
    assert _decimal_ptbr("1.234,56") == Decimal("1234.56")  # separador de milhar
    assert isinstance(_decimal_ptbr("0,36188"), Decimal)  # nunca float direto
    assert _decimal_ptbr("") is None
    assert _decimal_ptbr("n/d") is None


def test_data_br_placeholder_e_lixo_viram_none() -> None:
    assert _data_br("30/06/2026") == dt.date(2026, 6, 30)
    assert _data_br("31/12/9999") is None  # placeholder da B3
    assert _data_br("") is None
    assert _data_br("2026-06-30") is None


def test_payload_b64_round_trip() -> None:
    payload = {"cnpj": "11222333000144", "identifierFund": "HGLG", "typeFund": 7}
    assert json.loads(base64.b64decode(_payload_b64(payload))) == payload


# ---------------------------------------------------------------------------
# _consolidar — soma por (tipo, data-com), itens inválidos pulados
# ---------------------------------------------------------------------------
def test_consolidar_soma_exata_na_mesma_data_com() -> None:
    # Fato real congelado: 2 DIVIDENDOs de TAEE11 aprovados em 29/04/2026.
    itens = [
        {"label": "DIVIDENDO", "lastDatePrior": "29/04/2026", "rate": "0,15348614817"},
        {"label": "DIVIDENDO", "lastDatePrior": "29/04/2026", "rate": "0,75537413646"},
    ]
    item = _consolidar(itens, "TAEE11")[("DIVIDENDO", dt.date(2026, 4, 29))]
    assert item.valor == Decimal("0.90886028463")  # aritmética Decimal, sem erro binário


def test_consolidar_data_pagamento_mais_recente_vence() -> None:
    jcp = {"label": "JRS CAP PROPRIO", "lastDatePrior": "11/05/2026"}
    itens = [
        {**jcp, "rate": "0,10", "paymentDate": "26/09/2026"},
        {**jcp, "rate": "0,20", "paymentDate": "26/08/2026"},
    ]
    consolidado = _consolidar(itens, "X")[("JCP", dt.date(2026, 5, 11))]  # label -> tipo canônico
    assert consolidado.valor == Decimal("0.30")
    assert consolidado.data_pagamento == dt.date(2026, 9, 26)


def test_consolidar_pula_itens_invalidos() -> None:
    itens = [
        {"label": "RENDIMENTO", "lastDatePrior": "31/12/9999", "rate": "1,10"},  # placeholder
        {"label": "RENDIMENTO", "lastDatePrior": "30/06/2026", "rate": "0,00"},  # valor <= 0
        {"label": "RENDIMENTO", "lastDatePrior": "30/06/2026", "rate": "lixo"},  # rate inválido
        {"label": "", "lastDatePrior": "30/06/2026", "rate": "1,10"},  # sem rótulo
    ]
    assert _consolidar(itens, "X") == {}


def test_consolidar_rotulo_desconhecido_entra_normalizado() -> None:
    itens = [{"label": "amortizacao rj", "lastDatePrior": "30/06/2026", "rate": "1,00"}]
    assert ("AMORTIZACAO RJ", dt.date(2026, 6, 30)) in _consolidar(itens, "X")


# ---------------------------------------------------------------------------
# FII (fundsProxy) — atribuição pelo ISIN do fundo, fonte B3, cache
# ---------------------------------------------------------------------------
def test_fii_persiste_so_os_rendimentos_do_isin_do_fundo(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    proventos = ensure_proventos(
        sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: FUNDS_HGLG})
    )
    # 20 itens no endpoint; os 8 de recibos de subscrição (BRHGLGR*) ficam FORA.
    assert len(proventos) == 12
    assert all(p.tipo == "RENDIMENTO" for p in proventos)
    assert all(Decimal(str(p.valor)) == Decimal("1.1") for p in proventos)
    # Mais recente primeiro; ground truth da fixture congelada.
    assert proventos[0].data_com == dt.date(2026, 6, 30)
    assert proventos[0].data_pagamento == dt.date(2026, 7, 14)


def test_fii_grava_fonte_b3_com_url_data_e_metodologia(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    proventos = ensure_proventos(
        sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: FUNDS_HGLG})
    )
    (fonte,) = sessao.execute(select(Fonte)).scalars().all()
    assert fonte.url == URL_HGLG
    assert fonte.dt_referencia == HOJE
    assert "GetListedSupplementFunds" in fonte.descricao
    assert ISIN_HGLG in fonte.descricao  # metodologia de atribuição declarada
    assert all(p.fonte_id == fonte.id for p in proventos)  # sem fonte não é fato


def test_payload_do_fii_e_construido_server_side_a_partir_do_cadastro(sessao: Session) -> None:
    _cadastrar_fii(sessao)  # CNPJ formatado no cadastro -> só dígitos no payload
    chamadas: list[str] = []
    ensure_proventos(
        sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: FUNDS_HGLG}, chamadas)
    )
    payload = json.loads(base64.b64decode(chamadas[0].rsplit("/", 1)[1]))
    assert payload == {"cnpj": "11222333000144", "identifierFund": "HGLG", "typeFund": 7}


def test_fii_sem_isin_no_cadastro_abstem(sessao: Session) -> None:
    _cadastrar_fii(sessao, isin=None)
    with pytest.raises(DadoNaoEncontrado, match="sem ISIN"):
        ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=_transport({}))


def test_fii_cnpj_invalido_no_cadastro_abstem(sessao: Session) -> None:
    _cadastrar_fii(sessao, cnpj="123")
    with pytest.raises(DadoNaoEncontrado, match="CNPJ inválido"):
        ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=_transport({}))


def test_fii_nenhum_item_do_isin_abstem_nunca_soma_recibos(sessao: Session) -> None:
    # ISIN divergente: os 20 itens existem mas NENHUM é atribuível ao fundo.
    _cadastrar_fii(sessao, isin="BRZZZZCTF000")
    with pytest.raises(DadoNaoEncontrado, match="nenhum provento atribuível ao ISIN"):
        ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: FUNDS_HGLG}))
    assert sessao.execute(select(Provento)).scalars().all() == []


def test_cache_fresco_nao_martela_o_endpoint(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    chamadas: list[str] = []
    transport = _transport({URL_HGLG: FUNDS_HGLG}, chamadas)
    ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=transport)
    de_cache = ensure_proventos(
        sessao, "HGLG11", hoje=HOJE + dt.timedelta(days=35), transport=transport
    )
    assert len(chamadas) == 1  # dentro do staleness: nada de rede
    assert len(de_cache) == 12


def test_apos_staleness_rebusca_e_upsert_nao_duplica(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    chamadas: list[str] = []
    transport = _transport({URL_HGLG: FUNDS_HGLG}, chamadas)
    ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=transport)
    depois = ensure_proventos(
        sessao, "HGLG11", hoje=HOJE + dt.timedelta(days=36), transport=transport
    )
    assert len(chamadas) == 2  # staleness vencido: rebusca
    assert len(depois) == 12  # upsert idempotente por (ticker, tipo, data_com)
    fontes = sessao.execute(select(Fonte)).scalars().all()
    assert len(fontes) == 2  # uma Fonte por consulta (dt_referencia distinto)


def test_ticker_normalizado_reusa_o_cache(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: FUNDS_HGLG}))
    # minúsculas/espaços não furam o cache (transport vazio derrubaria a rede).
    de_cache = ensure_proventos(sessao, " hglg11 ", hoje=HOJE, transport=_transport({}))
    assert len(de_cache) == 12


def test_endpoint_sem_itens_devolve_vazio_sem_persistir(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    corpo = json.dumps({"cashDividends": []}).encode()
    resultado = ensure_proventos(
        sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: corpo})
    )
    assert resultado == []  # fato "nenhum item", não erro
    assert sessao.execute(select(Fonte)).scalars().all() == []


# ---------------------------------------------------------------------------
# Ações (listedCompaniesProxy) — espécie inferida do sufixo B3
# ---------------------------------------------------------------------------
def test_acao_itub4_persiste_so_a_especie_pn(sessao: Session) -> None:
    proventos = ensure_proventos(
        sessao, "ITUB4", hoje=HOJE, transport=_transport({URL_ITUB: COMPANY_ITUB})
    )
    # 34 itens no endpoint (ON+PN); só os 17 da PN (ACNPR) entram: 16 JCP + 1 DIVIDENDO.
    assert len(proventos) == 17
    assert sum(1 for p in proventos if p.tipo == "DIVIDENDO") == 1
    assert sum(1 for p in proventos if p.tipo == "JCP") == 16
    # Ground truth da fixture congelada (JCP semestral e dividendo complementar).
    assert _valor(proventos, "JCP", dt.date(2026, 6, 18)) == Decimal("0.36188")
    assert _valor(proventos, "DIVIDENDO", dt.date(2025, 12, 9)) == Decimal("1.868223")
    (fonte,) = sessao.execute(select(Fonte)).scalars().all()
    assert "GetListedSupplementCompany" in fonte.descricao
    assert "ACNPR" in fonte.descricao  # metodologia (espécie do sufixo) declarada


def test_acao_unit_taee11_soma_mesma_data_com_e_vale_3x_a_on(sessao: Session) -> None:
    transport = _transport({URL_TAEE: COMPANY_TAEE})
    unit = ensure_proventos(sessao, "TAEE11", hoje=HOJE, transport=transport)
    on = ensure_proventos(sessao, "TAEE3", hoje=HOJE, transport=transport)
    assert len(unit) == 6  # 7 itens CDAM -> 6 eventos (2 DIVIDENDOs somados em 29/04)
    assert len(on) == 6
    div_unit = _valor(unit, "DIVIDENDO", dt.date(2026, 4, 29))
    div_on = _valor(on, "DIVIDENDO", dt.date(2026, 4, 29))
    # Round-trip do SQLite (Numeric sem scale) trunca em 10 casas — approx aqui;
    # a soma Decimal EXATA está provada no teste puro de _consolidar acima.
    assert float(div_unit) == pytest.approx(0.90886028463)  # 0,15348614817 + 0,75537413646
    assert float(div_unit) == pytest.approx(3 * float(div_on))  # unit = 1 ON + 2 PN (sanity)


def test_acao_especie_sem_itens_abstem(sessao: Session) -> None:
    # ITUB5 (PNA/ACNPA) existe no mapa mas não tem item na fixture -> abstenção.
    with pytest.raises(DadoNaoEncontrado, match="nenhum provento atribuível à espécie"):
        ensure_proventos(sessao, "ITUB5", hoje=HOJE, transport=_transport({URL_ITUB: COMPANY_ITUB}))


def test_acao_sufixo_sem_especie_mapeada_abstem_sem_rede(sessao: Session) -> None:
    chamadas: list[str] = []
    with pytest.raises(DadoNaoEncontrado, match="sem espécie mapeada"):
        ensure_proventos(sessao, "ITUB2", hoje=HOJE, transport=_transport({}, chamadas))
    assert chamadas == []  # abstém ANTES de qualquer requisição


def test_ticker_invalido_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="ticker inválido"):
        ensure_proventos(sessao, "BANANA", hoje=HOJE, transport=_transport({}))


# ---------------------------------------------------------------------------
# Alarme de schema — endpoint não documentado mudou -> abstenção, nunca chute
# ---------------------------------------------------------------------------
def test_resposta_nao_json_alarma_e_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="alarme de schema"):
        ensure_proventos(
            sessao, "ITUB4", hoje=HOJE, transport=_transport({URL_ITUB: b"<html>erro</html>"})
        )


def test_fundsproxy_sem_cashdividends_alarma(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    corpo = json.dumps({"fund": "FII HGLG PAX"}).encode()
    with pytest.raises(DadoNaoEncontrado, match="sem cashDividends"):
        ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: corpo}))


def test_companyproxy_raiz_nao_lista_alarma(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="raiz não é lista"):
        ensure_proventos(sessao, "ITUB4", hoje=HOJE, transport=_transport({URL_ITUB: b"{}"}))


def test_companyproxy_emissor_sem_dados_alarma(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="emissor sem dados"):
        ensure_proventos(sessao, "ITUB4", hoje=HOJE, transport=_transport({URL_ITUB: b"[]"}))


def test_todos_os_itens_invalidos_alarma(sessao: Session) -> None:
    _cadastrar_fii(sessao)
    corpo = json.dumps(
        {
            "cashDividends": [
                {"isinCode": ISIN_HGLG, "label": "RENDIMENTO", "lastDatePrior": "", "rate": "1,1"},
                {"isinCode": ISIN_HGLG, "label": "RENDIMENTO", "lastDatePrior": "30/06/2026"},
            ]
        }
    ).encode()
    with pytest.raises(DadoNaoEncontrado, match="alarme de schema"):
        ensure_proventos(sessao, "HGLG11", hoje=HOJE, transport=_transport({URL_HGLG: corpo}))
    assert sessao.execute(select(Provento)).scalars().all() == []


def test_status_http_inesperado_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="status inesperado"):
        ensure_proventos(sessao, "ITUB4", hoje=HOJE, transport=_transport({URL_ITUB: 500}))


def test_falha_de_rede_abstem(sessao: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns indisponível", request=request)

    with pytest.raises(DadoNaoEncontrado, match="falha HTTP"):
        ensure_proventos(sessao, "ITUB4", hoje=HOJE, transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Correção A13 — tabela ausente degrada para abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
def test_a13_sem_tabela_proventos_degrada_para_abstencao(sessao_sem_tabela: Session) -> None:
    _cadastrar_fii(sessao_sem_tabela)
    chamadas: list[str] = []
    with pytest.raises(DadoNaoEncontrado, match="migração 0006"):
        ensure_proventos(sessao_sem_tabela, "HGLG11", hoje=HOJE, transport=_transport({}, chamadas))
    assert chamadas == []  # abstém antes de gastar rede


class _SessaoQuebrada:
    """Dublê: qualquer execute levanta o erro do Postgres (padrão test_cotahist)."""

    def __init__(self, mensagem: str) -> None:
        self._mensagem = mensagem

    def execute(self, *_args, **_kwargs):
        raise ProgrammingError("SELECT proventos", {}, Exception(self._mensagem))


def test_a13_undefined_table_do_postgres_vira_dado_nao_encontrado() -> None:
    sessao = _SessaoQuebrada('relation "proventos" does not exist')
    with pytest.raises(DadoNaoEncontrado, match="migração 0006"):
        ensure_proventos(sessao, "ITUB4", hoje=HOJE, transport=_transport({}))


def test_a13_erro_de_banco_de_outra_natureza_propaga() -> None:
    sessao = _SessaoQuebrada("syntax error at or near SELECT")
    with pytest.raises(ProgrammingError):
        ensure_proventos(sessao, "ITUB4", hoje=HOJE, transport=_transport({}))
