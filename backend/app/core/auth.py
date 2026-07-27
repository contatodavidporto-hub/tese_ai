"""Validação criptográfica do access token do GoTrue (missão "A Portaria").

O navegador nunca fala com o Supabase (CSP `connect-src 'self'`): a auth vive no
BFF (Next.js) e a identidade viaja ao FastAPI como o access token REAL do GoTrue
(`Authorization: Bearer`). Aqui o backend valida esse token LOCALMENTE contra o
JWKS público do projeto (`/auth/v1/.well-known/jwks.json`), com **allowlist ES256
explícita** — o projeto já assina assimétrico (verificado ao vivo 2026-07-27,
`kid 2220fdf2-…`, EC P-256). Nada de segredo compartilhado, nada de re-cunhar
token (o pass-through do JWT real é o que faz `request.jwt.claims` no Postgres
refletir a fonte de verdade para a RLS).

Defesas embutidas (não afrouxar):
- `algorithms=["ES256"]` EXPLÍCITO: rejeita `alg: none` e a confusão HS256 (assinar
  um token HS256 usando a chave PÚBLICA como segredo HMAC).
- `audience`/`issuer` pinados e `require: exp, sub, session_id` — token sem os
  claims estruturais é recusado antes de ser confiável.
- As claims injetadas na RLS incluem `aal`/`amr`/`session_id` (não só `sub`), senão
  qualquer policy/função que leia o nível de garantia (ex.: 2FA) falha.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Allowlist FECHADA. O projeto assina ES256 (assimétrico) — aceitar o `alg` do
# header do token abriria forja por HS256-com-chave-pública ou `alg: none`.
ALGORITMOS = ["ES256"]


@dataclass(frozen=True)
class Identidade:
    """Identidade verificada do usuário autenticado (claims do access token)."""

    user_id: str
    session_id: str
    role: str
    aal: str | None
    amr: list[Any] | None
    email: str | None
    claims: dict[str, Any]

    def claims_rls(self) -> dict[str, Any]:
        """Claims a injetar em `request.jwt.claims` para a RLS (não só o sub).

        Inclui `aal`/`amr`/`session_id` porque policies e funções de 2FA leem o
        nível de garantia; injetar só `{sub, role}` faria essas checagens falharem.
        """
        saida: dict[str, Any] = {"sub": self.user_id, "role": self.role or "authenticated"}
        if self.session_id:
            saida["session_id"] = self.session_id
        if self.aal is not None:
            saida["aal"] = self.aal
        if self.amr is not None:
            saida["amr"] = self.amr
        return saida


@lru_cache
def _jwks_client() -> PyJWKClient:
    s = get_settings()
    if not s.supabase_url:
        raise RuntimeError("SUPABASE_URL ausente — não há como validar o JWT do GoTrue.")
    url = f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    # cache_keys: guarda as chaves entre requests; PyJWKClient refaz o fetch quando
    # um `kid` desconhecido aparece (rotação futura da chave de assinatura).
    return PyJWKClient(url, cache_keys=True)


def _chave_de_assinatura(token: str):
    """Resolve a chave pública ES256 pelo `kid` do token.

    Seam de teste: os testes fazem monkeypatch daqui para injetar uma chave local,
    sem tocar a rede/JWKS.
    """
    return _jwks_client().get_signing_key_from_jwt(token).key


def _issuer() -> str:
    return f"{get_settings().supabase_url.rstrip('/')}/auth/v1"


class TokenInvalido(Exception):
    """Falha de validação do access token (mapeada para 401 na dependency)."""


def validar_token(token: str) -> Identidade:
    """Valida assinatura + claims estruturais do access token e devolve a Identidade.

    Levanta `TokenInvalido` em qualquer falha (assinatura, alg, exp, aud, iss,
    claims obrigatórios ausentes) — nunca vaza detalhe do erro ao chamador.
    """
    s = get_settings()
    try:
        chave = _chave_de_assinatura(token)
        claims = jwt.decode(
            token,
            chave,
            algorithms=ALGORITMOS,
            audience=s.supabase_jwt_audience,
            issuer=_issuer(),
            leeway=s.jwt_leeway_segundos,
            options={"require": ["exp", "sub", "session_id"]},
        )
    except jwt.PyJWTError as exc:
        # DecodeError/ExpiredSignature/InvalidAudience/InvalidIssuer/InvalidAlgorithm/
        # MissingRequiredClaim — tudo vira 401 sem revelar qual.
        logger.info("jwt_recusado", motivo=type(exc).__name__)
        raise TokenInvalido(str(exc)) from exc
    except Exception as exc:  # resolução de chave (kid desconhecido, JWKS fora): 401, não 500
        logger.info("jwt_sem_chave", motivo=type(exc).__name__)
        raise TokenInvalido("não foi possível resolver a chave de assinatura") from exc

    sub = claims.get("sub")
    session_id = claims.get("session_id")
    if not sub or not session_id:  # defesa extra além do require
        raise TokenInvalido("claims estruturais ausentes")

    return Identidade(
        user_id=str(sub),
        session_id=str(session_id),
        role=str(claims.get("role") or "authenticated"),
        aal=claims.get("aal"),
        amr=claims.get("amr"),
        email=claims.get("email"),
        claims=claims,
    )


_bearer = HTTPBearer(auto_error=True)


def usuario_atual(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Identidade:
    """Dependency FastAPI: exige um Bearer válido e devolve a Identidade.

    Guarda a identidade em `request.state.identidade` para a chave de rate-limit
    por usuário (ver `core/ratelimit`). Credencial ausente => 401 (o `HTTPBearer`
    com `auto_error=True` já barra nesta versão do FastAPI); credencial apresentada
    e inválida => 401 aqui.
    """
    try:
        identidade = validar_token(creds.credentials)
    except TokenInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    request.state.identidade = identidade
    return identidade


def usuario_opcional(request: Request) -> Identidade | None:
    """Identidade quando há Bearer válido; `None` quando ausente/ inválido.

    Para rotas que servem público E logado (a vitrine pública não pode 401 por
    falta de token). Nunca levanta — token ruim vira anônimo.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        identidade = validar_token(token)
    except TokenInvalido:
        return None
    request.state.identidade = identidade
    return identidade
