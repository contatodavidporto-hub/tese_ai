"""Perfil da classe RENDA_FIXA — Tesouro Direto (etapa 11, D5/D8).

Gramática do código de tese: ``TD-<SIGLA>-<ANO>`` (ex.: TD-IPCA-2035). A sigla
identifica a FAMÍLIA do título e o ano identifica o vencimento; a resolução
ano -> ``data_vencimento`` concreta é do serviço do Tesouro (``tesouro.py``):
SELECT DISTINCT de ``data_vencimento`` (0 -> DadoNaoEncontrado; 2+ vencimentos
distintos no ano -> abstém) e ``max(data_base)`` por (tipo, vencimento) — o CSV
da STN NÃO é cronológico (reconciliação, delta 5).

MOTOR (PerfilClasse):
- coleta de ``titulos_publicos`` via ``tesouro.titulo_atual`` (taxas de
  compra/venda, PUs, SEMPRE com a Data Base; staleness 30d -> abstém) + macro
  (Selic meta, CDI, IPCA, Focus) + DERIVADAS com hedge fixo: marcação a
  mercado (variação de PU histórica em janelas 30/365d, rotulada 'variação
  passada; levado ao vencimento paga a taxa contratada') e diferencial de
  taxa vs CDI (rotulado 'comparação contemporânea, NÃO retorno esperado');
- template PRÓPRIO (``_SYSTEM_RF``): Características do título, Taxas e preços
  (com Data Base), Cenário de juros e inflação (Focus = expectativa), Camada
  geopolítica e correlações (H2 contém 'geopol' — gate D6), Síntese, Riscos
  (marcação × carrego), Fontes e Lacunas com a linha FIXA da curva DI. Se a
  tese citar a estrutura por vencimentos do Tesouro, o nome é SEMPRE 'proxy da
  curva soberana' — NUNCA 'curva DI'. SEM seção "Pares globais" (D5);
- elos (D8): co-movimento taxa×Selic mensalizada e taxa×Treasury 10y (Pearson
  não-causal, n<24 abstém) + interpretativos IPCA→IPCA+ e Focus→prefixado,
  rotulados 'expectativa'. Nenhum elo de ação vaza para cá.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Fonte, TituloPublico
from app.services import anbima_ettj, tesouro
from app.services.ativos import comum
from app.services.ativos.base import RENDA_FIXA as INFO
from app.services.correlacao import Elo, elo_co_movimento, elo_interpretativo
from app.services.dados import DadoNaoEncontrado

CLASSE = INFO.codigo

# Gramática dos códigos aceitos (D4): TD-(sigla)-(ano de 4 dígitos, 19xx/20xx).
# grupo 1 = sigla da família; grupo 2 = ano do vencimento.
TD_CODIGO_RE = re.compile(r"^TD-(PRE|PREJ|SELIC|IPCA|IPCAJ|IGPMJ|RENDA|EDUCA)-((?:19|20)\d{2})$")

# Mapa COMPLETO sigla -> 'Tipo Titulo' (nome oficial no CSV da STN,
# tesourotransparente.gov.br). Fonte de verdade única — o tesouro.py (etapa 8)
# resolve TD-código -> título com ESTE mapa; errar aqui resolveria para o
# título errado (premissa validada no recon delta 5).
SIGLA_PARA_TIPO: dict[str, str] = {
    "PRE": "Tesouro Prefixado",
    "PREJ": "Tesouro Prefixado com Juros Semestrais",
    "SELIC": "Tesouro Selic",
    "IPCA": "Tesouro IPCA+",
    "IPCAJ": "Tesouro IPCA+ com Juros Semestrais",
    "IGPMJ": "Tesouro IGPM+ com Juros Semestrais",
    "RENDA": "Tesouro Renda+ Aposentadoria Extra",
    "EDUCA": "Tesouro Educa+",
}

# Inverso 'Tipo Titulo' -> sigla. Bijeção garantida por teste (nenhum tipo
# oficial duplicado) — usado para rotular/derivar o código a partir do CSV.
TIPO_PARA_SIGLA: dict[str, str] = {tipo: sigla for sigla, tipo in SIGLA_PARA_TIPO.items()}

# Famílias indexadas à inflação e prefixadas — decidem os elos interpretativos.
_FAMILIAS_IPCA = frozenset({"IPCA", "IPCAJ"})
_FAMILIAS_PREFIXADAS = frozenset({"PRE", "PREJ"})

# Séries macro RELEVANTES para renda fixa (o helper soma as FOCUS_* por prefixo).
CODIGOS_MACRO_RF: tuple[str, ...] = (
    "SELIC_META_ANUAL",
    "IPCA_MENSAL",
    "CDI_ANUAL",
    "CDI_DIARIO",
    "GLOBAL_TREASURY_10Y",
)

# Janelas da marcação a mercado (variação PASSADA de PU) e tolerância de
# casamento de datas (~5 dias úteis em dias corridos; NUNCA interpolar).
JANELAS_MARCACAO_DIAS: tuple[int, ...] = (30, 365)
TOLERANCIA_DIAS = 7

_HEDGE_MARCACAO = (
    "variação passada do PU (marcação a mercado); levado ao vencimento, o "
    "título paga a taxa contratada"
)
_HEDGE_CARREGO = (
    "comparação contemporânea entre a taxa contratada e a taxa pós-fixada "
    "corrente — NÃO é retorno esperado"
)

_SYSTEM_RF = """\
Você é o motor de teses do "Tese AI". Monta teses de investimento ESTRUTURADAS e \
AUDITÁVEIS para TÍTULOS PÚBLICOS do Tesouro Direto (STN), em português do Brasil.

