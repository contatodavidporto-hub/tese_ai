"""Orquestração da ingestão das 5 dimensões, com falha ISOLADA por fonte.

Uma fonte indisponível não derruba as demais (cada passo abstém e registra). A
ingestão dos PARES (a mais pesada) já é paralela internamente (sec.ingest_pares via
map_concorrente, respeitando 10 req/s da SEC). Persistência serial no orquestrador
(Session não é thread-safe — achado M4). Commit único ao final.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.models.models import Empresa
from app.services import commodities, macro_global, sec
from app.services import dados as dados_svc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)


def ingest_completo(session: Session, empresa: Empresa) -> dict[str, str]:
    """Ingere fundamentos (D1) + macro BR (D3) + Brent (D3) + macro global (D4) +
    pares globais (D2). Cada passo é isolado; devolve o status de cada um."""
    resultados: dict[str, str] = {}

    def passo(nome: str, fn: Callable[[], object]) -> None:
        try:
            fn()
            resultados[nome] = "ok"
        except Exception as exc:  # falha isolada — não aborta o conjunto
            resultados[nome] = f"falha: {type(exc).__name__}"
            logger.warning("ingest_passo_falhou", passo=nome, erro=type(exc).__name__)

    passo("fundamentos", lambda: dados_svc.ingest_fundamentos(session, empresa))
    passo("macro_br", lambda: dados_svc.ingest_macro(session))
    passo("commodities_brent", lambda: commodities.ingest_brent(session))
    passo("macro_global_wb", lambda: macro_global.ingest_world_bank(session))
    passo("macro_global_treasury", lambda: macro_global.ingest_treasury_10y(session))
    passo("pares_globais", lambda: sec.ingest_pares(session, empresa))

    session.commit()
    logger.info("ingest_completo", ticker=empresa.ticker, resultados=resultados)
    return resultados
