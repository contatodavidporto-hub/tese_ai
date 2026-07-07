"""Motor de correlação cross-dimensão (D5) — grafo causal AUDITÁVEL.

O diferencial da tese: liga pontos de dimensões diferentes (macro, commodity, pares
globais, fundamento) num raciocínio causal legível — mas com travas anti-alucinação
rígidas (achado A4 do red-team):

- Cada `Elo` exige FONTE nas DUAS pontas; sem isso é descartado (validada=False).
- `metodo='co_movimento_pearson'` é CORRELAÇÃO, NUNCA causalidade: não pode afirmar
  `ligacao_causal`, exige `hedge` explícito e `n_amostras >= MIN_N` (senão abstém).
- `metodo='interpretacao_hedge'`: a ligação causal é condicional e SEMPRE com hedge.
- `n_amostras`/`periodo` registrados para o coeficiente ser auditável.

`montar_grafo` é puro (recebe um contexto já coletado do banco) e testável offline.
`elos_para_llm` serializa cada elo com as duas fontes/datas para o motor de tese.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Elo as EloModel
from app.models.models import Empresa, Fundamento, MacroSerie, Par, ParFundamento
from app.services import sec

MIN_N = 24  # mínimo de observações para um co-movimento não ser espúrio

METODO_CO_MOVIMENTO = "co_movimento_pearson"
METODO_INTERPRETACAO = "interpretacao_hedge"

_HEDGE_CO_MOVIMENTO = "co-movimento histórico; correlação não implica causalidade"


@dataclass
class Elo:
    dimensao: str
    origem_label: str
    origem_fonte_id: object | None
    destino_label: str
    destino_fonte_id: object | None
    metodo: str
    hedge: str | None = None
    ligacao_causal: str | None = None
    forca_ligacao: float | None = None
    n_amostras: int | None = None
    periodo: str | None = None
    validada: bool = field(default=False)


# ---------------------------------------------------------------------------
# Estatística pura
# ---------------------------------------------------------------------------
def correlacao_pearson(pontos: list[tuple[float, float]]) -> tuple[float, int] | None:
    """r de Pearson + n. None se n<2 ou variância nula. r sempre em [-1, 1]."""
    n = len(pontos)
    if n < 2:
        return None
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    r = sxy / (sxx**0.5 * syy**0.5)
    return max(-1.0, min(1.0, r)), n


def alinhar_series(
    serie_a: list[tuple[dt.date, float]], serie_b: list[tuple[dt.date, float]]
) -> list[tuple[float, float]]:
    """Pares (a, b) nas datas em comum às duas séries."""
    mapa_b = {d: v for d, v in serie_b}
    return [(va, mapa_b[da]) for da, va in serie_a if da in mapa_b]


# ---------------------------------------------------------------------------
# Validação (trava A4)
# ---------------------------------------------------------------------------
def validar_elo(elo: Elo) -> bool:
    """Regras inegociáveis do grafo (achado A4). Marca `elo.validada`."""
    ok = True
    if elo.origem_fonte_id is None or elo.destino_fonte_id is None:
        ok = False  # fonte ausente numa das pontas
    elif elo.metodo == METODO_CO_MOVIMENTO:
        # Pearson nunca é causal: não pode afirmar causa; precisa hedge; n suficiente.
        if elo.ligacao_causal:
            ok = False
        elif not elo.hedge:
            ok = False
        elif (elo.n_amostras or 0) < MIN_N:
            ok = False
    else:  # interpretacao: ligação causal só com hedge
        if not elo.hedge:
            ok = False
    # Reforço: qualquer elo fraco (força<0.7) sem hedge é inválido.
    if elo.forca_ligacao is not None and elo.forca_ligacao < 0.7 and not elo.hedge:
        ok = False
    elo.validada = ok
    return ok


# ---------------------------------------------------------------------------
# Construção de elos
# ---------------------------------------------------------------------------
def elo_co_movimento(
    dimensao: str,
    origem: tuple[str, object | None],
    destino: tuple[str, object | None],
    serie_a: list[tuple[dt.date, float]],
    serie_b: list[tuple[dt.date, float]],
) -> Elo | None:
    """Elo de co-movimento (Pearson). Abstém se n<MIN_N ou variância nula."""
    res = correlacao_pearson(alinhar_series(serie_a, serie_b))
    if res is None or res[1] < MIN_N:
        return None
    r, n = res
    datas = sorted(d for d, _ in serie_a if d in {db for db, _ in serie_b})
    periodo = f"{datas[0]}..{datas[-1]}" if datas else None
    elo = Elo(
        dimensao=dimensao,
        origem_label=origem[0],
        origem_fonte_id=origem[1],
        destino_label=destino[0],
        destino_fonte_id=destino[1],
        metodo=METODO_CO_MOVIMENTO,
        hedge=_HEDGE_CO_MOVIMENTO,
        ligacao_causal=None,  # Pearson NUNCA afirma causa
        forca_ligacao=abs(r),
        n_amostras=n,
        periodo=periodo,
    )
    validar_elo(elo)
    return elo


def elo_interpretativo(
    dimensao: str,
    origem: tuple[str, object | None],
    destino: tuple[str, object | None],
    ligacao_causal: str,
    hedge: str,
    forca_ligacao: float = 0.5,
) -> Elo:
    """Elo de interpretação causal — SEMPRE condicional/hedged."""
    elo = Elo(
        dimensao=dimensao,
        origem_label=origem[0],
        origem_fonte_id=origem[1],
        destino_label=destino[0],
        destino_fonte_id=destino[1],
        metodo=METODO_INTERPRETACAO,
        hedge=hedge,
        ligacao_causal=ligacao_causal,
        forca_ligacao=forca_ligacao,
    )
    validar_elo(elo)
    return elo


def montar_grafo(contexto: dict) -> list[Elo]:
    """Monta os elos a partir do contexto coletado do banco. PURA.

    `contexto` = {
        "setor": str|None,
        "macro": {codigo: {"valor","data","fonte_id"}},   # último ponto por série
        "empresa_fonte_id": id|None,                        # fonte de um fundamento âncora
        "tem_pares": bool, "pares_fonte_id": id|None,
        "series_historicas": {codigo: [(date,val)...]},     # opcional (co-movimento)
    }
    Só retorna elos VALIDADOS (fonte nas duas pontas + travas A4).
    """
    macro = contexto.get("macro") or {}
    setor = (contexto.get("setor") or "").lower()
    emp_fonte = contexto.get("empresa_fonte_id")
    elos: list[Elo] = []

    def fonte(codigo: str):
        return (macro.get(codigo) or {}).get("fonte_id")

    # 1) Câmbio -> receita (empresa com receita exposta ao dólar). Interpretação.
    if "USD_VENDA" in macro and emp_fonte is not None:
        elos.append(
            elo_interpretativo(
                "câmbio→empresa",
                ("Dólar (R$/US$)", fonte("USD_VENDA")),
                ("Receita da empresa", emp_fonte),
                ligacao_causal=(
                    "cenário: depreciação do real tende a elevar receita dolarizada "
                    "convertida em reais; efeito líquido depende de dívida em dólar"
                ),
                hedge="condicional; sem dado da parcela dolarizada de receita/dívida",
            )
        )

    # 2) Brent -> setor petróleo (empresa e/ou pares do setor). Interpretação.
    if "COMMODITY_BRENT" in macro and "petról" in setor and emp_fonte is not None:
        elos.append(
            elo_interpretativo(
                "commodity→setor",
                ("Petróleo Brent (US$/barril)", fonte("COMMODITY_BRENT")),
                ("Receita de produtora de petróleo", emp_fonte),
                ligacao_causal=(
                    "cadeia: choque de oferta global → preço do Brent → receita de "
                    "produtora integrada; sentido depende de política de preços e tributação"
                ),
                hedge="condicional; nenhum evento de oferta é afirmado como ocorrido",
            )
        )

    # 3) Juros BR (Meta Selic) vs juros EUA (Treasury 10y): fluxo de capital. Interpretação.
    if "SELIC_META_ANUAL" in macro and "GLOBAL_TREASURY_10Y" in macro:
        elos.append(
            elo_interpretativo(
                "juros_global→custo_de_capital",
                ("Meta Selic (% a.a.)", fonte("SELIC_META_ANUAL")),
                ("Juro do Tesouro EUA 10a (% a.a.)", fonte("GLOBAL_TREASURY_10Y")),
                ligacao_causal=(
                    "cenário: diferencial de juros BR–EUA influencia fluxo de capital, "
                    "câmbio e custo de oportunidade de ações"
                ),
                hedge="condicional; relação macro geral, não específica da empresa",
            )
        )

    # 4) Empresa vs pares globais (comparação com ressalva de padrão contábil).
    if contexto.get("tem_pares") and contexto.get("pares_fonte_id") is not None and emp_fonte:
        elos.append(
            elo_interpretativo(
                "empresa↔pares_globais",
                ("Fundamentos da empresa (CVM)", emp_fonte),
                ("Fundamentos de pares globais (SEC)", contexto["pares_fonte_id"]),
                ligacao_causal=(
                    "comparação setorial com pares globais; interpretar com ressalva de "
                    "padrão contábil (US-GAAP vs IFRS) e moeda"
                ),
                hedge="pares são seleção interpretativa; padrões contábeis podem diferir",
            )
        )

    # 5) Co-movimento (Pearson) onde há histórico suficiente — abstém se n<MIN_N.
    hist = contexto.get("series_historicas") or {}
    if "USD_VENDA" in hist and "COMMODITY_BRENT" in hist:
        elo = elo_co_movimento(
            "co_movimento",
            ("Dólar (R$/US$)", fonte("USD_VENDA")),
            ("Petróleo Brent (US$/barril)", fonte("COMMODITY_BRENT")),
            hist["USD_VENDA"],
            hist["COMMODITY_BRENT"],
        )
        if elo is not None:
            elos.append(elo)

    return [e for e in elos if e.validada]


def coletar_contexto(session: Session, empresa: Empresa) -> dict:
    """Reúne do banco o contexto para o grafo (último ponto por série macro, uma
    fonte-âncora de fundamento da empresa, presença de pares)."""
    macro: dict[str, dict] = {}
    for m in session.execute(
        select(MacroSerie).order_by(MacroSerie.codigo, MacroSerie.data.desc())
    ).scalars():
        if m.codigo not in macro and m.valor is not None:
            macro[m.codigo] = {"valor": float(m.valor), "data": m.data, "fonte_id": m.fonte_id}

    fund = (
        session.execute(
            select(Fundamento)
            .where(Fundamento.empresa_id == empresa.id, Fundamento.fonte_id.is_not(None))
            .order_by(Fundamento.dt_refer.desc())
        )
        .scalars()
        .first()
    )

    # Mesmo corte de idade da ingestão/tese: par com dado velho não ancora elo D2.
    stmt_par = (
        select(ParFundamento)
        .join(Par, Par.id == ParFundamento.par_id)
        .where(Par.empresa_id == empresa.id, ParFundamento.fonte_id.is_not(None))
    )
    corte_pares = sec.data_corte_pares()
    if corte_pares is not None:
        stmt_par = stmt_par.where(ParFundamento.dt_refer >= corte_pares)
    par_fund = session.execute(stmt_par).scalars().first()

    return {
        "setor": empresa.setor,
        "macro": macro,
        "empresa_fonte_id": fund.fonte_id if fund else None,
        "tem_pares": par_fund is not None,
        "pares_fonte_id": par_fund.fonte_id if par_fund else None,
    }


def construir_grafo(session: Session, empresa: Empresa) -> list[Elo]:
    """Coleta o contexto do banco e monta o grafo (só elos validados)."""
    return montar_grafo(coletar_contexto(session, empresa))


def persistir_elos(
    session: Session,
    empresa_id: uuid.UUID,
    elos: list[Elo],
    tese_versao_id: uuid.UUID | None = None,
) -> None:
    """Grava os elos validados (trilha de auditoria do raciocínio)."""
    for e in elos:
        session.add(
            EloModel(
                empresa_id=empresa_id,
                dimensao=e.dimensao,
                origem_label=e.origem_label,
                origem_fonte_id=e.origem_fonte_id,
                destino_label=e.destino_label,
                destino_fonte_id=e.destino_fonte_id,
                ligacao_causal=e.ligacao_causal,
                metodo=e.metodo,
                forca_ligacao=e.forca_ligacao,
                n_amostras=e.n_amostras,
                periodo=e.periodo,
                hedge=e.hedge,
                validada=e.validada,
                tese_versao_id=tese_versao_id,
            )
        )


def elos_para_envelope(elos: list[Elo]) -> list[dict]:
    """Serializa elos para o envelope da tese (auditoria + checagem do gate)."""
    return [
        {
            "dimensao": e.dimensao,
            "origem_label": e.origem_label,
            "origem_fonte_id": str(e.origem_fonte_id) if e.origem_fonte_id else None,
            "destino_label": e.destino_label,
            "destino_fonte_id": str(e.destino_fonte_id) if e.destino_fonte_id else None,
            "metodo": e.metodo,
            "forca_ligacao": e.forca_ligacao,
            "n_amostras": e.n_amostras,
            "hedge": e.hedge,
            "ligacao_causal": e.ligacao_causal,
        }
        for e in elos
    ]


def elos_para_llm(elos: list[Elo]) -> list[str]:
    """Serializa cada elo de forma auditável (método, força, hedge, ambas as fontes)."""
    linhas: list[str] = []
    for e in elos:
        base = f"[{e.dimensao}] {e.origem_label} → {e.destino_label} " f"(método: {e.metodo}"
        if e.forca_ligacao is not None:
            base += f"; força {e.forca_ligacao:.2f}"
        if e.n_amostras:
            base += f"; n={e.n_amostras}; período {e.periodo}"
        base += ")"
        if e.ligacao_causal:
            base += f" — {e.ligacao_causal}"
        base += f" [HEDGE: {e.hedge}]"
        base += f" [fontes: origem={e.origem_fonte_id}, destino={e.destino_fonte_id}]"
        linhas.append(base)
    return linhas
