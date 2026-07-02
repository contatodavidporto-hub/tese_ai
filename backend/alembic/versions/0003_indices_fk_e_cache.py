"""índices de FK (performance) + suporte a cache/reaper de teses

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02

Migração ADITIVA (só cria índices — não altera dados nem tabelas). Motivada por
dois eixos da Fase 2 (organização de dados + performance):

1. **Índices de foreign key** — o Supabase advisor (performance) apontou 11 FKs
   sem índice de cobertura. Sem eles, um `DELETE`/`UPDATE` na tabela-pai varre a
   filha inteira e os JOINs por `fonte_id` (procedência/auditoria) ficam lentos.
   Todas as FKs `fonte_id` + as três FKs de `elos` + `tese_versoes.user_id`.

2. **Suporte ao cache/idempotência e ao reaper** — índices em `teses` para:
   - `(ticker, status, criado_em desc)`: achar a última tese `ready` pública de um
     ticker em O(log n) (cache — reaproveita em vez de regenerar via LLM);
   - `(status, criado_em)`: o reaper varrer teses `processing` órfãs (crash no meio
     da geração) sem full scan.

Idempotente (`create index if not exists`), aplicável a quente (não bloqueia).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
-- ---------- Índices de FK (procedência/auditoria + integridade referencial) ----------
create index if not exists ix_fundamentos_fonte_id        on fundamentos (fonte_id);
create index if not exists ix_macro_series_fonte_id       on macro_series (fonte_id);
create index if not exists ix_eventos_geopoliticos_fonte  on eventos_geopoliticos (fonte_id);
create index if not exists ix_cvm_cadastro_fonte_id       on cvm_cadastro (fonte_id);
create index if not exists ix_pares_fonte_id              on pares (fonte_id);
create index if not exists ix_pares_fundamentos_fonte_id  on pares_fundamentos (fonte_id);
create index if not exists ix_documentos_fonte_id         on documentos (fonte_id);
create index if not exists ix_elos_origem_fonte_id        on elos (origem_fonte_id);
create index if not exists ix_elos_destino_fonte_id       on elos (destino_fonte_id);
create index if not exists ix_elos_tese_versao_id         on elos (tese_versao_id);
create index if not exists ix_tese_versoes_user_id        on tese_versoes (user_id);

-- ---------- Suporte a cache de tese pública + reaper de órfãs ----------
create index if not exists ix_teses_ticker_status_criado  on teses (ticker, status, criado_em desc);
create index if not exists ix_teses_status_criado         on teses (status, criado_em);
"""

DOWNGRADE_SQL = """
drop index if exists ix_teses_status_criado;
drop index if exists ix_teses_ticker_status_criado;
drop index if exists ix_tese_versoes_user_id;
drop index if exists ix_elos_tese_versao_id;
drop index if exists ix_elos_destino_fonte_id;
drop index if exists ix_elos_origem_fonte_id;
drop index if exists ix_documentos_fonte_id;
drop index if exists ix_pares_fundamentos_fonte_id;
drop index if exists ix_pares_fonte_id;
drop index if exists ix_cvm_cadastro_fonte_id;
drop index if exists ix_eventos_geopoliticos_fonte;
drop index if exists ix_macro_series_fonte_id;
drop index if exists ix_fundamentos_fonte_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
