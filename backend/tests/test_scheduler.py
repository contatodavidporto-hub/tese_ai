"""Scheduler in-app: cadência por ledger (job_runs), flags e proteções.

Sem banco: sessões fake. O contrato testado é o do conselho — cadência decidida
por `now - last_run_at >= intervalo` (restart não zera), catch-up na primeira
execução, intervalo 0 desliga o job, kill-switch geral, e o corpo síncrono
respeita lock/dupla-checagem.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.services import scheduler as sch


def _settings(**overrides) -> SimpleNamespace:
    base = dict(
        scheduler_enabled=True,
        scheduler_tick_seconds=60,
        scheduler_reaper_min=15,
        scheduler_macro_horas=24,
        scheduler_cadastro_horas=168,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# jobs_configurados — flags por job
# ---------------------------------------------------------------------------
def test_jobs_configurados_padrao_tem_os_tres() -> None:
    jobs = sch.jobs_configurados(_settings())
    assert [j.nome for j in jobs] == ["reaper", "refresh_macro", "bootstrap_cadastro"]
    assert jobs[0].intervalo == dt.timedelta(minutes=15)
    assert jobs[1].intervalo == dt.timedelta(hours=24)
    assert jobs[2].intervalo == dt.timedelta(hours=168)


def test_intervalo_zero_desliga_o_job() -> None:
    jobs = sch.jobs_configurados(_settings(scheduler_macro_horas=0, scheduler_cadastro_horas=0))
    assert [j.nome for j in jobs] == ["reaper"]


# ---------------------------------------------------------------------------
# job_devido — ledger decide, não timer em memória
# ---------------------------------------------------------------------------
class _FakeResult:
    def __init__(self, row) -> None:
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeLedgerSession:
    def __init__(self, row) -> None:
        self._row = row

    def execute(self, _stmt):
        return _FakeResult(self._row)


_AGORA = dt.datetime(2026, 7, 7, 12, 0, tzinfo=dt.UTC)
_JOB = sch.Job(nome="reaper", intervalo=dt.timedelta(minutes=15), timeout_s=60, func=lambda: None)


def test_job_sem_registro_e_devido_catch_up() -> None:
    # Primeira execução (ou ledger novo): vencido — catch-up automático.
    assert sch.job_devido(_FakeLedgerSession(None), _JOB, _AGORA) is True


def test_job_recente_nao_e_devido() -> None:
    run = SimpleNamespace(last_run_at=_AGORA - dt.timedelta(minutes=5))
    assert sch.job_devido(_FakeLedgerSession(run), _JOB, _AGORA) is False


def test_job_vencido_e_devido_mesmo_apos_restart() -> None:
    # O relógio vive no banco: restart/deploy não zera a cadência.
    run = SimpleNamespace(last_run_at=_AGORA - dt.timedelta(minutes=16))
    assert sch.job_devido(_FakeLedgerSession(run), _JOB, _AGORA) is True


# ---------------------------------------------------------------------------
# registrar_run — last_run_at sempre gravada (sucesso E falha)
# ---------------------------------------------------------------------------
class _FakeUpsertSession(_FakeLedgerSession):
    def __init__(self, row) -> None:
        super().__init__(row)
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1


def test_registrar_run_insere_quando_nao_existe() -> None:
    sess = _FakeUpsertSession(None)
    sch.registrar_run(sess, "reaper", _AGORA, "ok", "3")
    assert len(sess.added) == 1
    assert sess.added[0].job_name == "reaper"
    assert sess.added[0].last_run_at == _AGORA
    assert sess.commits == 1


def test_registrar_run_atualiza_mesmo_em_falha() -> None:
    # Falha também avança o relógio: job quebrado espera o próximo intervalo
    # em vez de martelar a fonte a cada tick.
    run = SimpleNamespace(last_run_at=_AGORA - dt.timedelta(days=1), last_status="ok", detalhe="")
    sess = _FakeUpsertSession(run)
    sch.registrar_run(sess, "refresh_macro", _AGORA, "erro", "TimeoutException")
    assert run.last_run_at == _AGORA
    assert run.last_status == "erro"
    assert sess.added == []  # update, não insert
    assert sess.commits == 1


# ---------------------------------------------------------------------------
# executar_job_sincrono — guardas de ambiente e lock
# ---------------------------------------------------------------------------
def test_executar_sem_database_url_abstem(monkeypatch) -> None:
    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", None)
    assert sch.executar_job_sincrono(_JOB) == "sem_database_url"


def test_executar_com_lock_ocupado_pula(monkeypatch) -> None:
    import app.db.session as db_session

    class _LockBusySession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *_a, **_k):
            return SimpleNamespace(scalar=lambda: False)  # pg_try_advisory_lock nega

    monkeypatch.setattr(db_session, "SessionLocal", lambda: _LockBusySession())
    assert sch.executar_job_sincrono(_JOB) == "lock_ocupado"


def test_lock_key_estavel_e_distinta() -> None:
    assert sch._lock_key("reaper") == sch._lock_key("reaper")
    assert sch._lock_key("reaper") != sch._lock_key("refresh_macro")


# ---------------------------------------------------------------------------
# Happy-path do executar_job_sincrono (achado M2 da auditoria): lock -> devido
# -> roda -> registra ledger -> unlock no finally, exatamente uma vez.
# ---------------------------------------------------------------------------
class _RegistroSession:
    """Sessão fake que responde lock/unlock (text) e select de JobRun."""

    def __init__(self, log: list) -> None:
        self._log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        s = str(stmt)
        if "pg_try_advisory_lock" in s:
            self._log.append("lock")
            return SimpleNamespace(scalar=lambda: True)
        if "pg_advisory_unlock" in s:
            self._log.append("unlock")
            return SimpleNamespace(scalar=lambda: True)
        return _FakeResult(None)  # job_devido: sem registro -> devido (catch-up)

    def add(self, obj) -> None:
        self._log.append(("ledger", obj.job_name, obj.last_status))

    def commit(self) -> None:
        self._log.append("commit")


def _monta_sessao(monkeypatch, log: list) -> None:
    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", lambda: _RegistroSession(log))


def test_executar_happy_path_roda_registra_e_solta_o_lock(monkeypatch) -> None:
    log: list = []
    _monta_sessao(monkeypatch, log)
    job = sch.Job(nome="reaper", intervalo=dt.timedelta(minutes=15), timeout_s=60, func=lambda: 3)

    assert sch.executar_job_sincrono(job) == "ok"
    assert log.count("lock") == 1
    assert log.count("unlock") == 1  # exatamente uma vez, e depois do trabalho
    assert log.index("unlock") > log.index("lock")
    ledgers = [e for e in log if isinstance(e, tuple) and e[0] == "ledger"]
    assert ledgers == [("ledger", "reaper", "ok")]


def test_executar_job_que_falha_registra_erro_e_solta_o_lock(monkeypatch) -> None:
    log: list = []
    _monta_sessao(monkeypatch, log)

    def _quebra() -> None:
        raise RuntimeError("rede caiu")

    job = sch.Job(nome="reaper", intervalo=dt.timedelta(minutes=15), timeout_s=60, func=_quebra)
    assert sch.executar_job_sincrono(job) == "erro"
    assert log.count("unlock") == 1  # finally solta o lock mesmo em falha
    ledgers = [e for e in log if isinstance(e, tuple) and e[0] == "ledger"]
    assert ledgers == [("ledger", "reaper", "erro")]  # falha TAMBÉM avança o relógio


# ---------------------------------------------------------------------------
# Ciclo de vida do scheduler_loop (achado M1): falha/timeout não derrubam o
# loop; cancel encerra de verdade.
# ---------------------------------------------------------------------------
def test_scheduler_loop_sobrevive_a_falha_e_timeout_e_cancela(monkeypatch) -> None:
    import asyncio

    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", object())  # não-None basta p/ o gate
    chamadas: list[str] = []

    def _executa(job: sch.Job) -> str:
        chamadas.append(job.nome)
        if len(chamadas) == 1:
            raise RuntimeError("falha de rede")  # 1º tick: exceção não derruba o loop
        return "ok"

    monkeypatch.setattr(sch, "executar_job_sincrono", _executa)
    job = sch.Job(nome="reaper", intervalo=dt.timedelta(minutes=15), timeout_s=60, func=lambda: 0)
    monkeypatch.setattr(sch, "jobs_configurados", lambda s: [job])

    real_sleep = asyncio.sleep

    async def _sleep_rapido(_s: float) -> None:
        await real_sleep(0)  # tick sem espera real

    monkeypatch.setattr(sch.asyncio, "sleep", _sleep_rapido)

    async def _cenario() -> bool:
        task = asyncio.create_task(sch.scheduler_loop(_settings()))
        # Espera REAL limitada (até ~10s): o job roda num thread do pool — yields
        # cooperativos de 0s não davam tempo de a thread ser agendada pelo SO
        # (era a causa do flake M1 da auditoria). Tipicamente resolve em <0,5s.
        for _ in range(200):
            await real_sleep(0.05)
            if len(chamadas) >= 3:
                break
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return task.done()

    assert asyncio.run(_cenario()) is True
    assert len(chamadas) >= 3  # continuou tickando após a falha do 1º tick
