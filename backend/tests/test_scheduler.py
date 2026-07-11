"""Scheduler in-app: cadência por ledger (job_runs), flags e proteções.

Sem banco: sessões fake. O contrato testado é o do conselho — cadência decidida
por `now - last_run_at >= intervalo` (restart não zera), catch-up na primeira
execução, intervalo 0 desliga o job, kill-switch geral, e o corpo síncrono
respeita lock/dupla-checagem.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from app.services import scheduler as sch


def _settings(**overrides) -> SimpleNamespace:
    base = dict(
        scheduler_enabled=True,
        scheduler_tick_seconds=60,
        scheduler_reaper_min=15,
        scheduler_macro_horas=24,
        scheduler_cadastro_horas=168,
        # Jobs novos de ingest ampliado (fase "Tese Profunda", §2.12) — mesmos
        # defaults de app.core.config.Settings.
        scheduler_cotahist_horas=24,
        scheduler_anbima_horas=24,
        scheduler_ifdata_horas=720,
        scheduler_aneel_horas=720,
        scheduler_warm_cache_horas=24,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# jobs_configurados — flags por job
# ---------------------------------------------------------------------------
def test_jobs_configurados_padrao_tem_os_oito() -> None:
    # Fase "Tese Profunda" (§2.12) acrescenta 4 jobs de ingest ampliado entre
    # bootstrap_cadastro e warm_cache: 4 -> 8 jobs no default.
    jobs = sch.jobs_configurados(_settings())
    assert [j.nome for j in jobs] == [
        "reaper",
        "refresh_macro",
        "bootstrap_cadastro",
        "precos_cotahist",
        "anbima_ettj",
        "ifdata_trimestral",
        "aneel_rap",
        "warm_cache",
    ]
    assert jobs[0].intervalo == dt.timedelta(minutes=15)
    assert jobs[1].intervalo == dt.timedelta(hours=24)
    assert jobs[2].intervalo == dt.timedelta(hours=168)
    assert jobs[3].intervalo == dt.timedelta(hours=24)  # precos_cotahist
    assert jobs[4].intervalo == dt.timedelta(hours=24)  # anbima_ettj
    assert jobs[5].intervalo == dt.timedelta(hours=720)  # ifdata_trimestral
    assert jobs[6].intervalo == dt.timedelta(hours=720)  # aneel_rap
    assert jobs[7].intervalo == dt.timedelta(hours=24)  # warm_cache


def test_timeouts_dos_jobs_novos_de_ingest_ampliado() -> None:
    # Timeouts da tabela do plano §2.12 (900/300/600/300s).
    jobs = {j.nome: j for j in sch.jobs_configurados(_settings())}
    assert jobs["precos_cotahist"].timeout_s == 900
    assert jobs["anbima_ettj"].timeout_s == 300
    assert jobs["ifdata_trimestral"].timeout_s == 600
    assert jobs["aneel_rap"].timeout_s == 300


def test_warm_cache_roda_por_ultimo_no_tick() -> None:
    # Ordem é contrato: no mesmo tick o refresh_macro E o ingest ampliado
    # (COTAHIST/ANBIMA/IF.data/ANEEL) rodam ANTES do warm_cache, então as
    # teses re-geradas já saem com as séries/indicadores atualizados.
    jobs = sch.jobs_configurados(_settings())
    nomes = [j.nome for j in jobs]
    assert nomes.index("refresh_macro") < nomes.index("warm_cache")
    for novo in ("precos_cotahist", "anbima_ettj", "ifdata_trimestral", "aneel_rap"):
        assert nomes.index(novo) < nomes.index("warm_cache")
    assert nomes[-1] == "warm_cache"


def test_job_warm_cache_aquece_lote_default_ibov_mais_multiativo(monkeypatch) -> None:
    # O job do scheduler aquece o MESMO lote do CLI sem args (lote_default):
    # top 10 IBOV + exemplos multiativo (HGLG11, TD-IPCA-2035).
    from app.scripts import warm_cache as wc

    recebido: dict = {}

    def _aquecer(tickers):
        recebido["tickers"] = list(tickers)
        return {"prontas": 12, "total": 12, "custo_usd": 0.0, "falhas": []}

    monkeypatch.setattr(wc, "aquecer", _aquecer)
    detalhe = sch._job_warm_cache()

    assert recebido["tickers"] == wc.lote_default()
    assert recebido["tickers"][-2:] == ["HGLG11", "TD-IPCA-2035"]
    assert "12/12 ready" in str(detalhe)


def test_warm_cache_timeout_dimensionado_para_13_geracoes() -> None:
    # Lote default cresceu para 13 gerações (top 10 IBOV + TAEE11/HGLG11/
    # TD-IPCA-2035 — F6 acrescentou TAEE11, exemplo de energia do DoD):
    # timeout do job sobe para 3900s (folga extra: síntese maior + consenso).
    jobs = sch.jobs_configurados(_settings())
    warm = next(j for j in jobs if j.nome == "warm_cache")
    assert warm.timeout_s == 3900


def test_intervalo_zero_desliga_o_job() -> None:
    jobs = sch.jobs_configurados(
        _settings(
            scheduler_macro_horas=0,
            scheduler_cadastro_horas=0,
            scheduler_cotahist_horas=0,
            scheduler_anbima_horas=0,
            scheduler_ifdata_horas=0,
            scheduler_aneel_horas=0,
            scheduler_warm_cache_horas=0,
        )
    )
    assert [j.nome for j in jobs] == ["reaper"]


def test_warm_cache_zero_desliga_so_ele() -> None:
    jobs = sch.jobs_configurados(_settings(scheduler_warm_cache_horas=0))
    assert [j.nome for j in jobs] == [
        "reaper",
        "refresh_macro",
        "bootstrap_cadastro",
        "precos_cotahist",
        "anbima_ettj",
        "ifdata_trimestral",
        "aneel_rap",
    ]


@pytest.mark.parametrize(
    ("campo", "nome_job"),
    [
        ("scheduler_cotahist_horas", "precos_cotahist"),
        ("scheduler_anbima_horas", "anbima_ettj"),
        ("scheduler_ifdata_horas", "ifdata_trimestral"),
        ("scheduler_aneel_horas", "aneel_rap"),
    ],
)
def test_cada_job_novo_desliga_individualmente_por_intervalo_zero(
    campo: str, nome_job: str
) -> None:
    jobs = sch.jobs_configurados(_settings(**{campo: 0}))
    nomes = [j.nome for j in jobs]
    assert nome_job not in nomes
    assert len(nomes) == 7  # os outros 7 (dos 8 do default) continuam ligados


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


# ---------------------------------------------------------------------------
# Jobs novos de ingest ampliado (fase "Tese Profunda", §2.12) — cada corpo
# tolera `DadoNaoEncontrado` (correção A13: tabela ausente/fonte sem dado)
# como NO-OP com log, nunca uma exceção que o scheduler registraria como
# "erro" no ledger. Sessão NOVA por item nos jobs que iteram um mapa curado
# (ifdata/aneel) — evita carregar uma transação abortada de um item para o
# próximo (Postgres exige ROLLBACK explícito after ProgrammingError).
# ---------------------------------------------------------------------------
class _FakeCommitSession:
    """Sessão fake: só conta commit/rollback/close (sem banco real)."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _monta_session_local_factory(monkeypatch, sessoes: list) -> None:
    """`SessionLocal()` devolve uma `_FakeCommitSession` NOVA a cada chamada
    (mesmo contrato do `sessionmaker` real) — `sessoes` acumula as instâncias
    na ordem de criação, para o teste inspecionar cada uma."""
    import app.db.session as db_session

    def _factory() -> _FakeCommitSession:
        s = _FakeCommitSession()
        sessoes.append(s)
        return s

    monkeypatch.setattr(db_session, "SessionLocal", _factory)


