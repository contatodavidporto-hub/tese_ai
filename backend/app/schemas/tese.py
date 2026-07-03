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
    # Formato de ticker B3: raiz de 4 alfanuméricos iniciada por letra + 1-2 dígitos
    # + sufixo 'B' opcional (balcão). Validar o FORMATO reduz a superfície de entrada
    # (defesa em profundidade — o resolvedor de cadastro é a autoridade final).
    ticker: str = Field(..., min_length=4, max_length=7, examples=["PETR4"])

    @field_validator("ticker")
    @classmethod
    def _normalizar_e_validar(cls, v: str) -> str:
        import re

        alvo = (v or "").strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9]{3}[0-9]{1,2}B?", alvo):
            raise ValueError("ticker inválido (formato B3 esperado, ex.: PETR4)")
        return alvo


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
