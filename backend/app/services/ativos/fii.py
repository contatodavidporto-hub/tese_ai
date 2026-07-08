"""Perfil da classe FII — motor por classe (etapa 11, D5/D8).

Identidade: ticker B3 com sufixo 11 (cota) que NÃO consta em ``cvm_cadastro``
(units de ação vencem, D4) e resolve em ``fii_cadastro`` por ticker. O ticker
do cadastro vem de HEURÍSTICA de ISIN rotulada (``ticker_metodo=
'heuristica_isin'``); colisão ou sufixo 12/13 -> ticker NULL e o fundo só
resolve por CNPJ — nesse caso a identidade abstém (``DadoNaoEncontrado``),
nunca chuta.

MOTOR (PerfilClasse):
- coleta de ``fii_indicadores`` via ``indicadores_recentes`` (staleness 90d,
  delta 4 da reconciliação) + vacância agregada (metodologia declarada) +
  macro RELEVANTE (Selic/IPCA/CDI/Focus — filtrada, nunca a tabela inteira);
- template PRÓPRIO (``_SYSTEM_FII``): Fundamentos do fundo, Contexto macro e
  juros, Camada geopolítica e correlações (H2 contém 'geopol' — gate D6),
  Síntese, Riscos bull×bear, Fontes e Lacunas com as DUAS linhas fixas de
  P/VP e DY a preço de mercado (cotação B3 é licenciada). SEM seção "Pares
  globais" (abstenção ESTRUTURAL, D5 — a seção não existe, não fica vazia);
- elos (D8): interpretativo Selic→VP/DY + co-movimento DY_MES_INFORME×Selic
  mensal (Pearson não-causal; n<24 abstém). NUNCA os elos de ação (câmbio→
  receita etc. não vazam para FII).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import FiiCadastro, FiiIndicador, Fonte
from app.services import fii_dados
from app.services.ativos import comum
from app.services.ativos.base import FII as INFO
from app.services.correlacao import Elo, elo_co_movimento, elo_interpretativo

CLASSE = INFO.codigo

# Séries macro RELEVANTES para FII (Selic/IPCA/CDI + todas as FOCUS_*, que o
# helper inclui por prefixo). Lista explícita: a tese de FII não arrasta
# câmbio/Brent/PIB — contexto macro enxuto e pertinente a juros/inflação.
CODIGOS_MACRO_FII: tuple[str, ...] = (
    "SELIC_META_ANUAL",
    "IPCA_MENSAL",
    "CDI_ANUAL",
    "CDI_DIARIO",
)

# Rótulo humano por indicador tipado (fii_indicadores.indicador). Os
# auto-declarados carregam a ressalva no próprio rótulo — o LLM cita o rótulo.
_ROTULOS_INDICADOR: dict[str, str] = {
    "PL": "Patrimônio líquido do fundo",
    "VP_COTA": "Valor patrimonial por cota",
    "COTAS_EMITIDAS": "Cotas emitidas",
    "COTISTAS": "Número de cotistas",
    "DY_MES_INFORME": (
        "Dividend yield mensal do informe (auto-declarado pelo administrador; "
        "metodologia do informe mensal CVM — NÃO é DY a preço de mercado e "
        "NUNCA deve ser anualizado)"
    ),
    "RENT_EFETIVA_MES": "Rentabilidade efetiva mensal (auto-declarada pelo administrador)",
    "VACANCIA_AGREGADA": "Vacância agregada do fundo",
}

_SYSTEM_FII = """\
Você é o motor de teses do "Tese AI". Monta teses de investimento ESTRUTURADAS e \
AUDITÁVEIS para FUNDOS IMOBILIÁRIOS (FIIs) listados na B3, em português do Brasil.

REGRAS INEGOCIÁVEIS:
1. NUNCA invente número ou fato. Todo dado factual deve vir EXCLUSIVAMENTE dos \
documentos-fonte fornecidos nesta mensagem, e cada número deve estar ancorado numa \
citação à fonte. Se um dado necessário NÃO está nos documentos, escreva \
"dado não encontrado" e siga — jamais estime ou preencha.
2. NUNCA dê recomendação de compra/venda. Proibido "compre", "venda", "mantenha", \
"subscreva", "vale a pena", preço-alvo ou opinião direcional. Você ESTRUTURA o \
raciocínio; a decisão é do leitor (postura regulatória CVM).
3. SEPARE fato de interpretação. Marque o que é dado factual (citado) e o que é \
sua leitura/cenário ("interpretação:", "cenário:").
4. Os indicadores do informe mensal CVM (PL, VP/cota, cotas, cotistas, dividend \
yield mensal, rentabilidade) são AUTO-DECLARADOS pelo administrador: cite-os com \
essa ressalva, exatamente como rotulados nos documentos. O dividend yield do \
informe segue a metodologia do próprio informe — NUNCA o anualize nem o trate \
como DY a preço de mercado. A vacância agregada declara a própria metodologia \
(média ponderada pela área): cite a metodologia junto do número.
5. A camada geopolítica e as CORRELAÇÕES são raciocínio causal e são \
INTERPRETAÇÃO: ancore-as apenas nos dados fornecidos (juros, inflação, \
expectativas) e NÃO afirme eventos específicos como fato se eles não estiverem \
nos documentos. Use SOMENTE raciocínio condicional com hedge explícito \
("cenário:", "caso", "se houver"). Os "elos de correlação" fornecidos já vêm \
com hedge e com fontes nas duas pontas: use-os como fio condutor, sem endurecê-los.
6. Séries do Focus/BCB são EXPECTATIVA de mercado, não fato realizado — rotule-as \
exatamente como vêm no documento. Não confunda CDI/Selic diários (% a.d.) com as \
taxas anuais (% a.a.).
7. NÃO há seção de pares globais para FII (abstenção estrutural): não compare com \
REITs nem com outros fundos.

