# PROJETO — Tese AI (MVP)

SaaS de IA que monta teses de investimento estruturadas e auditáveis (ações → FIIs → renda
fixa), cruzando fundamentos + macro + geopolítica, com cada afirmação rastreável.

> Princípios inegociáveis (ver `../AGENTS.md`): **nunca inventar dado** (fonte+data ou abstém);
> **nunca recomendar compra/venda**; **rastreabilidade > esperteza**; **segurança desde o dia 1**.

## Estrutura

```
PROJETO/
  backend/   # FastAPI + pipeline de tese (RAG, citações) + tests (pytest)
  frontend/  # Next.js + shadcn/ui + Tremor
  infra/     # docker-compose (pgvector local opcional), IaC
  .github/   # CI (lint + test + gitleaks + trivy)
```

## Quickstart (backend)

```bash
cd backend
python -m pip install uv          # gerenciador rápido (uma vez)
uv venv                            # cria .venv
uv pip install -e ".[dev]"        # instala deps + dev
cp .env.example .env               # preencha DATABASE_URL e chaves
uv run uvicorn app.main:app --reload --port 8000
# GET http://localhost:8000/health -> {"status":"ok"}
```

Testes e lint:

```bash
cd backend
uv run pytest -q
uv run ruff check .
uv run black --check .
```

Migrações (Supabase Postgres + pgvector):

```bash
cd backend
uv run alembic upgrade head        # aplica o schema (requer DATABASE_URL no .env)
```

## Quickstart (frontend)

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                         # http://localhost:3000 mostra "backend: ok"
```

## Banco

Postgres gerenciado no **Supabase** (projeto `tese-ai-mvp`, região `sa-east-1`), com `pgvector`
habilitado. A `DATABASE_URL` usa o **Session pooler** (IPv4) do Supabase. Nunca commite o `.env`.
