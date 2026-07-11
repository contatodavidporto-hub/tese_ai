"""Perfil da classe ACAO — motor por classe (etapa 11, D5/D8).

Identidade: ticker B3 (raiz de 4 alfanuméricos iniciada por letra + 1-2
dígitos + sufixo 'B' opcional de balcão). Sufixos numéricos 11-13 são
AMBÍGUOS (units SANB11/TAEE11/BPAC11 vs cotas de FII): a identidade consulta
``cvm_cadastro`` PRIMEIRO — units vencem (D4) — ver
``identidade.resolver_classe``. A autoridade final do cadastro na geração
segue sendo ``cvm_cadastro.resolve_ticker`` (com seed offline).

Semântica de persistência: ``teses.classe_ativo`` NULL = 'acao' (migração
0005) — o caminho legado da ação permanece byte-idêntico.

MOTOR (PerfilClasse): este perfil DELEGA ao fluxo atual — ``ensure_empresa`` /
``orquestracao.ingest_completo`` / ``tese._coletar`` / ``tese._SYSTEM`` /
``correlacao.montar_grafo`` (os 8 elos legados, byte-idênticos). A única
variação é DENTRO da classe, por plano de contas (D4: 'financeira' não é
classe): empresas com plano 'banco'/'seguradora' usam o template VARIANTE
(``_SYSTEM`` + apêndice — mesmas 8 seções, instruções de crédito/PDD/ROE, a
regra '3.05 não é EBIT' e a lacuna fixa do Índice de Basileia); o plano
'banco' ganha ainda os elos interpretativos Selic→custo de captação (3.02) e
Selic→PDD, com fonte nas duas pontas + hedge (D8).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.models import (
    Empresa,
    Fonte,
    Fundamento,
    MacroSerie,
    PrecoDiario,
    Provento,
    SetorIndicador,
)
from app.services import correlacao, cotahist, planos_contas
from app.services import dados as dados_svc
from app.services.ativos.base import ACAO as INFO
from app.services.correlacao import Elo, elo_co_movimento, elo_interpretativo

CLASSE = INFO.codigo

# Apêndice do template VARIANTE de emissor financeiro (banco/seguradora):
# concatenado a `tese._SYSTEM` (que fica BYTE-IDÊNTICO — teste de hash pina o
# valor). Mesmas 8 seções; muda só a instrução dentro delas (D5).
_APENDICE_FINANCEIRA = """

