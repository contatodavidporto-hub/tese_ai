# backend — Tese AI

FastAPI + SQLAlchemy + Alembic + pgvector. Motor de teses com citações e auditoria.

## Setup

```bash
python -m pip install uv
uv venv
uv pip install -e ".[dev]"
cp .env.example .env   # preencha DATABASE_URL (Session pooler do Supabase) e chaves
```

## Rodar

```bash
uv run uvicorn app.main:app --reload --port 8000
# GET /health -> {"status":"ok"}
```

## Qualidade

```bash
uv run ruff check .
uv run black --check .
uv run pytest -q
```

## Migrações

```bash
uv run alembic upgrade head      # aplica schema no Postgres (DATABASE_URL no .env)
uv run alembic revision -m "msg" # nova migração (manual ou --autogenerate)
```

## Layout

```
app/
  main.py                 # FastAPI + /health
  core/config.py          # pydantic-settings (lê .env)
  core/logging.py         # structlog com redação de segredos
  db/base.py, db/session.py
  models/models.py        # ORM (empresas, fundamentos, ..., chunks[vector])
  observability/langfuse_client.py  # stub no-op sem credenciais
alembic/                  # env.py + versions/
tests/                    # pytest (smoke /health)
```
