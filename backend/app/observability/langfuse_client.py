"""Observabilidade com Langfuse — stub seguro.

Retorna um cliente Langfuse real quando há credenciais no ambiente (.env);
caso contrário, retorna `None` (no-op) para que a app rode sem observabilidade.
Credenciais SEMPRE vêm de `settings` (.env) — nunca hardcoded.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_langfuse() -> Any | None:
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("langfuse_disabled", reason="missing_credentials")
        return None
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("langfuse_enabled", host=settings.langfuse_host)
        return client
    except Exception as exc:  # pragma: no cover - defensivo
        # Loga só o tipo da exceção (não o texto cru, que pode conter segredos do SDK).
        logger.warning("langfuse_init_failed", error_type=type(exc).__name__)
        return None
