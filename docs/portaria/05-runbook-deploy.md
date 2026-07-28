# Runbook de deploy — A Portaria (Ondas 1+2+3)

> A Portaria só vai a produção como UM bloco (as três ondas juntas). O backend é
> **fail-closed por desenho** (não sobe sem `PORTARIA_SECRET`; a geração 500 sem o role
> `app_backend`/`DATABASE_URL_RLS`), então **mergear `feat/portaria` em `master` ANTES dos
> pré-requisitos abaixo DERRUBA a produção** (o Railway/Vercel auto-deployam do master).
> Este runbook é a ordem segura. Os passos marcados **[HUMANO]** só você pode fazer (não
> tenho acesso ao Railway nem ao Google Cloud Console); os **[EU]** eu executo por MCP/gh
> assim que os anteriores estiverem prontos.

## 0. Estado atual
- PR **#47** (`feat/portaria`) verde no que é meu: **backend + rls-isolation** (prova de
  isolamento e de step-up aal2 contra Postgres real). `frontend`/`security` do CI seguem
  vermelhos por dívida PRÉ-EXISTENTE do master (`npm audit`/`trivy` no `next`/`sharp` —
  fila do Dependabot, não é desta branch).
- Produção hoje: frontend `4790479` (Vercel), backend vivo (Railway), Supabase migrado até `0006`.

## 1. [HUMANO] Segredos e envs (antes de qualquer deploy)
1. **Gere o segredo de perímetro:** `openssl rand -hex 32` → guarde como `PORTARIA_SECRET`.
2. **Vercel** (Project Settings → Environment Variables, Production), SEM `NEXT_PUBLIC_`:
   - `SUPABASE_URL=https://rjpqaaymwhcwxtinppvc.supabase.co`
   - `SUPABASE_PUBLISHABLE_KEY=<a publishable key do projeto>`
   - `PORTARIA_SECRET=<o mesmo segredo>`
   - (`API_URL` já deve apontar para o backend Railway.)
3. **Railway** (backend, Variables):
   - `PORTARIA_SECRET=<o mesmo segredo>`
   - `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` (já existem; confira).
   - `DATABASE_URL_RLS=` — **deixe em branco por enquanto** (o role ainda não existe; passo 3).

## 2. [EU] Migração expand (0007) — aditiva, reversível, compatível com o código atual
Aplico `0007_portaria_expand` no Supabase de produção (cria a coluna `visibilidade`,
`user_id` nullable, o role **`app_worker`**, `historico_itens`, o cofre `codigos_recuperacao`,
policies e FORCE RLS). É backward-compatible: o código velho (conexão `postgres`, bypassrls)
segue funcionando. **Não deploya nada ainda.**

## 3. [HUMANO] Criar o role de login `app_backend` (depois do 0007)
No **SQL Editor** do dashboard (a senha NÃO pode ir a migração/código):
```sql
create role app_backend with login noinherit nobypassrls password '<SENHA-FORTE>';
grant anon, authenticated, app_worker to app_backend;
alter role app_backend set statement_timeout = '30s';
```
**Preflight OBRIGATÓRIO** (relatos reais de "Tenant or user not found" com role custom no
Supavisor): de um terminal com `psql`,
```
psql 'postgresql://app_backend.rjpqaaymwhcwxtinppvc:<SENHA>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres' \
  -c "set role authenticated; select 1;" -c "set role service_role;"
```
O primeiro `set role authenticated` deve funcionar; `set role service_role` deve **falhar**
(app_backend não é membro). Se o LOGIN falhar, pare e escale ao suporte Supabase.
Depois, no **Railway**: `DATABASE_URL_RLS=postgresql+psycopg://app_backend.rjpqaaymwhcwxtinppvc:<SENHA>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres`.

## 4. [HUMANO] Dashboard Supabase (Auth) e Google OAuth
- **Auth → Providers → Email:** Confirm email **ON**; access token TTL **600s**; reuse-detection
  de refresh **ligada** (default — não mexer). **NÃO** tocar em Signing Keys (já ES256).
- **Auth → Providers → Phone/MFA:** habilitar **TOTP** (MFA).
- **Auth → URL Configuration:** Site URL = `https://tese-ai.vercel.app`; redirect allow-list com
  as URLs EXATAS: `/api/auth/callback`, `/confirmar/pronto`, `/recuperar/redefinir` (+ o padrão
  dos previews da Vercel).
- **Auth → Email Templates:** Confirm signup, Reset password, Change email com links
  `{{ .SiteURL }}/confirmar/pronto?token_hash={{ .TokenHash }}&type=email` (e o análogo
  `/recuperar/redefinir?...&type=recovery`, `type=email_change`).
- **Google Cloud Console:** crie OAuth consent screen + client ID/secret (redirect URI =
  `https://rjpqaaymwhcwxtinppvc.supabase.co/auth/v1/callback`) → cole no **Auth → Providers →
  Google** do Supabase.
- (Opcional) "Require current password when changing password" **ON**.
- **Leaked Password Protection** é Pro — deixe OFF (compensamos com HIBP em app).

## 5. [EU] Migrações backfill (0008) e 2FA (0009)
Com o role e o código prestes a subir: aplico `0008_portaria_backfill` (as 314 teses do
demo viram acervo público; backup reversível `_portaria_backup_demo`) e `0009_portaria_2fa`
(cofre, `tem_fator_totp_verified`, step-up aal2). ⚠ **0008 roda DEPOIS do deploy do código
sem `demo_user`** (senão um processo velho recria o demo pelo `lru_cache`) — então a ordem
real é: **6 (merge/deploy) → 5 (backfill)**, com o smoke entre eles.

## 6. [EU] Merge + deploy
`gh pr ready 47 && gh pr merge 47 --squash` (ou merge normal) → Railway redeploya o backend
(agora com `PORTARIA_SECRET` + `DATABASE_URL_RLS` → sobe) e a Vercel redeploya o frontend.

## 7. [EU] Smoke pós-deploy
- Backend: `GET /health` → `{"status":"ok"}`.
- Frontend (tri-engine, via URL de produção): a **vitrine pública abre sem login**
  (as 13 teses); `/entrar`, `/criar-conta`, `/recuperar` renderizam; console limpo (0 erro CSP);
  gerar tese sem login → leva a `/entrar`.
- Fluxo real de auth (cadastro→confirmação→login→2FA→OAuth): só verificável DEPOIS do passo 4.

## 8. Rollback (testado por desenho)
- **Código:** `gh pr revert` ou redeploy do commit anterior (`4790479`) na Vercel/Railway.
- **Migração:** `alembic downgrade 0008` (desfaz 0009), `downgrade 0007` (desfaz 0008 via
  `_portaria_backup_demo` — válido enquanto o demo existir), `downgrade 0006` (desfaz 0007).
  Todos os downgrades existem e são reversíveis (0005 é o único destrutivo, e não entra aqui).
- **Perímetro:** se o backend não subir, o log dirá `PORTARIA_SECRET ausente` (fail-closed) —
  setar a var e redeploy.

## O que NÃO fazer
- **Não** mergear antes dos passos 1–4. **Não** rodar 0008 antes do deploy do código novo.
- **Não** deletar o `auth.users` do demo antes do soak (o script de contract
  `aposentar_demo_user.py` é passo posterior, com verificação de count=0).
