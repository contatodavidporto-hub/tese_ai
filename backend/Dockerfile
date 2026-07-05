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

# Dependências PINADAS pelo uv.lock (build reprodutível: a imagem instala exatamente
# as versões testadas, não a última que satisfaz os lower-bounds). Camada separada do
# código: só invalida quando o lock muda. `--system` instala no site-packages da
# imagem (ambiente isolado); `--no-emit-project` exporta só as deps.
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-emit-project --format requirements-txt \
        -o /tmp/requirements.lock \
    && uv pip install --system --no-cache -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

# Código do app (mudar código não reinstala dependências). `--no-deps`: as deps já
# estão pinadas acima; aqui entra só o pacote `app` em si.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv pip install --system --no-cache --no-deps .

# Usuário não-root (hardening).
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Railway/Render/Fly injetam $PORT; default 8000 para rodar local.
ENV PORT=8000
EXPOSE 8000

# Atrás do edge-proxy da plataforma, scheme/host/IP reais chegam nos headers
# X-Forwarded-*; esta env manda o uvicorn honrá-los (proxy-headers já é default) —
# para logs e scheme corretos. A CHAVE do rate-limit NÃO depende disso: ela é
# derivada em app/core/ratelimit.py do valor MAIS À DIREITA do X-Forwarded-For
# (o único que o cliente não controla), imune a spoof por rotação de header —
# o uvicorn com "*" usaria o mais à esquerda, forjável em acesso direto ao host.
# Se a imagem rodar exposta SEM proxy, sobreponha com FORWARDED_ALLOW_IPS=127.0.0.1.
ENV FORWARDED_ALLOW_IPS="*"

# Healthcheck do container (a plataforma também aponta para /health).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health').read()" || exit 1

# Shell form para expandir $PORT. 1 worker por padrão: os guardas de capacidade
# (cap de concorrência + teto de custo de LLM em app/core/limits.py) são POR
# PROCESSO. Com 1 worker os limites configurados valem EXATOS; escalar workers
# multiplica os limites (mover p/ Redis é roadmap). Health é handler sync (roda
# no threadpool), não é bloqueado pela geração de fundo.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
