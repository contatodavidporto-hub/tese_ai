"""Indicadores técnicos — módulo PURO (plano §2.3 + contrato-envelope-v3 §1/§2).

Regras inegociáveis deste módulo:

- 100% determinístico e puro: nenhuma rede/LLM/DB. A F3 (integração) lê a série
  de `precos_diarios` (COTAHIST, cada linha com sua ``Fonte``) e chama
  :func:`calcular`; aqui só se calcula, rotula e descreve.
- Preços de ENTRADA são de fim de dia NÃO ajustados por proventos (B3/COTAHIST):
  a nota fixa acompanha o bloco e TODOS os gráficos (risco 4 do plano).
- Série insuficiente → indicador OMITIDO com motivo declarado (lacuna rotulada,
  padrão `derivadas.py`/`valuation.py`) — nunca NaN, nunca 0-fill, nunca exceção.
- Leituras são templates determinísticos NEUTROS (correções A5/A7): descrevem o
  valor e a região histórica; JAMAIS linguagem diretiva (compra/venda/entrada/
  saída/hora de/momento de/oportunidade).
- Implementação em Python puro (stdlib): pandas não está nas dependências do
  projeto e dependência nova é proibida (pandas-ta banida).

Convenções numéricas (validadas por KATs bukosabino/ta E Tulip Indicators —
`tests/test_tecnica.py` + `tests/fixtures/kats/`):

- SMA(20/50/200); EMA(12/26) com semente = SMA(n) em produção (modo
  ``seed="primeiro"`` existe só para os KATs); MACD(12, 26, 9);
- RSI(14) Wilder: α=1/14, recursivo (adjust=False), semente = média simples dos
  n primeiros ganhos/perdas; AvgLoss=0 → RSI=100 (modo ``seed="zero"`` = KAT);
- Estocástico lento (14, 3, 3); Bandas de Bollinger (20, 2) com desvio-padrão
  POPULACIONAL (ddof=0); Williams %R(14); A/D com MFM=0 quando High==Low;
- Retração de Fibonacci sobre a janela de 252 pregões (regra documentada em
  :func:`fibonacci_retracoes`);
- warm-up: indicadores RECURSIVOS (EMA/MACD/RSI), cujo início depende da
  semente, têm as primeiras 2n barras descartadas da saída; indicadores de
  JANELA (SMA/Bollinger/Estocástico/Williams) são exatos a partir da barra n−1
  e não têm semente a contaminar;
- séries para gráfico com downsampling ≤ 252 pontos (o último ponto sempre
  permanece).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

# ---------------------------------------------------------------------------
# Constantes de convenção (nunca mudar sem re-baseline dos KATs)
# ---------------------------------------------------------------------------

SMA_JANELAS = (20, 50, 200)
EMA_JANELAS = (12, 26)
MACD_PARAMS = (12, 26, 9)
RSI_N = 14
ESTOCASTICO_PARAMS = (14, 3, 3)
BOLLINGER_N = 20
BOLLINGER_K = 2.0
WILLIAMS_N = 14
FIBONACCI_JANELA = 252
FIBONACCI_NIVEIS = (0.236, 0.382, 0.5, 0.618, 0.786)

#: fator de warm-up dos indicadores recursivos: descarta as primeiras 2n barras.
WARMUP_FATOR = 2

#: teto de pontos por série de gráfico (plano §2.5).
MAX_PONTOS_SERIE = 252

#: nota fixa do bloco `tecnica` (obrigatória — risco 4 do plano).
NOTA_TECNICA = (
    "Indicadores calculados sobre preços de fim de dia NÃO ajustados por "
    "proventos (B3/COTAHIST)."
)

#: nota fixa de cada gráfico (contrato §1: sempre inclui o rótulo de não-ajuste).
NOTA_GRAFICO = "Preços de fim de dia não ajustados por proventos (B3/COTAHIST)."

_DESCRICAO_FONTE = "B3 — COTAHIST (dados de fim de dia): preços não ajustados por proventos"

# Neutralidade quando a amplitude máx−mín da janela é nula (série achatada) —
# regra documentada: o quociente é indefinido; adota-se o centro da escala.
_ESTOCASTICO_NEUTRO = 50.0
_WILLIAMS_NEUTRO = -50.0

_AD_JANELA_LEITURA = 21  # pregões (~1 mês) usados na leitura de direção da linha A/D


class PrecoOHLCV(Protocol):
    """Barra OHLCV mínima (duck-typing de `models.PrecoDiario`)."""

    ticker: str
    data_pregao: dt.date
    maxima: float | None
    minima: float | None
    fechamento: float | None
    volume: float | None


# ---------------------------------------------------------------------------
# Contratos de SAÍDA — espelham contrato-envelope-v3 §1 (graficos) e §2 (tecnica)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FonteRef:
    """Referência de fonte do envelope: descrição + url + data (contrato v3)."""

    descricao: str
    url: str | None = None
    dt_referencia: dt.date | None = None


@dataclass(frozen=True)
class Ponto:
    """Ponto de série: data ISO + valor."""

    d: str
    v: float


@dataclass(frozen=True)
class PontoFaixa:
    """Ponto de faixa (Bollinger): data ISO + limites superior/inferior."""

    d: str
    sup: float
    inf: float


@dataclass(frozen=True)
class Serie:
    nome: str
    pontos: tuple[Ponto, ...]


@dataclass(frozen=True)
class Faixa:
    nome: str
    pontos: tuple[PontoFaixa, ...]


@dataclass(frozen=True)
class LinhaRef:
    """Linha de referência horizontal (RSI 30/70, %R −20/−80, níveis Fibonacci)."""

    nome: str
    valor: float


@dataclass(frozen=True)
class Grafico:
    """Um gráfico do envelope (contrato v3 §1)."""

    id: str
    tipo: str  # "linha" | "linha_faixa" | "macd" | "oscilador"
    titulo: str
    ticker: str
    eixo_y: str  # "BRL" | "indice" | "pct"
    nota: str
    fonte: FonteRef
    series: tuple[Serie, ...] = ()
    faixa: Faixa | None = None
    linhas_ref: tuple[LinhaRef, ...] = ()


@dataclass(frozen=True)
class IndicadorTecnico:
    """Valor atual + leitura descritiva NEUTRA de um indicador (contrato v3 §2)."""

    nome: str
    valor: float | None
    unidade: str  # "indice" | "BRL" | "pct"
    detalhe: str | None
    o_que_mede: str
    leitura: str


@dataclass(frozen=True)
class IndicadoresTecnicos:
    """Bloco técnico completo: indicadores + gráficos + lacunas rotuladas."""

    nota: str
    fonte: FonteRef
    indicadores: tuple[IndicadorTecnico, ...] = ()
    graficos: tuple[Grafico, ...] = ()
    lacunas: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetracaoFibonacci:
    """Níveis de retração da janela: regra documentada em `fibonacci_retracoes`."""

    topo: float
    fundo: float
    direcao: str  # "alta" | "baixa"
    janela: int  # pregões efetivamente usados
    sobre_fechamentos: bool  # True quando máx/mín intradiários indisponíveis
    niveis: tuple[tuple[float, float], ...]  # (proporção, preço)


# ---------------------------------------------------------------------------
# Formatação pt-BR (leituras determinísticas)
# ---------------------------------------------------------------------------


def _fmt_num(x: float, casas: int = 2) -> str:
    """Número em pt-BR: vírgula decimal e ponto de milhar."""
    inteiro, _, frac = f"{x:,.{casas}f}".partition(".")
    inteiro = inteiro.replace(",", ".")
    return f"{inteiro},{frac}" if casas else inteiro


def _fmt_brl(x: float, casas: int = 2) -> str:
    return "R$ " + _fmt_num(x, casas)


def _fmt_sinal(x: float, casas: int = 2) -> str:
    return ("+" if x >= 0 else "-") + _fmt_num(abs(x), casas)


# ---------------------------------------------------------------------------
# Núcleo numérico (funções puras; listas ALINHADAS ao input, None = indefinido)
# ---------------------------------------------------------------------------


def sma(valores: Sequence[float], n: int) -> list[float | None]:
    """Média móvel simples de janela `n`, alinhada (None antes da barra n−1)."""
    if n <= 0:
        raise ValueError("n deve ser positivo")
    saida: list[float | None] = [None] * len(valores)
    if len(valores) < n:
        return saida
    soma = math.fsum(valores[:n])
    saida[n - 1] = soma / n
    for i in range(n, len(valores)):
        soma += valores[i] - valores[i - n]
        saida[i] = soma / n
    return saida


def _sma_alinhada(valores: Sequence[float | None], n: int) -> list[float | None]:
    """SMA sobre uma série alinhada com prefixo None (osciladores encadeados)."""
    saida: list[float | None] = [None] * len(valores)
    definidos = [(i, v) for i, v in enumerate(valores) if v is not None]
    if len(definidos) < n:
        return saida
    apenas = [v for _, v in definidos]
    medias = sma(apenas, n)
    for (i, _), m in zip(definidos, medias, strict=True):
        saida[i] = m
    return saida


def ema(valores: Sequence[float], n: int, *, seed: str = "sma") -> list[float | None]:
    """Média móvel exponencial (fator k=2/(n+1)), recursiva (adjust=False).

    seed="sma" (produção): 1º valor na barra n−1 = SMA(n).
    seed="primeiro" (KATs Tulip/StockCharts): 1º valor na barra 0 = valores[0].
    """
    if seed not in ("sma", "primeiro"):
        raise ValueError(f"seed inválida: {seed!r}")
    saida: list[float | None] = [None] * len(valores)
    k = 2.0 / (n + 1)
    if seed == "primeiro":
        if not valores:
            return saida
        atual = float(valores[0])
        saida[0] = atual
        inicio = 1
    else:
        if len(valores) < n:
            return saida
        atual = math.fsum(valores[:n]) / n
        saida[n - 1] = atual
        inicio = n
    for i in range(inicio, len(valores)):
        atual = valores[i] * k + atual * (1.0 - k)
        saida[i] = atual
    return saida


def _rsi_de(avg_ganho: float, avg_perda: float) -> float:
    """RSI a partir das médias: AvgLoss=0 → 100 (convenção fixa do plano)."""
    if avg_perda == 0.0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_ganho / avg_perda)


def rsi(fechamentos: Sequence[float], n: int = RSI_N, *, seed: str = "media") -> list[float | None]:
    """RSI de Wilder (α=1/n, recursivo/adjust=False), alinhado (definido da barra n).

    seed="media" (produção/Tulip): semente = média SIMPLES dos n primeiros
    ganhos/perdas. seed="zero" (KAT bukosabino/ta): recursão parte de 0 na
    1ª barra (ewm adjust=False sobre ganhos/perdas com 0 inicial).
    """
    if seed not in ("media", "zero"):
        raise ValueError(f"seed inválida: {seed!r}")
    saida: list[float | None] = [None] * len(fechamentos)
    if len(fechamentos) < n + 1:
        return saida
    ganhos = [max(fechamentos[i] - fechamentos[i - 1], 0.0) for i in range(1, len(fechamentos))]
    perdas = [max(fechamentos[i - 1] - fechamentos[i], 0.0) for i in range(1, len(fechamentos))]
    alpha = 1.0 / n
    if seed == "media":
        ag = math.fsum(ganhos[:n]) / n
        ap = math.fsum(perdas[:n]) / n
        saida[n] = _rsi_de(ag, ap)
        inicio = n + 1
    else:
        ag = 0.0
        ap = 0.0
        inicio = 1
    for i in range(inicio, len(fechamentos)):
        ag = ganhos[i - 1] * alpha + ag * (1.0 - alpha)
        ap = perdas[i - 1] * alpha + ap * (1.0 - alpha)
        if i >= n:
            saida[i] = _rsi_de(ag, ap)
    return saida


def macd(
    fechamentos: Sequence[float],
    curto: int = MACD_PARAMS[0],
    longo: int = MACD_PARAMS[1],
    sinal: int = MACD_PARAMS[2],
    *,
    seed: str = "sma",
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD → (linha, linha de sinal, histograma), listas alinhadas.

    linha = EMA(curto) − EMA(longo); sinal = EMA(`sinal`) da linha a partir da
    barra longo−1 (semente conforme ``seed``); histograma = linha − sinal.
    """
    ema_curto = ema(fechamentos, curto, seed=seed)
    ema_longo = ema(fechamentos, longo, seed=seed)
    linha: list[float | None] = [
        (c - lo) if c is not None and lo is not None else None
        for c, lo in zip(ema_curto, ema_longo, strict=True)
    ]
    linha_sinal: list[float | None] = [None] * len(linha)
    base = longo - 1
    definida = [v for v in linha[base:] if v is not None]
    if definida:
        sinal_local = ema(definida, sinal, seed=seed)
        for j, v in enumerate(sinal_local):
            linha_sinal[base + j] = v
    histograma: list[float | None] = [
        (li - si) if li is not None and si is not None else None
        for li, si in zip(linha, linha_sinal, strict=True)
    ]
    return linha, linha_sinal, histograma


