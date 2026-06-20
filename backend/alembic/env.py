"""Ambiente do Alembic.

A URL do banco vem de `app.core.config` (.env). O engine é criado direto a
partir dela (sem interpolação do .ini), evitando problemas com `%` em senhas.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models.models  # noqa: F401 — registra os modelos no metadata
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata


def _require_url() -> str:
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL não configurado. Preencha o .env (Session pooler do Supabase) "
            "antes de rodar 'alembic upgrade head'."
        )
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_require_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_require_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
