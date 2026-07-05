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
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class BodySizeLimitMiddleware:
    """Rejeita corpos acima do teto (defesa contra payloads gigantes / DoS).

    ASGI puro. Além do fast-path pelo header Content-Length, o corpo é lido AQUI
    (bufferizado até o teto) antes de invocar o app: um corpo `Transfer-Encoding:
    chunked` não declara tamanho, e uma exceção lançada de dentro do `receive()`
    seria engolida por camadas internas (o parse de body do FastAPI converte
    qualquer falha em 400). Ler-e-reproduzir é a via confiável; o custo de memória
    é limitado pelo próprio teto (default 64 KiB).
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self._max = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        chunked = False
        for nome, valor in scope.get("headers") or []:
            if nome == b"content-length":
                try:
                    if int(valor) > self._max:
                        await self._responder(scope, send, 413, "corpo da requisição grande demais")
                        return
                except ValueError:
                    await self._responder(scope, send, 400, "content-length inválido")
                    return
            elif nome == b"transfer-encoding":
                chunked = True

        # Só é preciso ler-e-reproduzir quando o corpo NÃO declara tamanho
        # (chunked). Com Content-Length o servidor (h11/httptools) já rejeita
        # corpo que exceda o declarado; e sem corpo nenhum, entrar no loop de
        # leitura seguraria a conexão à espera de um corpo que nunca vem.
        if not chunked:
            await self.app(scope, receive, send)
            return

        mensagens: list[Message] = []
        recebido = 0
        while True:
            mensagem = await receive()
            mensagens.append(mensagem)
            if mensagem["type"] != "http.request":
                break  # http.disconnect: reproduz e deixa o app tratar
            recebido += len(mensagem.get("body", b"") or b"")
            if recebido > self._max:
                await self._responder(scope, send, 413, "corpo da requisição grande demais")
                return
            if not mensagem.get("more_body"):
                break

        fila = iter(mensagens)

        async def receive_replay() -> Message:
            try:
                return next(fila)
            except StopIteration:
                return await receive()

        await self.app(scope, receive_replay, send)

    @staticmethod
    async def _responder(scope: Scope, send: Send, status: int, detail: str) -> None:
        resposta = JSONResponse({"detail": detail}, status_code=status, headers=_SECURITY_HEADERS)
        await resposta(scope, _receive_vazio, send)


async def _receive_vazio() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", app_env=settings.app_env)
    get_langfuse()  # inicializa observabilidade (no-op se não configurada)
    yield
    logger.info("app_shutdown")


# Superfície mínima em produção: /docs, /redoc e /openapi.json ficam desligados
# (produto ainda sem login; a spec é reconstruível do código quando necessário).
_em_producao = settings.app_env.strip().lower() == "production"
app = FastAPI(
    title="Tese AI — Backend",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _em_producao else "/docs",
    redoc_url=None if _em_producao else "/redoc",
    openapi_url=None if _em_producao else "/openapi.json",
)

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
@limiter.exempt
def health() -> dict[str, str]:
    """Liveness check. Não toca no banco — sempre responde se a app está de pé.

    Isento do rate-limit global: atrás de um edge-proxy o tráfego pode compartilhar
    o IP visto pelo processo, e um pico de 429 não pode derrubar o healthcheck da
    plataforma (que reiniciaria um serviço saudável).
    """
    return {"status": "ok"}


app.include_router(teses_router.router)
