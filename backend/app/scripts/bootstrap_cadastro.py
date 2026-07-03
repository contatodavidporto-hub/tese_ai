"""Bootstrap semanal do cadastro CVM (resolução universal de ticker B3).

Popula `cvm_cadastro` (FCA valor_mobiliario + CAD_CIA_ABERTA) para que QUALQUER
ticker de companhia aberta seja resolvível. Idempotente. Rodar semanalmente.

Uso:
    python -m app.scripts.bootstrap_cadastro
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.cvm_cadastro import ingest_cvm_cadastro

logger = get_logger(__name__)


def main() -> int:
    with SessionLocal() as session:
        n = ingest_cvm_cadastro(session)
        session.commit()
    logger.info("bootstrap_cadastro_concluido", linhas=n)
    print(f"cvm_cadastro: {n} linhas (tickers resolvíveis) atualizadas.")
    return n


if __name__ == "__main__":  # pragma: no cover
    main()
