"""Warm cache: pré-gera teses dos tickers mais líquidos do Ibovespa.

Deixa N teses `ready` no banco para o público ver resposta instantânea (o POST
/teses reaproveita tese `ready` dentro de `tese_cache_horas`). Respeita o teto
de custo diário de LLM (`tese_teto_custo_usd_dia`): estourou => a geração abstém
e o script segue para o próximo ticker (registra a abstenção).

FONTE DA LISTA (zero alucinação): carteira teórica do Ibovespa, B3, consultada em
2026-07-07 via endpoint público do site da B3 (GetPortfolioDay, índice IBOV) —
página humana: https://www.b3.com.br/pt_br/market-data-e-indices/indices/
indices-amplos/ibovespa-composicao-da-carteira.htm. Os 10 maiores pesos (% da
carteira em 07/07/2026): VALE3 11,486 · ITUB4 8,976 · PETR4 6,957 · AXIA3 4,822 ·
PETR3 3,911 · BBDC4 3,817 · SBSP3 3,561 · ITSA4 3,356 · B3SA3 3,042 · WEGE3 2,871.
A lista é um RETRATO datado (a carteira muda a cada quadrimestre) — atualizar
junto com a rebalanceamento da B3.

Empresas financeiras (ITUB4/BBDC4/ITSA4/B3SA3) têm plano de contas próprio: as
derivadas e os pares SEC abstêm — a tese sai com as dimensões que têm fonte
(abstenção honesta, nunca inventa).

Uso:
    python -m app.scripts.warm_cache            # todos os 10
    python -m app.scripts.warm_cache VALE3 WEGE3  # subconjunto
"""

from __future__ import annotations

import json
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.models import TeseVersao
from app.services.tese import buscar_tese_cache, criar_tese, gerar_tese

logger = get_logger(__name__)

# (ticker, participação % na carteira IBOV em 2026-07-07 — fonte no docstring)
TICKERS_IBOV_TOP: list[tuple[str, float]] = [
    ("VALE3", 11.486),
    ("ITUB4", 8.976),
    ("PETR4", 6.957),
    ("AXIA3", 4.822),
    ("PETR3", 3.911),
    ("BBDC4", 3.817),
    ("SBSP3", 3.561),
    ("ITSA4", 3.356),
    ("B3SA3", 3.042),
    ("WEGE3", 2.871),
]


def _custo_da_tese(session, tese_id) -> float | None:
    versao = (
        session.query(TeseVersao)
        .filter(TeseVersao.tese_id == tese_id)
        .order_by(TeseVersao.criado_em.desc())
        .first()
    )
    if versao is None or not versao.conteudo:
        return None
    uso = (json.loads(versao.conteudo) or {}).get("uso") or {}
    return uso.get("custo_estimado_usd")


def main(tickers: list[str]) -> int:
    configure_logging("development")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if SessionLocal is None:
        print("ERRO: DATABASE_URL ausente (.env).")
        return 2

    settings = get_settings()
    custo_total = 0.0
    prontas = 0
    for ticker in tickers:
        session = SessionLocal()
        try:
            em_cache = buscar_tese_cache(session, ticker, settings.tese_cache_horas)
            if em_cache is not None:
                print(f"{ticker}: cache HIT (tese {em_cache.id} de {em_cache.criado_em}) — pulado")
                prontas += 1
                continue
            tese = criar_tese(session, ticker)
            print(f"{ticker}: gerando (tese {tese.id})...")
            gerar_tese(session, tese.id)
            session.expire_all()
            session.refresh(tese)
            custo = _custo_da_tese(session, tese.id)
            if custo:
                custo_total += custo
            print(f"{ticker}: status={tese.status} custo_estimado=US${custo or 0:.2f}")
            if tese.status == "ready":
                prontas += 1
        except Exception as exc:  # um ticker com problema não derruba o lote
            print(f"{ticker}: FALHOU ({type(exc).__name__})")
            logger.warning("warm_cache_ticker_falhou", ticker=ticker, erro=type(exc).__name__)
        finally:
            session.close()

    print(
        f"\nwarm_cache: {prontas}/{len(tickers)} ready; custo total estimado US${custo_total:.2f}"
    )
    return 0 if prontas > 0 else 1


if __name__ == "__main__":  # pragma: no cover
    alvos = sys.argv[1:] or [t for t, _ in TICKERS_IBOV_TOP]
    raise SystemExit(main(alvos))
