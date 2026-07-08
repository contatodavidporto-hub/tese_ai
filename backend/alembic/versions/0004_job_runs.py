"""ledger de jobs agendados (scheduler in-app)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07

Migração ADITIVA: cria só a tabela `job_runs` (ledger do scheduler in-app,
decisão do conselho na fase "produção-ready"). A cadência dos jobs é decidida
contra `last_run_at` no banco (não por timer em memória), então restart/deploy
não zera o relógio e o catch-up é automático.

RLS ON **sem policy** (deny-all): a tabela é exclusiva do backend (conexão de
owner/service_role, que bypassa RLS) — mesmo desenho do `alembic_version`.
Nenhum cliente (anon/authenticated) precisa ler ou escrever aqui.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
create table if not exists job_runs (
    job_name        text primary key,
    last_run_at     timestamptz not null,
    last_status     text,
    detalhe         text,
    atualizado_em   timestamptz not null default now()
);

alter table job_runs enable row level security;

comment on table job_runs is
  'Ledger do scheduler in-app: última execução por job (cadência por relógio de parede; deny-all — só o backend acessa).';
"""

DOWNGRADE_SQL = """
drop table if exists job_runs;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
