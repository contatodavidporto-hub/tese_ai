"""Prova COMPORTAMENTAL de isolamento da RLS entre dois usuários (o P0 nº 2 da
Fortaleza — RLS enforçada de verdade, não lint textual do SQL).

Roda contra um Postgres REAL (marker `rls`): pula sem `TEST_PG_URL`. No CI, um service
container `pgvector/pgvector:pg17`; para prova ao vivo, um branch efêmero do Supabase
(onde o schema `auth` e os roles já existem — o bootstrap abaixo é idempotente).

Estratégia: bootstrap idempotente (schema `auth`, `auth.users`, `auth.uid()`/`auth.role()`
VERBATIM da produção — a definição lê o GUC legado `request.jwt.claim.sub` PRIMEIRO —,
roles `anon`/`authenticated`/`service_role`), `alembic upgrade head` num subprocesso, e
consultas sob cada lane via `SET LOCAL ROLE` + `set_config('request.jwt.claims', …)` —
exatamente o que `app/db/rls.py` faz em produção.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.rls

TEST_PG_URL = os.environ.get("TEST_PG_URL")

if not TEST_PG_URL:
    pytest.skip(
        "TEST_PG_URL ausente — prova de RLS só roda contra Postgres real", allow_module_level=True
    )

import psycopg  # noqa: E402  (só importa quando a prova vai rodar)

_BACKEND = pathlib.Path(__file__).resolve().parents[1]

# auth.uid()/auth.role() copiados VERBATIM de auth.uid()/auth.role() da produção
# (pg_get_functiondef, 2026-07-27): coalesce lê o GUC legado 'request.jwt.claim.sub'
# ANTES de 'request.jwt.claims'->>'sub'. Redigitar divergente aprovaria policy que
# reprova em produção — por isso é cópia fiel.
_BOOTSTRAP = r"""
create schema if not exists auth;
create table if not exists auth.users (
    id uuid primary key default gen_random_uuid(),
    email text unique
);
create or replace function auth.uid() returns uuid language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;
create or replace function auth.role() returns text language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;
do $$
declare r text;
begin
  foreach r in array array['anon', 'authenticated', 'service_role'] loop
    if not exists (select 1 from pg_roles where rolname = r) then
      execute format('create role %I nologin', r);
    end if;
  end loop;
end $$;
grant usage on schema public to anon, authenticated, service_role;
grant usage on schema auth to anon, authenticated, service_role;
grant select on auth.users to anon, authenticated, service_role;
"""

A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"


def _run_alembic() -> None:
    env = dict(os.environ, DATABASE_URL=TEST_PG_URL)
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"alembic upgrade head falhou:\n{proc.stdout}\n{proc.stderr}")


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(TEST_PG_URL, autocommit=True) as c:
        c.execute(_BOOTSTRAP)
    _run_alembic()
    with psycopg.connect(TEST_PG_URL, autocommit=False) as c:
        # Usuários e teses de referência (como owner/postgres — bypassa RLS no SETUP).
        c.execute(
            "insert into auth.users (id, email) values (%s,'a@t'),(%s,'b@t') "
            "on conflict do nothing",
            (A, B),
        )
        c.commit()
        yield c


def _lane(cur, role: str, sub: str | None) -> None:
    cur.execute(f"set local role {role}")
    if sub is not None:
        cur.execute(
            "select set_config('request.jwt.claims', %s, true)",
            (json.dumps({"sub": sub, "role": "authenticated"}),),
        )


def _as(conn, role: str, sub: str | None, sql: str, params=()):
    """Roda uma consulta sob a lane (transação isolada, sempre revertida)."""
    cur = conn.cursor()
    try:
        _lane(cur, role, sub)
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else None
    finally:
        conn.rollback()


def _commit_as(conn, role: str, sub: str | None, sql: str, params=()):
    cur = conn.cursor()
    _lane(cur, role, sub)
    cur.execute(sql, params)
    row = cur.fetchone() if cur.description else None
    conn.commit()
    return row


def test_isolamento_cross_tenant(conn) -> None:
    # A cria a PRÓPRIA tese privada (owner_all WITH CHECK: auth.uid()=user_id).
    tese_a = _commit_as(
        conn,
        "authenticated",
        A,
        "insert into teses (user_id, visibilidade, ticker, status) "
        "values (%s,'privada','PETR4','ready') returning id",
        (A,),
    )[0]
    # Worker cria uma tese PÚBLICA do sistema (user_id NULL).
    tese_pub = _commit_as(
        conn,
        "app_worker",
        None,
        "insert into teses (user_id, visibilidade, ticker, status) "
        "values (null,'publica','VALE3','ready') returning id",
    )[0]

    # 1) B não enxerga a tese privada de A — nem por id (IDOR morto).
    assert _as(conn, "authenticated", B, "select count(*) from teses where id=%s", (tese_a,)) == [
        (0,)
    ]
    # 2) B não lista nenhuma privada de A.
    vis_b = _as(conn, "authenticated", B, "select count(*) from teses where visibilidade='privada'")
    assert vis_b == [(0,)]
    # 3) anon não enxerga privada; 4) anon ENXERGA a pública (vitrine).
    assert _as(conn, "anon", None, "select count(*) from teses where id=%s", (tese_a,)) == [(0,)]
    assert _as(conn, "anon", None, "select count(*) from teses where id=%s", (tese_pub,)) == [(1,)]
    # 5) A enxerga a própria.
    assert _as(conn, "authenticated", A, "select count(*) from teses where id=%s", (tese_a,)) == [
        (1,)
    ]


def test_with_check_barra_forja_de_dono(conn) -> None:
    # B tenta forjar user_id=A: WITH CHECK (auth.uid()=user_id) recusa.
    with pytest.raises(psycopg.errors.Error):
        _commit_as(
            conn,
            "authenticated",
            B,
            "insert into teses (user_id, visibilidade, ticker, status) "
            "values (%s,'privada','ITUB4','ready')",
            (A,),
        )
    conn.rollback()


def test_restrictive_barra_publica_por_authenticated(conn) -> None:
    # authenticated NUNCA cria tese pública (policy restrictive teses_so_privada).
    with pytest.raises(psycopg.errors.Error):
        _commit_as(
            conn,
            "authenticated",
            A,
            "insert into teses (user_id, visibilidade, ticker, status) "
            "values (null,'publica','BBAS3','ready')",
        )
    conn.rollback()


def test_elos_nao_vazam_fragmento_de_tese(conn) -> None:
    # Elo privado de A (denormalizado) — invisível a B; elo público — visível a anon.
    _commit_as(
        conn,
        "app_worker",
        None,
        "insert into elos (empresa_id, origem_label, destino_label, user_id, visibilidade) "
        "values (null,'o','d',%s,'privada')",
        (A,),
    )
    _commit_as(
        conn,
        "app_worker",
        None,
        "insert into elos (empresa_id, origem_label, destino_label, user_id, visibilidade) "
        "values (null,'o','d',null,'publica')",
    )
    # B não vê o elo privado de A; anon vê o público, não o privado.
    assert _as(conn, "authenticated", B, "select count(*) from elos where user_id=%s", (A,)) == [
        (0,)
    ]
    assert _as(conn, "anon", None, "select count(*) from elos where visibilidade='publica'") == [
        (1,)
    ]
    assert _as(conn, "anon", None, "select count(*) from elos where visibilidade='privada'") == [
        (0,)
    ]
