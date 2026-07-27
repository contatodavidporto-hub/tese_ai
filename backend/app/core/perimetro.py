"""Perímetro X-Portaria entre o BFF (Vercel) e o backend (Railway).

O Railway é público: um access token roubado poderia ser reproduzido DIRETO no
FastAPI, pulando o rate-limit e a contenção do BFF. O BFF assina toda chamada com
um header `X-Portaria` (segredo compartilhado); o backend recusa quem não o traz.

FAIL-CLOSED em produção (correção do red-team): sem `PORTARIA_SECRET`, a app **não
sobe** (`verificar_perimetro_no_startup`). Em dev/test (sem o segredo), o middleware
é no-op — nunca um `if secret:` silencioso que desliga o perímetro num deploy com env
faltando. `compare_digest` evita timing na comparação.
"""

from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings

# Caminhos isentos (liveness da plataforma): o healthcheck do Railway não manda o header.
_ISENTOS = frozenset({"/health"})


def verificar_perimetro_no_startup(settings: Settings) -> None:
    """Aborta o startup se, EM PRODUÇÃO, o segredo do perímetro estiver ausente."""
    if settings.app_env.strip().lower() == "production" and not settings.portaria_secret:
        raise RuntimeError(
            "PORTARIA_SECRET ausente em produção — perímetro fail-closed (a app não sobe)."
        )


class PerimetroMiddleware(BaseHTTPMiddleware):
    """Exige `X-Portaria` quando o segredo está configurado. No-op sem segredo."""

    def __init__(self, app, *, settings: Settings) -> None:  # noqa: ANN001
        super().__init__(app)
        self._secret = settings.portaria_secret

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if self._secret and request.url.path not in _ISENTOS:
            recebido = request.headers.get("x-portaria", "")
            if not hmac.compare_digest(recebido, self._secret):
                return JSONResponse({"detail": "perímetro"}, status_code=403)
        return await call_next(request)
