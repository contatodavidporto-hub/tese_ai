"""Refresh das séries macro globais (BCB, Brent, World Bank, Treasury).

Mesma lógica do job agendado `refresh_macro` do scheduler in-app — este script
existe para paridade com um cron externo (Railway cron etc.): ligar o cron e
desligar a flag `SCHEDULER_ENABLED` é um swap sem fork de lógica. Idempotente
(upsert por série/data).

Uso:
    python -m app.scripts.refresh_macro
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.orquestracao import ingest_macro_refresh

logger = get_logger(__name__)


def main() -> int:
    if SessionLocal is None:
        print("ERRO: DATABASE_URL ausente (.env).")
        return 2
    with SessionLocal() as session:
        resultados = ingest_macro_refresh(session)
    print(f"refresh_macro: {resultados}")
    return 0 if all(v == "ok" for v in resultados.values()) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
