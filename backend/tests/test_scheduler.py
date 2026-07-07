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
