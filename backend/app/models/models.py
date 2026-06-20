"""Modelos ORM (SQLAlchemy 2.0).

Espelham o schema aplicado pela migração `0001_initial_schema`. As colunas
`user_id` apontam para `auth.users` no Supabase (a FK é declarada no SQL da
migração, não aqui, para manter os modelos independentes do schema `auth`).

`fontes` é o coração da auditoria: todo fato persistido referencia uma fonte.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBEDDING_DIM = 1536


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    cd_cvm: Mapped[int | None] = mapped_column(Integer, unique=True)
    cnpj: Mapped[str | None] = mapped_column(String(20), unique=True)
    ticker: Mapped[str | None] = mapped_column(String(12), index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    setor: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fundamentos: Mapped[list[Fundamento]] = relationship(back_populates="empresa")


class Fonte(Base):
    """Coração da auditoria: URL + descrição + data de referência."""

    __tablename__ = "fontes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    url: Mapped[str | None] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    dt_referencia: Mapped[dt.date | None] = mapped_column(Date)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Fundamento(Base):
    __tablename__ = "fundamentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conta: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float | None] = mapped_column(Numeric)
    dt_refer: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped[Empresa] = relationship(back_populates="fundamentos")


class MacroSerie(Base):
    __tablename__ = "macro_series"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    codigo: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    data: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valor: Mapped[float | None] = mapped_column(Numeric)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EventoGeopolitico(Base):
    __tablename__ = "eventos_geopoliticos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    data: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    ativos_afetados: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Tese(Base):
    """Dado do usuário — protegido por RLS (owner-only)."""

    __tablename__ = "teses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="processing")
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    versoes: Mapped[list[TeseVersao]] = relationship(back_populates="tese")


class TeseVersao(Base):
    """Trilha de auditoria da tese (modelo + prompt_hash). RLS owner-only."""

    __tablename__ = "tese_versoes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tese_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conteudo: Mapped[str | None] = mapped_column(Text)
    modelo: Mapped[str | None] = mapped_column(Text)
    prompt_hash: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tese: Mapped[Tese] = relationship(back_populates="versoes")


class Documento(Base):
    """Documento para RAG — RLS owner-only (multi-tenant)."""

    __tablename__ = "documentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    titulo: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list[Chunk]] = relationship(back_populates="documento")


class Chunk(Base):
    """Trecho vetorizado — RLS por usuário/tenant aplicada no SELECT vetorial."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    documento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documento: Mapped[Documento] = relationship(back_populates="chunks")
