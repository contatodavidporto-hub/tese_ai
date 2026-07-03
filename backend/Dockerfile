# Imagem de produção do backend FastAPI (Tese AI).
# Contexto de build = a pasta `backend/` (no Railway/Render: Root Directory = backend).
# Sobe o web server; a geração de tese roda in-process (BackgroundTasks) — 1 serviço.
FROM python:3.12-slim AS base

# Não gera .pyc, log sem buffer, UTF-8.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instala uv e depois as dependências do projeto (sem as de dev) a partir do
# pyproject. `--system` instala no site-packages da imagem (ambiente isolado).
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache .

# Usuário não-root (hardening).
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Railway/Render/Fly injetam $PORT; default 8000 para rodar local.
ENV PORT=8000
EXPOSE 8000

# Healthcheck do container (a plataforma também aponta para /health).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health').read()" || exit 1

# Shell form para expandir $PORT. 1 worker por padrão: os guardas de capacidade
# (cap de concorrência + teto de custo de LLM em app/core/limits.py) são POR
# PROCESSO. Com 1 worker os limites configurados valem EXATOS; escalar workers
# multiplica os limites (mover p/ Redis é roadmap). Health é handler sync (roda
# no threadpool), não é bloqueado pela geração de fundo.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
