"""Schemas dos endpoints de conta (missão "A Portaria", Onda 3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecuperacaoIn(BaseModel):
    """Break-glass: código de recuperação de 2FA (formato XXXX-XXXX-…)."""

    codigo: str = Field(min_length=8, max_length=40)


class CodigosOut(BaseModel):
    codigos: list[str]


class OkOut(BaseModel):
    ok: bool
