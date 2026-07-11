"""Scheduler in-app de jobs de manutenção — decisão do conselho (fase produção-ready).

Condições não-negociáveis implementadas:
1. Cadência por LEDGER no Postgres (`job_runs`): um job roda quando
   `now - last_run_at >= intervalo`. Restart/deploy não zera o relógio; job
   vencido dispara no primeiro tick após o startup (catch-up automático).
2. Jobs síncronos SEMPRE via `asyncio.to_thread` — o event loop (que serve
   /health e os requests) nunca bloqueia.
3. `pg_try_advisory_lock` NÃO-bloqueante por job (conexão dedicada): instâncias
   sobrepostas num rolling deploy (ou workers extras) não executam em dobro.
4. Timeout por job (`wait_for`) + jitter no tick — um job pendurado não trava o
   scheduler; o tempo real de rede continua limitado pelos timeouts do httpx.
5. Falha de job NUNCA derruba o processo: try/except por job, log estruturado.
6. Kill-switch (`scheduler_enabled`) + intervalo POR JOB na config (0 desliga o job).
7. Mesma lógica dos scripts `app.scripts.*` (zero fork): migrar para um cron
   externo depois = ligar o cron e desligar a flag.

Jobs são idempotentes: reaper é UPDATE por status; refresh de macro/cadastro são
upserts. Reexecução ocasional desperdiça rede, não corrompe dado.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
import zlib
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select, text

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.models import JobRun

logger = get_logger(__name__)

# Namespace dos advisory locks deste app (evita colisão com outros usos do banco).
_LOCK_NS = "tese-ai:job:"

# ETF do Ibovespa (CODBDI 14) — proxy do índice, incluído no COTAHIST diário
# além do lote do warm-cache (mesmo ticker usado no β aproximado de tese.py).
_TICKER_BOVA11 = "BOVA11"


@dataclass(frozen=True)
class Job:
    nome: str
    intervalo: dt.timedelta
    timeout_s: float
    func: Callable[[], object]  # síncrono; roda em to_thread


def _lock_key(nome: str) -> int:
    """Chave estável (int32) para pg_try_advisory_lock, derivada do nome."""
    return zlib.crc32(f"{_LOCK_NS}{nome}".encode())


def _job_reaper() -> object:
    from app.db.session import SessionLocal
    from app.services.tese import reaper_teses_orfas

    settings = get_settings()
    with SessionLocal() as session:
        return reaper_teses_orfas(session, settings.tese_processing_timeout_min)


def _job_refresh_macro() -> object:
    from app.db.session import SessionLocal
    from app.services.orquestracao import ingest_macro_refresh

    with SessionLocal() as session:
        return ingest_macro_refresh(session)


def _job_bootstrap_cadastro() -> object:
    from app.db.session import SessionLocal
    from app.services.cvm_cadastro import ingest_cvm_cadastro

    with SessionLocal() as session:
        n = ingest_cvm_cadastro(session)
        session.commit()
        return n


def _job_precos_cotahist() -> object:
    """COTAHIST B3 — preços diários de fim de dia (fase "Tese Profunda", §2.12).

    Ingesta SÓ os tickers RASTREADOS (`cotahist._CODBDI_PERMITIDOS`, correção
    A9): o mesmo lote do warm-cache (`lote_default()` — top 10 IBOV + exemplos
    multiativo) + BOVA11 (ETF do Ibovespa, proxy do β aproximado) — NUNCA o
    mercado inteiro. Feriado/fim de semana = HTTP 404 = 0 linhas gravadas
    SILENCIOSAMENTE (já tratado dentro de `ingest_arquivo_diario`; nada a
    fazer aqui). Tabela `precos_diarios` ausente (migração 0006 pendente) ->
    `DadoNaoEncontrado` (correção A13): absorvida aqui como NO-OP com log
    estruturado — nunca um "erro" que martele o ledger a cada tick."""
    from app.db.session import SessionLocal
    from app.scripts.warm_cache import lote_default
    from app.services import cotahist
    from app.services.dados import DadoNaoEncontrado

    tickers = set(lote_default()) | {_TICKER_BOVA11}
    session = SessionLocal()
    try:
        gravados = cotahist.ingest_arquivo_diario(session, dt.date.today(), tickers=tickers)
        session.commit()
        return f"gravados={gravados} tickers_rastreados={len(tickers)}"
    except DadoNaoEncontrado as exc:
        session.rollback()
        logger.info("scheduler_precos_cotahist_sem_dado", motivo=str(exc))
        return "sem_dado"
    finally:
        session.close()


def _job_anbima_ettj() -> object:
    """ANBIMA ETTJ — snapshot do dia (fase "Tese Profunda", §2.12).

    SÓ o snapshot mais recente (`ensure_snapshot`, TRAVA ToS: a função nunca
    aceita intervalo de datas nem monta série histórica). Sem snapshot
    publicado nos dias úteis regredidos, ou tabela `curva_snapshot` ausente
    (correção A13) -> `DadoNaoEncontrado`: absorvida aqui como NO-OP com log
    estruturado, nunca "erro" a cada tick."""
    from app.db.session import SessionLocal
    from app.services import anbima_ettj
    from app.services.dados import DadoNaoEncontrado

    session = SessionLocal()
    try:
        linhas = anbima_ettj.ensure_snapshot(session)
        session.commit()
        return f"linhas={len(linhas)}"
    except DadoNaoEncontrado as exc:
        session.rollback()
        logger.info("scheduler_anbima_ettj_sem_dado", motivo=str(exc))
        return "sem_dado"
    finally:
        session.close()


def _job_ifdata_trimestral() -> object:
    """IF.data BCB — indicadores prudenciais de bancos (fase "Tese Profunda",
    §2.12). Itera o MAPA CURADO cd_cvm -> IF.data (`ifdata.MAPA_CVM_IFDATA`),
    UMA SESSÃO NOVA POR BANCO (evita carregar uma transação abortada por
    `ProgrammingError`/tabela ausente de um banco para o próximo — Postgres
    exige ROLLBACK antes de reusar a sessão). `DadoNaoEncontrado` por banco
    (fonte fora do ar, tabela `banco_indicadores` ausente — correção A13,
    alarme de schema/remapeamento) é tolerada com log estruturado; os demais
    bancos do lote seguem."""
    from app.db.session import SessionLocal
    from app.services import ifdata
    from app.services.dados import DadoNaoEncontrado

    ok = 0
    sem_dado = 0
    for cd_cvm in ifdata.MAPA_CVM_IFDATA:
        session = SessionLocal()
        try:
            ifdata.ensure_indicadores_banco(session, cd_cvm)
            session.commit()
            ok += 1
        except DadoNaoEncontrado as exc:
            session.rollback()
            sem_dado += 1
            logger.info("scheduler_ifdata_banco_sem_dado", cd_cvm=cd_cvm, motivo=str(exc))
        finally:
            session.close()
    return f"ok={ok} sem_dado={sem_dado} bancos={ok + sem_dado}"


def _job_aneel_rap() -> object:
    """ANEEL RAP — ciclo tarifário de transmissoras (fase "Tese Profunda",
    §2.12, correção A8). Itera o MAPA CURADO ticker -> grupo econômico
    (`aneel._GRUPOS_RAP_V1`), UMA SESSÃO NOVA POR TICKER (mesma razão do
    IF.data: evita transação abortada entre iterações). `DadoNaoEncontrado`
    por ticker (rede fora do ar sem histórico persistido, anomalia
    fail-closed nos registros do ciclo-alvo, tabela `setor_indicadores`
    ausente — correção A13) é tolerada com log estruturado; os demais tickers
    do lote seguem."""
    from app.db.session import SessionLocal
    from app.services import aneel
    from app.services.dados import DadoNaoEncontrado

    ok = 0
    sem_dado = 0
    for ticker in aneel._GRUPOS_RAP_V1:
        session = SessionLocal()
        try:
            resultado = aneel.ensure_rap(session, ticker)
            session.commit()
            if resultado is not None:
                ok += 1
            else:  # defensivo: nunca deveria ocorrer (iteramos o próprio mapa)
                sem_dado += 1
        except DadoNaoEncontrado as exc:
            session.rollback()
            sem_dado += 1
            logger.info("scheduler_aneel_rap_sem_dado", ticker=ticker, motivo=str(exc))
        finally:
            session.close()
    return f"ok={ok} sem_dado={sem_dado} tickers={ok + sem_dado}"


def _job_warm_cache() -> object:
    """Aquece o cache das teses da galeria (top-10 IBOV + exemplos adicionais
    TAEE11/HGLG11/TD-IPCA-2035 — `lote_default`, o MESMO lote do CLI sem
    args; 13 tickers desde a fase "Tese Profunda"). GASTA LLM — ver a config
    `scheduler_warm_cache_horas` (teto de custo diário aplica; cache hit não
    gasta nada)."""
    from app.scripts.warm_cache import aquecer, lote_default

    resumo = aquecer(lote_default())
    return (
        f"{resumo['prontas']}/{resumo['total']} ready; "
        f"custo=US${resumo['custo_usd']}; falhas={resumo['falhas'] or '-'}"
    )


def jobs_configurados(settings: Settings) -> list[Job]:
    """Jobs habilitados pela config (intervalo 0 = job desligado)."""
    jobs: list[Job] = []
    if settings.scheduler_reaper_min > 0:
        jobs.append(
            Job(
                nome="reaper",
                intervalo=dt.timedelta(minutes=settings.scheduler_reaper_min),
                timeout_s=120,
                func=_job_reaper,
            )
        )
    if settings.scheduler_macro_horas > 0:
        jobs.append(
            Job(
                nome="refresh_macro",
                intervalo=dt.timedelta(hours=settings.scheduler_macro_horas),
                timeout_s=600,
                func=_job_refresh_macro,
            )
        )
    if settings.scheduler_cadastro_horas > 0:
        jobs.append(
            Job(
                nome="bootstrap_cadastro",
                intervalo=dt.timedelta(hours=settings.scheduler_cadastro_horas),
                # Pior caso observado do download FCA (3 anos em série) ~540s.
                timeout_s=900,
                func=_job_bootstrap_cadastro,
            )
        )
    # Ingest ampliado (fase "Tese Profunda", §2.12) — ANTES do warm_cache de
    # propósito: no mesmo tick, preços/curva/indicadores/RAP atualizam PRIMEIRO
    # para a pré-síntese determinística (técnica/valuation/métricas) usar dado
    # fresco quando o warm_cache re-gera as teses da galeria logo em seguida.
    if settings.scheduler_cotahist_horas > 0:
        jobs.append(
            Job(
                nome="precos_cotahist",
                intervalo=dt.timedelta(hours=settings.scheduler_cotahist_horas),
                timeout_s=900,
                func=_job_precos_cotahist,
            )
        )
    if settings.scheduler_anbima_horas > 0:
        jobs.append(
            Job(
                nome="anbima_ettj",
                intervalo=dt.timedelta(hours=settings.scheduler_anbima_horas),
                timeout_s=300,
                func=_job_anbima_ettj,
            )
        )
    if settings.scheduler_ifdata_horas > 0:
        jobs.append(
            Job(
                nome="ifdata_trimestral",
                intervalo=dt.timedelta(hours=settings.scheduler_ifdata_horas),
                timeout_s=600,
                func=_job_ifdata_trimestral,
            )
        )
    if settings.scheduler_aneel_horas > 0:
        jobs.append(
            Job(
                nome="aneel_rap",
                intervalo=dt.timedelta(hours=settings.scheduler_aneel_horas),
                timeout_s=300,
                func=_job_aneel_rap,
            )
        )
    if settings.scheduler_warm_cache_horas > 0:
        jobs.append(
            # POR ÚLTIMO de propósito: num mesmo tick, o refresh_macro e o
            # ingest ampliado rodam antes — as teses re-geradas já saem com as
            # séries/indicadores atualizados.
            Job(
                nome="warm_cache",
                intervalo=dt.timedelta(hours=settings.scheduler_warm_cache_horas),
                # Lote frio = até 13 gerações sequenciais: top 10 IBOV +
                # TAEE11/HGLG11/TD-IPCA-2035 (fase "Tese Profunda" — 12 -> 13,
                # decisão F6). Teto subiu de 2400s (12 × ~2min) para 3900s
                # (13 × ~5min de folga): a síntese cresceu (max_tokens 16000)
                # e ganhou o estágio de consenso (Haiku+web_search) — sem
                # medição ao vivo neste ambiente offline, o teto é
                # deliberadamente generoso para não matar o lote no meio.
                timeout_s=3900,
                func=_job_warm_cache,
            )
        )
    return jobs


def job_devido(session, job: Job, agora: dt.datetime) -> bool:
    """Vencido? `last_run_at` ausente (primeira vez) conta como vencido (catch-up)."""
    run = session.execute(select(JobRun).where(JobRun.job_name == job.nome)).scalar_one_or_none()
    if run is None:
        return True
    return (agora - run.last_run_at) >= job.intervalo


def registrar_run(session, nome: str, inicio: dt.datetime, status: str, detalhe: str | None):
    """Upsert do ledger. `last_run_at` é SEMPRE gravado (sucesso ou falha): um job
    que falha espera o próximo intervalo em vez de martelar a fonte a cada tick."""
    run = session.execute(select(JobRun).where(JobRun.job_name == nome)).scalar_one_or_none()
    if run is None:
        run = JobRun(job_name=nome, last_run_at=inicio, last_status=status, detalhe=detalhe)
        session.add(run)
    else:
        run.last_run_at = inicio
        run.last_status = status
        run.detalhe = detalhe
    session.commit()


def executar_job_sincrono(job: Job) -> str:
    """Corpo síncrono de um tick de job (roda em to_thread).

    Conexão dedicada segura o advisory lock durante TODA a execução; o "devido?"
    é re-checado sob o lock (double-check) para instâncias sobrepostas não
    executarem em dobro no mesmo intervalo.
    """
    from app.db.session import SessionLocal

    if SessionLocal is None:
        return "sem_database_url"

    with SessionLocal() as lock_sess:
        got = lock_sess.execute(
            text("select pg_try_advisory_lock(:k)"), {"k": _lock_key(job.nome)}
        ).scalar()
        if not got:
            return "lock_ocupado"
        # Daqui em diante o lock É nosso: o finally solta exatamente uma vez.
        try:
            agora = dt.datetime.now(dt.UTC)
            with SessionLocal() as session:
                if not job_devido(session, job, agora):
                    return "nao_devido"
            try:
                resultado = job.func()
                status, detalhe = "ok", str(resultado)[:500]
            except Exception as exc:
                status, detalhe = "erro", type(exc).__name__
                logger.warning("scheduler_job_falhou", job=job.nome, erro=type(exc).__name__)
            with SessionLocal() as session:
                registrar_run(session, job.nome, agora, status, detalhe)
            logger.info("scheduler_job_executado", job=job.nome, status=status)
            return status
        finally:
            lock_sess.execute(text("select pg_advisory_unlock(:k)"), {"k": _lock_key(job.nome)})
            lock_sess.commit()


async def scheduler_loop(settings: Settings | None = None) -> None:
    """Loop do scheduler (uma task asyncio no lifespan). Cancelável no shutdown."""
    settings = settings or get_settings()
    from app.db.session import SessionLocal

    if SessionLocal is None:
        logger.info("scheduler_desligado", motivo="sem_database_url")
        return
    jobs = jobs_configurados(settings)
    if not jobs:
        logger.info("scheduler_desligado", motivo="nenhum_job_habilitado")
        return
    tick = max(settings.scheduler_tick_seconds, 10)
    logger.info("scheduler_iniciado", jobs=[j.nome for j in jobs], tick_s=tick)
    while True:
        for job in jobs:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(executar_job_sincrono, job), timeout=job.timeout_s
                )
            except TimeoutError:
                # O await desistiu; a thread termina sozinha (timeouts do httpx).
                logger.warning("scheduler_job_timeout", job=job.nome, timeout_s=job.timeout_s)
            except Exception as exc:  # nunca derruba o loop
                logger.warning("scheduler_tick_falhou", job=job.nome, erro=type(exc).__name__)
        # Jitter: instâncias sobrepostas não ticam em fase (menos disputa de lock).
        await asyncio.sleep(tick + random.uniform(0, tick * 0.1))  # noqa: S311 (não-cripto)
