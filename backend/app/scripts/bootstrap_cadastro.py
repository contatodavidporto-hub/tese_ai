"""Bootstrap semanal do cadastro CVM (resolução universal de ticker B3 + FIIs).

Popula `cvm_cadastro` (FCA valor_mobiliario + CAD_CIA_ABERTA) para que QUALQUER
ticker de companhia aberta seja resolvível, e `fii_cadastro` com o universo do
informe mensal de FIIs (achado A2 do red-team: banco fresco também precisa
resolver HGLG11 etc. sem depender de um primeiro request online). Idempotente.
Rodar semanalmente. Cada passo é ISOLADO (padrão orquestração): falha no passo
FII não derruba o bootstrap de cias.

Uso:
    python -m app.scripts.bootstrap_cadastro
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.cvm_cadastro import ingest_cvm_cadastro
from app.services.fii_dados import bootstrap_fiis

logger = get_logger(__name__)


def main() -> int:
    with SessionLocal() as session:
        n = ingest_cvm_cadastro(session)
        session.commit()
    logger.info("bootstrap_cadastro_concluido", linhas=n)
    print(f"cvm_cadastro: {n} linhas (tickers resolvíveis) atualizadas.")

    # Passo FII ISOLADO (A2): sessão própria e try/except — uma falha aqui
    # (rede/CVM fora do ar) NÃO derruba o bootstrap de cias já commitado.
    try:
        with SessionLocal() as session:
            n_fii = bootstrap_fiis(session)
            session.commit()
        logger.info("bootstrap_fiis_concluido", fundos=n_fii)
        print(f"fii_cadastro: {n_fii} fundos do informe mensal CVM atualizados.")
    except Exception as exc:  # passo isolado: registra e segue
        logger.warning("bootstrap_fiis_falhou", erro=type(exc).__name__, detalhe=str(exc))
        print("fii_cadastro: passo FII falhou (ver log) — bootstrap de cias preservado.")
    return n


if __name__ == "__main__":  # pragma: no cover
    main()
