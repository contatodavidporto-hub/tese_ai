"""Contratos da API do motor de tese.

A saída é desenhada para a **auditabilidade**: cada citação aponta para uma
fonte (URL + data), e a UI consegue tornar cada afirmação clicável. `lacunas`
expõe as abstenções ("dado não encontrado") em vez de escondê-las.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field, field_validator


class TeseCreateIn(BaseModel):
    # União de formatos aceitos (D4 — Fase 2 multiativo):
    # - ticker B3: raiz de 4 alfanuméricos iniciada por letra + 1-2 dígitos + sufixo
    #   'B' opcional (balcão) — cobre ações, units e cotas de FII (PETR4, SANB11,
    #   HGLG11);
    # - código do Tesouro Direto: gramática TD-<SIGLA>-<ANO> (ex.: TD-IPCA-2035).
    # Validar o FORMATO reduz a superfície de entrada (defesa em profundidade —
    # a autoridade final é o resolvedor por classe: ativos.identidade + cadastros).
    ticker: str = Field(..., min_length=4, max_length=16, examples=["PETR4", "TD-IPCA-2035"])

    @field_validator("ticker")
    @classmethod
    def _normalizar_e_validar(cls, v: str) -> str:
        import re

        # Import local: fonte ÚNICA da gramática TD (sem acoplar o módulo de
        # schemas ao pacote de serviços no import-time).
        from app.services.ativos.renda_fixa import TD_CODIGO_RE

        alvo = (v or "").strip().upper()
        if re.fullmatch(r"[A-Z][A-Z0-9]{3}[0-9]{1,2}B?", alvo) or TD_CODIGO_RE.fullmatch(alvo):
            return alvo
        raise ValueError(
            "ticker inválido (esperado formato B3, ex.: PETR4, ou código do "
            "Tesouro Direto, ex.: TD-IPCA-2035)"
        )


class TeseCreateOut(BaseModel):
    id: uuid.UUID
    ticker: str
    status: str  # processing | ready | error


class FonteOut(BaseModel):
    id: uuid.UUID | None = None
    url: str | None = None
    descricao: str
    dt_referencia: dt.date | None = None


class CitacaoOut(BaseModel):
    """Âncora de citação devolvida pela Anthropic Citations.

    `document_index` referencia o documento-fonte enviado ao modelo; mapeamos
    para `fonte` para que a UI abra a fonte exata do trecho citado.
    """

    texto_citado: str
    document_index: int | None = None
    titulo_documento: str | None = None
    fonte: FonteOut | None = None


class UsoOut(BaseModel):
    modelo: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    custo_estimado_usd: float | None = None


class FonteRefOut(BaseModel):
    """Referência de fonte dos 5 blocos novos (contrato v3) — mais enxuta que
    `FonteOut`: sem `id` (cita a origem do DADO — B3/CVM/BCB/ANEEL/ANBIMA —,
    não uma linha do registro de fontes da tese)."""

    descricao: str
    url: str | None = None
    dt_referencia: dt.date | None = None


# --- 1. Gráficos --------------------------------------------------------------


class PontoGraficoOut(BaseModel):
    d: str
    v: float


class PontoFaixaGraficoOut(BaseModel):
    d: str
    sup: float
    inf: float


class SerieGraficoOut(BaseModel):
    nome: str
    pontos: list[PontoGraficoOut] = Field(default_factory=list)


class FaixaGraficoOut(BaseModel):
    nome: str
    pontos: list[PontoFaixaGraficoOut] = Field(default_factory=list)


class LinhaRefGraficoOut(BaseModel):
    nome: str
    valor: float


class GraficoOut(BaseModel):
    id: str
    tipo: str  # "linha" | "linha_faixa" | "macd" | "oscilador"
    titulo: str
    ticker: str
    eixo_y: str  # "BRL" | "indice" | "pct"
    nota: str
    fonte: FonteRefOut
    series: list[SerieGraficoOut] = Field(default_factory=list)
    faixa: FaixaGraficoOut | None = None
    linhas_ref: list[LinhaRefGraficoOut] = Field(default_factory=list)


# --- 2. Técnica -----------------------------------------------------------


class IndicadorTecnicoOut(BaseModel):
    nome: str
    valor: float | None = None
    unidade: str  # "indice" | "BRL" | "pct"
    detalhe: str | None = None
    o_que_mede: str
    leitura: str


class TecnicaOut(BaseModel):
    nota: str
    fonte: FonteRefOut
    indicadores: list[IndicadorTecnicoOut] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)


# --- 3. Valuation -----------------------------------------------------------


class PremissaValuationOut(BaseModel):
    nome: str
    valor: str  # já formatado pt-BR — a UI só exibe
    origem: str
    rotulo: str  # "fato" | "premissa" | "aproximação"


class CenarioValuationOut(BaseModel):
    nome: str  # "conservador" | "base" | "otimista"
    parametros: str
    valor: float | None = None
    unidade: str
    omitido: str | None = None


class FaixaValuationOut(BaseModel):
    min: float
    max: float
    unidade: str


class SensibilidadeValuationOut(BaseModel):
    eixo_linhas: str
    eixo_colunas: str
    linhas: list[str] = Field(default_factory=list)
    colunas: list[str] = Field(default_factory=list)
    celulas: list[list[float | None]] = Field(default_factory=list)


class ModeloValuationOut(BaseModel):
    nome: str
    descricao: str
    premissas: list[PremissaValuationOut] = Field(default_factory=list)
    cenarios: list[CenarioValuationOut] = Field(default_factory=list)
    faixa: FaixaValuationOut | None = None
    sensibilidade: SensibilidadeValuationOut | None = None
    omitido: str | None = None


class ValuationOut(BaseModel):
    aviso: str
    modelos: list[ModeloValuationOut] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)


# --- 4. Consenso --------------------------------------------------------------


class ItemConsensoOut(BaseModel):
    casa: str | None = None
    metrica: str  # "preco_alvo"
    valor: float
    moeda: str
    veiculo: str
    url: str
    titulo: str
    data_materia: str | None = None
    data_busca: str


class ConsensoOut(BaseModel):
    aviso: str
    itens: list[ItemConsensoOut] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)


# --- 5. Métricas do setor ------------------------------------------------------


class MetricaSetorOut(BaseModel):
    nome: str
    valor: float | None = None
    unidade: str  # "pct" | "BRL" | "razao" | "x"
    formula: str
    o_que_mede: str
    implicacao: str
    fontes: list[FonteRefOut] = Field(default_factory=list)
    rotulos: list[str] = Field(default_factory=list)
    lacuna: str | None = None


class TeseOut(BaseModel):
    id: uuid.UUID
    ticker: str
    status: str
    # Classe do ativo ('acao'|'fii'|'renda_fixa'); None = ação (legado — NULL no
    # banco significa 'acao', migração 0005) ou tese anterior à Fase 2. Aditivo.
    classe_ativo: str | None = None
    criado_em: dt.datetime | None = None
    # Disclaimer regulatório fixo — nunca é recomendação de compra/venda.
    aviso: str = (
        "Não é recomendação de investimento. Tese estruturada a partir de "
        "dados públicos; a decisão é do leitor."
    )
    markdown: str | None = None
    citacoes: list[CitacaoOut] = Field(default_factory=list)
    fontes: list[FonteOut] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    uso: UsoOut | None = None
    erro: str | None = None
    # Blocos novos ("Tese Profunda", contrato-envelope-v3.md) — ADITIVOS e
    # opcionais: ausência = tese legada válida (default_factory/None). O
    # router (fail-closed) NÃO os preenche em status=error/gate bloqueado.
    graficos: list[GraficoOut] = Field(default_factory=list)
    tecnica: TecnicaOut | None = None
    valuation: ValuationOut | None = None
    consenso: ConsensoOut | None = None
    metricas_setor: list[MetricaSetorOut] = Field(default_factory=list)
