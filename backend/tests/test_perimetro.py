"""Perímetro X-Portaria (`app/core/perimetro.py`).

Fail-closed em produção (sem segredo, a app não sobe), enforce quando o segredo está
setado (header ausente/errado = 403; `/health` isento), e no-op em dev/test sem segredo
(por isso os 1015 testes não precisam do header).
"""

from __future__ import annotations

import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.perimetro import PerimetroMiddleware, verificar_perimetro_no_startup

SEGREDO = "portaria-teste-123"


def _settings(*, env: str = "development", secret: str | None = None):
    return types.SimpleNamespace(app_env=env, portaria_secret=secret)


# --- Fail-closed no startup --------------------------------------------------
def test_startup_producao_sem_segredo_aborta() -> None:
    with pytest.raises(RuntimeError):
        verificar_perimetro_no_startup(_settings(env="production", secret=None))


def test_startup_producao_com_segredo_ok() -> None:
    verificar_perimetro_no_startup(_settings(env="production", secret=SEGREDO))  # não levanta


def test_startup_dev_sem_segredo_ok() -> None:
    verificar_perimetro_no_startup(_settings(env="development", secret=None))  # no-op


# --- Middleware --------------------------------------------------------------
def _app(settings) -> TestClient:  # noqa: ANN001
    app = FastAPI()
    app.add_middleware(PerimetroMiddleware, settings=settings)

    @app.get("/x")
    def x() -> dict:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return TestClient(app)


def test_com_segredo_sem_header_e_403() -> None:
    client = _app(_settings(secret=SEGREDO))
    assert client.get("/x").status_code == 403


def test_com_segredo_header_errado_e_403() -> None:
    client = _app(_settings(secret=SEGREDO))
    assert client.get("/x", headers={"X-Portaria": "errado"}).status_code == 403


def test_com_segredo_header_certo_passa() -> None:
    client = _app(_settings(secret=SEGREDO))
    r = client.get("/x", headers={"X-Portaria": SEGREDO})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_health_isento_mesmo_com_segredo() -> None:
    client = _app(_settings(secret=SEGREDO))
    assert client.get("/health").status_code == 200


def test_sem_segredo_e_noop() -> None:
    client = _app(_settings(secret=None))
    assert client.get("/x").status_code == 200  # dev/test: perímetro desligado
