"""Entrypoint da API FastAPI."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.observability.langfuse_client import get_langfuse

settings = get_settings()
configure_logging(settings.app_env)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", app_env=settings.app_env)
    get_langfuse()  # inicializa observabilidade (no-op se não configurada)
    yield
    logger.info("app_shutdown")


app = FastAPI(title="Tese AI — Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Não toca no banco — sempre responde se a app está de pé."""
    return {"status": "ok"}
