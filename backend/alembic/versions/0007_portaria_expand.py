"""Portaria (expand) — acervo do sistema (user_id NULL + visibilidade), RLS enforçada
por lanes, cache de conteúdo worker-only, histórico por usuário, fim do vazamento de elos

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-27

Missão "A Portaria" — a virada do modelo de confiança. EXPAND (aditiva e reversível;
o backfill dos 314 do demo vem na 0008). Convive com o código atual: as colunas novas
têm default seguro ('privada') e os CHECKs entram NOT VALID (só validam linhas novas)
até a 0008 normalizar o acervo.

Desenho (ADR `docs/portaria/02-adrs.md`, ratificado por red-team):
- `teses`/`tese_versoes`/`elos` ganham `visibilidade` e `user_id` NULLABLE. NULL =
  acervo do SISTEMA (público); preenchido = privada do dono. CHECK amarra
  `(user_id IS NULL) = (visibilidade='publica')`.
- `elos` para de ser world-readable a qualquer `authenticated` (vazava fragmentos de
  tese): a leitura passa a ser pública-ou-do-dono (denormalizado; sem join por linha).
- Lanes de RLS SEM bypassrls: o role de login `app_backend` (criado FORA daqui, com
  senha out-of-band) faz `SET LOCAL ROLE authenticated|anon|app_worker`. `app_worker`
  (NOLOGIN) é a lane dos jobs (geração/warm-cache/reaper) e recebe acesso pleno via
  `worker_all_*` (um por tabela, montado por loop) — a geração escreve tabelas de
  REFERÊNCIA (fontes) e é negada sob `authenticated`, então roda na lane worker.
- `tese_cache_conteudo` worker-only (RLS ON, policy só p/ app_worker): invisível a
  anon/authenticated. `historico_itens` owner-only.
- Restrictive: `authenticated` NUNCA insere tese pública.
- FORCE RLS nas tabelas do usuário (um ALTER por tabela — multi-tabela é inválido).

⚠ O role de LOGIN `app_backend` e sua senha NÃO entram aqui (hook protect-secrets;
segredo out-of-band). O humano cria `app_backend` e faz `GRANT anon, authenticated,
app_worker TO app_backend` no SQL editor (ver docs/portaria + escalonamentos).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- ---------- Lane worker (NOLOGIN; acesso pleno via policies, NUNCA bypassrls) ----------
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_worker') then
    create role app_worker nologin;
  end if;
end $$;
grant usage on schema public to app_worker;
grant select, insert, update, delete on all tables in schema public to app_worker;
grant usage, select on all sequences in schema public to app_worker;
alter default privileges in schema public grant select, insert, update, delete on tables to app_worker;
alter default privileges in schema public grant usage, select on sequences to app_worker;

-- ---------- Colunas: acervo do sistema (user_id NULL) + visibilidade ----------
alter table teses alter column user_id drop not null;
alter table teses add column if not exists visibilidade text not null default 'privada'
  check (visibilidade in ('publica','privada'));
alter table teses add constraint ck_teses_publica_sistema
  check ((user_id is null) = (visibilidade = 'publica')) not valid;

alter table tese_versoes alter column user_id drop not null;
alter table tese_versoes add column if not exists visibilidade text not null default 'privada'
  check (visibilidade in ('publica','privada'));
alter table tese_versoes add constraint ck_versoes_publica_sistema
  check ((user_id is null) = (visibilidade = 'publica')) not valid;

alter table elos add column if not exists user_id uuid references auth.users (id) on delete cascade;
alter table elos add column if not exists visibilidade text not null default 'privada'
  check (visibilidade in ('publica','privada'));
alter table elos add constraint ck_elos_publica_sistema
  check ((user_id is null) = (visibilidade = 'publica')) not valid;

-- ---------- Índices (parciais: caminho do cache) ----------
create index if not exists ix_teses_publica_cache on teses (ticker, criado_em desc)
  where visibilidade = 'publica' and status = 'ready';
create index if not exists ix_teses_user_ticker on teses (user_id, ticker, criado_em desc)
  where visibilidade = 'privada';
create index if not exists ix_elos_user on elos (user_id);

-- ---------- Histórico/favoritos por usuário (owner-only) ----------
create table if not exists historico_itens (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    tese_id     uuid not null references teses (id) on delete cascade,
    origem      text not null default 'gerada' check (origem in ('gerada','favoritada')),
    favorito    boolean not null default false,
    criado_em   timestamptz not null default now(),
    unique (user_id, tese_id)
);
create index if not exists ix_historico_user on historico_itens (user_id);
alter table historico_itens enable row level security;
create policy historico_owner on historico_itens for all to authenticated
    using ((select auth.uid()) is not null and (select auth.uid()) = user_id)
    with check ((select auth.uid()) is not null and (select auth.uid()) = user_id);

-- ---------- Cache de CONTEÚDO (worker-only; invisível a anon/authenticated) ----------
create table if not exists tese_cache_conteudo (
    id            uuid primary key default gen_random_uuid(),
    ticker        varchar(32) not null,
    classe_ativo  text,
    prompt_hash   text not null,
    conteudo      text not null,
    criado_em     timestamptz not null default now(),
    unique (ticker, prompt_hash)
);
alter table tese_cache_conteudo enable row level security;

-- ---------- elos: fecha o vazamento (era `using(true)` a qualquer authenticated) ----------
drop policy if exists "ref_read_elos" on elos;
create policy elos_publica on elos for select to anon, authenticated
    using (visibilidade = 'publica');
create policy elos_owner on elos for select to authenticated
    using ((select auth.uid()) is not null and (select auth.uid()) = user_id);

-- ---------- Leitura pública do acervo (anon + authenticated, só visibilidade='publica') ----------
create policy teses_publica on teses for select to anon, authenticated
    using (visibilidade = 'publica');
create policy versoes_publica on tese_versoes for select to anon, authenticated
    using (visibilidade = 'publica');

-- ---------- Cinto-e-suspensório: authenticated NUNCA cria tese pública ----------
create policy teses_so_privada on teses as restrictive for insert to authenticated
    with check (visibilidade = 'privada');
create policy versoes_so_privada on tese_versoes as restrictive for insert to authenticated
    with check (visibilidade = 'privada');

-- ---------- Lane worker: acesso pleno por policy (um worker_all_<t> por tabela) ----------
-- A geração escreve REFERÊNCIA (fontes) + USUÁRIO (teses/versões/elos); sob authenticated
-- os INSERTs de referência são negados. app_worker (NOBYPASSRLS) recebe policy `for all`
-- em toda tabela do schema, exceto o ledger de migração.
do $$
declare t text;
begin
  for t in
    select tablename from pg_tables
    where schemaname = 'public' and tablename <> 'alembic_version'
  loop
    execute format('drop policy if exists %I on public.%I', 'worker_all_' || t, t);
    execute format(
      'create policy %I on public.%I for all to app_worker using (true) with check (true)',
      'worker_all_' || t, t
    );
  end loop;
end $$;

-- ---------- Grants explícitos (RLS != grant; o GRANT é o portão grosso, a policy decide
-- QUAIS linhas). No Supabase, anon/authenticated já têm esses grants por padrão; num
-- Postgres puro (CI) não — sem eles, o INSERT do dono nem chega na policy (42501). ----------
grant select on teses, tese_versoes, elos to anon;
grant select, insert, update, delete on teses, tese_versoes, elos to authenticated;
grant select, insert, update, delete on historico_itens to authenticated;

-- ---------- FORCE RLS (um ALTER por tabela) ----------
alter table teses force row level security;
alter table tese_versoes force row level security;
alter table elos force row level security;
alter table documentos force row level security;
alter table chunks force row level security;
alter table historico_itens force row level security;
alter table tese_cache_conteudo force row level security;
"""


