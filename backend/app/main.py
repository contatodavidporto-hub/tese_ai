"""Entrypoint da API FastAPI."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import limiter
from app.observability.langfuse_client import get_langfuse
from app.routers import teses as teses_router

settings = get_settings()
configure_logging(settings.app_env)
logger = get_logger(__name__)


# Headers de segurança em TODA resposta da API (defesa em profundidade — o frontend
# já os tem, mas a API pode ser chamada diretamente). Sem CSP aqui: a API responde
# JSON, não HTML; nosniff + DENY + no-store cobrem o vetor.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in _SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejeita corpos acima do teto (defesa contra payloads gigantes / DoS)."""

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self._max = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > self._max:
                    return JSONResponse(
                        {"detail": "corpo da requisição grande demais"}, status_code=413
                    )
            except ValueError:
                return JSONResponse({"detail": "content-length inválido"}, status_code=400)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", app_env=settings.app_env)
    get_langfuse()  # inicializa observabilidade (no-op se não configurada)
    yield
    logger.info("app_shutdown")


app = FastAPI(title="Tese AI — Backend", version="0.1.0", lifespan=lifespan)

# Rate limiting (slowapi): registra o limiter e o handler de 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Ordem importa: middlewares adicionados por último rodam primeiro. Body-size antes
# de tudo (barra payload gigante cedo); headers de segurança envolvem a resposta.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)

# CORS explícito: só as origens configuradas, métodos e headers ESTRITOS (não '*').
# Com credentials=True, o wildcard seria inseguro e inválido pelo próprio spec.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Não toca no banco — sempre responde se a app está de pé."""
    return {"status": "ok"}


app.include_router(teses_router.router)
