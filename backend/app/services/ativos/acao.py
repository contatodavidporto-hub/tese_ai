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
from sqlalchemy.orm import Session

from app.models.models import Empresa, Fonte, Fundamento
from app.services import correlacao, planos_contas
from app.services import dados as dados_svc
from app.services.ativos.base import ACAO as INFO
from app.services.correlacao import Elo, elo_interpretativo

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
    """Mesmo gatilho do fluxo legado: ingere só se a empresa não tem fundamento."""
    return (
        session.execute(
            select(Fundamento.id).where(Fundamento.empresa_id == empresa.id).limit(1)
        ).first()
        is None
    )


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


def montar_elos(session: Session, empresa: Empresa) -> list[Elo]:
    """Elos da classe AÇÃO: grafo legado (8 elos, BYTE-IDÊNTICO — vive em
    `correlacao.montar_grafo`) + elos do plano financeiro quando o filing
    detectou banco/seguradora (D8)."""
    contexto = correlacao.coletar_contexto(session, empresa)
    elos = correlacao.montar_grafo(contexto)
    elos.extend(montar_elos_financeira(contexto))
    return elos


__all__ = [
    "CLASSE",
    "INFO",
    "ancora_elos",
    "coletar",
    "ensure_ativo",
    "ingest",
    "montar_elos",
    "montar_elos_financeira",
    "nome_ativo",
    "precisa_ingest",
    "system_prompt",
]
