# Runbook de deploy — A Portaria (Ondas 1+2+3)

> A Portaria só vai a produção como UM bloco (as três ondas juntas). O backend é
> **fail-closed por desenho** (não sobe sem `PORTARIA_SECRET`; a geração 500 sem o role
> `app_backend`/`DATABASE_URL_RLS`), então **mergear `feat/portaria` em `master` ANTES dos
> pré-requisitos abaixo DERRUBA a produção** (o Railway/Vercel auto-deployam do master).
> Este runbook é a ordem segura. Os passos marcados **[HUMANO]** só você pode fazer (não
> tenho acesso ao Railway nem ao Google Cloud Console); os **[EU]** eu executo por MCP/gh
> assim que os anteriores estiverem prontos.

## ⚠ ATUALIZAÇÃO 2026-07-30 — esteira verde, lane RLS provada, achados de código fechados
Estado real (ver `07-fechamento-codigo-onda5.md` para o detalhe e os vereditos):
- **Esteira VERDE**: `master` compila; CI verde nos 4 jobs + Vercel (o build quebrava por
  `react-dom@19.2.8` vs `react@19.2.7` — corrigido; TS7 segurado; postcss/sharp remediados).
- **app_backend** agora tem **LOGIN + senha** (setada por MCP). **Preflight da lane RLS
  PROVADO** pelo pooler **`aws-1-sa-east-1`** (⚠ NÃO `aws-0` — este dá *"tenant/user not
  found"*; os passos 1/3 abaixo ainda dizem `aws-0`, **use `aws-1`**). NOBYPASSRLS; vê 327
  públicas / 0 privadas; cofre e `service_role` negados (42501).
- **Migrações até `0011`** aplicadas em produção (`alembic_version=0011`): **0010**
  (menor-privilégio LIVE-1 + FORCE RLS cofre/backup LIVE-3) e **0011** (oráculo 2FA
  `tem_fator_totp_verified` movido p/ schema `private`, fora do PostgREST — LIVE-2/MFA-04).
  **Reversibilidade provada** (round-trip down→up em transação revertida).
- **Achados de código fechados** (AC-01, MFA-01, SESS-01 código, piso senha 12, HIBP,
  LLM-COST-01, LLM-GATE-01) — PRs mergeados, testes verdes e crescendo.
- **Segredos** `PORTARIA_SECRET` e a senha do `app_backend` foram **gerados e entregues ao
  dono** (cofre pessoal) — NÃO estão no repo/bundle/log/Vault.

**O que FALTA para o login funcionar de ponta a ponta** (precisa das suas credenciais):
1. **Vercel** (token): `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `PORTARIA_SECRET` em
   Production+Preview (sem `NEXT_PUBLIC_`).
2. **Railway** (token): `PORTARIA_SECRET` (o mesmo) + `DATABASE_URL_RLS` (host **aws-1**) →
   deploy do backend novo (fail-closed) **só após a fiação provada**.
3. **Supabase** (PAT): MFA/TOTP + templates pt-BR + **medir** TTL do access token (SESS-01),
   rate-limits do GoTrue (AUTH-01) e cap do SMTP.
4. **Google OAuth**: client no Cloud Console → Auth→Providers→Google. Depois: smoke + ciclo
   de login real (2 usuários) + campanha de ataque §6.

## ⚠ ATUALIZAÇÃO 2026-07-28 — INCIDENTE: merge/deploy fora de ordem, remediado em parte
O código de `feat/portaria` (Ondas 1–3) foi **mergeado em master e deployado ANTES** dos
pré-requisitos deste runbook (Vercel/Railway/role). Resultado: **código novo rodando sobre
schema velho (0006)** — o Postgres logava `column "visibilidade" does not exist` e as leituras/
geração de tese ficaram quebradas (a vitrine estática + `/health` seguiram de pé, mascarando).

**O que EU já fiz (28/07, por MCP Supabase — parte programável):**
- Apliquei `0007`→`0008`→`0009` em produção e acertei `alembic_version = 0009`. Verificado:
  `visibilidade` existe; role `app_worker` criado; 327 teses viraram acervo público
  (`user_id NULL`, backup reversível em `_portaria_backup_demo`, 654 linhas); cofre
  `codigos_recuperacao` deny-all; `tem_fator_totp_verified` SECURITY DEFINER; 5 policies aal2.
- **Pré-criei o role `app_backend`** com os grants (`anon, authenticated, app_worker`) +
  `statement_timeout=30s`, porém **NOLOGIN e sem senha** — a senha é segredo e não passa por mim.

**O que FALTA (só você — Railway/Vercel/SQL editor/dashboard):** ver passos 3/4/1 abaixo. Enquanto
não forem feitos, **auth + geração + leitura de tese via lane RLS seguem fora do ar** (a vitrine
pública e o `/health` funcionam). Um advisor novo a tratar na Onda 4: `tem_fator_totp_verified` é
chamável por `authenticated` via `/rest/v1/rpc/...` com `uid` arbitrário → oráculo (baixo) de quem
tem 2FA; não dá pra revogar EXECUTE (a policy aal2 precisa) — fix é esconder de schema, não agora.

## 0. Estado atual (pós-remediação 28/07)
- PR **#47** (`feat/portaria`) verde no que é meu: **backend + rls-isolation** (prova de
  isolamento e de step-up aal2 contra Postgres real). `frontend`/`security` do CI seguem
  vermelhos por dívida PRÉ-EXISTENTE do master (`npm audit`/`trivy` no `next`/`sharp` —
  fila do Dependabot, não é desta branch).
- Produção hoje: frontend novo (Vercel, /entrar renderiza), backend novo vivo (Railway),
  **Supabase migrado até `0009`** (era 0006 até 28/07). Falta só o wiring de runtime (role+envs).

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

## 2. [EU] Migração expand (0007) — ✅ FEITO 28/07
Aplico `0007_portaria_expand` no Supabase de produção (cria a coluna `visibilidade`,
`user_id` nullable, o role **`app_worker`**, `historico_itens`, o cofre `codigos_recuperacao`,
policies e FORCE RLS). É backward-compatible: o código velho (conexão `postgres`, bypassrls)
segue funcionando. **Não deploya nada ainda.**

## 3. [HUMANO] Dar LOGIN+senha ao role `app_backend` (já pré-criado em 28/07)
O role **já existe** (NOLOGIN, com os grants e o `statement_timeout`). No **SQL Editor** do
dashboard, só falta injetar a senha (que NÃO pode ir a migração/código):
```sql
alter role app_backend with login password '<SENHA-FORTE>';
```
(Se preferir recriar do zero: `create role app_backend with login noinherit nobypassrls
password '<SENHA-FORTE>'; grant anon, authenticated, app_worker to app_backend; alter role
app_backend set statement_timeout = '30s';`)
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

## 5. [EU] Migrações backfill (0008) e 2FA (0009) — ✅ FEITO 28/07 (327 teses migradas)
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
