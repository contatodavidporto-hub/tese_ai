"""Testes offline dos elos POR CLASSE (etapa 12, D8) — funções PURAS.

As regras por classe vivem nos perfis (`ativos/acao|fii|renda_fixa.py`);
`correlacao.montar_grafo` segue sendo o grafo legado da AÇÃO (8 elos,
byte-idêntico — coberto por tests/test_correlacao.py). Aqui:

- contexto FII/RF NUNCA produz o elo câmbio→receita nem os elos D1 de
  não-financeira (o vazamento que o D8 corrige);
- co-movimento com n<24 abstém (trava A4 herdada dos primitivos);
- elo sem fonte numa ponta é descartado;
- banco (via perfil ação + plano financeiro) ganha Selic→captação e Selic→PDD;
- `persistir_elos` grava `ativo_codigo` quando `empresa_id` é None (o CHECK
  ck_elos_ancora exige um dos dois).
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services import correlacao
from app.services.ativos import acao, fii, renda_fixa
from app.services.correlacao import (
    METODO_CO_MOVIMENTO,
    METODO_INTERPRETACAO,
    MIN_N,
    elo_interpretativo,
    persistir_elos,
)

# Dimensões do grafo LEGADO de ação — nenhuma pode vazar para FII/RF.
_DIMS_ACAO = {
    "câmbio→empresa",
    "commodity→setor",
    "juros_global→custo_de_capital",
    "empresa↔pares_globais",
    "juros_global→divida_empresa",
    "câmbio→resultado_financeiro",
    "selic→despesas_financeiras",
    "co_movimento",
}


def _meses(n: int, inicio: tuple[int, int] = (2024, 1)) -> list[dt.date]:
    ano0, mes0 = inicio
    datas = []
    for i in range(n):
        total = ano0 * 12 + (mes0 - 1) + i
        a, m = divmod(total, 12)
        datas.append(dt.date(a, m + 1, 28))
    return datas


# ---------------------------------------------------------------------------
# FII (perfil fii) — interpretativo Selic→VP/DY + co-movimento DY×Selic
# ---------------------------------------------------------------------------
def _contexto_fii(n_meses: int = MIN_N + 4) -> dict:
    meses = _meses(n_meses)
    return {
        "macro": {
            "SELIC_META_ANUAL": {
                "valor": 14.25,
                "data": dt.date(2026, 6, 30),
                "fonte_id": "f-selic",
            },
        },
        "fontes_indicador": {"VP_COTA": "f-vp", "DY_MES_INFORME": "f-dy"},
        "series": {
            "DY_MES_INFORME": [(d, 0.006 + i * 0.0001) for i, d in enumerate(meses)],
            "SELIC_META_ANUAL": [(d, 10.0 + i * 0.1) for i, d in enumerate(meses)],
        },
    }


def test_fii_monta_interpretativo_e_co_movimento_validados() -> None:
    elos = fii.montar_elos_fii(_contexto_fii())
    dims = {e.dimensao for e in elos}
    assert "selic→vp_dy_fii" in dims
    assert "co_movimento_dy_selic" in dims
    for e in elos:
        assert e.validada is True
        assert e.origem_fonte_id and e.destino_fonte_id
        assert e.hedge
    co = next(e for e in elos if e.metodo == METODO_CO_MOVIMENTO)
    assert co.n_amostras >= MIN_N
    assert co.ligacao_causal is None  # Pearson NUNCA afirma causa


def test_fii_nao_produz_elos_de_acao() -> None:
    # O vazamento que o D8 corrige: contexto FII jamais dispara câmbio→receita
    # ou qualquer elo D1 de não-financeira.
    dims = {e.dimensao for e in fii.montar_elos_fii(_contexto_fii())}
    assert dims.isdisjoint(_DIMS_ACAO)


def test_fii_co_movimento_n_menor_que_24_abstem() -> None:
    elos = fii.montar_elos_fii(_contexto_fii(n_meses=MIN_N - 1))
    dims = {e.dimensao for e in elos}
    assert "co_movimento_dy_selic" not in dims  # abstém
    assert "selic→vp_dy_fii" in dims  # interpretativo segue (fonte nas 2 pontas)


def test_fii_sem_fonte_selic_descarta_tudo() -> None:
    ctx = _contexto_fii()
    ctx["macro"]["SELIC_META_ANUAL"]["fonte_id"] = None
    assert fii.montar_elos_fii(ctx) == []


def test_fii_sem_fonte_do_indicador_descarta_interpretativo() -> None:
    ctx = _contexto_fii()
    ctx["fontes_indicador"] = {}  # elo sem fonte numa ponta -> descartado
    dims = {e.dimensao for e in fii.montar_elos_fii(ctx)}
    assert "selic→vp_dy_fii" not in dims
    assert "co_movimento_dy_selic" not in dims


# ---------------------------------------------------------------------------
# Renda fixa (perfil renda_fixa) — co-movimentos + interpretativos 'expectativa'
# ---------------------------------------------------------------------------
def _contexto_rf(
    familia: str = "IPCA",
    n_meses: int = MIN_N + 6,
    *,
    com_treasury: bool = True,
) -> dict:
    meses = _meses(n_meses)
    macro = {
        "SELIC_META_ANUAL": {"valor": 14.25, "data": dt.date(2026, 6, 30), "fonte_id": "f-selic"},
        "IPCA_MENSAL": {"valor": 0.4, "data": dt.date(2026, 6, 30), "fonte_id": "f-ipca"},
        "FOCUS_SELIC_COPOM": {
            "valor": 12.0,
            "data": dt.date(2026, 7, 3),
            "fonte_id": "f-focus",
        },
    }
    series = {
        "TAXA_TITULO": [(d, 6.0 + i * 0.05) for i, d in enumerate(meses)],
        "SELIC_META_ANUAL": [(d, 10.0 + i * 0.1) for i, d in enumerate(meses)],
    }
    if com_treasury:
        macro["GLOBAL_TREASURY_10Y"] = {
            "valor": 4.2,
            "data": dt.date(2026, 6, 30),
            "fonte_id": "f-dgs",
        }
        series["GLOBAL_TREASURY_10Y"] = [(d, 3.0 + i * 0.02) for i, d in enumerate(meses)]
    return {
        "familia": familia,
        "codigo": f"TD-{familia}-2035",
        "titulo_fonte_id": "f-stn",
        "macro": macro,
        "series": series,
    }


def test_rf_ipca_monta_co_movimentos_e_interpretativo_expectativa() -> None:
    elos = renda_fixa.montar_elos_rf(_contexto_rf("IPCA"))
    dims = {e.dimensao for e in elos}
    assert "co_movimento_taxa_selic" in dims
    assert "co_movimento_taxa_treasury10y" in dims
    assert "ipca→titulo_indexado (expectativa)" in dims
    assert "focus→prefixado (expectativa)" not in dims  # IPCA não é prefixado
    for e in elos:
        assert e.validada is True
        assert e.origem_fonte_id and e.destino_fonte_id
        assert e.hedge
    interp = next(e for e in elos if e.metodo == METODO_INTERPRETACAO)
    assert "expectativa" in interp.hedge.lower()


def test_rf_prefixado_ganha_elo_focus_rotulado_expectativa() -> None:
    elos = renda_fixa.montar_elos_rf(_contexto_rf("PRE"))
    dims = {e.dimensao for e in elos}
    assert "focus→prefixado (expectativa)" in dims
    assert "ipca→titulo_indexado (expectativa)" not in dims
    focus = next(e for e in elos if e.dimensao == "focus→prefixado (expectativa)")
    assert "expectativa" in focus.hedge.lower()
    assert "não fato realizado" in focus.hedge.lower()


def test_rf_nao_produz_elos_de_acao() -> None:
    dims = {e.dimensao for e in renda_fixa.montar_elos_rf(_contexto_rf("IPCA"))}
    assert dims.isdisjoint(_DIMS_ACAO)


def test_rf_co_movimento_n_menor_que_24_abstem() -> None:
    elos = renda_fixa.montar_elos_rf(_contexto_rf("IPCA", n_meses=MIN_N - 2))
    dims = {e.dimensao for e in elos}
    assert "co_movimento_taxa_selic" not in dims
    assert "co_movimento_taxa_treasury10y" not in dims
    assert "ipca→titulo_indexado (expectativa)" in dims  # interpretativo segue


def test_rf_sem_fonte_do_titulo_abstem_tudo() -> None:
    ctx = _contexto_rf("IPCA")
    ctx["titulo_fonte_id"] = None  # sem fonte na ponta do título -> nada
    assert renda_fixa.montar_elos_rf(ctx) == []


# ---------------------------------------------------------------------------
# Banco (via perfil AÇÃO com plano financeiro) — Selic→captação e Selic→PDD
# ---------------------------------------------------------------------------
def _contexto_banco(plano: str | None = "banco") -> dict:
    return {
        "setor": "Bancos",
        "plano_contas": plano,
        "empresa_fonte_id": "f-cvm",
        "macro": {
            "SELIC_META_ANUAL": {
                "valor": 14.25,
                "data": dt.date(2026, 6, 30),
                "fonte_id": "f-selic",
            },
        },
        "fundamento_fontes": {"3.02": "f-captacao", "3.04.01": "f-pdd"},
    }


def test_banco_monta_selic_captacao_e_selic_pdd_com_hedge() -> None:
    elos = acao.montar_elos_financeira(_contexto_banco())
    dims = {e.dimensao for e in elos}
    assert dims == {"selic→custo_de_captacao", "selic→pdd"}
    for e in elos:
        assert e.validada is True
        assert e.origem_fonte_id and e.destino_fonte_id
        assert e.hedge
        assert e.metodo == METODO_INTERPRETACAO


def test_banco_pdd_do_itub_em_3_02_02_tambem_ancora() -> None:
    ctx = _contexto_banco()
    ctx["fundamento_fontes"] = {"3.02": "f-captacao", "3.02.02": "f-pdd-itub"}
    elos = acao.montar_elos_financeira(ctx)
    pdd = next(e for e in elos if e.dimensao == "selic→pdd")
    assert pdd.destino_fonte_id == "f-pdd-itub"


def test_banco_sem_fonte_pdd_so_monta_captacao() -> None:
    ctx = _contexto_banco()
    ctx["fundamento_fontes"] = {"3.02": "f-captacao"}  # PDD sem fonte -> elo ausente
    dims = {e.dimensao for e in acao.montar_elos_financeira(ctx)}
    assert dims == {"selic→custo_de_captacao"}


def test_plano_padrao_e_seguradora_nao_ganham_elos_de_banco() -> None:
    # Seguradora: 3.02 são despesas de seguros — rotular como captação seria
    # interpretação errada; padrão/None: elos de banco não se aplicam.
    for plano in (None, "padrao", "seguradora"):
        assert acao.montar_elos_financeira(_contexto_banco(plano)) == []


def test_banco_sem_selic_abstem() -> None:
    ctx = _contexto_banco()
    ctx["macro"] = {}
    assert acao.montar_elos_financeira(ctx) == []


def test_acao_montar_grafo_ignora_chave_plano_contas() -> None:
    # O contexto legado ganhou a chave 'plano_contas' (D8); montar_grafo deve
    # ignorá-la — o grafo de ação segue byte-idêntico (mesmos elos de sempre).
    ctx = {
        "setor": "Petróleo",
        "plano_contas": "padrao",
        "empresa_fonte_id": "f-cvm",
        "macro": {
            "USD_VENDA": {"valor": 5.1, "data": dt.date(2026, 6, 22), "fonte_id": "f-usd"},
        },
    }
    dims = {e.dimensao for e in correlacao.montar_grafo(ctx)}
    assert dims == {"câmbio→empresa"}


# ---------------------------------------------------------------------------
# persistir_elos — âncora empresa_id OU ativo_codigo (ck_elos_ancora)
# ---------------------------------------------------------------------------
class _SessaoCaptura:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)


def _elo_valido() -> correlacao.Elo:
    return elo_interpretativo(
        "selic→vp_dy_fii",
        ("Selic", "f-selic"),
        ("VP/cota", "f-vp"),
        ligacao_causal="cenário: juros pressionam o valor presente",
        hedge="condicional",
    )


def test_persistir_elos_grava_ativo_codigo_quando_sem_empresa() -> None:
    sess = _SessaoCaptura()
    persistir_elos(sess, None, [_elo_valido()], None, ativo_codigo="HGLG11")
    assert len(sess.added) == 1
    row = sess.added[0]
    assert row.empresa_id is None
    assert row.ativo_codigo == "HGLG11"
    assert row.origem_fonte_id == "f-selic"


def test_persistir_elos_sem_ancora_nenhuma_falha_rapido() -> None:
    with pytest.raises(ValueError, match="ck_elos_ancora"):
        persistir_elos(_SessaoCaptura(), None, [_elo_valido()], None)


def test_persistir_elos_lista_vazia_sem_ancora_e_noop() -> None:
    sess = _SessaoCaptura()
    persistir_elos(sess, None, [], None)  # nada a gravar -> nada a validar
    assert sess.added == []


def test_persistir_elos_com_empresa_segue_legado() -> None:
    sess = _SessaoCaptura()
    persistir_elos(sess, "emp-uuid", [_elo_valido()], None)
    assert sess.added[0].empresa_id == "emp-uuid"
    assert sess.added[0].ativo_codigo is None
