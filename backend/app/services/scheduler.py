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


def _job_warm_cache() -> object:
    """Aquece o cache das teses da galeria (top-10 IBOV). GASTA LLM — ver a
    config `scheduler_warm_cache_horas` (teto de custo diário aplica; cache
    hit não gasta nada)."""
    from app.scripts.warm_cache import TICKERS_IBOV_TOP, aquecer

    resumo = aquecer([t for t, _ in TICKERS_IBOV_TOP])
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
    if settings.scheduler_warm_cache_horas > 0:
        jobs.append(
            # POR ÚLTIMO de propósito: num mesmo tick, o refresh_macro roda
            # antes — as teses re-geradas já saem com as séries atualizadas.
            Job(
                nome="warm_cache",
                intervalo=dt.timedelta(hours=settings.scheduler_warm_cache_horas),
                # Lote frio = até 10 gerações sequenciais (~1-2 min cada).
                timeout_s=1800,
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
