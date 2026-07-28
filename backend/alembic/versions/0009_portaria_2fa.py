"""Portaria (2FA) — cofre de códigos de recuperação (deny-all), helper aal2
(SECURITY DEFINER) e step-up: dado privado do usuário com 2FA exige aal2

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-28

Onda 3 da missão "A Portaria". APLICADA POR ÚLTIMO (depois do fluxo de MFA no ar e da
virada de role da Onda 1): uma policy restrictive de aal2 que erra = negação TOTAL, então
o helper é SECURITY DEFINER à prova de erro e a leitura pública tem escape explícito.

- `codigos_recuperacao`: cofre dos códigos de recuperação de 2FA. RLS ON, ZERO policies
  (deny-all) — nenhum cliente (anon/authenticated) toca; só o FastAPI, pela conexão de
  sistema (postgres, bypassrls), escopando por user_id do JWT VERIFICADO. Os códigos são
  hasheados NA APLICAÇÃO (SHA-256 de 80 bits CSPRNG) — o plaintext nunca entra em SQL/log.
- `public.tem_fator_totp_verified(uid)`: SECURITY DEFINER (dono postgres, search_path='')
  porque `authenticated` NÃO lê `auth.mfa_factors` (provado ao vivo). Usada na policy E no
  `exigir_aal2` do FastAPI — nunca ler `auth.mfa_factors` direto de uma policy.
- Policies restrictive de step-up em teses/tese_versoes/elos/documentos/chunks: quem tem
  fator TOTP verificado só acessa o PRÓPRIO dado privado com sessão aal2. ESCAPE: linha
  pública (`visibilidade='publica'`) nunca é gateada — a vitrine não quebra para logado
  aal1. `app_worker`/`anon` não são atingidos (policy `to authenticated`).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabelas de dado do usuário que ganham o step-up aal2 (as owner-only da 0001).
_TABELAS_AAL2 = ["teses", "tese_versoes", "elos", "documentos", "chunks"]


def _policy_aal2(tabela: str) -> str:
    # `visibilidade='publica'` só existe em teses/tese_versoes/elos — nas outras a
    # coluna não há, então o escape só entra onde faz sentido (as demais são 100%
    # privadas). Lê o aal do GUC das claims (mesmo padrão do auth.uid()).
    tem_visibilidade = tabela in ("teses", "tese_versoes", "elos")
    escape_publica = "visibilidade = 'publica' or " if tem_visibilidade else ""
    return f"""
    create policy aal2_{tabela} on public.{tabela} as restrictive to authenticated
      using (
        {escape_publica}
        not public.tem_fator_totp_verified((select auth.uid()))
        or coalesce(
             nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'aal',
             'aal1'
           ) = 'aal2'
      );
    """


UPGRADE_SQL = (
    r"""
-- ---------- Cofre dos códigos de recuperação (deny-all: só o FastAPI/sistema) ----------
create table if not exists codigos_recuperacao (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references auth.users (id) on delete cascade,
    codigo_hash   bytea not null unique,   -- sha256(codigo) calculado NA APLICAÇÃO
    lote          uuid not null,           -- regerar = novo lote (apaga o anterior)
    criado_em     timestamptz not null default now(),
    usado_em      timestamptz
);
create index if not exists ix_codigos_recuperacao_ativos
    on codigos_recuperacao (user_id) where usado_em is null;
alter table codigos_recuperacao enable row level security;  -- ZERO policies = deny-all

-- ---------- Helper aal2: lê auth.mfa_factors com privilégio do dono (SECURITY DEFINER) ----------
create or replace function public.tem_fator_totp_verified(uid uuid)
  returns boolean language sql stable security definer set search_path = '' as $$
    select exists (
      select 1 from auth.mfa_factors
      where user_id = uid and status = 'verified' and factor_type = 'totp'
    )
$$;
revoke all on function public.tem_fator_totp_verified(uuid) from public, anon;
grant execute on function public.tem_fator_totp_verified(uuid) to authenticated;

-- ---------- Step-up aal2 (restrictive; POR ÚLTIMO) ----------
"""
    + "\n".join(_policy_aal2(t) for t in _TABELAS_AAL2)
)


DOWNGRADE_SQL = (
    "\n".join(f"drop policy if exists aal2_{t} on public.{t};" for t in _TABELAS_AAL2)
    + r"""
drop function if exists public.tem_fator_totp_verified(uuid);
drop table if exists codigos_recuperacao;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
