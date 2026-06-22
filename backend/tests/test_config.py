"""Testes da normalização do DATABASE_URL (garante o driver psycopg v3)."""

from __future__ import annotations

from app.core.config import Settings


def test_database_url_postgresql_scheme_coerced() -> None:
    s = Settings(database_url="postgresql://u:p@h:5432/db")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/db"


def test_database_url_postgres_scheme_coerced() -> None:
    s = Settings(database_url="postgres://u:p@h:5432/db")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/db"


def test_database_url_psycopg_unchanged() -> None:
    s = Settings(database_url="postgresql+psycopg://u:p@h/db")
    assert s.database_url == "postgresql+psycopg://u:p@h/db"
