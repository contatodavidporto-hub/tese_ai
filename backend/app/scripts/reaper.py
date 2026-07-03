"""Reaper de teses `processing` órfãs (integridade de dados).

Marca como `error` teses presas em `processing` além do timeout configurado
(`tese_processing_timeout_min`) — um crash no meio da geração não pode deixar a
tese em `processing` para sempre. O endpoint POST já roda o reaper de forma
oportunista; este script é para um schedule (ex.: a cada 15 min).

Uso:
    python -m app.scripts.reaper
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.tese import reaper_teses_orfas

logger = get_logger(__name__)


def main() -> int:
    if SessionLocal is None:
        print("ERRO: DATABASE_URL ausente (.env).")
        return 2
    settings = get_settings()
    with SessionLocal() as session:
        n = reaper_teses_orfas(session, settings.tese_processing_timeout_min)
    print(f"reaper: {n} tese(s) órfã(s) marcada(s) como error.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
