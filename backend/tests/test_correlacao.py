"""Testes offline do motor de correlação (grafo causal auditável, achado A4)."""

from __future__ import annotations

import datetime as dt

from app.services.correlacao import (
    METODO_CO_MOVIMENTO,
    MIN_N,
    Elo,
    alinhar_series,
    correlacao_pearson,
    elo_interpretativo,
    elos_para_llm,
    montar_grafo,
    validar_elo,
)


# ---------------------------------------------------------------------------
# Estatística
# ---------------------------------------------------------------------------
def test_pearson_correlacao_perfeita_positiva() -> None:
    r, n = correlacao_pearson([(1, 2), (2, 4), (3, 6), (4, 8)])
    assert abs(r - 1.0) < 1e-9
    assert n == 4


def test_pearson_sempre_entre_menos_um_e_um() -> None:
    r, _ = correlacao_pearson([(1, 5), (2, 1), (3, 9), (4, 2), (5, 7)])
    assert -1.0 <= r <= 1.0


def test_pearson_abstem_com_poucos_pontos_ou_variancia_nula() -> None:
    assert correlacao_pearson([(1, 2)]) is None  # n<2
    assert correlacao_pearson([(5, 1), (5, 9)]) is None  # variância nula em x


def test_alinhar_series_por_data_comum() -> None:
    a = [(dt.date(2025, 1, 1), 1.0), (dt.date(2025, 2, 1), 2.0)]
    b = [(dt.date(2025, 2, 1), 20.0), (dt.date(2025, 3, 1), 30.0)]
    assert alinhar_series(a, b) == [(2.0, 20.0)]


# ---------------------------------------------------------------------------
# Validação (travas A4)
# ---------------------------------------------------------------------------
def test_elo_com_fonte_ausente_numa_ponta_e_invalido() -> None:
    elo = elo_interpretativo(
        "x", ("A", "fonte-a"), ("B", None), ligacao_causal="cenário: ...", hedge="condicional"
    )
    assert elo.validada is False


def test_co_movimento_nao_pode_afirmar_causalidade() -> None:
    elo = Elo(
        dimensao="x",
        origem_label="A",
        origem_fonte_id="fa",
        destino_label="B",
        destino_fonte_id="fb",
        metodo=METODO_CO_MOVIMENTO,
        hedge="co-movimento",
        ligacao_causal="A causa B",  # proibido para Pearson
        forca_ligacao=0.9,
        n_amostras=50,
    )
    assert validar_elo(elo) is False


def test_co_movimento_com_amostra_pequena_abstem() -> None:
    elo = Elo(
        dimensao="x",
        origem_label="A",
        origem_fonte_id="fa",
        destino_label="B",
        destino_fonte_id="fb",
        metodo=METODO_CO_MOVIMENTO,
        hedge="co-movimento",
        forca_ligacao=0.9,
        n_amostras=MIN_N - 1,
    )
    assert validar_elo(elo) is False


def test_elo_fraco_sem_hedge_e_invalido() -> None:
    elo = Elo(
        dimensao="x",
        origem_label="A",
        origem_fonte_id="fa",
        destino_label="B",
        destino_fonte_id="fb",
        metodo="interpretacao_hedge",
        hedge=None,
        forca_ligacao=0.5,
    )
    assert validar_elo(elo) is False


def test_elo_interpretativo_com_hedge_e_fontes_e_valido() -> None:
    elo = elo_interpretativo(
        "câmbio→empresa",
        ("Dólar", "fonte-usd"),
        ("Receita", "fonte-rec"),
        ligacao_causal="cenário: depreciação eleva receita dolarizada",
        hedge="condicional",
    )
    assert elo.validada is True


# ---------------------------------------------------------------------------
# montar_grafo (só elos validados) + serialização p/ LLM
# ---------------------------------------------------------------------------
def _contexto_petroleo() -> dict:
    return {
        "setor": "Petróleo, Gás e Biocombustíveis",
        "empresa_fonte_id": "f-cvm",
        "tem_pares": True,
        "pares_fonte_id": "f-sec",
        "macro": {
            "USD_VENDA": {"valor": 5.1, "data": dt.date(2026, 6, 22), "fonte_id": "f-usd"},
            "COMMODITY_BRENT": {"valor": 82.0, "data": dt.date(2026, 6, 20), "fonte_id": "f-brent"},
            "SELIC_META_ANUAL": {
                "valor": 14.25,
                "data": dt.date(2026, 8, 5),
                "fonte_id": "f-selic",
            },
            "GLOBAL_TREASURY_10Y": {
                "valor": 4.2,
                "data": dt.date(2026, 6, 20),
                "fonte_id": "f-dgs",
            },
        },
    }


