"""Lane de RLS ENFORÇADA (missão "A Portaria").

O caminho de dados do usuário para de bypassar a RLS: um segundo engine
(`engine_rls`) conecta como o role de login `app_backend` (LOGIN, NOINHERIT,
**NOBYPASSRLS**) e, a CADA transação, estampa `SET LOCAL ROLE <lane>` +
`set_config('request.jwt.claims', …)` num listener `after_begin`. Assim
`auth.uid()` resolve e as policies owner-only passam a valer de verdade.

Lanes (whitelist FECHADA — o nome do role nunca vem de input):
- `user`   -> `SET LOCAL ROLE authenticated` + claims completas do JWT verificado
- `anon`   -> `SET LOCAL ROLE anon` (vitrine pública; nunca impersona um usuário)
- `worker` -> `SET LOCAL ROLE app_worker` (jobs de geração/warm-cache/reaper; acesso
  pleno via policies `worker_all_*`, sem bypassrls)

FAIL-CLOSED: transação numa sessão RLS sem lane definida levanta erro (nunca roda
como `app_backend` puro, que não tem policy nenhuma). `SET LOCAL` morre no COMMIT e a
geração comita várias vezes — por isso o carimbo é no `after_begin` (re-dispara a cada
transação), nunca uma vez no início da request.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import Identidade, usuario_atual, usuario_opcional
from app.core.config import get_settings

# Mapa FECHADO lane -> role Postgres. Interpolar o role no SQL é seguro SÓ porque
# vem daqui (constantes), nunca de input do cliente.
_LANE_ROLE = {"user": "authenticated", "anon": "anon", "worker": "app_worker"}


class RlsSemEscopo(RuntimeError):
    """Sessão RLS sem lane definida — fail-closed (nunca roda sem escopo)."""


def comandos_rls(lane: str | None, claims_json: str | None) -> list[tuple[str, tuple[Any, ...]]]:
    """SQL a executar no início de cada transação da lane. Função PURA (testável).

    Levanta `RlsSemEscopo` para lane ausente/desconhecida (fail-closed). Para a lane
    `user`, exige as claims (o `set_config` é SEMPRE parametrizado — nunca f-string).
    """
    if lane not in _LANE_ROLE:
        raise RlsSemEscopo(f"lane RLS inválida ou ausente: {lane!r}")
    role = _LANE_ROLE[lane]
    cmds: list[tuple[str, tuple[Any, ...]]] = [(f"set local role {role}", ())]
    if lane == "user":
        if not claims_json:
            raise RlsSemEscopo("lane 'user' sem claims — fail-closed")
        cmds.append(("select set_config('request.jwt.claims', %s, true)", (claims_json,)))
    return cmds


def _criar_engine():
    s = get_settings()
    if not s.database_url_rls:
        return None
    # Pools pequenos: dois engines (sistema + rls) somam contra o limite do Supavisor
    # no plano Free. pool_pre_ping evita conexão morta do pooler.
    return create_engine(s.database_url_rls, pool_pre_ping=True, pool_size=5, max_overflow=2)


engine_rls = _criar_engine()

# expire_on_commit=False: 1 request/job = 1 sessão = 1 identidade (nunca reusar objeto
# carregado sob uma identidade dentro da sessão de outra).
SessionRLS = (
    sessionmaker(bind=engine_rls, autoflush=False, autocommit=False, expire_on_commit=False)
    if engine_rls is not None
    else None
)


@event.listens_for(Session, "after_begin")
def _estampar_rls(session: Session, transaction, connection) -> None:  # noqa: ANN001
    """Re-arma role+claims a CADA transação de uma sessão RLS. No-op fora da lane."""
    lane = session.info.get("rls_lane")
    if lane is None:
        return  # sessão de sistema/SQLite (sem lane) — não é uma sessão RLS
    for sql, params in comandos_rls(lane, session.info.get("rls_claims")):
        connection.exec_driver_sql(sql, params)


def _nova_sessao(lane: str, claims_json: str | None = None) -> Session:
    if SessionRLS is None:
        raise RuntimeError("DATABASE_URL_RLS não configurado — lane de RLS indisponível.")
    session = SessionRLS()
    session.info["rls_lane"] = lane
    if claims_json is not None:
        session.info["rls_claims"] = claims_json
    return session


def get_session_usuario(
    identidade: Annotated[Identidade, Depends(usuario_atual)],
) -> Generator[Session, None, None]:
    """Dependency: sessão na lane `authenticated`, com as claims do JWT verificado."""
    session = _nova_sessao("user", json.dumps(identidade.claims_rls()))
    try:
        yield session
    finally:
        session.close()


def get_session_anon() -> Generator[Session, None, None]:
    """Dependency: sessão na lane `anon` (vitrine pública; sem impersonar usuário)."""
    session = _nova_sessao("anon")
    try:
        yield session
    finally:
        session.close()


def get_session_leitura(request: Request) -> Generator[Session, None, None]:
    """Dependency de LEITURA público-ou-do-dono: lane `user` se há Bearer válido,
    senão lane `anon`. Preserva a vitrine 100% pública (anônimo lê o acervo) e deixa
    o dono ler a própria tese privada — a RLS filtra o resto (o filtro explícito no
    router é a camada B)."""
    identidade = usuario_opcional(request)
    if identidade is not None:
        session = _nova_sessao("user", json.dumps(identidade.claims_rls()))
    else:
        session = _nova_sessao("anon")
    try:
        yield session
    finally:
        session.close()


@contextmanager
def nova_sessao_worker() -> Generator[Session, None, None]:
    """Sessão na lane `app_worker` para jobs (geração/warm-cache/reaper). Server-side."""
    session = _nova_sessao("worker")
    try:
        yield session
    finally:
        session.close()
