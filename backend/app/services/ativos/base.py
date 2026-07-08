"""Registry por classe de ativo — identidade e metadados (BLOCO C, D4/D5).

Cada classe suportada pelo motor multiativo ('acao' | 'fii' | 'renda_fixa') tem
uma entrada em `CLASSES` com os metadados de identidade: fonte primária citável
(keyless), se participa de "Pares globais" (D5: FII e renda fixa abstêm de
pares ESTRUTURALMENTE — a seção não existe, não fica vazia) e as lacunas
estruturais que o template da classe declara como linha fixa em `## Lacunas`
(o gate D6 veta esses termos seguidos de número — fecha o convite à alucinação).

O que este módulo NÃO faz (deliberado, etapa 6 do plano): coleta, ingestão,
template e elos por classe chegam no bloco do motor (etapa 11). O contrato que
os módulos de classe cumprirão está descrito em `PerfilClasse` — interface
documentada para os blocos paralelos, sem implementação aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ClasseAtivo:
    """Metadados de identidade de uma classe de ativo suportada pelo motor."""

    codigo: str  # 'acao' | 'fii' | 'renda_fixa'
    rotulo: str
    # Fonte primária citável (keyless) — todo fato da classe nasce dela.
    fonte_primaria: str
    # D5: False = abstenção ESTRUTURAL de "Pares globais" (sem seção, não vazia).
    pares_globais: bool
    # Linhas fixas de '## Lacunas' da classe (D5/D6). Lacunas de PLANO de contas
    # (ex.: Basileia, do plano banco) pertencem ao plano dentro de 'acao'.
    lacunas_estruturais: tuple[str, ...]
    descricao: str


class PerfilClasse(Protocol):
    """Contrato do motor por classe — implementado na etapa 11, NÃO aqui.

    Cada módulo de classe (acao/fii/renda_fixa) cumprirá esta interface:

    - ``ensure_ativo(session, codigo)``: resolve e persiste a âncora da classe
      (Empresa para 'acao' via ``cvm_cadastro.resolve_ticker``; FiiCadastro para
      'fii'; família+vencimento em ``titulos_publicos`` para 'renda_fixa', por
      SELECT DISTINCT de ``data_vencimento`` — nunca contar linhas). Abstém com
      ``DadoNaoEncontrado`` quando o ativo não existe nas fontes públicas.
    - ``ingest(session, ativo)``: ingestão keyless da classe (DFP/informes CVM,
      CSV da STN); cada fato persistido com fonte+data; sem dado -> lacuna.
    - ``coletar(session, ativo)``: documentos rotulados (valor + fonte + data +
      unidade) para o LLM com citações — nunca texto sem fonte.
    - ``montar_elos(session, contexto)``: elos D5 do perfil da classe (fonte
      validada nas DUAS pontas; Pearson rotulado não-causal; n>=24 ou abstém).
    """

    def ensure_ativo(self, session: Any, codigo: str) -> Any: ...

    def ingest(self, session: Any, ativo: Any) -> None: ...

    def coletar(self, session: Any, ativo: Any) -> list[Any]: ...

    def montar_elos(self, session: Any, contexto: Any) -> list[Any]: ...


ACAO = ClasseAtivo(
    codigo="acao",
    rotulo="Ação de companhia aberta (B3)",
    fonte_primaria="CVM — DFP/ITR + FCA (dados.cvm.gov.br, ODbL)",
    pares_globais=True,
    lacunas_estruturais=(),
    descricao=(
        "Classe legada — byte-idêntica: teses.classe_ativo NULL significa 'acao'. "
        "Planos de contas 'banco'/'seguradora' são variações DENTRO desta classe "
        "(D4: 'financeira' não é classe, é plano de contas), com lacunas próprias "
        "(ex.: Índice de Basileia) declaradas pelo plano, não pela classe."
    ),
)

FII = ClasseAtivo(
    codigo="fii",
    rotulo="Fundo de Investimento Imobiliário (FII)",
    fonte_primaria=("CVM — informes mensal/trimestral de FII (dados.cvm.gov.br/dados/FII/, ODbL)"),
    pares_globais=False,
    lacunas_estruturais=(
        "P/VP a preço de mercado (preço B3 é licenciado — dado não encontrado)",
        "dividend yield a preço de mercado (preço B3 é licenciado — dado não encontrado)",
    ),
    descricao=(
        "Indicadores TIPADOS do informe mensal em fii_indicadores (PL, VP/cota, "
        "cotas, cotistas, DY do informe — auto-declarado, NUNCA anualizar). Ticker "
        "por heurística de ISIN rotulada ('heuristica_isin'); a resolução oficial "
        "é por CNPJ. Sem pares globais (abstenção estrutural, D5)."
    ),
)

RENDA_FIXA = ClasseAtivo(
    codigo="renda_fixa",
    rotulo="Título público — Tesouro Direto (STN)",
    fonte_primaria=(
        "STN — Tesouro Transparente, preços e taxas diários "
        "(www.tesourotransparente.gov.br, ODbL + autorização comercial STN)"
    ),
    pares_globais=False,
    lacunas_estruturais=(
        "curva DI completa (sem fonte keyless licenciável; proxy rotulado = "
        "taxas do Tesouro prefixado por vencimento — dado não encontrado)",
    ),
    descricao=(
        "Identidade pela gramática TD-<SIGLA>-<ANO> (ver renda_fixa.TD_CODIGO_RE "
        "e o mapa sigla<->'Tipo Titulo' da STN). Taxa/PU são fato com 'Data Base' "
        "citada; marcação e carrego são derivadas com hedge. Sem pares globais."
    ),
)

# Registry por classe (D4/D5): a chave é o código canônico gravado em
# teses.classe_ativo (NULL = 'acao', legado).
CLASSES: dict[str, ClasseAtivo] = {c.codigo: c for c in (ACAO, FII, RENDA_FIXA)}


def obter_classe(codigo: str) -> ClasseAtivo:
    """Metadados da classe pelo código canônico.

    Código desconhecido é bug interno (a identidade só produz códigos do
    registry), não entrada de usuário — por isso ValueError, não abstenção.
    """
    try:
        return CLASSES[codigo]
    except KeyError as exc:
        raise ValueError(f"classe de ativo desconhecida: {codigo!r}") from exc
