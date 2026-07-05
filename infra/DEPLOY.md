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
   - `CORS_ORIGINS` = domínio(s) de produção do Vercel, **separados por vírgula, sem espaços**
     (ex.: `https://tese-ai.vercel.app` ou `https://a.app,https://b.app`).
   - `APP_ENV` = `production` · `APP_BASE_URL` = URL do frontend de produção.
   - Opcionais: `FRED_API_KEY`, `EIA_API_KEY` (sem eles, D3/D4 keyless seguem; premium abstém), `LANGFUSE_*`.
   - `FORWARDED_ALLOW_IPS` **não precisa ser setada**: a imagem já embute `*` (atrás do
     edge-proxy da plataforma o IP real vem no `X-Forwarded-For`; sem isso o rate-limit
     por IP colapsaria num bucket global). Só sobreponha (`127.0.0.1`) se algum dia a
     imagem rodar exposta sem proxy na frente.
4. **Migrações:** já aplicadas (Supabase em `0003`). Se um dia precisar: one-off **`alembic upgrade head`**
   direto (o CLI já está no PATH da imagem; **não** use `uv run` dentro do container — criaria um venv).
5. **Verificar:** `GET https://<backend-railway>/health` → `{"status":"ok"}` [200] com headers de segurança
   (nosniff, HSTS, no-store). Em produção `/docs`, `/redoc` e `/openapi.json` ficam **desligados**
   (`APP_ENV=production`) — 404 neles é o esperado.

> Os guardas de capacidade (rate-limit, cap de concorrência, teto de custo de LLM) e os
> headers já estão no código e sobem ligados. O Dockerfile usa **1 worker** para os
> limites por-processo valerem exatos (escalar workers multiplica os limites — Redis é roadmap).

## Passo 2 — Frontend (Vercel)

1. **Vercel → Add New Project → Import** `tese_ai` · **Root Directory = `frontend`** · framework **Next.js** (autodetect).
2. **Environment Variables (escopos Preview E Production, mesmo valor):**
   - `API_URL` = URL pública do backend do Passo 1 (ex.: `https://tese-ai-backend.up.railway.app`).
     A resolução server-only (`src/lib/backend.ts`, usada pelos proxies e pela home) lê `API_URL ?? NEXT_PUBLIC_API_URL`;
     use `API_URL` (server-only) para **não** inlinar a URL no bundle do cliente. O navegador só fala same-origin
     (CSP `connect-src 'self'`).
   - ⚠️ Marque a env para **Preview e Production**: a fumaça roda num deploy de Preview (sem a env no
     escopo Preview, o proxy responde 502 "Backend não configurado"). **Promote não rebuilda** nem re-injeta
     env — o deployment promovido carrega a env capturada quando foi criado; mudou env → faça novo deploy.
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
