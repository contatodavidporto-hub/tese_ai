"""Testes offline de `app.services.tecnica` (KATs + contrato do bloco técnico).

100% puro — nenhuma rede/DB. Validação cruzada em DOIS conjuntos de KATs
(ambos DEVEM passar):

1. CSVs ``cs-*.csv`` (bukosabino/ta, MIT — `tests/fixtures/kats/`, atribuição
   no README e licença em `ta_LICENSE.txt`), com colunas intermediárias;
2. vetores numéricos transcritos do smoke-test do Tulip Indicators (APENAS os
   números publicados, precisão de 3 casas — nenhum código LGPL copiado).

Convenções que diferem entre produção e KAT usam o modo correspondente do
helper (ex.: EMA ``seed="primeiro"``), documentado em cada teste. Foco
anti-alucinação no contrato: série insuficiente → omissão com motivo (nunca
NaN); leituras por template NEUTRO (pré-checagem do gate A5/A7); nota fixa de
preços não ajustados; séries de gráfico ≤ 252 pontos.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.tecnica import (
    MAX_PONTOS_SERIE,
    NOTA_GRAFICO,
    NOTA_TECNICA,
    IndicadoresTecnicos,
    bollinger,
    calcular,
    ema,
    estocastico,
    fibonacci_retracoes,
    graficos_para_envelope,
    linha_ad,
    macd,
    rsi,
    sma,
    tecnica_para_envelope,
    williams_r,
)

_KATS = Path(__file__).parent / "fixtures" / "kats"


def _coluna(arquivo: str, coluna: str) -> list[float | None]:
    """Coluna numérica de um CSV de KAT (célula vazia → None)."""
    with open(_KATS / arquivo, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return [float(li[coluna]) if li[coluna].strip() else None for li in linhas]


def _definidos(valores: list[float | None]) -> list[float]:
    return [v for v in valores if v is not None]


def _comparar_alinhado(
    obtido: list[float | None],
    esperado: list[float | None],
    tol: float,
    *,
    a_partir_de: int = 0,
) -> int:
    """Compara onde o esperado está definido; devolve o nº de pares checados."""
    pares = 0
    for i, (o, e) in enumerate(zip(obtido, esperado, strict=True)):
        if e is None or i < a_partir_de:
            continue
        assert o is not None, f"linha {i}: obtido None, esperado {e}"
        assert o == pytest.approx(e, abs=tol), f"linha {i}: {o} != {e}"
        pares += 1
    assert pares > 0
    return pares


# ---------------------------------------------------------------------------
# KATs conjunto 2 — Tulip Indicators (números transcritos; 3 casas decimais)
# ---------------------------------------------------------------------------

_T_CLOSE = [
    81.59,
    81.06,
    82.87,
    83.00,
    83.61,
    83.15,
    82.84,
    83.99,
    84.55,
    84.36,
    85.53,
    86.54,
    86.89,
    87.77,
    87.29,
]  # noqa: E501
_T_HIGH = [
    82.15,
    81.89,
    83.03,
    83.30,
    83.85,
    83.90,
    83.33,
    84.30,
    84.84,
    85.00,
    85.90,
    86.58,
    86.98,
    88.00,
    87.87,
]  # noqa: E501
_T_LOW = [
    81.29,
    80.64,
    81.31,
    82.65,
    83.07,
    83.11,
    82.49,
    82.30,
    84.15,
    84.11,
    84.03,
    85.39,
    85.76,
    87.17,
    87.01,
]  # noqa: E501
_T_VOLUME = [
    5653100.0,
    6447400.0,
    7690900.0,
    3831400.0,
    4455100.0,
    3798000.0,
    3936200.0,
    4732000.0,
    4841300.0,
    3915300.0,
    6830800.0,
    6694100.0,
    5293600.0,
    7985800.0,
    4807900.0,
]  # noqa: E501

_TOL_TULIP = 1e-3  # precisão publicada: 3 casas decimais


def test_kat_tulip_sma5() -> None:
    esperado = [
        82.426,
        82.738,
        83.094,
        83.318,
        83.628,
        83.778,
        84.254,
        84.994,
        85.574,
        86.218,
        86.804,
    ]  # noqa: E501
    assert _definidos(sma(_T_CLOSE, 5)) == pytest.approx(esperado, abs=_TOL_TULIP)


def test_kat_tulip_ema5_seed_primeiro() -> None:
    """Tulip semeia a EMA no 1º valor (modo KAT ``seed="primeiro"``)."""
    esperado = [
        81.590,
        81.413,
        81.899,
        82.266,
        82.714,
        82.859,
        82.853,
        83.232,
        83.671,
        83.901,
        84.444,
        85.143,
        85.725,
        86.407,
        86.701,
    ]  # noqa: E501
    assert _definidos(ema(_T_CLOSE, 5, seed="primeiro")) == pytest.approx(esperado, abs=_TOL_TULIP)


def test_kat_tulip_rsi5_wilder_seed_media() -> None:
    """Tulip usa a convenção de PRODUÇÃO: semente = média simples (Wilder)."""
    esperado = [
        72.034,
        64.927,
        75.936,
        79.796,
        74.713,
        83.033,
        87.478,
        88.755,
        91.483,
        78.498,
    ]  # noqa: E501
    assert _definidos(rsi(_T_CLOSE, 5, seed="media")) == pytest.approx(esperado, abs=_TOL_TULIP)


def test_kat_tulip_macd_2_5_9() -> None:
    """MACD Tulip: EMAs seed=primeiro; sinal semeado no 1º valor emitido (idx longo−1)."""
    linha, sinal, hist = macd(_T_CLOSE, 2, 5, 9, seed="primeiro")
    esp_linha = [0.618, 0.351, 0.111, 0.416, 0.578, 0.422, 0.684, 0.927, 0.891, 0.979, 0.621]
    esp_sinal = [0.618, 0.564, 0.474, 0.462, 0.485, 0.473, 0.515, 0.597, 0.656, 0.721, 0.701]
    esp_hist = [0.000, -0.213, -0.363, -0.046, 0.093, -0.050, 0.169, 0.329, 0.235, 0.258, -0.080]
    assert linha[4:] == pytest.approx(esp_linha, abs=_TOL_TULIP)
    assert sinal[4:] == pytest.approx(esp_sinal, abs=_TOL_TULIP)
    assert hist[4:] == pytest.approx(esp_hist, abs=_TOL_TULIP)


def test_kat_tulip_bbands_5_2() -> None:
    central, superior, inferior = bollinger(_T_CLOSE, 5, 2)
    esp_inf = [
        80.530,
        80.987,
        82.533,
        82.472,
        82.418,
        82.435,
        82.511,
        83.143,
        83.536,
        83.870,
        85.289,
    ]  # noqa: E501
    esp_cen = [
        82.426,
        82.738,
        83.094,
        83.318,
        83.628,
        83.778,
        84.254,
        84.994,
        85.574,
        86.218,
        86.804,
    ]  # noqa: E501
    esp_sup = [
        84.322,
        84.489,
        83.655,
        84.164,
        84.838,
        85.121,
        85.997,
        86.845,
        87.612,
        88.566,
        88.319,
    ]  # noqa: E501
    assert _definidos(inferior) == pytest.approx(esp_inf, abs=_TOL_TULIP)
    assert _definidos(central) == pytest.approx(esp_cen, abs=_TOL_TULIP)
    assert _definidos(superior) == pytest.approx(esp_sup, abs=_TOL_TULIP)


def test_kat_tulip_stoch_5_3_3() -> None:
    """Tulip publica %K lento e %D alinhados ao início do %D (últimos 7 valores)."""
    _, k_lento, linha_d = estocastico(_T_HIGH, _T_LOW, _T_CLOSE, 5, 3, 3)
    esp_k = [77.385, 83.126, 84.867, 88.361, 95.246, 96.740, 91.091]
    esp_d = [75.702, 78.011, 81.793, 85.452, 89.491, 93.449, 94.359]
    assert _definidos(k_lento)[2:] == pytest.approx(esp_k, abs=_TOL_TULIP)
    assert _definidos(linha_d) == pytest.approx(esp_d, abs=_TOL_TULIP)


def test_kat_tulip_willr5() -> None:
    esperado = [
        -7.477,
        -23.006,
        -40.927,
        -15.500,
        -11.417,
        -23.704,
        -10.278,
        -0.935,
        -3.051,
        -5.793,
        -17.884,
    ]  # noqa: E501
    assert _definidos(williams_r(_T_HIGH, _T_LOW, _T_CLOSE, 5)) == pytest.approx(
        esperado, abs=_TOL_TULIP
    )


def test_kat_tulip_ad() -> None:
    esperado = [
        -1709076.744,
        -3823823.944,
        2436210.940,
        2730934.016,
        4444434.016,
        1031041.611,
        375008.278,
        3640088.278,
        4411889.727,
        2696196.469,
        6823899.143,
        13067975.613,
        17580552.662,
        21140487.602,
        19463313.184,
    ]  # noqa: E501
    # magnitude ~1e7 com 3 casas publicadas → tolerância absoluta 1e-2
    assert linha_ad(_T_HIGH, _T_LOW, _T_CLOSE, _T_VOLUME) == pytest.approx(esperado, abs=1e-2)


# ---------------------------------------------------------------------------
# KATs conjunto 1 — CSVs cs-* (bukosabino/ta, MIT; planilhas StockCharts)
# ---------------------------------------------------------------------------


def test_kat_cs_rsi_seed_zero() -> None:
    """Convenção do CSV: ewm(α=1/14, adjust=False) partindo de 0 na 1ª barra."""
    closes = _definidos(_coluna("cs-rsi.csv", "Close"))
    obtido = rsi(closes, 14, seed="zero")
    pares = _comparar_alinhado(obtido, _coluna("cs-rsi.csv", "RSI"), 1e-4)
    assert pares == 19


def test_kat_cs_macd_emas_e_linha() -> None:
    """EMAs e linha MACD do CSV usam seed=primeiro (planilha), comparadas 1:1."""
    closes = _definidos(_coluna("cs-macd.csv", "Close"))
    linha, _, _ = macd(closes, 12, 26, 9, seed="primeiro")
    _comparar_alinhado(ema(closes, 12, seed="primeiro"), _coluna("cs-macd.csv", "short_ema"), 1e-6)
    _comparar_alinhado(ema(closes, 26, seed="primeiro"), _coluna("cs-macd.csv", "long_ema"), 1e-6)
    _comparar_alinhado(linha, _coluna("cs-macd.csv", "MACD_line"), 1e-6)


def test_kat_cs_macd_sinal_e_histograma_convergem() -> None:
    """A coluna MACD_signal do CSV usa semente própria da planilha (EMA(9) desde
    a 1ª linha da MACD_line); o esquecimento exponencial (α=0,2) garante
    convergência — comparamos a cauda (linha ≥ 80), onde o efeito da semente
    é < 2e-6. A convenção de semente do sinal é validada exatamente pelo KAT
    Tulip (`test_kat_tulip_macd_2_5_9`)."""
    closes = _definidos(_coluna("cs-macd.csv", "Close"))
    _, sinal, hist = macd(closes, 12, 26, 9, seed="primeiro")
    _comparar_alinhado(sinal, _coluna("cs-macd.csv", "MACD_signal"), 1e-4, a_partir_de=80)
    _comparar_alinhado(hist, _coluna("cs-macd.csv", "MACD_diff"), 1e-4, a_partir_de=80)


def test_kat_cs_bbands_ddof0() -> None:
    """Bollinger(20, 2) com desvio-padrão POPULACIONAL (ddof=0)."""
    closes = _definidos(_coluna("cs-bbands.csv", "Close"))
    central, superior, inferior = bollinger(closes, 20, 2)
    assert _comparar_alinhado(central, _coluna("cs-bbands.csv", "MiddleBand"), 1e-4) == 23
    _comparar_alinhado(superior, _coluna("cs-bbands.csv", "HighBand"), 1e-4)
    _comparar_alinhado(inferior, _coluna("cs-bbands.csv", "LowBand"), 1e-4)


def test_kat_cs_soo_estocastico_rapido() -> None:
    """SO = %K rápido(14); SO_SIG = SMA(3) do %K (o %K lento da versão 14,3,3)."""
    maximas = _definidos(_coluna("cs-soo.csv", "High"))
    minimas = _definidos(_coluna("cs-soo.csv", "Low"))
    closes = [v if v is not None else 0.0 for v in _coluna("cs-soo.csv", "Close")]
    k_rapido, k_lento, _ = estocastico(maximas, minimas, closes, 14, 3, 3)
    assert _comparar_alinhado(k_rapido, _coluna("cs-soo.csv", "SO"), 1e-4) == 17
    _comparar_alinhado(k_lento, _coluna("cs-soo.csv", "SO_SIG"), 1e-4)


def test_kat_cs_percentr_williams() -> None:
    maximas = _definidos(_coluna("cs-percentr.csv", "High"))
    minimas = _definidos(_coluna("cs-percentr.csv", "Low"))
    closes = [v if v is not None else 0.0 for v in _coluna("cs-percentr.csv", "Close")]
    obtido = williams_r(maximas, minimas, closes, 14)
    assert _comparar_alinhado(obtido, _coluna("cs-percentr.csv", "Williams_%R"), 1e-4) == 17


def test_kat_cs_accum_ad() -> None:
    obtido = linha_ad(
        _definidos(_coluna("cs-accum.csv", "High")),
        _definidos(_coluna("cs-accum.csv", "Low")),
        _definidos(_coluna("cs-accum.csv", "Close")),
        _definidos(_coluna("cs-accum.csv", "Volume")),
    )
    esperado = _definidos(_coluna("cs-accum.csv", "ADLine"))
    assert obtido == pytest.approx(esperado, abs=1e-3)


# ---------------------------------------------------------------------------
# Regras unitárias das convenções fixas
# ---------------------------------------------------------------------------


def test_rsi_avg_loss_zero_da_100() -> None:
    """Convenção fixa do plano: AvgLoss=0 → RSI=100 (série só de altas)."""
    closes = [10.0 + i for i in range(40)]
    assert _definidos(rsi(closes, 14))[-1] == 100.0


def test_ad_mfm_zero_quando_high_igual_low() -> None:
    """MFM=0 quando High==Low: a barra não move a linha A/D."""
    serie = linha_ad(
        [10.0, 11.0, 11.0], [9.0, 11.0, 10.0], [9.5, 11.0, 10.5], [100.0, 999.0, 100.0]
    )
    assert serie[1] == serie[0]  # barra 2 (H==L) não contribui


def test_estocastico_e_williams_amplitude_nula_neutros() -> None:
    """Série achatada (HH==LL): quociente indefinido → centro da escala."""
    plano = [5.0] * 20
    assert _definidos(estocastico(plano, plano, plano, 14, 3, 3)[0]) == [50.0] * 7
    assert _definidos(williams_r(plano, plano, plano, 14)) == [-50.0] * 7


def test_fibonacci_direcao_alta_golden() -> None:
    """Fundo 10 (idx 0), topo 20 (idx final) → alta; nível = topo − p×amplitude."""
    baixas = [10.0] + [12.0] * 8 + [15.0]
    altas = [11.0] + [13.0] * 8 + [20.0]
    fib = fibonacci_retracoes(altas, baixas, janela=252)
    assert fib is not None
    assert fib.direcao == "alta"
    assert (fib.topo, fib.fundo, fib.janela) == (20.0, 10.0, 10)
    niveis = dict(fib.niveis)
    assert niveis[0.5] == pytest.approx(15.0)
    assert niveis[0.236] == pytest.approx(20.0 - 0.236 * 10.0)
    assert niveis[0.786] == pytest.approx(20.0 - 0.786 * 10.0)


def test_fibonacci_direcao_baixa_golden() -> None:
    """Topo 20 (idx 0), fundo 10 (idx final) → baixa; nível = fundo + p×amplitude."""
    altas = [20.0] + [13.0] * 8 + [11.0]
    baixas = [15.0] + [12.0] * 8 + [10.0]
    fib = fibonacci_retracoes(altas, baixas, janela=252)
    assert fib is not None
    assert fib.direcao == "baixa"
    assert dict(fib.niveis)[0.618] == pytest.approx(10.0 + 0.618 * 10.0)


def test_fibonacci_janela_252_ignora_extremos_antigos() -> None:
    """Extremo fora da janela de 252 não entra no cálculo."""
    altas = [99.0] + [20.0] * 252
    baixas = [1.0] + [10.0] * 252
    fib = fibonacci_retracoes(altas, baixas, janela=252)
    assert fib is not None
    assert (fib.topo, fib.fundo, fib.janela) == (20.0, 10.0, 252)


def test_fibonacci_amplitude_nula_none() -> None:
    assert fibonacci_retracoes([5.0] * 30, [5.0] * 30) is None


def test_parametros_invalidos_sao_erro_de_contrato() -> None:
    with pytest.raises(ValueError):
        sma([1.0], 0)
    with pytest.raises(ValueError):
        ema([1.0], 5, seed="outra")
    with pytest.raises(ValueError):
        rsi([1.0], 5, seed="outra")


# ---------------------------------------------------------------------------
# Contrato de `calcular` (bloco técnico do envelope)
# ---------------------------------------------------------------------------


def _barras(
    n: int,
    *,
    ticker: str = "TESTE3",
    usar_decimal: bool = False,
    sem_hl: bool = False,
    queda: bool = False,
) -> list[SimpleNamespace]:
    """Série OHLCV sintética determinística (dias úteis a partir de 02/01/2025)."""
    saida: list[SimpleNamespace] = []
    data = dt.date(2025, 1, 2)
    for i in range(n):
        while data.weekday() >= 5:
            data += dt.timedelta(days=1)
        if queda:
            fech = 100.0 - i * 0.4
            maxima, minima = fech + 1.5, fech - 0.3  # fechamento perto da mínima
        else:
            fech = 100.0 + 10.0 * math.sin(i / 9.0) + i * 0.03
            maxima, minima = fech + 0.8, fech - 0.9

        def conv(x: float) -> object:
            return Decimal(str(round(x, 2))) if usar_decimal else round(x, 2)

        saida.append(
            SimpleNamespace(
                ticker=ticker,
                data_pregao=data,
                abertura=conv(fech - 0.2),
                maxima=None if sem_hl else conv(maxima),
                minima=None if sem_hl else conv(minima),
                fechamento=conv(fech),
                volume=None if sem_hl else conv(1_000_000.0 + (i % 7) * 10_000),
            )
        )
        data += dt.timedelta(days=1)
    return saida


_NOMES_COMPLETOS = {
    "Média móvel (20)",
    "Média móvel (50)",
    "Média móvel (200)",
    "Média móvel exponencial (12)",
    "Média móvel exponencial (26)",
    "MACD (12, 26, 9)",
    "RSI (14)",
    "Estocástico (14, 3, 3)",
    "Bandas de Bollinger (20, 2)",
    "Williams %R (14)",
    "Acumulação/Distribuição",
    "Retração de Fibonacci (252 pregões)",
}

_ORDEM_GRAFICOS = ["preco_bollinger", "macd", "rsi", "estocastico", "williams", "volume_ad"]

# Espelha o R10/A7 do gate v3: palavra diretiva em texto user-visible = veto.
# "sobrecompra"/"sobrevenda" NÃO casam (sem fronteira de palavra antes de compr/vend).
_PROIBIDO = re.compile(
    r"\b(compr\w*|vend\w*|entrada|sa[íi]da|hora de|momento de|oportunidad\w*"
    r"|recomend\w*|posicionar|pre[çc]o[- ]alvo|upside|aproveit\w*|barganha)\b",
    re.IGNORECASE,
)


def test_calcular_serie_completa_todos_indicadores() -> None:
    resultado = calcular(_barras(300))
    assert isinstance(resultado, IndicadoresTecnicos)
    assert {i.nome for i in resultado.indicadores} == _NOMES_COMPLETOS
    assert resultado.lacunas == ()
    assert resultado.nota == NOTA_TECNICA
    assert resultado.fonte.dt_referencia == _barras(300)[-1].data_pregao
    assert "não ajustados por proventos" in resultado.fonte.descricao
    for ind in resultado.indicadores:
        assert ind.valor is None or not math.isnan(ind.valor)
        assert ind.unidade in ("indice", "BRL", "pct")
        assert ind.o_que_mede and ind.leitura


def test_graficos_ordem_canonica_e_estrutura() -> None:
    resultado = calcular(_barras(300))
    assert [g.id for g in resultado.graficos] == _ORDEM_GRAFICOS
    por_id = {g.id: g for g in resultado.graficos}

    preco = por_id["preco_bollinger"]
    assert preco.tipo == "linha_faixa"
    assert preco.eixo_y == "BRL"
    assert [s.nome for s in preco.series] == [
        "Fechamento",
        "Média móvel (20)",
        "Média móvel (50)",
        "Média móvel (200)",
    ]
    assert preco.faixa is not None and preco.faixa.pontos
    assert all(p.sup >= p.inf for p in preco.faixa.pontos)
    assert len(preco.linhas_ref) == 5  # níveis de Fibonacci

    assert [s.nome for s in por_id["macd"].series] == ["MACD", "Sinal", "Histograma"]
    assert {lr.valor for lr in por_id["rsi"].linhas_ref} == {30.0, 70.0}
    assert {lr.valor for lr in por_id["estocastico"].linhas_ref} == {20.0, 80.0}
    assert {lr.valor for lr in por_id["williams"].linhas_ref} == {-20.0, -80.0}
    assert [s.nome for s in por_id["volume_ad"].series] == ["Volume financeiro", "Linha A/D"]

    ultima = _barras(300)[-1].data_pregao.isoformat()
    for grafico in resultado.graficos:
        assert grafico.ticker == "TESTE3"
        assert grafico.nota == NOTA_GRAFICO
        assert "ajustados por proventos" in grafico.nota
        for serie in grafico.series:
            assert 0 < len(serie.pontos) <= MAX_PONTOS_SERIE
        # o último pregão sempre permanece após o downsampling
        assert grafico.series[0].pontos[-1].d == ultima


def test_warmup_recursivo_descartado_das_series() -> None:
    """EMA/MACD/RSI descartam 2n barras de warm-up; SMA começa na barra n−1."""
    barras = _barras(300)
    datas = [b.data_pregao.isoformat() for b in barras]
    por_id = {g.id: g for g in calcular(barras).graficos}
    # MACD: 2×26 = 52 barras descartadas → 248 pontos (sem downsampling)
    assert por_id["macd"].series[0].pontos[0].d == datas[52]
    # RSI: 2×14 = 28 descartadas → 272 pontos → downsampling passo 2 mantém o fim
    primeiro_rsi = por_id["rsi"].series[0].pontos[0].d
    assert primeiro_rsi >= datas[28]
    # SMA(20): janela exata a partir da barra 19 (sem semente, sem descarte extra)
    assert por_id["preco_bollinger"].series[1].pontos[0].d == datas[19]


def test_serie_curta_omite_com_motivo_nunca_nan() -> None:
    resultado = calcular(_barras(40))
    nomes = {i.nome for i in resultado.indicadores}
    assert "Média móvel (20)" in nomes
    assert "RSI (14)" in nomes  # exige 29
    assert "Média móvel exponencial (12)" in nomes  # exige 25
    for ausente in ("Média móvel (50)", "Média móvel (200)", "MACD (12, 26, 9)"):
        assert ausente not in nomes
        assert any(
            lac.startswith(ausente) and "série insuficiente" in lac for lac in resultado.lacunas
        )
    assert "Média móvel exponencial (26)" not in nomes  # exige 2×26+1 = 53
    assert "macd" not in {g.id for g in resultado.graficos}
    for ind in resultado.indicadores:
        assert ind.valor is None or not math.isnan(ind.valor)


def test_limiares_minimos_recursivos() -> None:
    """MACD entra com 53 barras (2×26+1) e sai com 52; RSI entra com 29, sai com 28."""
    assert "MACD (12, 26, 9)" in {i.nome for i in calcular(_barras(53)).indicadores}
    assert "MACD (12, 26, 9)" not in {i.nome for i in calcular(_barras(52)).indicadores}
    assert "RSI (14)" in {i.nome for i in calcular(_barras(29)).indicadores}
    assert "RSI (14)" not in {i.nome for i in calcular(_barras(28)).indicadores}


def test_precos_vazios_abstencao_rotulada() -> None:
    resultado = calcular([])
    assert resultado.indicadores == ()
    assert resultado.graficos == ()
    assert any("série de preços vazia" in lac for lac in resultado.lacunas)
    assert resultado.fonte.dt_referencia is None


def test_barras_sem_fechamento_descartadas_com_lacuna() -> None:
    barras = _barras(60)
    for barra in barras[10:13]:
        barra.fechamento = None
    resultado = calcular(barras)
    assert any("3 pregões sem fechamento" in lac for lac in resultado.lacunas)
    assert "RSI (14)" in {i.nome for i in resultado.indicadores}


def test_sem_maxima_minima_omite_hlc_e_fibonacci_cai_para_fechamentos() -> None:
    resultado = calcular(_barras(60, sem_hl=True))
    nomes = {i.nome for i in resultado.indicadores}
    assert "Estocástico (14, 3, 3)" not in nomes
    assert "Williams %R (14)" not in nomes
    assert "Acumulação/Distribuição" not in nomes
    assert sum("máxima/mínima" in lac for lac in resultado.lacunas) == 3
    assert {g.id for g in resultado.graficos}.isdisjoint({"estocastico", "williams", "volume_ad"})
    # RSI/Bollinger (só fechamento) permanecem; Fibonacci degrada com rótulo
    assert "RSI (14)" in nomes
    fib = next(i for i in resultado.indicadores if i.nome.startswith("Retração de Fibonacci"))
    assert fib.detalhe is not None and "sobre fechamentos" in fib.detalhe


def test_decimal_e_ordem_embaralhada_normalizados() -> None:
    """Decimal (SQLAlchemy Numeric) vira float e a série é ordenada por data."""
    barras = _barras(80, usar_decimal=True)
    embaralhadas = barras[40:] + barras[:40][::-1]
    resultado = calcular(embaralhadas)
    referencia = calcular(_barras(80))
    assert resultado.fonte.dt_referencia == barras[-1].data_pregao
    rsi_a = next(i for i in resultado.indicadores if i.nome == "RSI (14)").valor
    rsi_b = next(i for i in referencia.indicadores if i.nome == "RSI (14)").valor
    assert rsi_a == pytest.approx(rsi_b)
    pontos = calcular(embaralhadas).graficos[0].series[0].pontos
    assert [p.d for p in pontos] == sorted(p.d for p in pontos)


def test_downsample_series_longas() -> None:
    """Série > 252 barras reduz para ≤ 252 pontos mantendo o último pregão."""
    barras = _barras(300)
    fechamento = calcular(barras).graficos[0].series[0]
    assert len(fechamento.pontos) <= MAX_PONTOS_SERIE
    assert fechamento.pontos[-1].d == barras[-1].data_pregao.isoformat()


def test_leituras_neutras_passam_pelo_gate() -> None:
    """Templates determinísticos NUNCA contêm linguagem diretiva (A5/A7) —
    varre alta e queda para exercitar sobrecompra E sobrevenda."""
    achou_sobrecompra = achou_sobrevenda = False
    for cenario in (_barras(300), _barras(60, queda=True)):
        resultado = calcular(cenario)
        textos = [resultado.nota, resultado.fonte.descricao, *resultado.lacunas]
        for ind in resultado.indicadores:
            textos += [ind.nome, ind.leitura, ind.o_que_mede, ind.detalhe or ""]
        for grafico in resultado.graficos:
            textos += [grafico.titulo, grafico.nota]
            textos += [s.nome for s in grafico.series]
            textos += [lr.nome for lr in grafico.linhas_ref]
        for texto in textos:
            assert not _PROIBIDO.search(texto), f"linguagem diretiva em: {texto!r}"
        junto = " ".join(textos)
        achou_sobrecompra |= "sobrecompra" in junto
        achou_sobrevenda |= "sobrevenda" in junto
    # prova que os ramos descritivos foram exercitados (e não casam no regex)
    assert achou_sobrecompra and achou_sobrevenda


def test_leitura_rsi_template_deterministico() -> None:
    """Golden do template: valor formatado pt-BR + região histórica descritiva."""
    resultado = calcular(_barras(60, queda=True))
    leitura = next(i for i in resultado.indicadores if i.nome == "RSI (14)").leitura
    assert leitura.startswith("RSI(14) em ")
    assert "sobrevenda" in leitura
    assert re.search(r"\d,\d", leitura)  # vírgula decimal pt-BR


def test_envelope_contrato_v3() -> None:
    resultado = calcular(_barras(300))
    tecnica = tecnica_para_envelope(resultado)
    assert set(tecnica) == {"nota", "fonte", "indicadores", "lacunas"}
    assert set(tecnica["fonte"]) == {"descricao", "url", "dt_referencia"}
    assert tecnica["fonte"]["dt_referencia"] == resultado.fonte.dt_referencia.isoformat()
    for item in tecnica["indicadores"]:
        assert set(item) == {"nome", "valor", "unidade", "detalhe", "o_que_mede", "leitura"}

    graficos = graficos_para_envelope(resultado)
    assert [g["id"] for g in graficos] == _ORDEM_GRAFICOS
    for grafico in graficos:
        assert set(grafico) == {
            "id",
            "tipo",
            "titulo",
            "ticker",
            "eixo_y",
            "nota",
            "fonte",
            "series",
            "faixa",
            "linhas_ref",
        }
        for serie in grafico["series"]:
            assert len(serie["pontos"]) <= MAX_PONTOS_SERIE
    # serializável para o TeseVersao.conteudo (JSON) sem conversões extras
    json.dumps({"tecnica": tecnica, "graficos": graficos})
