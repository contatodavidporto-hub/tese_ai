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


def _passos_isolados(
    session: Session, resultados: dict[str, str]
) -> Callable[[str, Callable[[], object]], None]:
    def passo(nome: str, fn: Callable[[], object]) -> None:
        try:
            # SAVEPOINT por passo (achado MÉDIO da auditoria da fase 1): uma
            # exceção no meio de um passo desfaz SÓ o DML dele — o snapshot
            # antigo sobrevive (ex.: delete+insert dos pares) e os passos que
            # já deram certo seguem para o commit único do chamador.
            with session.begin_nested():
                fn()
            resultados[nome] = "ok"
        except Exception as exc:  # falha isolada — não aborta o conjunto
            resultados[nome] = f"falha: {type(exc).__name__}"
            logger.warning("ingest_passo_falhou", passo=nome, erro=type(exc).__name__)

    return passo


def ingest_macro_refresh(session: Session) -> dict[str, str]:
    """Refresh das séries macro GLOBAIS (independentes de empresa): BCB (D3),
    Brent (D3), World Bank + Treasury (D4). Idempotente (upsert por série/data);
    é o corpo do job agendado `refresh_macro` e pode rodar sozinho num cron."""
    resultados: dict[str, str] = {}
    passo = _passos_isolados(session, resultados)

    passo("macro_br", lambda: dados_svc.ingest_macro(session))
    passo("usd_historico", lambda: dados_svc.ingest_usd_historico(session))
    passo("commodities_brent", lambda: commodities.ingest_brent(session))
    passo("brent_historico", lambda: commodities.ingest_brent_historico(session))
    passo("macro_global_wb", lambda: macro_global.ingest_world_bank(session))
    passo("macro_global_treasury", lambda: macro_global.ingest_treasury_10y(session))

    session.commit()
    logger.info("ingest_macro_refresh", resultados=resultados)
    return resultados


def ingest_completo(session: Session, empresa: Empresa) -> dict[str, str]:
    """Ingere fundamentos (D1) + macro BR (D3) + Brent (D3) + macro global (D4) +
    pares globais (D2). Cada passo é isolado; devolve o status de cada um."""
    resultados: dict[str, str] = {}
    passo = _passos_isolados(session, resultados)

    passo("fundamentos", lambda: dados_svc.ingest_fundamentos(session, empresa))
    passo("macro_br", lambda: dados_svc.ingest_macro(session))
    passo("usd_historico", lambda: dados_svc.ingest_usd_historico(session))
    passo("commodities_brent", lambda: commodities.ingest_brent(session))
    passo("brent_historico", lambda: commodities.ingest_brent_historico(session))
    passo("macro_global_wb", lambda: macro_global.ingest_world_bank(session))
    passo("macro_global_treasury", lambda: macro_global.ingest_treasury_10y(session))
    passo("pares_globais", lambda: sec.ingest_pares(session, empresa))

    session.commit()
    logger.info("ingest_completo", ticker=empresa.ticker, resultados=resultados)
    return resultados
