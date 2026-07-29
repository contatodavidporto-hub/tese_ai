"""Portaria (Onda 4 — remediação) — LIVE-2/MFA-04: esconde o oráculo de 2FA do PostgREST

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-29

`tem_fator_totp_verified(uuid)` é SECURITY DEFINER e vivia em `public` → o PostgREST a
expunha como `/rest/v1/rpc/tem_fator_totp_verified`, chamável por `authenticated` com um
`uid` arbitrário (oráculo BAIXO de "quem tem 2FA verificado"; achado LIVE-2/MFA-04 da
Onda 4). Não dá para revogar EXECUTE — a policy aal2 (5 tabelas) usa a função avaliando
como role `authenticated`. Fix: mover para um schema **não exposto** (`private`). O
PostgREST publica só `public` (+ `graphql_public`); `private` fica fora da API REST.

As policies referenciam a função por OID → **sobrevivem** ao move (não é preciso recriá-las).
O caller (a policy avalia como `authenticated`; e o backend em `mfa.py`) precisa de USAGE em
`private` + EXECUTE — ambos concedidos aqui. Mantém o EXECUTE a `authenticated` (a policy
depende dele). Reversível: o downgrade devolve a função ao `public` e o EXECUTE.

Verificado ao vivo (2026-07-29, pooler `aws-1`): as 5 policies aal2 continuam resolvendo
(select em teses sob a lane authenticated aal1/aal2 = 327, sem erro) e o caller authenticated
executa `private.tem_fator_totp_verified` (usage+execute OK).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
create schema if not exists private;
grant usage on schema private to authenticated, service_role, app_worker;
alter function public.tem_fator_totp_verified(uuid) set schema private;
grant execute on function private.tem_fator_totp_verified(uuid) to authenticated;
"""


DOWNGRADE_SQL = r"""
alter function private.tem_fator_totp_verified(uuid) set schema public;
grant execute on function public.tem_fator_totp_verified(uuid) to authenticated;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
