# Deploy de Produção — Runbook

> Vercel hospeda **só o frontend** (Next.js). O **backend FastAPI** (com job de
> geração in-process) precisa de host próprio: **Railway / Fly / Render**.
> **Frontend sem backend alcançável = página "backend offline".** Hospede o
> backend PRIMEIRO. Segredos vão **só no painel do host** — nunca commitados.

Estado no merge para `master` (0552252): CI 3/3 verde; migrações no Supabase em `0003`.

---

## Passo 1 — Backend (Railway recomendado; menos config)

Artefatos já prontos neste repo: `backend/Dockerfile`, `backend/.dockerignore`,
`backend/railway.json` (healthcheck `/health`, restart on-failure).

1. **Railway → New Project → Deploy from GitHub repo** → `contatodavidporto-hub/tese_ai`.
2. No serviço, **Settings → Root Directory = `backend`** (o Dockerfile + railway.json são detectados).
3. **Variables** (painel do Railway — NÃO commitar):
   - `DATABASE_URL` = URI do **Session pooler** do Supabase `tese-ai` (o app normaliza para o driver `psycopg`).
   - `ANTHROPIC_API_KEY` = chave da Anthropic (produto).
   - `SUPABASE_URL` = `https://rjpqaaymwhcwxtinppvc.supabase.co`.
   - `SUPABASE_SERVICE_ROLE_KEY` = service_role (**só no backend**, nunca no front).
   - `CORS_ORIGINS` = domínio(s) de produção do Vercel (ex.: `https://tese-ai.vercel.app`).
   - `APP_ENV` = `production` · `APP_BASE_URL` = URL do frontend de produção.
   - Opcionais: `FRED_API_KEY`, `EIA_API_KEY` (sem eles, D3/D4 keyless seguem; premium abstém), `LANGFUSE_*`.
4. **Migrações:** já aplicadas (Supabase em `0003`). Se um dia precisar: one-off `uv run alembic upgrade head`.
5. **Verificar:** `GET https://<backend-railway>/health` → `{"status":"ok"}` [200] com headers de segurança (nosniff, HSTS, no-store).

> Os guardas de capacidade (rate-limit, cap de concorrência, teto de custo de LLM) e os
> headers já estão no código e sobem ligados. O Dockerfile usa **1 worker** para os
> limites por-processo valerem exatos (escalar workers multiplica os limites — Redis é roadmap).

## Passo 2 — Frontend (Vercel)

1. **Vercel → Add New Project → Import** `tese_ai` · **Root Directory = `frontend`** · framework **Next.js** (autodetect).
2. **Environment Variables (Production):**
   - `API_URL` = URL pública do backend do Passo 1 (ex.: `https://tese-ai-backend.up.railway.app`).
     O proxy same-origin (`src/app/api/teses/route.ts`) lê `NEXT_PUBLIC_API_URL ?? API_URL`; use `API_URL`
     (server-only) para **não** inlinar a URL no bundle do cliente. O navegador só fala same-origin (CSP `connect-src 'self'`).
3. **Deploy de Preview primeiro** (não-produção). Fumaça no Preview:
   - abre a página; `GET /health` do backend via app OK;
   - gera **1 tese de ticker já ingerido** (ex.: PETR4 → cache hit, custo US$ 0) → citações clicáveis, fontes, lacunas;
   - **banner de não-recomendação** presente; **console sem erro de CSP**.
4. Preview OK → **Promote to Production**. Confirmar na resposta de prod: HSTS, CSP (nonce), nosniff, X-Frame DENY.

## Passo 3 — Fechar o laço (CORS)
Com o domínio de produção do Vercel definido, garanta `CORS_ORIGINS` no backend = esse domínio (deny-by-default, sem `*`) e redeploy do backend.

---

## Smoke de produção (pós-deploy)
- [ ] `GET /health` do backend = 200 (headers de segurança presentes).
- [ ] Frontend de produção abre; gera 1 tese; citações + banner OK; CSP sem erro no console.
- [ ] Headers de segurança na resposta de produção do front (HSTS/CSP/nosniff/DENY).

## Rollback
- **Vercel:** Deployments → deploy anterior → **Instant Rollback**.
- **Railway:** Deployments → redeploy da versão anterior.
- Se algo grave: rollback + avisar. Não deixar produção quebrada.

## Rails (mantidos)
Segredo só no painel do host (nunca commit/log). `service_role` só no backend. RLS em toda tabela.
Zero alucinação (fonte+data; abster). Zero recomendação (postura CVM). Só o deploy do Vercel é irreversível autorizado.