ESTRUTURA DA SAÍDA (markdown, exatamente estas seções):
# Tese — {TICKER} ({FUNDO})
> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.
## 1. Fundamentos do fundo
## 2. Contexto macro e juros
## 3. Camada geopolítica e correlações (interpretação)
## 4. Síntese
## 5. Riscos e contra-tese (bull × bear)
## 6. Fontes
## 7. Lacunas
Em "1. Fundamentos do fundo", cubra: patrimônio líquido, valor patrimonial por \
cota, cotas emitidas, número de cotistas, dividend yield mensal do informe \
(auto-declarado) e vacância com a metodologia declarada — cada um citado à fonte \
ou "dado não encontrado".
Em "Lacunas", liste explicitamente os "dado não encontrado" e SEMPRE inclua \
estas duas linhas fixas:
- P/VP a preço de mercado: dado não encontrado (cotação B3 é licenciada)
- Dividend yield a preço de mercado: dado não encontrado (cotação B3 é licenciada)
"""


# ---------------------------------------------------------------------------
# PerfilClasse
# ---------------------------------------------------------------------------
def ensure_ativo(session: Session, codigo: str) -> FiiCadastro:
    """Resolve o ticker no cadastro persistido; só vai à CVM se ainda não há
    cadastro (idempotente — mesmo padrão cache-first do ensure_empresa)."""
    ticker = (codigo or "").strip().upper()
    fii = session.execute(
        select(FiiCadastro).where(FiiCadastro.ticker == ticker)
    ).scalar_one_or_none()
    if fii is not None:
        return fii
    return fii_dados.ensure_fii(session, ticker)


def precisa_ingest(session: Session, fii: FiiCadastro) -> bool:
    """Ingere quando não há indicador DENTRO da janela de staleness (90d)."""
    return not fii_dados.indicadores_recentes(session, fii)


def ingest(session: Session, fii: FiiCadastro) -> None:
    """Ingestão da classe com falha ISOLADA por passo (padrão orquestração)."""
    from app.services import orquestracao

    orquestracao.ingest_fii_completo(session, fii)


def nome_ativo(fii: FiiCadastro) -> str:
    return fii.nome


def system_prompt(_fii: FiiCadastro) -> str:
    return _SYSTEM_FII


def ancora_elos(fii: FiiCadastro) -> tuple[object | None, str | None]:
    """FII não tem empresa: âncora do elo é o ativo_codigo (ticker; CNPJ se a
    heurística de ticker foi zerada por colisão)."""
    return None, (fii.ticker or fii.cnpj)


def coletar(session: Session, fii: FiiCadastro) -> list[tuple[Fonte, str]]:
    """(fonte, fato) por indicador RECENTE (staleness 90d) + cadastro + macro.

    Cada indicador é formatado pela UNIDADE tipada (achado B2 — 525.069
    cotistas nunca vira "R$ 525.069,00") e carrega competência + metodologia.
    Sem indicador recente -> lista VAZIA (abstenção total do chamador, delta 4:
    macro sozinha não sustenta tese de FII — nunca servimos tese "macro-only"
    de um fundo cujo informe está defasado).
    """
    itens: list[tuple[Fonte, str]] = []
    recentes = fii_dados.indicadores_recentes(session, fii)
    if not recentes:
        return []
    for codigo in sorted(recentes):
        ind: FiiIndicador = recentes[codigo]
        fonte = session.get(Fonte, ind.fonte_id) if ind.fonte_id else None
        if fonte is None:
            continue  # sem fonte não é fato
        rotulo = _ROTULOS_INDICADOR.get(codigo, codigo)
        metodologia = f"; metodologia: {ind.metodologia}" if ind.metodologia else ""
        texto = (
            f"Indicador de {fii.nome} ({fii.ticker or fii.cnpj}): "
            f"{rotulo} = {comum.fmt_por_unidade(float(ind.valor), ind.unidade)} "
            f"(competência {ind.dt_referencia}{metodologia})."
        )
        itens.append((fonte, texto))

    # Cadastro (segmento/mandato/gestão) — auto-declarado no informe mensal.
    if itens and fii.fonte_id is not None:
        fonte_cad = session.get(Fonte, fii.fonte_id)
        if fonte_cad is not None:
            texto_cad = (
                f"Cadastro de {fii.nome} ({fii.ticker or fii.cnpj}), auto-declarado "
                f"pelo administrador no informe mensal CVM: "
                f"segmento de atuação: {fii.segmento or 'não informado'}; "
                f"mandato: {fii.mandato or 'não informado'}; "
                f"tipo de gestão: {fii.tipo_gestao or 'não informado'}."
            )
            itens.append((fonte_cad, texto_cad))

    itens.extend(comum.coletar_macro_docs(session, CODIGOS_MACRO_FII))
    return itens


# ---------------------------------------------------------------------------
# Elos da classe (D8) — PUROS + coletor de contexto
# ---------------------------------------------------------------------------
def montar_elos_fii(contexto: dict) -> list[Elo]:
    """Elos do perfil FII. PURA (testável offline).

    `contexto` = {
        "macro": {codigo: {"valor","data","fonte_id"}},
        "fontes_indicador": {indicador: fonte_id},           # VP_COTA/DY...
        "series": {"DY_MES_INFORME": [(date,val)...],        # histórico do fundo
                    "SELIC_META_ANUAL": [(date,val)...]},    # Selic p/ mensalizar
    }
    - interpretativo Selic→VP/DY (fonte nas DUAS pontas, hedge condicional);
    - co-movimento DY_MES_INFORME × Selic mensal (Pearson NÃO-causal; n<24
      abstém — trava A4 herdada dos primitivos).
    Nenhum elo de ação (câmbio→receita, pares etc.) existe aqui.
    """
    macro = contexto.get("macro") or {}
    fontes_ind: dict[str, object] = contexto.get("fontes_indicador") or {}
    series = contexto.get("series") or {}
    elos: list[Elo] = []

    fonte_selic = (macro.get("SELIC_META_ANUAL") or {}).get("fonte_id")
    fonte_vp_dy = fontes_ind.get("VP_COTA") or fontes_ind.get("DY_MES_INFORME")
    if fonte_selic is not None and fonte_vp_dy is not None:
        elos.append(
            elo_interpretativo(
                "selic→vp_dy_fii",
                ("Meta Selic (% a.a.)", fonte_selic),
                ("Valor patrimonial/dividend yield do fundo (informe CVM)", fonte_vp_dy),
                ligacao_causal=(
                    "cenário: juros mais altos tendem a pressionar o valor presente "
                    "dos aluguéis e a atratividade relativa do rendimento distribuído "
                    "frente à renda fixa"
                ),
                hedge=(
                    "condicional; a sensibilidade depende de segmento, prazo e "
                    "indexação dos contratos — não quantificável com os dados do informe"
                ),
            )
        )

    serie_dy = series.get("DY_MES_INFORME") or []
    serie_selic = series.get("SELIC_META_ANUAL") or []
    fonte_dy = fontes_ind.get("DY_MES_INFORME")
    if serie_dy and serie_selic and fonte_dy is not None and fonte_selic is not None:
        elo = elo_co_movimento(
            "co_movimento_dy_selic",
            ("Dividend yield mensal do informe (auto-declarado, CVM)", fonte_dy),
            ("Meta Selic (% a.a.)", fonte_selic),
            serie_dy,
            serie_selic,
        )
        if elo is not None:  # n<MIN_N ou variância nula -> abstém
            elos.append(elo)

    return [e for e in elos if e.validada]


def coletar_contexto(session: Session, fii: FiiCadastro) -> dict:
    """Contexto do grafo FII a partir do banco (indicadores + Selic)."""
    recentes = fii_dados.indicadores_recentes(session, fii)
    fontes_indicador = {cod: ind.fonte_id for cod, ind in recentes.items()}
    serie_dy = [
        (i.dt_referencia, float(i.valor))
        for i in session.execute(
            select(FiiIndicador)
            .where(FiiIndicador.fii_id == fii.id, FiiIndicador.indicador == "DY_MES_INFORME")
            .order_by(FiiIndicador.dt_referencia)
        ).scalars()
    ]
    return {
        "macro": comum.ultimo_ponto_macro(session, CODIGOS_MACRO_FII),
        "fontes_indicador": fontes_indicador,
        "series": {
            "DY_MES_INFORME": serie_dy,
            "SELIC_META_ANUAL": comum.serie_macro(session, "SELIC_META_ANUAL"),
        },
    }


def montar_elos(session: Session, fii: FiiCadastro) -> list[Elo]:
    return montar_elos_fii(coletar_contexto(session, fii))


__all__ = [
    "CLASSE",
    "CODIGOS_MACRO_FII",
    "INFO",
    "ancora_elos",
    "coletar",
    "coletar_contexto",
    "ensure_ativo",
    "ingest",
    "montar_elos",
    "montar_elos_fii",
    "nome_ativo",
    "precisa_ingest",
    "system_prompt",
]