def test_montar_grafo_liga_cinco_dimensoes_todas_com_hedge_e_fontes() -> None:
    elos = montar_grafo(_contexto_petroleo())
    dims = {e.dimensao for e in elos}
    assert "câmbio→empresa" in dims
    assert "commodity→setor" in dims
    assert "juros_global→custo_de_capital" in dims
    assert "empresa↔pares_globais" in dims
    # Toda aresta validada: fonte nas duas pontas + hedge presente.
    for e in elos:
        assert e.validada is True
        assert e.origem_fonte_id and e.destino_fonte_id
        assert e.hedge


def test_montar_grafo_descarta_elo_sem_fonte_de_empresa() -> None:
    ctx = _contexto_petroleo()
    ctx["empresa_fonte_id"] = None  # sem âncora de empresa
    elos = montar_grafo(ctx)
    # sem fonte de empresa, câmbio→empresa e commodity→setor não entram
    dims = {e.dimensao for e in elos}
    assert "câmbio→empresa" not in dims
    assert "commodity→setor" not in dims


def _meses(n: int) -> list[dt.date]:
    """n observações mensais (dia 28), a partir de 2024-01."""
    datas = []
    for i in range(n):
        m = i  # meses desde 2024-01
        datas.append(dt.date(2024 + m // 12, m % 12 + 1, 28))
    return datas


def test_montar_grafo_co_movimento_com_historico_mensal_suficiente() -> None:
    ctx = _contexto_petroleo()
    meses = _meses(MIN_N + 5)
    ctx["series_historicas"] = {
        "USD_VENDA": [(d, 5.0 + i * 0.01) for i, d in enumerate(meses)],
        "COMMODITY_BRENT": [(d, 80.0 + i * 0.5) for i, d in enumerate(meses)],
    }
    elos = montar_grafo(ctx)
    co = [e for e in elos if e.metodo == METODO_CO_MOVIMENTO]
    assert len(co) == 1
    assert co[0].ligacao_causal is None  # Pearson não afirma causa
    assert co[0].n_amostras >= MIN_N
    assert co[0].hedge
    assert "mensal" in (co[0].periodo or "")


def test_co_movimento_alinha_por_mes_mesmo_com_frequencias_diferentes() -> None:
    # Dólar diário × Brent mensal: as DATAS exatas quase nunca coincidem, mas o
    # alinhamento casa (ano, mês) — o cenário real que antes dava n≈0 e nunca
    # disparava o co-movimento.
    ctx = _contexto_petroleo()
    meses = _meses(MIN_N + 2)
    usd_diario = []
    for i, d in enumerate(meses):
        usd_diario.append((d.replace(day=10), 5.0 + i * 0.01))
        usd_diario.append((d.replace(day=25), 5.1 + i * 0.01))  # última do mês vence
    brent_mensal = [(d.replace(day=1), 80.0 + i * 0.5) for i, d in enumerate(meses)]
    ctx["series_historicas"] = {"USD_VENDA": usd_diario, "COMMODITY_BRENT": brent_mensal}
    elos = montar_grafo(ctx)
    co = [e for e in elos if e.metodo == METODO_CO_MOVIMENTO]
    assert len(co) == 1
    assert co[0].n_amostras == MIN_N + 2


def test_montar_grafo_novos_elos_d1_com_fonte_nas_duas_pontas() -> None:
    ctx = _contexto_petroleo()
    ctx["fundamento_fontes"] = {
        "Dívida bruta (derivado)": "f-divida",
        "3.06": "f-resfin",
        "3.06.02": "f-despfin",
    }
    dims = {e.dimensao for e in montar_grafo(ctx)}
    assert "juros_global→divida_empresa" in dims
    assert "câmbio→resultado_financeiro" in dims
    assert "selic→despesas_financeiras" in dims


def test_montar_grafo_novos_elos_abstem_sem_a_conta() -> None:
    # Sem as contas específicas (ex.: banco, plano de contas próprio), os elos
    # D1 novos NÃO entram — fonte nas duas pontas é inegociável.
    ctx = _contexto_petroleo()
    ctx["fundamento_fontes"] = {}
    dims = {e.dimensao for e in montar_grafo(ctx)}
    assert "juros_global→divida_empresa" not in dims
    assert "câmbio→resultado_financeiro" not in dims
    assert "selic→despesas_financeiras" not in dims


def test_elos_para_llm_inclui_ambas_as_fontes() -> None:
    linhas = elos_para_llm(montar_grafo(_contexto_petroleo()))
    assert linhas
    for linha in linhas:
        assert "origem=" in linha and "destino=" in linha
        assert "HEDGE" in linha
