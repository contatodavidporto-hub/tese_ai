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

Fase 2 multiativo (D8): as REGRAS POR CLASSE vivem nos perfis de
``app/services/ativos`` (``perfil.montar_elos``) — aqui ficam só os PRIMITIVOS
(``validar_elo``, Pearson não-causal com ``MIN_N``, hedge, ``persistir_elos``) e
o grafo legado da AÇÃO (``montar_grafo``, byte-idêntico: 8 elos). FII/renda fixa
NUNCA passam por ``montar_grafo`` — é isso que corrige o vazamento do elo
câmbio→receita (que disparava por ``empresa_fonte_id``, não por classe).
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


def alinhar_series_mensal(
    serie_a: list[tuple[dt.date, float]], serie_b: list[tuple[dt.date, float]]
) -> list[tuple[float, float]]:
    """Pares (a, b) por (ano, mês) — última observação de cada mês em cada série.

    Séries de frequências diferentes (dólar diário × Brent mensal) quase nunca
    compartilham a MESMA data — o alinhamento exato dava n≈0 e o co-movimento
    nunca disparava. Mês é a granularidade honesta comum às duas.
    """

    def _por_mes(
        serie: list[tuple[dt.date, float]],
    ) -> dict[tuple[int, int], tuple[dt.date, float]]:
        m: dict[tuple[int, int], tuple[dt.date, float]] = {}
        for d, v in serie:
            chave = (d.year, d.month)
            if chave not in m or d > m[chave][0]:
                m[chave] = (d, v)
        return m

    ma, mb = _por_mes(serie_a), _por_mes(serie_b)
    return [(ma[k][1], mb[k][1]) for k in sorted(ma.keys() & mb.keys())]


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
    """Elo de co-movimento (Pearson, granularidade MENSAL). Abstém se n<MIN_N
    meses em comum ou variância nula."""
    res = correlacao_pearson(alinhar_series_mensal(serie_a, serie_b))
    if res is None or res[1] < MIN_N:
        return None
    r, n = res
    meses_a = {(d.year, d.month) for d, _ in serie_a}
    meses_comuns = sorted(meses_a & {(d.year, d.month) for d, _ in serie_b})
    periodo = (
        f"{meses_comuns[0][0]}-{meses_comuns[0][1]:02d}.."
        f"{meses_comuns[-1][0]}-{meses_comuns[-1][1]:02d} (mensal)"
        if meses_comuns
        else None
    )
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
        "fundamento_fontes": {conta_chave: fonte_id},       # fontes POR CONTA (elos D1)
        "tem_pares": bool, "pares_fonte_id": id|None,
        "series_historicas": {codigo: [(date,val)...]},     # co-movimento (mensal)
    }
    Só retorna elos VALIDADOS (fonte nas duas pontas + travas A4).
    """
    macro = contexto.get("macro") or {}
    setor = (contexto.get("setor") or "").lower()
    emp_fonte = contexto.get("empresa_fonte_id")
    fund_fontes: dict[str, object] = contexto.get("fundamento_fontes") or {}
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

    # 5) Juro global (Treasury 10a) -> custo de capital/refinanciamento da DÍVIDA
    #    da empresa. Fonte nas duas pontas: FRED/Treasury + conta CVM da dívida.
    fonte_divida = fund_fontes.get("Dívida bruta (derivado)") or fund_fontes.get("2.02.01")
    if "GLOBAL_TREASURY_10Y" in macro and fonte_divida is not None:
        elos.append(
            elo_interpretativo(
                "juros_global→divida_empresa",
                ("Juro do Tesouro EUA 10a (% a.a.)", fonte("GLOBAL_TREASURY_10Y")),
                ("Dívida bruta da empresa (CVM)", fonte_divida),
                ligacao_causal=(
                    "cenário: juro global mais alto tende a encarecer refinanciamento "
                    "e custo de capital de dívida corporativa emergente"
                ),
                hedge=(
                    "condicional; sem a estrutura de vencimentos/moeda da dívida, a "
                    "sensibilidade efetiva não é quantificável"
                ),
            )
        )

    # 6) Câmbio -> resultado financeiro (conta 3.06 da DRE, quando ingerida).
    if "USD_VENDA" in macro and fund_fontes.get("3.06") is not None:
        elos.append(
            elo_interpretativo(
                "câmbio→resultado_financeiro",
                ("Dólar (R$/US$)", fonte("USD_VENDA")),
                ("Resultado financeiro da empresa (DRE 3.06)", fund_fontes["3.06"]),
                ligacao_causal=(
                    "cenário: variação cambial afeta o resultado financeiro via dívida "
                    "e ativos dolarizados"
                ),
                hedge=(
                    "condicional; sem a parcela dolarizada de dívida/ativos, o sentido "
                    "e a magnitude do efeito são incertos"
                ),
            )
        )

    # 7) Selic -> despesas financeiras (dívida local pós-fixada, quando 3.06.02 existe).
    if "SELIC_META_ANUAL" in macro and fund_fontes.get("3.06.02") is not None:
        elos.append(
            elo_interpretativo(
                "selic→despesas_financeiras",
                ("Meta Selic (% a.a.)", fonte("SELIC_META_ANUAL")),
                ("Despesas financeiras da empresa (DRE 3.06.02)", fund_fontes["3.06.02"]),
                ligacao_causal=(
                    "cenário: Selic mais alta tende a elevar a despesa de juros da "
                    "parcela de dívida local pós-fixada"
                ),
                hedge=(
                    "condicional; a fração pós-fixada em CDI/Selic não está disponível "
                    "nas demonstrações padronizadas"
                ),
            )
        )

    # 8) Co-movimento (Pearson MENSAL) onde há histórico suficiente — abstém se n<MIN_N.
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

    # Fontes POR CONTA (mais recente por conta): ancoram os elos D1 específicos
    # (dívida, resultado financeiro, despesas financeiras). Chave = CD_CONTA quando
    # o rótulo termina em "(x.y.z)"; senão o rótulo inteiro (derivadas).
    fundamento_fontes: dict[str, object] = {}
    for f in session.execute(
        select(Fundamento)
        .where(Fundamento.empresa_id == empresa.id, Fundamento.fonte_id.is_not(None))
        .order_by(Fundamento.dt_refer.desc())
    ).scalars():
        chave = f.conta
        if chave.endswith(")") and "(" in chave:
            sufixo = chave.rsplit("(", 1)[1].rstrip(")")
            if sufixo and all(parte.isdigit() for parte in sufixo.split(".")):
                chave = sufixo
        if chave not in fundamento_fontes:  # dt_refer desc => fica a mais recente
            fundamento_fontes[chave] = f.fonte_id

    # Histórico das séries do co-movimento (mensalizado no alinhamento).
    series_historicas: dict[str, list[tuple[dt.date, float]]] = {}
    for codigo in ("USD_VENDA", "COMMODITY_BRENT"):
        pontos = [
            (m.data, float(m.valor))
            for m in session.execute(
                select(MacroSerie)
                .where(MacroSerie.codigo == codigo, MacroSerie.valor.is_not(None))
                .order_by(MacroSerie.data)
            ).scalars()
        ]
        if pontos:
            series_historicas[codigo] = pontos

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
        # Plano de contas detectado por filing (D2): o perfil da AÇÃO usa esta
        # chave para os elos de banco; `montar_grafo` a ignora (o grafo legado
        # da ação segue byte-idêntico).
        "plano_contas": getattr(empresa, "plano_contas", None),
        "macro": macro,
        "empresa_fonte_id": fund.fonte_id if fund else None,
        "fundamento_fontes": fundamento_fontes,
        "series_historicas": series_historicas,
        "tem_pares": par_fund is not None,
        "pares_fonte_id": par_fund.fonte_id if par_fund else None,
    }


def construir_grafo(session: Session, empresa: Empresa) -> list[Elo]:
    """Coleta o contexto do banco e monta o grafo (só elos validados)."""
    return montar_grafo(coletar_contexto(session, empresa))


def persistir_elos(
    session: Session,
    empresa_id: uuid.UUID | None,
    elos: list[Elo],
    tese_versao_id: uuid.UUID | None = None,
    *,
    ativo_codigo: str | None = None,
) -> None:
    """Grava os elos validados (trilha de auditoria do raciocínio).

    Âncora do elo (CHECK ``ck_elos_ancora`` da migração 0005): ``empresa_id``
    para ação; ``ativo_codigo`` (ticker de FII / código TD) quando não há
    empresa. Um dos dois é OBRIGATÓRIO — falha rápido aqui em vez de deixar o
    banco rejeitar no commit (elo órfão nunca é gravado).
    """
    if elos and empresa_id is None and ativo_codigo is None:
        raise ValueError("elo sem âncora: informe empresa_id OU ativo_codigo (ck_elos_ancora)")
    for e in elos:
        session.add(
            EloModel(
                empresa_id=empresa_id,
                ativo_codigo=ativo_codigo,
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
