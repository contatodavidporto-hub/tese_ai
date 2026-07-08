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

Fase 2 multiativo (D7/etapa 14): o argv aceita códigos de QUALQUER classe —
tickers B3, FIIs (HGLG11) e Tesouro Direto (TD-IPCA-2035) — sem validar contra
a lista IBOV (a identidade é resolvida pelo motor). `--force` pula o cache
(`buscar_tese_cache`) e regenera mesmo com HIT: a nova `ready` passa a ser
servida (GET /teses ordena por criado_em desc) e a antiga vira trilha de
auditoria. Sem `--force` o comportamento é idêntico ao da fase 1.

Uso:
    python -m app.scripts.warm_cache            # todos os 10
    python -m app.scripts.warm_cache VALE3 WEGE3  # subconjunto
    python -m app.scripts.warm_cache --force ITUB4 BBDC4 ITSA4 B3SA3
    python -m app.scripts.warm_cache --force HGLG11 TD-IPCA-2035
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Argumentos do CLI. Códigos multiclasse, SEM validação contra a lista IBOV."""
    parser = argparse.ArgumentParser(
        prog="warm_cache",
        description="Pré-gera teses (warm cache). Sem códigos: top 10 do IBOV.",
    )
    parser.add_argument(
        "codigos",
        nargs="*",
        metavar="CODIGO",
        help="Tickers B3, FIIs (HGLG11) ou Tesouro Direto (TD-IPCA-2035); "
        "sem validação contra a lista IBOV — a identidade é resolvida pelo motor.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenera mesmo com cache HIT (pula buscar_tese_cache).",
    )
    return parser.parse_args(argv)


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


def aquecer(
    tickers: Sequence[str],
    *,
    force: bool = False,
    log_fn: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Aquece o cache do lote: gera só as teses sem `ready` vigente (hit = pulado).

    Núcleo compartilhado entre o CLI (main) e o job `warm_cache` do scheduler.
    Cada geração passa pelo caminho normal (`gerar_tese`): respeita o teto
    diário de custo (`tese_teto_custo_usd_dia`, abstém ao estourar) e o gate
    anti-recomendação. Um ticker com problema não derruba o lote.

    `force=True` (etapa 14) pula `buscar_tese_cache` e regenera mesmo com HIT;
    com o default (False) o comportamento é idêntico ao da fase 1.

    Devolve o resumo {"prontas", "total", "custo_usd", "falhas"}.
    """
    from app.db.session import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL ausente")

    log = log_fn or (lambda _msg: None)
    settings = get_settings()
    custo_total = 0.0
    prontas = 0
    falhas: list[str] = []
    for ticker in tickers:
        session = SessionLocal()
        try:
            # --force: pula o cache e regenera mesmo com HIT (a nova `ready`
            # supera a antiga no GET /teses, que ordena por criado_em desc).
            if not force:
                em_cache = buscar_tese_cache(session, ticker, settings.tese_cache_horas)
                if em_cache is not None:
                    log(
                        f"{ticker}: cache HIT (tese {em_cache.id} de {em_cache.criado_em})"
                        " — pulado"
                    )
                    prontas += 1
                    continue
            tese = criar_tese(session, ticker)
            log(f"{ticker}: gerando (tese {tese.id})...")
            gerar_tese(session, tese.id)
            session.expire_all()
            session.refresh(tese)
            custo = _custo_da_tese(session, tese.id)
            if custo:
                custo_total += custo
            log(f"{ticker}: status={tese.status} custo_estimado=US${custo or 0:.2f}")
            if tese.status == "ready":
                prontas += 1
            else:
                falhas.append(ticker)
        except Exception as exc:  # um ticker com problema não derruba o lote
            falhas.append(ticker)
            log(f"{ticker}: FALHOU ({type(exc).__name__})")
            logger.warning("warm_cache_ticker_falhou", ticker=ticker, erro=type(exc).__name__)
        finally:
            session.close()

    return {
        "prontas": prontas,
        "total": len(tickers),
        "custo_usd": round(custo_total, 2),
        "falhas": falhas,
    }


def main(tickers: list[str], force: bool = False) -> int:
    configure_logging("development")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        resumo = aquecer(tickers, force=force, log_fn=print)
    except RuntimeError:
        print("ERRO: DATABASE_URL ausente (.env).")
        return 2

    print(
        f"\nwarm_cache: {resumo['prontas']}/{resumo['total']} ready; "
        f"custo total estimado US${resumo['custo_usd']:.2f}"
    )
    return 0 if resumo["prontas"] else 1


if __name__ == "__main__":  # pragma: no cover
    args = _parse_args()
    alvos = args.codigos or [t for t, _ in TICKERS_IBOV_TOP]
    raise SystemExit(main(alvos, force=args.force))