def test_job_precos_cotahist_ingesta_lote_default_mais_bova11(monkeypatch) -> None:
    from app.scripts import warm_cache as wc
    from app.services import cotahist

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)
    capturado: dict = {}

    def _ingest(_session, data, *, tickers):
        capturado["tickers"] = tickers
        capturado["data"] = data
        return 7

    monkeypatch.setattr(cotahist, "ingest_arquivo_diario", _ingest)

    detalhe = sch._job_precos_cotahist()

    # Rastreados = lote_default() (top 10 IBOV + TAEE11/HGLG11/TD-IPCA-2035)
    # + BOVA11 (proxy do índice) — NUNCA o mercado inteiro (correção A9).
    assert capturado["tickers"] == set(wc.lote_default()) | {"BOVA11"}
    assert capturado["data"] == dt.date.today()
    assert "gravados=7" in str(detalhe)
    assert sessoes[0].commits == 1
    assert sessoes[0].rollbacks == 0
    assert sessoes[0].closed is True


def test_job_precos_cotahist_dado_nao_encontrado_vira_no_op(monkeypatch) -> None:
    from app.services import cotahist
    from app.services.dados import DadoNaoEncontrado

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)

    def _ingest(*_a, **_k):
        raise DadoNaoEncontrado("precos_diarios indisponível (tabela ausente)")

    monkeypatch.setattr(cotahist, "ingest_arquivo_diario", _ingest)

    detalhe = sch._job_precos_cotahist()  # NÃO levanta — vira "sem_dado"

    assert detalhe == "sem_dado"
    assert sessoes[0].commits == 0
    assert sessoes[0].rollbacks == 1
    assert sessoes[0].closed is True


def test_job_anbima_ettj_chama_ensure_snapshot_e_comita(monkeypatch) -> None:
    from app.services import anbima_ettj

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)
    monkeypatch.setattr(anbima_ettj, "ensure_snapshot", lambda _s: [1, 2, 3])

    detalhe = sch._job_anbima_ettj()

    assert "linhas=3" in str(detalhe)
    assert sessoes[0].commits == 1


