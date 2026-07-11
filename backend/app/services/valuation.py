"""Valuation determinístico por classe — módulo PURO (plano §2.7 + correções A2/A5/A6).

Regras inegociáveis deste módulo:

- 100% determinístico: nenhuma chamada de rede/LLM/DB. A F3 (integração) coleta os
  insumos das tabelas de fatos (cada um já com sua ``Fonte``) e preenche
  :class:`InsumosValuation`; aqui só se calcula e rotula.
- Todo número que sai carrega premissas COM origem (valor + fonte + rótulo + data).
- O resultado é SEMPRE uma grade de cenários (conservador/base/otimista) com faixa
  entre eles + tabela de sensibilidade — NUNCA um ponto único destacado.
- Inputs insuficientes → modelo/cenário OMITIDO com motivo declarado (abstenção
  rotulada, padrão `derivadas.py`) — nunca 0-fill, nunca exceção em produção.
- Linguagem dos templates é NEUTRA e descritiva (gate A5/A6): sem "justo" solto,
  sem comparação com o preço atual em linguagem de oportunidade.

Modelos v1 (nunca outros):

- ação genérica  → Gordon (se paga dividendos) + múltiplos vs pares (P/L, P/VP);
- banco          → P/VP justificado ``BVPS × (ROE − g)/(Ke − g)`` + múltiplos P/VP
  e P/L vs pares (NUNCA EV/EBITDA para banco);
- energia        → Gordon/DDM + múltiplos + RAP como CONTEXTO (não entra na conta);
- FII            → leitura de mercado (P/VP, DY 12m, diferença vs CDI/Selic), SEM
  modelo de valor intrínseco;
- renda fixa     → ``None`` (marcação/carrego já existem em `tesouro`/derivadas; a
  F3 usa o caminho existente).

Convenção de unidades: TODA taxa (Selic, CDI, IPCA esperado, ROE, ERP, g, Ke) entra
como FRAÇÃO decimal a.a. (0,15 = 15% a.a.). Valor fora de escala → ``ValueError``
imediato (erro de contrato, não de dado).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

AVISO_VALUATION = (
    "Exercício de sensibilidade sob premissas explícitas — " "NÃO é preço-alvo nem recomendação"
)

# Premissa fixa do produto (banda 4%–6% a.a.) — rotulada, NÃO é previsão.
ERP_BANDA: dict[str, float] = {"conservador": 0.06, "base": 0.05, "otimista": 0.04}
ORIGEM_ERP = "premissa fixa do produto — banda 4%–6% a.a."
ROTULO_ERP = "premissa v1, não é previsão"

# Grade fixa de g (crescimento perpétuo nominal) — cada ponto com origem própria.
G_ZERO = 0.0
G_META_INFLACAO = 0.03
ORIGEM_G_ZERO = "grade fixa do produto"
ROTULO_G_ZERO = "crescimento nulo — piso da grade v1, não é previsão"
ORIGEM_G_META = "meta de inflação — CMN/BCB (3,00% a.a., regime de meta contínua)"
ROTULO_G_META = "proxy de crescimento nominal de longo prazo — grade v1, não é previsão"
ROTULO_G_FOCUS = "expectativa de mercado (Focus/BCB) — expectativa, não fato realizado"

ROTULO_RF = "taxa livre de risco local = Selic atual (simplificação v1)"
ROTULO_BETA_APROX = "aproximado, preços não ajustados"
ROTULO_BETA_NEUTRO = "neutro por ausência de estimativa"
ORIGEM_BETA_NEUTRO = "padrão do produto na ausência de estimativa (β = 1,0)"
ORIGEM_KE = "CAPM-lite v1: Ke = Rf + β × ERP"

NOTA_SENSIBILIDADE = (
    "Ke ±1 p.p. × g ±1 p.p. em torno do cenário base; células vazias onde a "
    "combinação é matematicamente indefinida (Ke ≤ g ou numerador não positivo)"
)

# Múltiplos suportados em v1: P/L e P/VP (valor implícito requer só LPA/VPA).
# EV/EBITDA implícito fica FORA (exigiria ponte EV→equity com dívida líquida).
_MIN_PARES = 2
_MIN_CENARIOS = 2  # faixa exige ≥2 cenários — nunca ponto único

# Campos de InsumosValuation que são TAXA em fração decimal a.a. (validação de escala).
_CAMPOS_TAXA = ("selic", "cdi", "treasury10y", "ipca_esperado", "roe", "inflacao_implicita")
_TAXA_MAX_ABS = 1.5  # 150% a.a. — acima disso é quase certamente escala percentual errada


# ---------------------------------------------------------------------------
# Contratos de INSUMO (a F3 preenche; cada valor viaja com sua fonte)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Insumo:
    """Valor com fonte anexa — nenhum número entra no valuation sem origem.

    ``fonte`` é a descrição humana (ex.: 'BCB/SGS 432 — meta Selic');
    ``fonte_id`` é o uuid (como str) da `Fonte` persistida, quando houver.
    """

    valor: float
    fonte: str
    dt_referencia: dt.date | None = None
    fonte_id: str | None = None
    rotulo: str | None = None


@dataclass(frozen=True)
class PeerMultiplo:
    """Múltiplo observado de um par comparável (seleção interpretativa, rotulada)."""

    nome: str
    metrica: str  # 'P/L' | 'P/VP' | 'EV/EBITDA' | ...
    valor: float
    fonte: str
    dt_referencia: dt.date | None = None
    fonte_id: str | None = None


@dataclass(frozen=True)
class InsumosValuation:
    """Insumos explícitos do valuation — todos opcionais; faltou → abstenção rotulada.

    Unidades: valores monetários em BRL; taxas em FRAÇÃO decimal a.a. (0,15 = 15%).
    ``treasury10y`` faz parte do contrato para uso futuro, mas NÃO entra no Ke v1
    (Rf = Selic atual, decisão documentada no plano §2.7).
    """

    lucro_liquido_12m: Insumo | None = None  # BRL (12m)
    patrimonio_liquido: Insumo | None = None  # BRL
    num_acoes: Insumo | None = None  # unidades
    dividendos_12m: Insumo | None = None  # BRL (total 12m)
    dividendo_por_acao_12m: Insumo | None = None  # BRL/ação (12m)
    preco_atual: Insumo | None = None  # BRL — COTAHIST, NÃO ajustado por proventos
    selic: Insumo | None = None  # fração a.a.
    cdi: Insumo | None = None  # fração a.a.
    treasury10y: Insumo | None = None  # fração a.a. (não usado no Ke v1)
    ipca_esperado: Insumo | None = None  # fração a.a. (Focus)
    beta_aprox: Insumo | None = None  # adimensional ('aproximado, preços não ajustados')
    roe: Insumo | None = None  # fração (RAZAO)
    bvps: Insumo | None = None  # BRL/ação (valor patrimonial por ação)
    vp_cota: Insumo | None = None  # BRL/cota (FII, informe CVM)
    proventos_12m_por_cota: Insumo | None = None  # BRL/cota (FII, 12m)
    rap: Insumo | None = None  # BRL (energia — contexto, nunca insumo do DDM)
    inflacao_implicita: Insumo | None = None  # fração a.a. (RF, ANBIMA)
    peers_multiplos: tuple[PeerMultiplo, ...] = ()


# ---------------------------------------------------------------------------
# Contratos de SAÍDA
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Premissa:
    """Premissa rotulada: valor + origem (fonte) + rótulo obrigatório + data."""

    nome: str
    valor: float
    origem: str
    rotulo: str
    dt_referencia: dt.date | None = None
    unidade: str | None = None  # 'FRACAO_AA' | 'BRL_POR_ACAO' | 'ADIMENSIONAL' | ...


@dataclass(frozen=True)
class Cenario:
    """Um ponto da grade (combinação documentada de Ke × g) com TODAS as premissas."""

    nome: str  # 'conservador' | 'base' | 'otimista'
    valor: float  # BRL/ação (resultado do modelo nesta combinação)
    premissas: tuple[Premissa, ...]


@dataclass(frozen=True)
class Sensibilidade:
    """Tabela valor(Ke, g); célula ``None`` = combinação matematicamente indefinida."""

    eixo_ke: tuple[float, ...]
    eixo_g: tuple[float, ...]
    valores: tuple[tuple[float | None, ...], ...]  # linhas = Ke, colunas = g
    nota: str = NOTA_SENSIBILIDADE


@dataclass(frozen=True)
class ModeloResultado:
    """Resultado (ou abstenção rotulada) de UM modelo da grade v1."""

    modelo: str  # 'gordon' | 'pvp_justificado' | 'multiplos_pl' | ...
    descricao: str
    cenarios: tuple[Cenario, ...] = ()
    faixa: tuple[float, float] | None = None  # (mín, máx) entre cenários — nunca ponto
    sensibilidade: Sensibilidade | None = None
    premissas: tuple[Premissa, ...] = ()  # premissas/fatos comuns aos cenários
    observacoes: tuple[str, ...] = ()  # leituras descritivas neutras, com fontes
    omissoes: tuple[str, ...] = ()  # cenários/componentes omitidos com motivo
    omitido: bool = False
    motivo_omissao: str | None = None


@dataclass(frozen=True)
class Valuation:
    """Bloco de valuation da tese — grade de cenários rotulada, nunca preço-alvo."""

    classe: str
    modelos: tuple[ModeloResultado, ...]
    contexto: tuple[str, ...] = ()  # âncoras descritivas (ex.: RAP) e notas de escopo
    aviso: str = field(default=AVISO_VALUATION)


# ---------------------------------------------------------------------------
# Formatação pt-BR (para motivos/observações — texto neutro, com fontes)
# ---------------------------------------------------------------------------


def _fmt_num(x: float, casas: int = 2) -> str:
    """Número decimal em pt-BR (vírgula), sem separador de milhar."""
    return f"{x:.{casas}f}".replace(".", ",")


def _fmt_pct(x: float, casas: int = 2) -> str:
    """Fração decimal → percentual pt-BR (0,096 → '9,60%')."""
    return _fmt_num(x * 100, casas) + "%"


def _fmt_brl(x: float) -> str:
    return "R$ " + _fmt_num(x)


def _fmt_data(d: dt.date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "data não informada"


def _fonte_curta(i: Insumo) -> str:
    return f"{i.fonte} ({_fmt_data(i.dt_referencia)})"


# ---------------------------------------------------------------------------
# Validação de contrato (escala das taxas) — erro de programação, não de dado
# ---------------------------------------------------------------------------


def _validar_taxas(insumos: InsumosValuation) -> None:
    """Taxas devem vir em fração decimal (0,15 = 15% a.a.); fora de escala → ValueError."""
    for campo in _CAMPOS_TAXA:
        insumo: Insumo | None = getattr(insumos, campo)
        if insumo is not None and abs(insumo.valor) > _TAXA_MAX_ABS:
            raise ValueError(
                f"insumo '{campo}'={insumo.valor} fora de escala: taxas entram como "
                f"fração decimal a.a. (0,15 = 15%), não em pontos percentuais"
            )


# ---------------------------------------------------------------------------
# Premissas (cada uma com valor + origem + rótulo)
# ---------------------------------------------------------------------------


def _premissa_rf(selic: Insumo) -> Premissa:
    return Premissa(
        nome="Rf",
        valor=selic.valor,
        origem=selic.fonte,
        rotulo=ROTULO_RF,
        dt_referencia=selic.dt_referencia,
        unidade="FRACAO_AA",
    )


def _premissa_erp(cenario: str) -> Premissa:
    return Premissa(
        nome="ERP",
        valor=ERP_BANDA[cenario],
        origem=ORIGEM_ERP,
        rotulo=ROTULO_ERP,
        unidade="FRACAO_AA",
    )


def _premissa_beta(beta: Insumo | None) -> Premissa:
    if beta is None:
        return Premissa(
            nome="beta",
            valor=1.0,
            origem=ORIGEM_BETA_NEUTRO,
            rotulo=ROTULO_BETA_NEUTRO,
            unidade="ADIMENSIONAL",
        )
    return Premissa(
        nome="beta",
        valor=beta.valor,
        origem=beta.fonte,
        rotulo=beta.rotulo or ROTULO_BETA_APROX,
        dt_referencia=beta.dt_referencia,
        unidade="ADIMENSIONAL",
    )


def _premissas_g(insumos: InsumosValuation) -> dict[str, Premissa]:
    """Grade fixa de g por cenário: 0% / meta 3% / IPCA esperado (Focus, se houver)."""
    g_zero = Premissa(
        nome="g", valor=G_ZERO, origem=ORIGEM_G_ZERO, rotulo=ROTULO_G_ZERO, unidade="FRACAO_AA"
    )
    g_meta = Premissa(
        nome="g",
        valor=G_META_INFLACAO,
        origem=ORIGEM_G_META,
        rotulo=ROTULO_G_META,
        unidade="FRACAO_AA",
    )
    ipca = insumos.ipca_esperado
    if ipca is not None:
        g_otimista = Premissa(
            nome="g",
            valor=ipca.valor,
            origem=ipca.fonte,
            rotulo=ROTULO_G_FOCUS,
            dt_referencia=ipca.dt_referencia,
            unidade="FRACAO_AA",
        )
    else:
        g_otimista = dataclasses.replace(
            g_meta,
            rotulo=ROTULO_G_META + " — IPCA esperado (Focus) indisponível; usada a meta",
        )
    return {"conservador": g_zero, "base": g_meta, "otimista": g_otimista}


def _grade_ke_g(
    insumos: InsumosValuation,
) -> dict[str, tuple[tuple[Premissa, ...], float, float]]:
    """Combinações documentadas de Ke × g por cenário.

    Devolve {cenario: (premissas de Ke+g, ke, g)}. Pré-condição: selic presente.
    """
    selic = insumos.selic
    if selic is None:  # pragma: no cover — guardado pelos chamadores
        raise ValueError("grade Ke×g exige Selic")
    rf = _premissa_rf(selic)
    beta = _premissa_beta(insumos.beta_aprox)
    gs = _premissas_g(insumos)
    grade: dict[str, tuple[tuple[Premissa, ...], float, float]] = {}
    for cenario in ("conservador", "base", "otimista"):
        erp = _premissa_erp(cenario)
        ke_valor = rf.valor + beta.valor * erp.valor
        ke = Premissa(
            nome="Ke",
            valor=ke_valor,
            origem=ORIGEM_KE,
            rotulo=f"cenário {cenario}: ERP {_fmt_pct(erp.valor)}",
            unidade="FRACAO_AA",
        )
        g = gs[cenario]
        grade[cenario] = ((rf, erp, beta, ke, g), ke_valor, g.valor)
    return grade


# ---------------------------------------------------------------------------
# Blocos comuns: cenários + faixa + sensibilidade
# ---------------------------------------------------------------------------


def _montar_cenarios(
    grade: dict[str, tuple[tuple[Premissa, ...], float, float]],
    valor_fn: Callable[[float, float], tuple[float | None, str | None]],
    premissas_extra_fn: Callable[[float], tuple[Premissa, ...]],
) -> tuple[tuple[Cenario, ...], tuple[str, ...]]:
    """Aplica ``valor_fn(ke, g)`` à grade; omissões viram motivo declarado."""
    cenarios: list[Cenario] = []
    omissoes: list[str] = []
    for nome, (premissas, ke, g) in grade.items():
        valor, motivo = valor_fn(ke, g)
        if valor is None:
            omissoes.append(f"cenário {nome} não computado — {motivo}")
            continue
        todas = premissas + premissas_extra_fn(g)
        cenarios.append(Cenario(nome=nome, valor=valor, premissas=todas))
    return tuple(cenarios), tuple(omissoes)


def _faixa(cenarios: tuple[Cenario, ...]) -> tuple[float, float]:
    valores = [c.valor for c in cenarios]
    return (min(valores), max(valores))


def _sensibilidade(
    ke_base: float,
    g_base: float,
    valor_fn: Callable[[float, float], tuple[float | None, str | None]],
) -> Sensibilidade:
    """Grade Ke ±1 p.p. × g ±1 p.p. em torno do cenário base; indefinido → None."""
    eixo_ke = (ke_base - 0.01, ke_base, ke_base + 0.01)
    eixo_g = (g_base - 0.01, g_base, g_base + 0.01)
    linhas = tuple(tuple(valor_fn(ke, g)[0] for g in eixo_g) for ke in eixo_ke)
    return Sensibilidade(eixo_ke=eixo_ke, eixo_g=eixo_g, valores=linhas)


def _modelo_de_grade(
    modelo: str,
    descricao: str,
    insumos: InsumosValuation,
    valor_fn: Callable[[float, float], tuple[float | None, str | None]],
    premissas_comuns: tuple[Premissa, ...],
    premissas_extra_fn: Callable[[float], tuple[Premissa, ...]],
) -> ModeloResultado:
    """Esqueleto comum dos modelos com grade Ke×g (Gordon e P/VP justificado)."""
    grade = _grade_ke_g(insumos)
    cenarios, omissoes = _montar_cenarios(grade, valor_fn, premissas_extra_fn)
    if len(cenarios) < _MIN_CENARIOS:
        motivo = (
            f"{modelo} não computado: menos de {_MIN_CENARIOS} cenários computáveis "
            f"(motivos: {'; '.join(omissoes) or 'nenhum cenário válido'})"
        )
        return ModeloResultado(
            modelo=modelo,
            descricao=descricao,
            omissoes=omissoes,
            omitido=True,
            motivo_omissao=motivo,
        )
    _, ke_base, g_base = grade["base"]
    return ModeloResultado(
        modelo=modelo,
        descricao=descricao,
        cenarios=cenarios,
        faixa=_faixa(cenarios),
        sensibilidade=_sensibilidade(ke_base, g_base, valor_fn),
        premissas=premissas_comuns,
        omissoes=omissoes,
    )


# ---------------------------------------------------------------------------
# Modelo: Gordon (ação genérica / energia)
# ---------------------------------------------------------------------------

_DESC_GORDON = (
    "Modelo de Gordon (dividendos em perpetuidade): V = D1/(Ke − g), com "
    "D1 = dividendos por ação dos últimos 12m × (1 + g)"
)


def _dividendo_por_acao(insumos: InsumosValuation) -> tuple[Insumo | None, str | None]:
    """Dividendo/ação 12m: direto do insumo ou total ÷ nº de ações. Faltou → motivo."""
    if insumos.dividendo_por_acao_12m is not None:
        return insumos.dividendo_por_acao_12m, None
    total, n = insumos.dividendos_12m, insumos.num_acoes
    if total is None:
        return None, "dividendos dos últimos 12 meses não disponíveis (dado não encontrado)"
    if n is None or n.valor <= 0:
        return None, "número de ações indisponível ou inválido para calcular dividendo/ação"
    derivado = Insumo(
        valor=total.valor / n.valor,
        fonte=f"{total.fonte} ÷ {n.fonte}",
        dt_referencia=total.dt_referencia,
        rotulo="dividendo por ação derivado (total 12m ÷ nº de ações)",
    )
    return derivado, None


def _modelo_gordon(insumos: InsumosValuation) -> ModeloResultado:
    """Gordon com grade Ke×g. Sem dividendos ou sem Selic → omitido com motivo."""
    if insumos.selic is None:
        return ModeloResultado(
            modelo="gordon",
            descricao=_DESC_GORDON,
            omitido=True,
            motivo_omissao=(
                "Gordon não computado: Ke indisponível — Selic atual não consta dos "
                "insumos (dado não encontrado)"
            ),
        )
    d0, motivo = _dividendo_por_acao(insumos)
    if d0 is None:
        return ModeloResultado(
            modelo="gordon",
            descricao=_DESC_GORDON,
            omitido=True,
            motivo_omissao=f"Gordon não computado: {motivo}",
        )
    if d0.valor <= 0:
        return ModeloResultado(
            modelo="gordon",
            descricao=_DESC_GORDON,
            omitido=True,
            motivo_omissao=(
                "Gordon não computado: empresa não pagou dividendos nos últimos 12 meses"
            ),
        )

    def valor_fn(ke: float, g: float) -> tuple[float | None, str | None]:
        if ke <= g:
            return None, f"Ke ({_fmt_pct(ke)}) ≤ g ({_fmt_pct(g)}): Gordon indefinido"
        return d0.valor * (1 + g) / (ke - g), None

    premissa_d0 = Premissa(
        nome="D0 (dividendos/ação 12m)",
        valor=d0.valor,
        origem=d0.fonte,
        rotulo=d0.rotulo or "proventos dos últimos 12 meses; preços/proventos não ajustados",
        dt_referencia=d0.dt_referencia,
        unidade="BRL_POR_ACAO",
    )

    def premissas_extra(g: float) -> tuple[Premissa, ...]:
        return (
            premissa_d0,
            Premissa(
                nome="D1",
                valor=d0.valor * (1 + g),
                origem="D1 = D0 × (1 + g)",
                rotulo="derivado das premissas do cenário",
                unidade="BRL_POR_ACAO",
            ),
        )

    return _modelo_de_grade(
        "gordon", _DESC_GORDON, insumos, valor_fn, (premissa_d0,), premissas_extra
    )


# ---------------------------------------------------------------------------
# Modelo: P/VP justificado (banco)
# ---------------------------------------------------------------------------

_DESC_PVP_JUST = (
    "P/VP justificado (banco): valor = BVPS × (ROE − g)/(Ke − g) — múltiplo "
    "derivado de rentabilidade em perpetuidade, sob as premissas do cenário"
)


def _modelo_pvp_justificado(insumos: InsumosValuation) -> ModeloResultado:
    """P/VP justificado com grade Ke×g. Sem BVPS/ROE/Selic → omitido com motivo."""
    faltas: list[str] = []
    if insumos.selic is None:
        faltas.append("Selic atual (Ke)")
    if insumos.bvps is None:
        faltas.append("BVPS (valor patrimonial por ação)")
    if insumos.roe is None:
        faltas.append("ROE")
    if faltas:
        return ModeloResultado(
            modelo="pvp_justificado",
            descricao=_DESC_PVP_JUST,
            omitido=True,
            motivo_omissao=(
                "P/VP justificado não computado: insumos ausentes — "
                + "; ".join(faltas)
                + " (dado não encontrado)"
            ),
        )
    bvps, roe = insumos.bvps, insumos.roe

    def valor_fn(ke: float, g: float) -> tuple[float | None, str | None]:
        if ke <= g:
            return None, f"Ke ({_fmt_pct(ke)}) ≤ g ({_fmt_pct(g)}): denominador não positivo"
        if roe.valor <= g:
            return None, (
                f"ROE ({_fmt_pct(roe.valor)}) ≤ g ({_fmt_pct(g)}): numerador não positivo — "
                "P/VP justificado indefinido nesta combinação"
            )
        return bvps.valor * (roe.valor - g) / (ke - g), None

    premissas_comuns = (
        Premissa(
            nome="BVPS",
            valor=bvps.valor,
            origem=bvps.fonte,
            rotulo=bvps.rotulo or "valor patrimonial por ação (DFP)",
            dt_referencia=bvps.dt_referencia,
            unidade="BRL_POR_ACAO",
        ),
        Premissa(
            nome="ROE",
            valor=roe.valor,
            origem=roe.fonte,
            rotulo=roe.rotulo or "lucro líquido / patrimônio líquido (RAZAO)",
            dt_referencia=roe.dt_referencia,
            unidade="FRACAO_AA",
        ),
    )

    def premissas_extra(_g: float) -> tuple[Premissa, ...]:
        return premissas_comuns

    return _modelo_de_grade(
        "pvp_justificado", _DESC_PVP_JUST, insumos, valor_fn, premissas_comuns, premissas_extra
    )


# ---------------------------------------------------------------------------
# Modelo: múltiplos vs pares (P/L e P/VP)
# ---------------------------------------------------------------------------


def _base_por_acao(insumos: InsumosValuation, metrica: str) -> tuple[float | None, str, str]:
    """Base por ação da métrica: (valor, descrição da base, motivo se ausente)."""
    n = insumos.num_acoes
    if metrica == "P/L":
        lucro = insumos.lucro_liquido_12m
        if lucro is None or n is None or n.valor <= 0:
            return None, "", "lucro 12m e/ou nº de ações indisponíveis (dado não encontrado)"
        if lucro.valor <= 0:
            return None, "", "lucro dos últimos 12m não positivo — P/L de pares inaplicável"
        return lucro.valor / n.valor, f"LPA ({_fonte_curta(lucro)})", ""
    pl = insumos.patrimonio_liquido
    if pl is None or n is None or n.valor <= 0:
        return None, "", "patrimônio líquido e/ou nº de ações indisponíveis (dado não encontrado)"
    if pl.valor <= 0:
        return None, "", "patrimônio líquido não positivo — P/VP de pares inaplicável"
    return pl.valor / n.valor, f"VPA ({_fonte_curta(pl)})", ""


def _modelo_multiplos(insumos: InsumosValuation, metrica: str) -> ModeloResultado:
    """Faixa implícita pela dispersão (mín–máx) do múltiplo dos pares. ≥2 pares."""
    nome_modelo = "multiplos_pl" if metrica == "P/L" else "multiplos_pvp"
    descricao = (
        f"Múltiplos vs pares ({metrica}): faixa implícita aplicando mín–máx do "
        f"múltiplo dos pares à base por ação do emissor — exercício comparativo; "
        f"pares são seleção interpretativa, não par oficial"
    )
    pares = [p for p in insumos.peers_multiplos if p.metrica == metrica and p.valor > 0]
    if len(pares) < _MIN_PARES:
        return ModeloResultado(
            modelo=nome_modelo,
            descricao=descricao,
            omitido=True,
            motivo_omissao=(
                f"múltiplos {metrica} não computados: menos de {_MIN_PARES} pares com a "
                f"métrica disponível ({len(pares)} encontrado(s))"
            ),
        )
    base, base_desc, motivo = _base_por_acao(insumos, metrica)
    if base is None:
        return ModeloResultado(
            modelo=nome_modelo,
            descricao=descricao,
            omitido=True,
            motivo_omissao=f"múltiplos {metrica} não computados: {motivo}",
        )
    valores = sorted(p.valor for p in pares)
    mediana = statistics.median(valores)
    faixa = (valores[0] * base, valores[-1] * base)
    premissas = tuple(
        Premissa(
            nome=f"{metrica} {p.nome}",
            valor=p.valor,
            origem=p.fonte,
            rotulo="múltiplo observado de par comparável (seleção interpretativa)",
            dt_referencia=p.dt_referencia,
            unidade="RAZAO",
        )
        for p in pares
    )
    obs = (
        f"{metrica} dos pares (n={len(pares)}): mín {_fmt_num(valores[0])}, "
        f"mediana {_fmt_num(mediana)}, máx {_fmt_num(valores[-1])}; aplicado a "
        f"{base_desc} de {_fmt_brl(base)}, resulta na faixa {_fmt_brl(faixa[0])} a "
        f"{_fmt_brl(faixa[1])} por ação — exercício comparativo sob os múltiplos "
        f"observados, não é estimativa própria de valor"
    )
    return ModeloResultado(
        modelo=nome_modelo,
        descricao=descricao,
        faixa=faixa,
        premissas=premissas,
        observacoes=(obs,),
    )


# ---------------------------------------------------------------------------
# Modelo: leitura de mercado (FII) — SEM valor intrínseco
# ---------------------------------------------------------------------------

_DESC_FII = (
    "Leitura de mercado de FII: P/VP a mercado, DY 12m a mercado e diferença vs "
    "taxa de referência — descrição de preços observados, sem modelo de valor intrínseco"
)


def _fii_pvp(insumos: InsumosValuation) -> tuple[str | None, str | None]:
    preco, vp = insumos.preco_atual, insumos.vp_cota
    if preco is None or vp is None:
        return None, "P/VP a mercado omitido: preço e/ou VP por cota indisponíveis"
    if preco.valor <= 0 or vp.valor <= 0:
        return None, "P/VP a mercado omitido: preço/VP por cota não positivos"
    razao = preco.valor / vp.valor
    return (
        f"P/VP a mercado: {_fmt_num(razao)} — fechamento de {_fmt_brl(preco.valor)} "
        f"({_fonte_curta(preco)}; preço não ajustado por proventos) ÷ VP por cota de "
        f"{_fmt_brl(vp.valor)} ({_fonte_curta(vp)}); leitura descritiva"
    ), None


def _fii_dy(insumos: InsumosValuation) -> tuple[float | None, str | None, str | None]:
    preco, prov = insumos.preco_atual, insumos.proventos_12m_por_cota
    if preco is None or prov is None:
        return None, None, "DY a mercado 12m omitido: preço e/ou proventos 12m indisponíveis"
    if preco.valor <= 0:
        return None, None, "DY a mercado 12m omitido: preço não positivo"
    dy = prov.valor / preco.valor
    texto = (
        f"DY a mercado 12m: {_fmt_pct(dy)} — metodologia: soma dos rendimentos por cota "
        f"dos últimos 12 meses ({_fmt_brl(prov.valor)}, {_fonte_curta(prov)}) ÷ fechamento "
        f"mais recente ({_fmt_brl(preco.valor)}, {_fonte_curta(preco)}; não ajustado)"
    )
    return dy, texto, None


def _fii_spread(dy: float, insumos: InsumosValuation) -> tuple[str | None, str | None]:
    ref = insumos.cdi if insumos.cdi is not None else insumos.selic
    nome_ref = "CDI" if insumos.cdi is not None else "Selic"
    if ref is None:
        return None, "diferença DY vs CDI/Selic omitida: nenhuma taxa de referência disponível"
    spread_pp = (dy - ref.valor) * 100
    return (
        f"Diferença entre DY a mercado 12m ({_fmt_pct(dy)}) e {nome_ref} "
        f"({_fmt_pct(ref.valor)}, {_fonte_curta(ref)}): {_fmt_num(spread_pp)} p.p. — "
        f"comparação descritiva; os dois rendimentos têm naturezas, riscos e "
        f"tributações distintos"
    ), None


def _modelo_fii(insumos: InsumosValuation) -> ModeloResultado:
    """Leitura de mercado do FII; cada componente ausente vira omissão declarada."""
    observacoes: list[str] = []
    omissoes: list[str] = []
    pvp_texto, pvp_motivo = _fii_pvp(insumos)
    if pvp_texto:
        observacoes.append(pvp_texto)
    elif pvp_motivo:
        omissoes.append(pvp_motivo)
    dy, dy_texto, dy_motivo = _fii_dy(insumos)
    if dy_texto:
        observacoes.append(dy_texto)
    elif dy_motivo:
        omissoes.append(dy_motivo)
    if dy is not None:
        spread_texto, spread_motivo = _fii_spread(dy, insumos)
        if spread_texto:
            observacoes.append(spread_texto)
        elif spread_motivo:
            omissoes.append(spread_motivo)
    if not observacoes:
        return ModeloResultado(
            modelo="leitura_mercado_fii",
            descricao=_DESC_FII,
            omissoes=tuple(omissoes),
            omitido=True,
            motivo_omissao=(
                "leitura de mercado não computada: nenhum componente disponível "
                f"(motivos: {'; '.join(omissoes)})"
            ),
        )
    return ModeloResultado(
        modelo="leitura_mercado_fii",
        descricao=_DESC_FII,
        observacoes=tuple(observacoes),
        omissoes=tuple(omissoes),
    )


# ---------------------------------------------------------------------------
# Contexto (energia: RAP como âncora descritiva — nunca insumo do DDM)
# ---------------------------------------------------------------------------


def _contexto_energia(insumos: InsumosValuation) -> tuple[str, ...]:
    rap = insumos.rap
    if rap is None:
        return (
            "RAP não disponível para este emissor — contexto regulatório omitido "
            "(dado não encontrado)",
        )
    rotulo = f"; {rap.rotulo}" if rap.rotulo else ""
    return (
        f"RAP (Receita Anual Permitida): {_fmt_brl(rap.valor)} ({_fonte_curta(rap)}"
        f"{rotulo}) — âncora de contexto da receita regulada de transmissão; NÃO entra "
        f"no cálculo dos cenários. Contratos de transmissão têm reajuste atrelado a "
        f"índice de inflação definido em contrato",
    )


_NOTA_BANCO_EV = (
    "Múltiplos EV/EBITDA de pares foram desconsiderados: EV/EBITDA não se aplica a "
    "bancos (o resultado financeiro é operacional; a conta 3.05 não equivale a EBIT)"
)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def _e_setor_energia(setor: str | None) -> bool:
    """Detecção simples por substring ('Energia Elétrica', 'Transmissão'...)."""
    s = (setor or "").lower()
    return "energ" in s or "transmiss" in s or "eletric" in s or "elétric" in s


def avaliar(
    classe: str | None,
    plano_contas: str | None,
    setor: str | None,
    insumos: InsumosValuation,
) -> Valuation | None:
    """Valuation determinístico por classe — cenários rotulados, nunca preço-alvo.

    - ``renda_fixa`` → ``None`` (marcação/carrego já existem no caminho de RF);
    - classe desconhecida → ``None`` (a F3 decide);
    - insumos insuficientes → modelos omitidos com motivo declarado (nunca exceção).

    Taxas nos insumos em fração decimal a.a. (0,15 = 15%) — fora de escala →
    ``ValueError`` (erro de contrato do chamador, não de dado).
    """
    _validar_taxas(insumos)
    classe_norm = (classe or "acao").strip().lower()
    if classe_norm == "fii":
        return Valuation(classe="fii", modelos=(_modelo_fii(insumos),))
    if classe_norm != "acao":
        return None

    plano = (plano_contas or "").strip().lower()
    if plano == "banco":
        modelos = (
            _modelo_pvp_justificado(insumos),
            _modelo_multiplos(insumos, "P/L"),
            _modelo_multiplos(insumos, "P/VP"),
        )
        contexto: tuple[str, ...] = ()
        if any(p.metrica.upper().startswith("EV/EBITDA") for p in insumos.peers_multiplos):
            contexto = (_NOTA_BANCO_EV,)
        return Valuation(classe="acao", modelos=modelos, contexto=contexto)

    modelos = (
        _modelo_gordon(insumos),
        _modelo_multiplos(insumos, "P/L"),
        _modelo_multiplos(insumos, "P/VP"),
    )
    contexto = _contexto_energia(insumos) if _e_setor_energia(setor) else ()
    return Valuation(classe="acao", modelos=modelos, contexto=contexto)


def valuation_para_envelope(valuation: Valuation) -> dict:
    """Serializa o Valuation para o envelope da tese (datas → ISO, tuplas → listas)."""

    def _conv(obj: object) -> object:
        if isinstance(obj, dict):
            return {k: _conv(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_conv(v) for v in obj]
        if isinstance(obj, dt.date):
            return obj.isoformat()
        return obj

    return _conv(dataclasses.asdict(valuation))  # type: ignore[return-value]
