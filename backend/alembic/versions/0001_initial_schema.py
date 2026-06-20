"""schema inicial — empresas, fundamentos, macro, eventos, teses, fontes, documentos, chunks[vector] + RLS

Revision ID: 0001
Revises:
Create Date: 2026-06-20

Tabelas de referência (empresas, fontes, fundamentos, macro_series,
eventos_geopoliticos): RLS ON, leitura para `authenticated`.
Tabelas de dados do usuário (teses, tese_versoes, documentos, chunks):
RLS ON, acesso owner-only via `auth.uid() = user_id`. `service_role`
(backend) ignora RLS por padrão.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
create extension if not exists vector;

-- ---------- Referência (compartilhada) ----------
create table empresas (
    id          uuid primary key default gen_random_uuid(),
    cd_cvm      integer unique,
    cnpj        text unique,
    ticker      text,
    nome        text not null,
    setor       text,
    criado_em   timestamptz not null default now()
);
create index ix_empresas_ticker on empresas (ticker);

create table fontes (
    id            uuid primary key default gen_random_uuid(),
    url           text,
    descricao     text not null,
    dt_referencia date,
    criado_em     timestamptz not null default now()
);

create table fundamentos (
    id          uuid primary key default gen_random_uuid(),
    empresa_id  uuid not null references empresas (id) on delete cascade,
    conta       text not null,
    valor       numeric,
    dt_refer    date not null,
    fonte_id    uuid references fontes (id),
    criado_em   timestamptz not null default now()
);
create index ix_fundamentos_empresa on fundamentos (empresa_id);
create index ix_fundamentos_dt_refer on fundamentos (dt_refer);

create table macro_series (
    id          uuid primary key default gen_random_uuid(),
    codigo      text not null,
    data        date not null,
    valor       numeric,
    fonte_id    uuid references fontes (id),
    criado_em   timestamptz not null default now(),
    unique (codigo, data)
);
create index ix_macro_series_codigo on macro_series (codigo);

create table eventos_geopoliticos (
    id              uuid primary key default gen_random_uuid(),
    data            date not null,
    descricao       text not null,
    ativos_afetados text[],
    fonte_id        uuid references fontes (id),
    criado_em       timestamptz not null default now()
);
create index ix_eventos_data on eventos_geopoliticos (data);

-- ---------- Dados do usuário (multi-tenant) ----------
create table teses (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    ticker      text not null,
    status      text not null default 'processing',
    criado_em   timestamptz not null default now()
);
create index ix_teses_user on teses (user_id);

create table tese_versoes (
    id          uuid primary key default gen_random_uuid(),
    tese_id     uuid not null references teses (id) on delete cascade,
    user_id     uuid not null references auth.users (id) on delete cascade,
    conteudo    text,
    modelo      text,
    prompt_hash text,
    criado_em   timestamptz not null default now()
);
create index ix_tese_versoes_tese on tese_versoes (tese_id);

create table documentos (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references auth.users (id) on delete cascade,
    tenant_id   uuid,
    titulo      text,
    url         text,
    fonte_id    uuid references fontes (id),
    criado_em   timestamptz not null default now()
);
create index ix_documentos_user on documentos (user_id);

create table chunks (
    id              uuid primary key default gen_random_uuid(),
    documento_id    uuid not null references documentos (id) on delete cascade,
    user_id         uuid references auth.users (id) on delete cascade,
    tenant_id       uuid,
    texto           text not null,
    embedding       vector(1536),
    criado_em       timestamptz not null default now()
);
create index ix_chunks_documento on chunks (documento_id);
create index ix_chunks_user on chunks (user_id);
create index ix_chunks_embedding on chunks using hnsw (embedding vector_cosine_ops);

-- ---------- RLS: referência (leitura para authenticated) ----------
alter table empresas             enable row level security;
alter table fontes               enable row level security;
alter table fundamentos          enable row level security;
alter table macro_series         enable row level security;
alter table eventos_geopoliticos enable row level security;

create policy "ref_read_empresas"    on empresas             for select to authenticated using (true);
create policy "ref_read_fontes"      on fontes               for select to authenticated using (true);
create policy "ref_read_fundamentos" on fundamentos          for select to authenticated using (true);
create policy "ref_read_macro"       on macro_series         for select to authenticated using (true);
create policy "ref_read_eventos"     on eventos_geopoliticos for select to authenticated using (true);

-- ---------- RLS: dados do usuário (owner-only) ----------
alter table teses        enable row level security;
alter table tese_versoes enable row level security;
alter table documentos   enable row level security;
alter table chunks       enable row level security;

create policy "owner_all_teses" on teses for all to authenticated
    using ((select auth.uid()) is not null and (select auth.uid()) = user_id)
    with check ((select auth.uid()) is not null and (select auth.uid()) = user_id);

create policy "owner_all_tese_versoes" on tese_versoes for all to authenticated
    using ((select auth.uid()) is not null and (select auth.uid()) = user_id)
    with check ((select auth.uid()) is not null and (select auth.uid()) = user_id);

create policy "owner_all_documentos" on documentos for all to authenticated
    using ((select auth.uid()) is not null and (select auth.uid()) = user_id)
    with check ((select auth.uid()) is not null and (select auth.uid()) = user_id);

create policy "owner_all_chunks" on chunks for all to authenticated
    using ((select auth.uid()) is not null and (select auth.uid()) = user_id)
    with check ((select auth.uid()) is not null and (select auth.uid()) = user_id);
"""

DOWNGRADE_SQL = """
drop table if exists chunks cascade;
drop table if exists documentos cascade;
drop table if exists tese_versoes cascade;
drop table if exists teses cascade;
drop table if exists eventos_geopoliticos cascade;
drop table if exists macro_series cascade;
drop table if exists fundamentos cascade;
drop table if exists fontes cascade;
drop table if exists empresas cascade;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