def bollinger(
    fechamentos: Sequence[float], n: int = BOLLINGER_N, k: float = BOLLINGER_K
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bandas de Bollinger → (central, superior, inferior); desvio POPULACIONAL."""
    central: list[float | None] = [None] * len(fechamentos)
    superior: list[float | None] = [None] * len(fechamentos)
    inferior: list[float | None] = [None] * len(fechamentos)
    for i in range(n - 1, len(fechamentos)):
        janela = fechamentos[i - n + 1 : i + 1]
        media = math.fsum(janela) / n
        desvio = statistics.pstdev(janela, mu=media)  # ddof=0
        central[i] = media
        superior[i] = media + k * desvio
        inferior[i] = media - k * desvio
    return central, superior, inferior


def estocastico(
    maximas: Sequence[float],
    minimas: Sequence[float],
    fechamentos: Sequence[float],
    n: int = ESTOCASTICO_PARAMS[0],
    suav_k: int = ESTOCASTICO_PARAMS[1],
    suav_d: int = ESTOCASTICO_PARAMS[2],
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Estocástico → (%K rápido, %K lento=SMA(suav_k), %D=SMA(suav_d) do lento).

    Amplitude nula (HH==LL) → 50 (centro da escala; quociente indefinido).
    """
    k_rapido: list[float | None] = [None] * len(fechamentos)
    for i in range(n - 1, len(fechamentos)):
        hh = max(maximas[i - n + 1 : i + 1])
        ll = min(minimas[i - n + 1 : i + 1])
        if hh == ll:
            k_rapido[i] = _ESTOCASTICO_NEUTRO
        else:
            k_rapido[i] = 100.0 * (fechamentos[i] - ll) / (hh - ll)
    k_lento = _sma_alinhada(k_rapido, suav_k)
    linha_d = _sma_alinhada(k_lento, suav_d)
    return k_rapido, k_lento, linha_d


def williams_r(
    maximas: Sequence[float],
    minimas: Sequence[float],
    fechamentos: Sequence[float],
    n: int = WILLIAMS_N,
) -> list[float | None]:
    """Williams %R (escala −100..0). Amplitude nula → −50 (centro da escala)."""
    saida: list[float | None] = [None] * len(fechamentos)
    for i in range(n - 1, len(fechamentos)):
        hh = max(maximas[i - n + 1 : i + 1])
        ll = min(minimas[i - n + 1 : i + 1])
        if hh == ll:
            saida[i] = _WILLIAMS_NEUTRO
        else:
            saida[i] = -100.0 * (hh - fechamentos[i]) / (hh - ll)
    return saida


def linha_ad(
    maximas: Sequence[float],
    minimas: Sequence[float],
    fechamentos: Sequence[float],
    volumes: Sequence[float],
) -> list[float]:
    """Linha de Acumulação/Distribuição (acumulada desde a 1ª barra).

    MFM = ((C−L)−(H−C))/(H−L), com MFM=0 quando High==Low (convenção fixa).
    """
    acumulado = 0.0
    saida: list[float] = []
    for h, baixa, c, v in zip(maximas, minimas, fechamentos, volumes, strict=True):
        if h == baixa:
            mfm = 0.0
        else:
            mfm = ((c - baixa) - (h - c)) / (h - baixa)
        acumulado += mfm * v
        saida.append(acumulado)
    return saida


def fibonacci_retracoes(
    maximas: Sequence[float],
    minimas: Sequence[float],
    *,
    janela: int = FIBONACCI_JANELA,
    sobre_fechamentos: bool = False,
) -> RetracaoFibonacci | None:
    """Retrações de Fibonacci sobre a janela dos últimos `janela` pregões.

    Regra documentada (fixa): topo = máxima da janela; fundo = mínima da
    janela (em empate vale a ocorrência mais RECENTE). Se o topo é mais
    recente que o fundo, o último movimento dominante é de ALTA e os níveis
    medem a retração para baixo a partir do topo: nível = topo − p×(topo−fundo).
    Se o fundo é mais recente, o movimento é de BAIXA e os níveis medem a
    recuperação a partir do fundo: nível = fundo + p×(topo−fundo). Empate de
    índice (topo e fundo na mesma barra) conta como alta. Amplitude nula → None.
    """
    altas = list(maximas[-janela:])
    baixas = list(minimas[-janela:])
    if not altas or len(altas) != len(baixas):
        return None
    topo = max(altas)
    fundo = min(baixas)
    if topo == fundo:
        return None
    idx_topo = max(i for i, v in enumerate(altas) if v == topo)
    idx_fundo = max(i for i, v in enumerate(baixas) if v == fundo)
    direcao = "alta" if idx_topo >= idx_fundo else "baixa"
    amplitude = topo - fundo
    if direcao == "alta":
        niveis = tuple((p, topo - p * amplitude) for p in FIBONACCI_NIVEIS)
    else:
        niveis = tuple((p, fundo + p * amplitude) for p in FIBONACCI_NIVEIS)
    return RetracaoFibonacci(
        topo=topo,
        fundo=fundo,
        direcao=direcao,
        janela=len(altas),
        sobre_fechamentos=sobre_fechamentos,
        niveis=niveis,
    )


# ---------------------------------------------------------------------------
# Normalização de entrada (Decimal→float, ordenação, descarte de barra sem C)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Barra:
    data: dt.date
    fechamento: float
    maxima: float | None
    minima: float | None
    volume: float | None


def _f(x: object) -> float | None:
    """Numeric/Decimal/int → float; None permanece None."""
    return None if x is None else float(x)  # type: ignore[arg-type]


def _normalizar(precos: Sequence[PrecoOHLCV]) -> tuple[list[_Barra], int]:
    """Barras ordenadas por data com fechamento presente; devolve (barras, descartadas)."""
    barras: list[_Barra] = []
    descartadas = 0
    for p in precos:
        fechamento = _f(getattr(p, "fechamento", None))
        if fechamento is None:
            descartadas += 1
            continue
        barras.append(
            _Barra(
                data=p.data_pregao,
                fechamento=fechamento,
                maxima=_f(getattr(p, "maxima", None)),
                minima=_f(getattr(p, "minima", None)),
                volume=_f(getattr(p, "volume", None)),
            )
        )
    barras.sort(key=lambda b: b.data)
    return barras, descartadas


# ---------------------------------------------------------------------------
# Séries de gráfico (warm-up + downsampling)
# ---------------------------------------------------------------------------


def _descartar_warmup(valores: list[float | None], corte: int) -> list[float | None]:
    """None nas primeiras `corte` posições (semente de recursão descartada)."""
    return [None if i < corte else v for i, v in enumerate(valores)]


def _downsample(pontos: list, maximo: int = MAX_PONTOS_SERIE) -> list:
    """Reduz para ≤ `maximo` pontos com passo uniforme; o ÚLTIMO ponto permanece."""
    if len(pontos) <= maximo:
        return pontos
    passo = math.ceil(len(pontos) / maximo)
    indices = range(len(pontos) - 1, -1, -passo)
    return [pontos[i] for i in reversed(indices)]


def _serie(nome: str, datas: Sequence[dt.date], valores: Sequence[float | None]) -> Serie:
    pontos = [
        Ponto(d=data.isoformat(), v=v)
        for data, v in zip(datas, valores, strict=True)
        if v is not None
    ]
    return Serie(nome=nome, pontos=tuple(_downsample(pontos)))


def _faixa(
    nome: str,
    datas: Sequence[dt.date],
    superior: Sequence[float | None],
    inferior: Sequence[float | None],
) -> Faixa:
    pontos = [
        PontoFaixa(d=data.isoformat(), sup=s, inf=i)
        for data, s, i in zip(datas, superior, inferior, strict=True)
        if s is not None and i is not None
    ]
    return Faixa(nome=nome, pontos=tuple(_downsample(pontos)))


def _ultimo(valores: Sequence[float | None]) -> float | None:
    for v in reversed(valores):
        if v is not None:
            return v
    return None


def _lacuna_insuficiente(nome: str, tem: int, minimo: int) -> str:
    return f"{nome}: série insuficiente ({tem} pregões; mínimo {minimo}) — indicador omitido"


# ---------------------------------------------------------------------------
# Leituras descritivas (templates determinísticos NEUTROS — gate A5/A7)
# ---------------------------------------------------------------------------


def _leitura_media(nome_curto: str, media: float, fechamento: float) -> str:
    dist = (fechamento / media - 1.0) * 100.0
    if abs(dist) < 0.005:
        posicao = "em linha com a"
    elif dist > 0:
        posicao = "acima da"
    else:
        posicao = "abaixo da"
    return (
        f"Fechamento de {_fmt_brl(fechamento)} {posicao} {nome_curto} "
        f"({_fmt_brl(media)}); distância de {_fmt_sinal(dist, 1)}%."
    )


def _regiao_escala(valor: float, piso: float, teto: float) -> str:
    if valor >= teto:
        return f"região historicamente descrita como sobrecompra (acima de {teto:g})"
    if valor <= piso:
        return f"região historicamente descrita como sobrevenda (abaixo de {piso:g})"
    return "região intermediária da escala"


# ---------------------------------------------------------------------------
# Montagem do bloco (calcular)
# ---------------------------------------------------------------------------


def calcular(precos: Sequence[PrecoOHLCV]) -> IndicadoresTecnicos:
    """Indicadores técnicos + séries de gráfico sobre a série OHLCV do ticker.

    Puro e total: nunca levanta exceção por dado faltante — série vazia ou
    insuficiente vira lacuna rotulada e indicador omitido (nunca NaN).
    """
    barras, descartadas = _normalizar(precos)
    ticker = str(getattr(precos[0], "ticker", "")) if precos else ""
    fonte = FonteRef(
        descricao=_DESCRICAO_FONTE,
        url=None,
        dt_referencia=barras[-1].data if barras else None,
    )
    lacunas: list[str] = []
    if descartadas:
        lacunas.append(f"{descartadas} pregões sem fechamento descartados da série")
    if not barras:
        lacunas.append("série de preços vazia — nenhum indicador calculado")
        return IndicadoresTecnicos(nota=NOTA_TECNICA, fonte=fonte, lacunas=tuple(lacunas))

    datas = [b.data for b in barras]
    fechamentos = [b.fechamento for b in barras]
    n_barras = len(barras)
    fech_atual = fechamentos[-1]

    hlc_ok = all(b.maxima is not None and b.minima is not None for b in barras)
    hlcv_ok = hlc_ok and all(b.volume is not None for b in barras)
    maximas = [b.maxima for b in barras] if hlc_ok else []
    minimas = [b.minima for b in barras] if hlc_ok else []
    volumes = [b.volume for b in barras] if hlcv_ok else []

    indicadores: list[IndicadorTecnico] = []

    # --- SMA (20/50/200) — janela: exata a partir da barra n−1 -------------
    smas: dict[int, list[float | None]] = {}
    for n in SMA_JANELAS:
        nome = f"Média móvel ({n})"
        if n_barras < n:
            lacunas.append(_lacuna_insuficiente(nome, n_barras, n))
            continue
        serie_sma = sma(fechamentos, n)
        valor = _ultimo(serie_sma)
        if valor is None:  # pragma: no cover — invariante: n_barras >= n
            continue
        smas[n] = serie_sma
        indicadores.append(
            IndicadorTecnico(
                nome=nome,
                valor=valor,
                unidade="BRL",
                detalhe=None,
                o_que_mede=(
                    f"Média aritmética dos fechamentos dos últimos {n} pregões — "
                    "suaviza a tendência do preço."
                ),
                leitura=_leitura_media(f"média móvel de {n} pregões", valor, fech_atual),
            )
        )

    # --- EMA (12/26) — recursiva: warm-up de 2n barras descartado ----------
    for n in EMA_JANELAS:
        nome = f"Média móvel exponencial ({n})"
        minimo = WARMUP_FATOR * n + 1
        if n_barras < minimo:
            lacunas.append(_lacuna_insuficiente(nome, n_barras, minimo))
            continue
        serie_ema = _descartar_warmup(ema(fechamentos, n), WARMUP_FATOR * n)
        valor = _ultimo(serie_ema)
        if valor is None:  # pragma: no cover — invariante: n_barras >= 2n+1
            continue
        indicadores.append(
            IndicadorTecnico(
                nome=nome,
                valor=valor,
                unidade="BRL",
                detalhe=None,
                o_que_mede=(
                    f"Média dos fechamentos com peso maior nos pregões recentes "
                    f"(fator 2/({n}+1))."
                ),
                leitura=_leitura_media(
                    f"média móvel exponencial de {n} pregões", valor, fech_atual
                ),
            )
        )

    # --- MACD (12, 26, 9) ---------------------------------------------------
    macd_curto, macd_longo, macd_sinal_n = MACD_PARAMS
    corte_macd = WARMUP_FATOR * macd_longo
    macd_linha: list[float | None] = []
    macd_sinal: list[float | None] = []
    macd_hist: list[float | None] = []
    nome_macd = f"MACD ({macd_curto}, {macd_longo}, {macd_sinal_n})"
    if n_barras < corte_macd + 1:
        lacunas.append(_lacuna_insuficiente(nome_macd, n_barras, corte_macd + 1))
    else:
        bruta = macd(fechamentos, macd_curto, macd_longo, macd_sinal_n)
        macd_linha = _descartar_warmup(bruta[0], corte_macd)
        macd_sinal = _descartar_warmup(bruta[1], corte_macd)
        macd_hist = _descartar_warmup(bruta[2], corte_macd)
        v_linha = _ultimo(macd_linha)
        v_sinal = _ultimo(macd_sinal)
        v_hist = _ultimo(macd_hist)
        if v_linha is None or v_sinal is None or v_hist is None:  # pragma: no cover
            macd_linha, macd_sinal, macd_hist = [], [], []
            lacunas.append(f"{nome_macd}: valor atual indefinido — indicador omitido")
        else:
            if v_hist > 0:
                frase = (
                    f"histograma positivo: média exponencial curta ({macd_curto}) acima "
                    f"da longa ({macd_longo}) no último pregão"
                )
            elif v_hist < 0:
                frase = (
                    f"histograma negativo: média exponencial curta ({macd_curto}) abaixo "
                    f"da longa ({macd_longo}) no último pregão"
                )
            else:
                frase = "histograma nulo: médias exponenciais curta e longa coincidem"
            indicadores.append(
                IndicadorTecnico(
                    nome=nome_macd,
                    valor=v_linha,
                    unidade="indice",
                    detalhe=(
                        f"linha {_fmt_sinal(v_linha)} / sinal {_fmt_sinal(v_sinal)} / "
                        f"histograma {_fmt_sinal(v_hist)}"
                    ),
                    o_que_mede=(
                        f"Diferença entre as médias exponenciais de {macd_curto} e "
                        f"{macd_longo} pregões, com linha de sinal de {macd_sinal_n} — "
                        "descreve a convergência/divergência das médias."
                    ),
                    leitura=(
                        f"Linha MACD em {_fmt_sinal(v_linha)}, linha de sinal em "
                        f"{_fmt_sinal(v_sinal)} e histograma em {_fmt_sinal(v_hist)} "
                        f"— {frase}."
                    ),
                )
            )

    # --- RSI (14) Wilder ------------------------------------------------------
    corte_rsi = WARMUP_FATOR * RSI_N
    rsi_serie: list[float | None] = []
    nome_rsi = f"RSI ({RSI_N})"
    if n_barras < corte_rsi + 1:
        lacunas.append(_lacuna_insuficiente(nome_rsi, n_barras, corte_rsi + 1))
    else:
        rsi_serie = _descartar_warmup(rsi(fechamentos, RSI_N), corte_rsi)
        v_rsi = _ultimo(rsi_serie)
        if v_rsi is None:  # pragma: no cover — invariante: n_barras >= 2n+1
            rsi_serie = []
            lacunas.append(f"{nome_rsi}: valor atual indefinido — indicador omitido")
        else:
            regiao = _regiao_escala(v_rsi, 30.0, 70.0)
            indicadores.append(
                IndicadorTecnico(
                    nome=nome_rsi,
                    valor=v_rsi,
                    unidade="indice",
                    detalhe=None,
                    o_que_mede=(
                        "Velocidade e magnitude das variações recentes do preço em "
                        "escala de 0 a 100 (suavização de Wilder)."
                    ),
                    leitura=f"RSI({RSI_N}) em {_fmt_num(v_rsi, 1)} — {regiao}.",
                )
            )

    # --- Estocástico lento (14, 3, 3) ---------------------------------------
    est_n, est_k, est_d = ESTOCASTICO_PARAMS
    nome_est = f"Estocástico ({est_n}, {est_k}, {est_d})"
    est_lento: list[float | None] = []
    est_linha_d: list[float | None] = []
    minimo_est = est_n + est_k + est_d - 2
    if not hlc_ok:
        lacunas.append(f"{nome_est}: máxima/mínima ausentes na série — indicador omitido")
    elif n_barras < minimo_est:
        lacunas.append(_lacuna_insuficiente(nome_est, n_barras, minimo_est))
    else:
        _, est_lento, est_linha_d = estocastico(maximas, minimas, fechamentos, est_n, est_k, est_d)
        v_k = _ultimo(est_lento)
        v_d = _ultimo(est_linha_d)
        if v_k is None or v_d is None:  # pragma: no cover — invariante: minimo_est
            est_lento, est_linha_d = [], []
            lacunas.append(f"{nome_est}: valor atual indefinido — indicador omitido")
        else:
            regiao = _regiao_escala(v_k, 20.0, 80.0)
            indicadores.append(
                IndicadorTecnico(
                    nome=nome_est,
                    valor=v_k,
                    unidade="indice",
                    detalhe=f"%K {_fmt_num(v_k, 1)} / %D {_fmt_num(v_d, 1)}",
                    o_que_mede=(
                        f"Posição do fechamento dentro da amplitude máxima–mínima dos "
                        f"últimos {est_n} pregões, em escala de 0 a 100 (versão lenta)."
                    ),
                    leitura=(
                        f"Estocástico lento em {_fmt_num(v_k, 1)} "
                        f"(%D em {_fmt_num(v_d, 1)}) — {regiao}."
                    ),
                )
            )

    # --- Bandas de Bollinger (20, 2) -----------------------------------------
    nome_bb = f"Bandas de Bollinger ({BOLLINGER_N}, {BOLLINGER_K:g})"
    bb_central: list[float | None] = []
    bb_sup: list[float | None] = []
    bb_inf: list[float | None] = []
    if n_barras < BOLLINGER_N:
        lacunas.append(_lacuna_insuficiente(nome_bb, n_barras, BOLLINGER_N))
    else:
        bb_central, bb_sup, bb_inf = bollinger(fechamentos, BOLLINGER_N, BOLLINGER_K)
        v_c = _ultimo(bb_central)
        v_s = _ultimo(bb_sup)
        v_i = _ultimo(bb_inf)
        if v_c is None or v_s is None or v_i is None:  # pragma: no cover — invariante
            bb_central, bb_sup, bb_inf = [], [], []
            lacunas.append(f"{nome_bb}: valor atual indefinido — indicador omitido")
        else:
            if v_s > v_i:
                posicao = (fech_atual - v_i) / (v_s - v_i) * 100.0
                largura = (v_s - v_i) / v_c * 100.0 if v_c else 0.0
                leitura_bb = (
                    f"Fechamento de {_fmt_brl(fech_atual)} posicionado a "
                    f"{_fmt_num(posicao, 0)}% da largura entre as bandas (inferior "
                    f"{_fmt_brl(v_i)}, superior {_fmt_brl(v_s)}); largura de "
                    f"{_fmt_num(largura, 1)}% sobre a banda central — medida da "
                    "dispersão recente dos preços."
                )
            else:
                leitura_bb = (
                    f"Bandas colapsadas em {_fmt_brl(v_c)} — dispersão nula dos "
                    f"fechamentos na janela de {BOLLINGER_N} pregões."
                )
            indicadores.append(
                IndicadorTecnico(
                    nome=nome_bb,
                    valor=v_c,
                    unidade="BRL",
                    detalhe=(
                        f"superior {_fmt_brl(v_s)} / central {_fmt_brl(v_c)} / "
                        f"inferior {_fmt_brl(v_i)}"
                    ),
                    o_que_mede=(
                        f"Faixa de ±{BOLLINGER_K:g} desvios-padrão (populacional) em "
                        f"torno da média de {BOLLINGER_N} pregões — mede a dispersão "
                        "recente do preço."
                    ),
                    leitura=leitura_bb,
                )
            )

    # --- Williams %R (14) -----------------------------------------------------
    nome_wr = f"Williams %R ({WILLIAMS_N})"
    wr_serie: list[float | None] = []
    if not hlc_ok:
        lacunas.append(f"{nome_wr}: máxima/mínima ausentes na série — indicador omitido")
    elif n_barras < WILLIAMS_N:
        lacunas.append(_lacuna_insuficiente(nome_wr, n_barras, WILLIAMS_N))
    else:
        wr_serie = williams_r(maximas, minimas, fechamentos, WILLIAMS_N)
        v_wr = _ultimo(wr_serie)
        if v_wr is None:  # pragma: no cover — invariante: n_barras >= n
            wr_serie = []
            lacunas.append(f"{nome_wr}: valor atual indefinido — indicador omitido")
        else:
            if v_wr >= -20.0:
                regiao = "região historicamente descrita como sobrecompra (acima de −20)"
            elif v_wr <= -80.0:
                regiao = "região historicamente descrita como sobrevenda (abaixo de −80)"
            else:
                regiao = "região intermediária da escala"
            indicadores.append(
                IndicadorTecnico(
                    nome=nome_wr,
                    valor=v_wr,
                    unidade="indice",
                    detalhe=None,
                    o_que_mede=(
                        f"Posição do fechamento em relação à máxima dos últimos "
                        f"{WILLIAMS_N} pregões, em escala de −100 a 0."
                    ),
                    leitura=(f"Williams %R({WILLIAMS_N}) em {_fmt_num(v_wr, 1)} — {regiao}."),
                )
            )

    # --- Acumulação/Distribuição ----------------------------------------------
    nome_ad = "Acumulação/Distribuição"
    ad_serie: list[float] = []
    if not hlcv_ok:
        lacunas.append(f"{nome_ad}: máxima/mínima/volume ausentes na série — indicador omitido")
    elif n_barras < 2:
        lacunas.append(_lacuna_insuficiente(nome_ad, n_barras, 2))
    else:
        ad_serie = linha_ad(maximas, minimas, fechamentos, volumes)
        v_ad = ad_serie[-1]
        recuo = min(_AD_JANELA_LEITURA, n_barras - 1)
        delta = v_ad - ad_serie[-1 - recuo]
        if delta > 0:
            direcao = "em elevação"
        elif delta < 0:
            direcao = "em queda"
        else:
            direcao = "estável"
        indicadores.append(
            IndicadorTecnico(
                nome=nome_ad,
                valor=v_ad,
                unidade="indice",
                detalhe=f"variação de {_fmt_sinal(delta, 0)} nos últimos {recuo} pregões",
                o_que_mede=(
                    "Acumulado do volume ponderado pela posição do fechamento dentro "
                    "da amplitude de cada pregão — descreve o fluxo de volume "
                    "associado ao movimento do preço."
                ),
                leitura=(
                    f"Linha de Acumulação/Distribuição em {_fmt_num(v_ad, 0)}, "
                    f"{direcao} nos últimos {recuo} pregões "
                    f"(variação de {_fmt_sinal(delta, 0)})."
                ),
            )
        )

    # --- Retração de Fibonacci (252 pregões) ------------------------------------
    nome_fib = f"Retração de Fibonacci ({FIBONACCI_JANELA} pregões)"
    fib: RetracaoFibonacci | None = None
    if hlc_ok:
        fib = fibonacci_retracoes(maximas, minimas, janela=FIBONACCI_JANELA)
    else:
        fib = fibonacci_retracoes(
            fechamentos, fechamentos, janela=FIBONACCI_JANELA, sobre_fechamentos=True
        )
    if fib is None:
        lacunas.append(f"{nome_fib}: amplitude nula na janela — indicador omitido")
    else:
        niveis_txt = " · ".join(f"{_fmt_num(p * 100, 1)}%: {_fmt_brl(v)}" for p, v in fib.niveis)
        if fib.sobre_fechamentos:
            base_txt = "sobre fechamentos (máx/mín intradiários indisponíveis)"
        else:
            base_txt = "sobre máximas/mínimas intradiárias"
        detalhe_fib = (
            f"{niveis_txt} (topo {_fmt_brl(fib.topo)}, fundo {_fmt_brl(fib.fundo)}, "
            f"janela efetiva de {fib.janela} pregões, {base_txt})"
        )
        indicadores.append(
            IndicadorTecnico(
                nome=nome_fib,
                valor=None,
                unidade="BRL",
                detalhe=detalhe_fib,
                o_que_mede=(
                    "Níveis proporcionais (23,6%–78,6%) da amplitude topo–fundo da "
                    "janela — referências históricas de preço, sem valor preditivo."
                ),
                leitura=(
                    f"Amplitude da janela de {fib.janela} pregões entre "
                    f"{_fmt_brl(fib.fundo)} (fundo) e {_fmt_brl(fib.topo)} (topo), "
                    f"com movimento dominante mais recente de {fib.direcao}; "
                    f"retrações em {niveis_txt}."
                ),
            )
        )

    # --- Gráficos (ordem canônica do contrato §1) -------------------------------
    graficos: list[Grafico] = []

    def _grafico(
        id: str,  # noqa: A002 — nome do campo no contrato do envelope
        tipo: str,
        titulo: str,
        eixo_y: str,
        series: tuple[Serie, ...],
        faixa: Faixa | None = None,
        linhas_ref: tuple[LinhaRef, ...] = (),
    ) -> Grafico:
        return Grafico(
            id=id,
            tipo=tipo,
            titulo=titulo,
            ticker=ticker,
            eixo_y=eixo_y,
            nota=NOTA_GRAFICO,
            fonte=fonte,
            series=series,
            faixa=faixa,
            linhas_ref=linhas_ref,
        )

    series_preco = [_serie("Fechamento", datas, fechamentos)]
    for n in SMA_JANELAS:
        if n in smas:
            series_preco.append(_serie(f"Média móvel ({n})", datas, smas[n]))
    faixa_bb = _faixa("Bandas de Bollinger", datas, bb_sup, bb_inf) if bb_central else None
    linhas_fib: tuple[LinhaRef, ...] = ()
    if fib is not None:
        linhas_fib = tuple(
            LinhaRef(nome=f"Fibonacci {_fmt_num(p * 100, 1)}%", valor=v) for p, v in fib.niveis
        )
    if len(barras) >= 2:
        graficos.append(
            _grafico(
                id="preco_bollinger",
                tipo="linha_faixa" if faixa_bb else "linha",
                titulo=(
                    f"Preço de fechamento e Bandas de Bollinger ({BOLLINGER_N}, "
                    f"{BOLLINGER_K:g})"
                    if faixa_bb
                    else "Preço de fechamento"
                ),
                eixo_y="BRL",
                series=tuple(series_preco),
                faixa=faixa_bb,
                linhas_ref=linhas_fib,
            )
        )
    if macd_linha:
        graficos.append(
            _grafico(
                id="macd",
                tipo="macd",
                titulo=f"MACD ({macd_curto}, {macd_longo}, {macd_sinal_n})",
                eixo_y="indice",
                series=(
                    _serie("MACD", datas, macd_linha),
                    _serie("Sinal", datas, macd_sinal),
                    _serie("Histograma", datas, macd_hist),
                ),
            )
        )
    if rsi_serie:
        graficos.append(
            _grafico(
                id="rsi",
                tipo="oscilador",
                titulo=f"RSI ({RSI_N})",
                eixo_y="indice",
                series=(_serie("RSI", datas, rsi_serie),),
                linhas_ref=(
                    LinhaRef(nome="Sobrecompra (70)", valor=70.0),
                    LinhaRef(nome="Sobrevenda (30)", valor=30.0),
                ),
            )
        )
    if est_lento:
        graficos.append(
            _grafico(
                id="estocastico",
                tipo="oscilador",
                titulo=f"Estocástico lento ({est_n}, {est_k}, {est_d})",
                eixo_y="indice",
                series=(
                    _serie("%K", datas, est_lento),
                    _serie("%D", datas, est_linha_d),
                ),
                linhas_ref=(
                    LinhaRef(nome="Sobrecompra (80)", valor=80.0),
                    LinhaRef(nome="Sobrevenda (20)", valor=20.0),
                ),
            )
        )
    if wr_serie:
        graficos.append(
            _grafico(
                id="williams",
                tipo="oscilador",
                titulo=f"Williams %R ({WILLIAMS_N})",
                eixo_y="indice",
                series=(_serie("%R", datas, wr_serie),),
                linhas_ref=(
                    LinhaRef(nome="Sobrecompra (−20)", valor=-20.0),
                    LinhaRef(nome="Sobrevenda (−80)", valor=-80.0),
                ),
            )
        )
    if ad_serie:
        graficos.append(
            _grafico(
                id="volume_ad",
                tipo="linha",
                titulo="Volume financeiro e linha de Acumulação/Distribuição",
                eixo_y="indice",
                series=(
                    _serie("Volume financeiro", datas, volumes),
                    _serie("Linha A/D", datas, ad_serie),
                ),
            )
        )

    return IndicadoresTecnicos(
        nota=NOTA_TECNICA,
        fonte=fonte,
        indicadores=tuple(indicadores),
        graficos=tuple(graficos),
        lacunas=tuple(lacunas),
    )


# ---------------------------------------------------------------------------
# Serialização para o envelope (contrato v3 §1 e §2)
# ---------------------------------------------------------------------------


def _conv(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _conv(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_conv(v) for v in obj]
    if isinstance(obj, dt.date):
        return obj.isoformat()
    return obj


def tecnica_para_envelope(resultado: IndicadoresTecnicos) -> dict:
    """Bloco `tecnica` do envelope (contrato v3 §2) — sem os gráficos."""
    bruto = dataclasses.asdict(resultado)
    bruto.pop("graficos", None)
    return _conv(bruto)  # type: ignore[return-value]


def graficos_para_envelope(resultado: IndicadoresTecnicos) -> list[dict]:
    """Lista `graficos` do envelope (contrato v3 §1), na ordem canônica."""
    return [_conv(dataclasses.asdict(g)) for g in resultado.graficos]  # type: ignore[misc]