def test_job_anbima_ettj_dado_nao_encontrado_vira_no_op(monkeypatch) -> None:
    from app.services import anbima_ettj
    from app.services.dados import DadoNaoEncontrado

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)

    def _ensure(_s):
        raise DadoNaoEncontrado("curva_snapshot indisponível (tabela ausente)")

    monkeypatch.setattr(anbima_ettj, "ensure_snapshot", _ensure)

    detalhe = sch._job_anbima_ettj()

    assert detalhe == "sem_dado"
    assert sessoes[0].rollbacks == 1


def test_job_ifdata_trimestral_itera_mapa_curado_tolerando_por_banco(monkeypatch) -> None:
    from app.services import ifdata
    from app.services.dados import DadoNaoEncontrado

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)
    monkeypatch.setattr(ifdata, "MAPA_CVM_IFDATA", {111: ("x", "ITAU"), 222: ("y", "OUTRO")})

    def _ensure(_session, cd_cvm):
        if cd_cvm == 222:
            raise DadoNaoEncontrado("banco_indicadores indisponível (tabela ausente)")
        return {"BASILEIA": object()}

    monkeypatch.setattr(ifdata, "ensure_indicadores_banco", _ensure)

    detalhe = sch._job_ifdata_trimestral()  # não levanta mesmo com 1 banco falhando

    assert "ok=1" in str(detalhe)
    assert "sem_dado=1" in str(detalhe)
    # Sessão NOVA por banco: o segundo banco não herda a transação abortada
    # do primeiro (aqui os dois "sucedem" isolados: commit e rollback, cada
    # um na SUA sessão).
    assert len(sessoes) == 2
    assert sessoes[0].commits == 1 and sessoes[0].rollbacks == 0
    assert sessoes[1].commits == 0 and sessoes[1].rollbacks == 1
    assert all(s.closed for s in sessoes)


def test_job_ifdata_trimestral_mapa_vazio_nao_levanta(monkeypatch) -> None:
    from app.services import ifdata

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)
    monkeypatch.setattr(ifdata, "MAPA_CVM_IFDATA", {})

    detalhe = sch._job_ifdata_trimestral()

    assert detalhe == "ok=0 sem_dado=0 bancos=0"
    assert sessoes == []


def test_job_aneel_rap_itera_mapa_curado_tolerando_por_ticker(monkeypatch) -> None:
    from app.services import aneel
    from app.services.dados import DadoNaoEncontrado

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)
    monkeypatch.setattr(aneel, "_GRUPOS_RAP_V1", {"TAEE11": object(), "FAKE99": object()})

    def _ensure(_session, ticker):
        if ticker == "FAKE99":
            raise DadoNaoEncontrado("setor_indicadores indisponível (tabela ausente)")
        return object()

    monkeypatch.setattr(aneel, "ensure_rap", _ensure)

    detalhe = sch._job_aneel_rap()

    assert "ok=1" in str(detalhe)
    assert "sem_dado=1" in str(detalhe)
    assert len(sessoes) == 2
    assert all(s.closed for s in sessoes)


def test_job_aneel_rap_ensure_rap_devolve_none_conta_como_sem_dado(monkeypatch) -> None:
    # Defensivo: `ensure_rap` só devolve None p/ ticker fora do mapa, o que
    # não deveria ocorrer aqui (iteramos o próprio mapa) — mas o job não
    # deve contar como "ok" um resultado ausente.
    from app.services import aneel

    sessoes: list = []
    _monta_session_local_factory(monkeypatch, sessoes)
    monkeypatch.setattr(aneel, "_GRUPOS_RAP_V1", {"TAEE11": object()})
    monkeypatch.setattr(aneel, "ensure_rap", lambda _s, _t: None)

    detalhe = sch._job_aneel_rap()

    assert detalhe == "ok=0 sem_dado=1 tickers=1"


def test_job_novo_com_dado_nao_encontrado_registra_ok_nao_erro_no_ledger(monkeypatch) -> None:
    # Fim a fim via executar_job_sincrono (correção A13/A10): um job cujo
    # corpo absorveu DadoNaoEncontrado devolve uma STRING normal ("sem_dado")
    # — o ledger registra "ok", NUNCA "erro", para uma tabela ainda não
    # migrada não martelar alarme a cada tick.
    log: list = []
    _monta_sessao(monkeypatch, log)

    job = sch.Job(
        nome="anbima_ettj",
        intervalo=dt.timedelta(hours=24),
        timeout_s=300,
        func=lambda: "sem_dado",
    )
    assert sch.executar_job_sincrono(job) == "ok"
    ledgers = [e for e in log if isinstance(e, tuple) and e[0] == "ledger"]
    assert ledgers == [("ledger", "anbima_ettj", "ok")]
