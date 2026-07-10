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
