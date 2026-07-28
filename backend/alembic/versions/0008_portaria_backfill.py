"""Portaria (backfill) — converte o acervo do demo_user em dados do SISTEMA (públicos)
e valida os CHECKs de coerência

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-27

CONTRACT-lite: move as teses/versões/elos do usuário-demo para o acervo do sistema
(`user_id = NULL`, `visibilidade = 'publica'`) e VALIDA os CHECKs que a 0007 criou
`NOT VALID`. Idempotente e seguro num banco vazio (CI): se não houver dono, não faz nada.

⚠ ORDEM FATAL (red-team): rode isto SÓ depois que o código SEM `demo_user` já estiver
no ar — um processo antigo do Railway com o `lru_cache` do demo recriaria o usuário e
gravaria teses nele DEPOIS do backfill. A exclusão do próprio `auth.users` do demo é um
passo OPERACIONAL posterior (script `aposentar_demo_user.py`), nunca esta migração
(a FK ON DELETE CASCADE apagaria as 314 teses se o delete viesse antes do backfill).

Resolução do dono: pelo ÚNICO `user_id` distinto existente em `teses` (empiricamente o
demo; independe do e-mail configurado). Se houver >1 dono, ABORTA (estado inesperado).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- Backup reversível (deny-all: RLS ON sem policy).
create table if not exists _portaria_backup_demo (
    tabela          text not null,
    linha_id        uuid not null,
    user_id_anterior uuid not null,
    migrado_em      timestamptz not null default now(),
    primary key (tabela, linha_id)
);
alter table _portaria_backup_demo enable row level security;

do $$
declare v_demo uuid; v_owners int;
begin
  select count(distinct user_id) into v_owners from teses where user_id is not null;
  if v_owners = 0 then
    return;  -- banco vazio (CI) ou já migrado: nada a fazer
  end if;
  if v_owners > 1 then
    raise exception 'backfill 0008: esperava 1 dono (demo), encontrou % — abortando', v_owners;
  end if;
  select distinct user_id into v_demo from teses where user_id is not null;

  insert into _portaria_backup_demo (tabela, linha_id, user_id_anterior)
    select 'teses', id, user_id from teses where user_id = v_demo
    on conflict (tabela, linha_id) do nothing;
  insert into _portaria_backup_demo (tabela, linha_id, user_id_anterior)
    select 'tese_versoes', id, user_id from tese_versoes where user_id = v_demo
    on conflict (tabela, linha_id) do nothing;

  -- elos: pelas versões do demo (antes de anular tese_versoes.user_id) + órfãos.
  update elos e set user_id = null, visibilidade = 'publica'
    from tese_versoes tv where tv.id = e.tese_versao_id and tv.user_id = v_demo;
  update elos set user_id = null, visibilidade = 'publica' where tese_versao_id is null;

  update tese_versoes set user_id = null, visibilidade = 'publica' where user_id = v_demo;
  update teses set user_id = null, visibilidade = 'publica' where user_id = v_demo;
end $$;

-- Agora que o acervo é coerente, valida os CHECKs (falha aqui = dado incoerente).
alter table teses validate constraint ck_teses_publica_sistema;
alter table tese_versoes validate constraint ck_versoes_publica_sistema;
alter table elos validate constraint ck_elos_publica_sistema;
"""


DOWNGRADE_SQL = r"""
-- Restaura o dono a partir do backup (válido só enquanto o auth.users do demo existir).
update teses t set user_id = b.user_id_anterior, visibilidade = 'privada'
  from _portaria_backup_demo b where b.tabela = 'teses' and b.linha_id = t.id;
update tese_versoes v set user_id = b.user_id_anterior, visibilidade = 'privada'
  from _portaria_backup_demo b where b.tabela = 'tese_versoes' and b.linha_id = v.id;
-- elos herdam do backup das versões (a que apontam); órfãos voltam a 'privada' sem dono.
update elos e set user_id = b.user_id_anterior, visibilidade = 'privada'
  from tese_versoes tv join _portaria_backup_demo b
    on b.tabela = 'tese_versoes' and b.linha_id = tv.id
  where tv.id = e.tese_versao_id;
drop table if exists _portaria_backup_demo;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
