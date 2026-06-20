"""Engine e sessão do SQLAlchemy.

Se `DATABASE_URL` não estiver configurado, o engine fica `None` e a app ainda
serve `/health` (o banco não é necessário para o health check da Fundação).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = (
    create_engine(_settings.database_url, pool_pre_ping=True) if _settings.database_url else None
)

SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    if engine
    else None
)


def get_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL não configurado (.env).")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