REGRAS INEGOCIÁVEIS:
1. NUNCA invente número ou fato. Todo dado factual deve vir EXCLUSIVAMENTE dos \
documentos-fonte fornecidos nesta mensagem, e cada número deve estar ancorado numa \
citação à fonte. Se um dado necessário NÃO está nos documentos, escreva \
"dado não encontrado" e siga — jamais estime ou preencha.
2. NUNCA dê recomendação de compra/venda. Proibido "compre", "venda", "trave a \
taxa", "aproveite", "vale a pena" ou qualquer diretiva ao leitor sobre comprar, \
resgatar, alocar ou carregar o título. Você ESTRUTURA o raciocínio; a decisão é \
do leitor (postura regulatória CVM).
3. SEPARE fato de interpretação. Marque o que é dado factual (citado) e o que é \
sua leitura/cenário ("interpretação:", "cenário:").
4. Taxas e preços valem NA DATA BASE: sempre mencione a Data Base ao citar taxa \
ou PU. A marcação a mercado fornecida é VARIAÇÃO PASSADA de PU — levado ao \
vencimento, o título paga a taxa contratada; nunca a apresente como retorno \
esperado. O diferencial de taxa vs CDI é comparação contemporânea, NÃO retorno \
esperado. Em títulos indexados (IPCA+/IGPM+), a taxa contratada é REAL (soma-se \
ao índice) — não a compare com taxas nominais como se fossem equivalentes.
5. Séries do Focus/BCB são EXPECTATIVA de mercado, não fato realizado — rotule-as \
exatamente como vêm no documento. Não confunda CDI/Selic diários (% a.d.) com as \
taxas anuais (% a.a.).
6. A curva DI completa NÃO está disponível (B3/ANBIMA são licenciadas). Se citar \
a estrutura de taxas do Tesouro por vencimento, chame-a SEMPRE de "proxy da curva \
soberana" — NUNCA de "curva DI".
7. A camada geopolítica e as CORRELAÇÕES são INTERPRETAÇÃO: ancore-as apenas nos \
dados fornecidos (juros, inflação, expectativas, Treasury) e NÃO afirme eventos \
específicos como fato. Use SOMENTE raciocínio condicional com hedge explícito \
("cenário:", "caso", "se houver"). Os "elos de correlação" fornecidos já vêm com \
hedge e com fontes nas duas pontas: use-os como fio condutor, sem endurecê-los.
8. NÃO há seção de pares globais para título público (abstenção estrutural).