DOWNGRADE_SQL = r"""
alter table teses no force row level security;
alter table tese_versoes no force row level security;
alter table elos no force row level security;
alter table documentos no force row level security;
alter table chunks no force row level security;
alter table historico_itens no force row level security;
alter table tese_cache_conteudo no force row level security;

do $$
declare t text;
begin
  for t in
    select tablename from pg_tables
    where schemaname = 'public' and tablename <> 'alembic_version'
  loop
    execute format('drop policy if exists %I on public.%I', 'worker_all_' || t, t);
  end loop;
end $$;

drop policy if exists versoes_so_privada on tese_versoes;
drop policy if exists teses_so_privada on teses;
drop policy if exists versoes_publica on tese_versoes;
drop policy if exists teses_publica on teses;
drop policy if exists elos_owner on elos;
drop policy if exists elos_publica on elos;
create policy "ref_read_elos" on elos for select to authenticated using (true);

drop table if exists tese_cache_conteudo;
drop policy if exists historico_owner on historico_itens;
drop table if exists historico_itens;

drop index if exists ix_elos_user;
drop index if exists ix_teses_user_ticker;
drop index if exists ix_teses_publica_cache;

alter table elos drop constraint if exists ck_elos_publica_sistema;
alter table elos drop column if exists visibilidade;
alter table elos drop column if exists user_id;
alter table tese_versoes drop constraint if exists ck_versoes_publica_sistema;
alter table tese_versoes drop column if exists visibilidade;
alter table tese_versoes alter column user_id set not null;
alter table teses drop constraint if exists ck_teses_publica_sistema;
alter table teses drop column if exists visibilidade;
alter table teses alter column user_id set not null;

-- app_worker: revoga e derruba (default privileges primeiro).
alter default privileges in schema public revoke select, insert, update, delete on tables from app_worker;
alter default privileges in schema public revoke usage, select on sequences from app_worker;
revoke all on all tables in schema public from app_worker;
revoke all on all sequences in schema public from app_worker;
revoke usage on schema public from app_worker;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'app_worker') then
    drop role app_worker;
  end if;
end $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