INSTRUÇÕES ADICIONAIS — EMISSOR FINANCEIRO (plano de contas de banco/seguradora):
A estrutura da saída é a MESMA (as 8 seções acima). Na seção "## 1. Fundamentos":
- O núcleo do resultado é a intermediação financeira (receitas 3.01, despesas \
3.02, resultado bruto 3.03) e a qualidade de crédito: analise a PDD/perda \
esperada de crédito (em relação à carteira de crédito, quando disponível) e o \
ROE (razão já derivada, com metodologia declarada na fonte) — cada número \
citado à sua fonte, como sempre.
- A conta 3.05 de banco é "Resultado antes dos Tributos sobre o Lucro" — NUNCA \
trate como EBIT; não calcule múltiplos de dívida/EBITDA (não se aplicam a \
instituição financeira).
Em "## 8. Lacunas", inclua SEMPRE esta linha fixa:
- Índice de Basileia: dado não encontrado (publicado no IF.data/BCB, não nas \
demonstrações CVM)
"""

# Chave de PDD em `fundamento_fontes` (contexto do grafo): a posição da PDD
# varia por emissor (BBAS/BBDC=3.04.01; ITUB=3.02.02 — ground truth DFP 2025),
# e o plano banco só persiste UMA conta de nível >=3 no grupo 3.x (a própria
# PDD, por tokens específicos de crédito). Nível 3+ em 3.02./3.04. => PDD.
_PDD_CHAVE_RE = re.compile(r"^3\.(?:02|04)\.\d{2}(?:\.\d{2})*$")


# ---------------------------------------------------------------------------
# PerfilClasse — delegação ao fluxo legado (byte-idêntico)
# ---------------------------------------------------------------------------
def ensure_ativo(session: Session, codigo: str) -> Empresa:
    """Resolve o ticker no cadastro CVM universal (cache + seed offline)."""
    return dados_svc.ensure_empresa(session, codigo)


def precisa_ingest(session: Session, empresa: Empresa) -> bool:
    """Ingere quando falta fundamento OU quando o preço do ticker está stale.

    Correção do bug "tese legada silenciosa" (2026-07-11): antes, uma
    empresa com fundamentos já persistidos nunca reingeria, mesmo sem
    NENHUMA linha de `precos_diarios` — `_tem_dado_novo` (tese.py) então
    nunca achava o preço novo e a tese saía com o prompt/blocos legados,
    sem erro nem lacuna visível. Reusa a MESMA regra de staleness de
    `cotahist.ensure_precos` (`cotahist.precos_frescos`) em vez de duplicá-
    la — sem ticker, a checagem de preço é pulada (nada a ingerir por essa
    via)."""
    sem_fundamento = (
        session.execute(
            select(Fundamento.id).where(Fundamento.empresa_id == empresa.id).limit(1)
        ).first()
        is None
    )
    if sem_fundamento:
        return True
    ticker = (empresa.ticker or "").strip().upper()
    if not ticker:
        return False
    return not cotahist.precos_frescos(session, ticker)


def ingest(session: Session, empresa: Empresa) -> None:
    """Fluxo atual intacto: 5 dimensões com falha isolada por passo."""
    # Import tardio (mesmo padrão do gerar_tese legado): evita ciclo de import.
    from app.services import orquestracao

    orquestracao.ingest_completo(session, empresa)


def coletar(session: Session, empresa: Empresa) -> list[tuple[Fonte, str]]:
    """Delegação BYTE-IDÊNTICA ao coletor legado (`tese._coletar`)."""
    from app.services import tese as tese_svc

    return tese_svc._coletar(session, empresa)


def nome_ativo(empresa: Empresa) -> str:
    return empresa.nome


def system_prompt(empresa: Empresa) -> str:
    """Template da classe: `_SYSTEM` legado; VARIANTE p/ plano financeiro (D5).

    O plano vem do próprio filing (D2, `empresas.plano_contas`); plano NULL ou
    'padrao' usa o system prompt EXATAMENTE igual ao de hoje (hash pinado em
    teste de regressão).
    """
    from app.services import tese as tese_svc

    plano = getattr(empresa, "plano_contas", None)
    if plano in planos_contas.PLANOS_FINANCEIROS:
        return tese_svc._SYSTEM + _APENDICE_FINANCEIRA
    return tese_svc._SYSTEM


def ancora_elos(empresa: Empresa) -> tuple[object | None, str | None]:
    """(empresa_id, ativo_codigo) p/ `persistir_elos` — ação ancora por empresa."""
    return empresa.id, None


# ---------------------------------------------------------------------------
# Elos da classe (D8) — 8 elos legados byte-idênticos + elos do plano banco
# ---------------------------------------------------------------------------
def montar_elos_financeira(contexto: dict) -> list[Elo]:
    """Elos interpretativos do plano BANCO (via perfil ação, D8). PURA.

    - Selic → custo de captação: fonte na Meta Selic E na conta 3.02 (Despesas
      de Intermediação Financeira) — sem uma das pontas, o elo NÃO existe.
    - Selic → PDD: fonte na Meta Selic E na conta de PDD localizada por DS
      (3.04.01 ou 3.02.02 — posição varia por emissor).
    SÓ para plano 'banco': no plano 'seguradora' a conta 3.02 são despesas de
    seguros/resseguros (NÃO custo de captação) — rotular seria número certo com
    interpretação errada; seguradora abstém destes elos. Só devolve VALIDADOS.
    """
    if contexto.get("plano_contas") != planos_contas.PLANO_BANCO:
        return []
    macro = contexto.get("macro") or {}
    fund_fontes: dict[str, object] = contexto.get("fundamento_fontes") or {}
    fonte_selic = (macro.get("SELIC_META_ANUAL") or {}).get("fonte_id")
    if fonte_selic is None:
        return []

    elos: list[Elo] = []
    fonte_captacao = fund_fontes.get("3.02")
    if fonte_captacao is not None:
        elos.append(
            elo_interpretativo(
                "selic→custo_de_captacao",
                ("Meta Selic (% a.a.)", fonte_selic),
                ("Despesas de intermediação financeira (DRE 3.02)", fonte_captacao),
                ligacao_causal=(
                    "cenário: Selic mais alta tende a encarecer a captação do banco "
                    "(funding pós-fixado) e a reprecificar a margem financeira"
                ),
                hedge=(
                    "condicional; o mix de funding (depósitos à vista/prazo, letras) "
                    "não está nas demonstrações padronizadas — sensibilidade não "
                    "quantificável"
                ),
            )
        )

    fonte_pdd = next(
        (fund_fontes[k] for k in sorted(fund_fontes) if _PDD_CHAVE_RE.fullmatch(k)),
        None,
    )
    if fonte_pdd is not None:
        elos.append(
            elo_interpretativo(
                "selic→pdd",
                ("Meta Selic (% a.a.)", fonte_selic),
                ("PDD / perda esperada de crédito (DRE, conta localizada por DS)", fonte_pdd),
                ligacao_causal=(
                    "cenário: ciclo de juros altos tende a elevar inadimplência e a "
                    "despesa de provisão para perda esperada de crédito"
                ),
                hedge=(
                    "condicional; a inadimplência efetiva depende de mix de carteira "
                    "e ciclo de crédito — relação histórica, não determinística"
                ),
            )
        )
    return [e for e in elos if e.validada]


# ---------------------------------------------------------------------------
# Elos AMPLIADOS (F3, plano §2.9) — reusam os primitivos de `correlacao`;
# fonte nas DUAS pontas sempre; abstenção silenciosa sem dado novo (nunca
# derruba a tese, nunca inventa elo).
# ---------------------------------------------------------------------------
_MIN_PREGOES_ELO_TECNICO = 30  # espelha MIN_N do co-movimento (correlacao.MIN_N)


def montar_elos_tecnica(session: Session, empresa: Empresa) -> list[Elo]:
    """Selic → linha de Acumulação/Distribuição técnica (co-movimento, plano
    §2.9). Recalcula o primitivo PURO de `tecnica.linha_ad` sobre o COTAHIST
    já persistido (nunca refaz o ingest) — Pearson NÃO-causal, `n<MIN_N`
    abstém (herdado de `correlacao.elo_co_movimento`)."""
    ticker = (empresa.ticker or "").strip().upper()
    if not ticker:
        return []
    try:
        linhas = (
            session.execute(
                select(PrecoDiario)
                .where(PrecoDiario.ticker == ticker)
                .order_by(PrecoDiario.data_pregao)
            )
            .scalars()
            .all()
        )
    except (ProgrammingError, OperationalError):
        return []  # tabela ausente (migração 0006 pendente/teste offline) — sem elo
    barras = [
        p
        for p in linhas
        if p.maxima is not None
        and p.minima is not None
        and p.fechamento is not None
        and p.volume is not None
    ]
    if len(barras) < _MIN_PREGOES_ELO_TECNICO:
        return []
    from app.services import tecnica as tecnica_svc  # import tardio — evita ciclo

    ad = tecnica_svc.linha_ad(
        [float(b.maxima) for b in barras],
        [float(b.minima) for b in barras],
        [float(b.fechamento) for b in barras],
        [float(b.volume) for b in barras],
    )
    serie_ad = list(zip((b.data_pregao for b in barras), ad, strict=True))
    serie_selic = [
        (m.data, float(m.valor))
        for m in session.execute(
            select(MacroSerie)
            .where(MacroSerie.codigo == "SELIC_META_ANUAL", MacroSerie.valor.is_not(None))
            .order_by(MacroSerie.data)
        ).scalars()
    ]
    fonte_selic = next(
        (
            m.fonte_id
            for m in session.execute(
                select(MacroSerie)
                .where(MacroSerie.codigo == "SELIC_META_ANUAL")
                .order_by(MacroSerie.data.desc())
                .limit(1)
            ).scalars()
        ),
        None,
    )
    fonte_precos = barras[-1].fonte_id
    if not serie_selic or fonte_selic is None or fonte_precos is None:
        return []
    elo = elo_co_movimento(
        "selic→ad_tecnico",
        ("Meta Selic (% a.a.)", fonte_selic),
        ("Linha de Acumulação/Distribuição (técnica, COTAHIST)", fonte_precos),
        serie_selic,
        serie_ad,
    )
    return [elo] if elo is not None else []


def montar_elos_energia(session: Session, empresa: Empresa) -> list[Elo]:
    """RAP → receita → dividendos (energia/transmissão, plano §2.9) —
    interpretativo com hedge: a RAP é TETO regulatório de receita, não fato de
    pagamento; a ligação com proventos é condicional."""
    ticker = (empresa.ticker or "").strip().upper()
    if not ticker:
        return []
    try:
        rap = session.execute(
            select(SetorIndicador)
            .where(
                SetorIndicador.ticker == ticker,
                SetorIndicador.indicador.in_(("RAP_CICLO", "RAP")),
            )
            .order_by(SetorIndicador.competencia.desc())
            .limit(1)
        ).scalar_one_or_none()
        if rap is None:
            return []
        provento = session.execute(
            select(Provento)
            .where(Provento.ticker == ticker)
            .order_by(Provento.data_com.desc())
            .limit(1)
        ).scalar_one_or_none()
    except (ProgrammingError, OperationalError):
        return []  # tabela ausente (migração 0006 pendente/teste offline) — sem elo
    if provento is None:
        return []
    return [
        elo_interpretativo(
            "rap→receita→dividendos",
            ("RAP — Receita Anual Permitida (ANEEL SIGET)", rap.fonte_id),
            ("Proventos distribuídos (B3)", provento.fonte_id),
            ligacao_causal=(
                "cadeia: a RAP homologada é o teto de receita regulada de transmissão; "
                "a receita realizada tende a se aproximar da RAP contratada, e parte do "
                "resultado pode ser distribuída como proventos"
            ),
            hedge=(
                "condicional; RAP é teto regulatório, não fato de pagamento — payout, "
                "alavancagem e outros usos do caixa não são capturados por este elo"
            ),
        )
    ]


def montar_elos(session: Session, empresa: Empresa) -> list[Elo]:
    """Elos da classe AÇÃO: grafo legado (8 elos, BYTE-IDÊNTICO — vive em
    `correlacao.montar_grafo`) + elos do plano financeiro quando o filing
    detectou banco/seguradora (D8) + elos AMPLIADOS (F3, §2.9: Selic→A/D
    técnico sempre que há COTAHIST suficiente; RAP→dividendos só quando há
    RAP e proventos persistidos — abstenção silenciosa sem dado novo)."""
    contexto = correlacao.coletar_contexto(session, empresa)
    elos = correlacao.montar_grafo(contexto)
    elos.extend(montar_elos_financeira(contexto))
    elos.extend(montar_elos_tecnica(session, empresa))
    elos.extend(montar_elos_energia(session, empresa))
    return elos


__all__ = [
    "CLASSE",
    "INFO",
    "ancora_elos",
    "coletar",
    "ensure_ativo",
    "ingest",
    "montar_elos",
    "montar_elos_energia",
    "montar_elos_financeira",
    "montar_elos_tecnica",
    "nome_ativo",
    "precisa_ingest",
    "system_prompt",
]