ESTRUTURA DA SAÍDA (markdown, exatamente estas seções):
# Tese — {CODIGO} ({TITULO})
> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.
## 1. Características do título
## 2. Taxas e preços (com Data Base)
## 3. Cenário de juros e inflação
## 4. Camada geopolítica e correlações (interpretação)
## 5. Síntese
## 6. Riscos (marcação a mercado × carrego)
## 7. Fontes
## 8. Lacunas
Em "Lacunas", liste explicitamente os "dado não encontrado" e SEMPRE inclua esta \
linha fixa:
- Curva DI completa por prazo: dado não encontrado (B3/ANBIMA licenciadas; taxas \
do Tesouro prefixado por vencimento servem apenas como proxy nomeado)
"""


@dataclass(frozen=True)
class TituloRef:
    """Âncora da classe: código TD validado + família/tipo oficial STN."""

    codigo: str
    familia: str
    ano: int
    tipo: str  # nome oficial 'Tipo Titulo' do CSV da STN


# ---------------------------------------------------------------------------
# Formatação local (taxas % a.a. e PU em reais, pt-BR)
# ---------------------------------------------------------------------------
def _fmt_taxa(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + "% a.a."


def _fmt_pu(valor: float) -> str:
    return comum.fmt_por_unidade(valor, "BRL")


def _fmt_variacao(fracao: float) -> str:
    return f"{fracao * 100:+.2f}".replace(".", ",") + "%"


# ---------------------------------------------------------------------------
# PerfilClasse
# ---------------------------------------------------------------------------
def ensure_ativo(session: Session, codigo: str) -> TituloRef:
    """Valida a gramática TD-* e devolve a âncora (sem rede; a resolução do
    vencimento concreto acontece na ingestão/coleta via `tesouro`)."""
    alvo = (codigo or "").strip().upper()
    m = TD_CODIGO_RE.fullmatch(alvo)
    if m is None:
        raise DadoNaoEncontrado(f"código {alvo} não é um código TD válido — dado não encontrado")
    sigla, ano = m.group(1), int(m.group(2))
    return TituloRef(codigo=alvo, familia=sigla, ano=ano, tipo=SIGLA_PARA_TIPO[sigla])


def precisa_ingest(session: Session, ref: TituloRef, *, hoje: dt.date | None = None) -> bool:
    """Ingere quando não há leitura ATUAL do título (sem linhas OU stale >30d)
    OU quando falta o snapshot ANBIMA ETTJ do dia (dentro da janela de
    regressão aceita).

    Correção do bug "tese legada silenciosa" (2026-07-11, mesmo padrão de
    `acao.precisa_ingest`/`fii.precisa_ingest`): o snapshot ANBIMA é
    alimentado principalmente pelo job diário do scheduler
    (`scheduler._job_anbima_ettj`) — esta segunda checagem é só o FALLBACK
    on-demand para o caso raro de o job ainda não ter rodado hoje."""
    try:
        titulo_stale = tesouro.titulo_atual(session, ref.familia, ref.ano, hoje) is None
    except DadoNaoEncontrado:
        titulo_stale = True
    if titulo_stale:
        return True
    return not anbima_ettj.snapshot_recente(session, hoje=hoje)


def ingest(session: Session, ref: TituloRef) -> None:
    """Ingestão da classe com falha ISOLADA por passo (padrão orquestração)."""
    from app.services import orquestracao

    orquestracao.ingest_renda_fixa_completo(session, ref.familia, ref.ano)


def nome_ativo(ref: TituloRef) -> str:
    return f"{ref.tipo} {ref.ano}"


def system_prompt(_ref: TituloRef) -> str:
    return _SYSTEM_RF


def ancora_elos(ref: TituloRef) -> tuple[object | None, str | None]:
    """Título público não tem empresa: âncora do elo é o código TD."""
    return None, ref.codigo


def _serie_titulo(session: Session, tipo: str, vencimento: dt.date) -> list[TituloPublico]:
    """Linhas persistidas do título, ascendentes por data_base."""
    return list(
        session.execute(
            select(TituloPublico)
            .where(
                TituloPublico.tipo == tipo,
                TituloPublico.data_vencimento == vencimento,
            )
            .order_by(TituloPublico.data_base)
        )
        .scalars()
        .all()
    )


def _pu_mais_proximo(
    linhas: list[TituloPublico], alvo: dt.date, tolerancia_dias: int = TOLERANCIA_DIAS
) -> TituloPublico | None:
    """Linha com PU de venda cuja data_base é a MAIS PRÓXIMA do alvo, dentro da
    tolerância (~5 dias úteis). NUNCA interpola: fora da tolerância -> None.

    PU = 0 é AUSÊNCIA (convenção STN, achado M1: título fora da janela de
    venda), não preço: fica fora dos candidatos — senão o 0 "mais próximo"
    mataria uma janela que um PU válido vizinho (dentro da tolerância) atende.
    """
    candidatos = [ln for ln in linhas if ln.pu_venda is not None and float(ln.pu_venda) > 0]
    if not candidatos:
        return None
    melhor = min(candidatos, key=lambda ln: abs((ln.data_base - alvo).days))
    if abs((melhor.data_base - alvo).days) > tolerancia_dias:
        return None
    return melhor


def _docs_marcacao(
    session: Session, ref: TituloRef, atual: dict, linhas: list[TituloPublico]
) -> list[tuple[Fonte, str]]:
    """Derivada 1 — marcação a mercado: variação de PU de venda nas janelas.

    Janela sem par de PUs casável (±tolerância, sem interpolação) é ABSTIDA em
    silêncio honesto: a variação simplesmente não aparece (nunca é estimada).
    """
    docs: list[tuple[Fonte, str]] = []
    pu_atual = atual.get("pu_venda")
    if pu_atual is None:
        return docs
    fonte = session.get(Fonte, atual["fonte_id"]) if atual.get("fonte_id") else None
    if fonte is None:
        return docs
    for janela in JANELAS_MARCACAO_DIAS:
        alvo = atual["data_base"] - dt.timedelta(days=janela)
        antiga = _pu_mais_proximo(linhas, alvo)
        if antiga is None or float(antiga.pu_venda) <= 0:
            continue
        if antiga.data_base >= atual["data_base"]:
            continue
        variacao = float(pu_atual) / float(antiga.pu_venda) - 1.0
        texto = (
            f"Derivada (marcação a mercado) de {ref.tipo} {ref.ano} ({ref.codigo}): "
            f"variação do PU de venda em ~{janela} dias = {_fmt_variacao(variacao)} "
            f"(de {_fmt_pu(float(antiga.pu_venda))} na Data Base {antiga.data_base} "
            f"para {_fmt_pu(float(pu_atual))} na Data Base {atual['data_base']}). "
            f"ATENÇÃO: {_HEDGE_MARCACAO}."
        )
        docs.append((fonte, texto))
    return docs


def _doc_carrego(
    session: Session, ref: TituloRef, atual: dict, macro: dict
) -> tuple[Fonte, str] | None:
    """Derivada 2 — diferencial taxa contratada vs CDI a.a. (SGS 4389).

    Abstém se falta taxa/CDI ou se as datas-base divergem além da tolerância
    (~5 dias úteis) — comparar leituras de momentos diferentes seria número
    enganoso COM fonte.
    """
    taxa = atual.get("taxa_compra") if atual.get("taxa_compra") is not None else None
    rotulo_taxa = "taxa de compra"
    if taxa is None:
        taxa = atual.get("taxa_venda")
        rotulo_taxa = "taxa de venda"
    cdi = macro.get("CDI_ANUAL")
    if taxa is None or cdi is None:
        return None
    if abs((atual["data_base"] - cdi["data"]).days) > TOLERANCIA_DIAS:
        return None
    fonte = session.get(Fonte, atual["fonte_id"]) if atual.get("fonte_id") else None
    if fonte is None:
        return None
    diferencial = float(taxa) - float(cdi["valor"])
    ressalva_real = (
        " Em título indexado, a taxa contratada é REAL (soma-se ao índice); o CDI é "
        "nominal — a diferença não é equivalência."
        if ref.familia in _FAMILIAS_IPCA or ref.familia == "IGPMJ"
        else ""
    )
    pp = f"{diferencial:+.2f}".replace(".", ",")
    texto = (
        f"Derivada (diferencial de taxa) de {ref.tipo} {ref.ano} ({ref.codigo}): "
        f"{rotulo_taxa} {_fmt_taxa(float(taxa))} (Data Base {atual['data_base']}) − "
        f"CDI anualizado {_fmt_taxa(float(cdi['valor']))} (referência {cdi['data']}) = "
        f"{pp} pontos percentuais. "
        f"ATENÇÃO: {_HEDGE_CARREGO}.{ressalva_real}"
    )
    return (fonte, texto)


def coletar(
    session: Session, ref: TituloRef, *, hoje: dt.date | None = None
) -> list[tuple[Fonte, str]]:
    """(fonte, fato) do título ATUAL + derivadas com hedge + macro relevante.

    `titulo_atual` já aplica max(Data Base) por título e o corte de staleness
    (30d): título fora de oferta -> abstenção TOTAL (DadoNaoEncontrado — número
    velho nunca sai como atual).
    """
    atual = tesouro.titulo_atual(session, ref.familia, ref.ano, hoje)
    if atual is None:
        raise DadoNaoEncontrado(
            f"{ref.codigo}: Data Base mais recente além do corte de staleness "
            f"(título fora de oferta) — dado não encontrado"
        )
    fonte = session.get(Fonte, atual["fonte_id"]) if atual.get("fonte_id") else None
    if fonte is None:
        raise DadoNaoEncontrado(f"{ref.codigo}: leitura sem fonte — dado não encontrado")

    itens: list[tuple[Fonte, str]] = []
    taxas = []
    if atual.get("taxa_compra") is not None:
        taxas.append(f"taxa de compra {_fmt_taxa(float(atual['taxa_compra']))}")
    if atual.get("taxa_venda") is not None:
        taxas.append(f"taxa de venda {_fmt_taxa(float(atual['taxa_venda']))}")
    pus = []
    if atual.get("pu_compra") is not None:
        pus.append(f"PU de compra {_fmt_pu(float(atual['pu_compra']))}")
    if atual.get("pu_venda") is not None:
        pus.append(f"PU de venda {_fmt_pu(float(atual['pu_venda']))}")
    if atual.get("pu_base") is not None:
        pus.append(f"PU base {_fmt_pu(float(atual['pu_base']))}")
    texto = (
        f"Título público {ref.tipo} ({ref.codigo}), vencimento em "
        f"{atual['data_vencimento']:%d/%m/%Y} — STN/Tesouro Transparente, "
        f"Data Base {atual['data_base']}: "
        f"{'; '.join(taxas) if taxas else 'taxas: dado não encontrado'}; "
        f"{'; '.join(pus) if pus else 'PUs: dado não encontrado'}."
    )
    itens.append((fonte, texto))

    macro = comum.ultimo_ponto_macro(session, CODIGOS_MACRO_RF)
    linhas = _serie_titulo(session, ref.tipo, atual["data_vencimento"])
    itens.extend(_docs_marcacao(session, ref, atual, linhas))
    carrego = _doc_carrego(session, ref, atual, macro)
    if carrego is not None:
        itens.append(carrego)

    itens.extend(comum.coletar_macro_docs(session, CODIGOS_MACRO_RF))
    return itens


# ---------------------------------------------------------------------------
# Elos da classe (D8) — PUROS + coletor de contexto
# ---------------------------------------------------------------------------
def montar_elos_rf(contexto: dict) -> list[Elo]:
    """Elos do perfil RENDA_FIXA. PURA (testável offline).

    `contexto` = {
        "familia": sigla TD, "codigo": 'TD-IPCA-2035',
        "titulo_fonte_id": fonte da leitura atual do título (ou None),
        "macro": {codigo: {"valor","data","fonte_id"}},
        "series": {"TAXA_TITULO": [(date,val)...],
                    "SELIC_META_ANUAL": [...], "GLOBAL_TREASURY_10Y": [...]},
    }
    - co-movimento taxa do título × Selic mensalizada (n<24 abstém);
    - co-movimento taxa do título × Treasury 10y (n<24 abstém);
    - interpretativo IPCA→IPCA+ (famílias IPCA/IPCAJ) rotulado 'expectativa';
    - interpretativo Focus→prefixado (famílias PRE/PREJ) rotulado 'expectativa'.
    Fonte nas DUAS pontas sempre; nenhum elo de ação (câmbio→receita) existe aqui.
    """
    macro = contexto.get("macro") or {}
    series = contexto.get("series") or {}
    familia = (contexto.get("familia") or "").upper()
    fonte_titulo = contexto.get("titulo_fonte_id")
    if fonte_titulo is None:
        return []
    rotulo_titulo = f"Taxa do título Tesouro Direto ({contexto.get('codigo', 'TD')}, % a.a., STN)"
    serie_taxa = series.get("TAXA_TITULO") or []
    elos: list[Elo] = []

    for codigo_macro, rotulo_macro_serie, dimensao in (
        ("SELIC_META_ANUAL", "Meta Selic (% a.a.)", "co_movimento_taxa_selic"),
        (
            "GLOBAL_TREASURY_10Y",
            "Juro do Tesouro EUA 10a (% a.a.)",
            "co_movimento_taxa_treasury10y",
        ),
    ):
        fonte_macro = (macro.get(codigo_macro) or {}).get("fonte_id")
        serie_m = series.get(codigo_macro) or []
        if fonte_macro is None or not serie_taxa or not serie_m:
            continue
        elo = elo_co_movimento(
            dimensao,
            (rotulo_titulo, fonte_titulo),
            (rotulo_macro_serie, fonte_macro),
            serie_taxa,
            serie_m,
        )
        if elo is not None:  # n<MIN_N ou variância nula -> abstém
            elos.append(elo)

    fonte_ipca = (macro.get("IPCA_MENSAL") or {}).get("fonte_id")
    if familia in _FAMILIAS_IPCA and fonte_ipca is not None:
        elos.append(
            elo_interpretativo(
                "ipca→titulo_indexado (expectativa)",
                ("IPCA - variação mensal (% a.m.)", fonte_ipca),
                (rotulo_titulo, fonte_titulo),
                ligacao_causal=(
                    "cenário: a dinâmica do IPCA e as EXPECTATIVAS de inflação "
                    "influenciam a taxa real exigida do título indexado; a inflação "
                    "implícita (prefixado × IPCA+) não é calculável aqui — "
                    "vencimentos não coincidem (dado não encontrado)"
                ),
                hedge=(
                    "expectativa/condicional — expectativa de mercado não é fato "
                    "realizado; sem número de inflação implícita"
                ),
            )
        )

    fonte_focus = next(
        (
            (macro[cod] or {}).get("fonte_id")
            for cod in sorted(macro)
            if cod.startswith("FOCUS_SELIC")
        ),
        None,
    )
    if familia in _FAMILIAS_PREFIXADAS and fonte_focus is not None:
        elos.append(
            elo_interpretativo(
                "focus→prefixado (expectativa)",
                ("Expectativa de mercado Focus/BCB — mediana Selic", fonte_focus),
                (rotulo_titulo, fonte_titulo),
                ligacao_causal=(
                    "cenário: a EXPECTATIVA de Selic do Focus influencia a taxa "
                    "prefixada exigida — revisões de expectativa tendem a mover a "
                    "taxa do título antes do fato realizado"
                ),
                hedge=(
                    "expectativa de mercado (Focus/BCB), não fato realizado; "
                    "condicional — a taxa efetiva depende do prêmio de prazo"
                ),
            )
        )

    return [e for e in elos if e.validada]


def coletar_contexto(session: Session, ref: TituloRef, *, hoje: dt.date | None = None) -> dict:
    """Contexto do grafo RF a partir do banco (título + Selic/Treasury/Focus)."""
    try:
        atual = tesouro.titulo_atual(session, ref.familia, ref.ano, hoje)
    except DadoNaoEncontrado:
        atual = None
    serie_taxa: list[tuple[dt.date, float]] = []
    if atual is not None:
        for ln in _serie_titulo(session, ref.tipo, atual["data_vencimento"]):
            # M1: taxa 0 no CSV da STN = "não ofertado" (ausência), não é
            # observação de mercado — fora da série do co-movimento. Taxa
            # NEGATIVA é legítima (ágio do Tesouro Selic) e segue entrando.
            taxa = next(
                (
                    float(t)
                    for t in (ln.taxa_venda, ln.taxa_compra)
                    if t is not None and float(t) != 0.0
                ),
                None,
            )
            if taxa is not None:
                serie_taxa.append((ln.data_base, taxa))
    return {
        "familia": ref.familia,
        "codigo": ref.codigo,
        "titulo_fonte_id": atual["fonte_id"] if atual is not None else None,
        "macro": comum.ultimo_ponto_macro(session, CODIGOS_MACRO_RF),
        "series": {
            "TAXA_TITULO": serie_taxa,
            "SELIC_META_ANUAL": comum.serie_macro(session, "SELIC_META_ANUAL"),
            "GLOBAL_TREASURY_10Y": comum.serie_macro(session, "GLOBAL_TREASURY_10Y"),
        },
    }


def montar_elos(session: Session, ref: TituloRef) -> list[Elo]:
    return montar_elos_rf(coletar_contexto(session, ref))


__all__ = [
    "CLASSE",
    "CODIGOS_MACRO_RF",
    "INFO",
    "SIGLA_PARA_TIPO",
    "TD_CODIGO_RE",
    "TIPO_PARA_SIGLA",
    "TituloRef",
    "ancora_elos",
    "coletar",
    "coletar_contexto",
    "ensure_ativo",
    "ingest",
    "montar_elos",
    "montar_elos_rf",
    "nome_ativo",
    "precisa_ingest",
    "system_prompt",
]
