"""Portaria (Onda 4 — remediação) — menor-privilégio de grants (LIVE-1) e
FORCE RLS no cofre/backup (LIVE-3)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-28

Remediação dos achados de DB da Onda 4 (ataque + ASVS — docs/portaria/06-onda4-ataque-asvs.md):

- LIVE-1 (MÉDIO): o schema `public` do Supabase concede `GRANT ALL` default a
  anon/authenticated em TODA tabela (inclui `TRUNCATE`, que NÃO passa por RLS). A 0007
  concedeu grants ESTREITOS, mas não REVOGOU o default — então o efetivo em produção é
  `ALL`. Aqui revogamos tudo de anon/authenticated e reconcedemos só o mínimo (idêntico
  ao intento da 0007). É cinto (RLS) + suspensório (grant de menor-privilégio).
- LIVE-3 (BAIXO / defesa-em-profundidade): FORCE RLS no cofre `codigos_recuperacao` e no
  backup `_portaria_backup_demo`. Honestidade: o dono das tabelas é `postgres`, que tem
  `bypassrls`, e é por essa conexão de sistema que o FastAPI acessa o cofre — então o FORCE
  é INERTE para o app (não protege nem quebra nada hoje). Só passa a valer se um dono
  não-bypassrls existir. `alembic_version` fica DE FORA de propósito (ledger de migração
  lido pela conexão de sistema).

Compatível com o CI (`rls-isolation`, Postgres puro): lá a 0007 já concedeu estreito, então
o REVOKE tira o estreito e o re-grant o repõe — net-zero. O ALL default só existe no Supabase.
O app conecta como `app_backend` (nobypassrls) e faz `SET LOCAL ROLE` para anon/authenticated/
app_worker; os grants de `app_worker` (0007) NÃO são tocados aqui.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- ---------- LIVE-1: menor-privilégio de grants para anon/authenticated ----------
-- Remove o GRANT ALL default do Supabase (inclui TRUNCATE/TRIGGER/REFERENCES) e o
-- estreito da 0007; em seguida reconcede APENAS o mínimo necessário a cada lane.
revoke all on all tables in schema public from anon, authenticated;

-- anon: só leitura pública do acervo (a RLS `*_publica` filtra as linhas).
grant select on teses, tese_versoes, elos to anon;

-- authenticated: CRUD nas tabelas de usuário (a RLS owner/aal2 filtra as linhas).
grant select, insert, update, delete on teses, tese_versoes, elos to authenticated;
grant select, insert, update, delete on historico_itens to authenticated;

-- Novas tabelas não devem herdar ALL para anon/authenticated. Revoga o default DESTE
-- grantor (postgres) — best-effort: se o default do Supabase foi setado por outro
-- grantor (supabase_admin), este comando não o alcança, mas o revoke acima já limpou
-- as tabelas existentes; tabelas futuras devem nascer com grant explícito na migração.
alter default privileges in schema public revoke all on tables from anon, authenticated;

-- ---------- LIVE-3: FORCE RLS no cofre e no backup (defesa em profundidade) ----------
-- Inerte hoje (dono = postgres, bypassrls), mas fecha a lacuna caso um dono
-- não-bypassrls venha a existir. NÃO tocar alembic_version.
alter table codigos_recuperacao force row level security;
alter table _portaria_backup_demo force row level security;
"""


DOWNGRADE_SQL = r"""
-- Reverte o FORCE (volta ao enable-only da 0008/0009).
alter table _portaria_backup_demo no force row level security;
alter table codigos_recuperacao no force row level security;

-- Reversão fiel do menor-privilégio: restaura o grant amplo anterior a anon/authenticated.
alter default privileges in schema public grant all on tables to anon, authenticated;
grant all on all tables in schema public to anon, authenticated;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
