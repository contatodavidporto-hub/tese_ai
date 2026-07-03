"""Testes do cache de tese pública, do reaper de órfãs e da métrica de fidelidade.

Cache e reaper usam uma sessão FAKE (sem DB): validam a LÓGICA de seleção/marcação
sem tocar no banco. A fidelidade numérica é testada sobre envelopes montados à mão.
"""

from __future__ import annotations

import datetime as dt

from app.services import tese as tese_svc
from app.services.avaliacao import _faithfulness_numerica, avaliar_tese


class _FakeTese:
    def __init__(self, ticker: str, status: str, criado_em: dt.datetime) -> None:
        self.id = f"id-{ticker}-{status}"
        self.user_id = "u1"
        self.ticker = ticker
        self.status = status
        self.criado_em = criado_em


class _FakeScalarResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeScalars:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeQuerySession:
    """Devolve `rows` filtradas por um predicado simples de status simulado."""

    def __init__(self, rows: list) -> None:
        self._rows = rows
        self.committed = False
        self.added: list = []

    def execute(self, _stmt):
        return _FakeScalarResult(self._rows)

    def add(self, obj) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.committed = True


# --- Cache de tese pública ---------------------------------------------------
def test_cache_desligado_retorna_none() -> None:
    s = _FakeQuerySession([_FakeTese("PETR4", "ready", dt.datetime.now(dt.UTC))])
    assert tese_svc.buscar_tese_cache(s, "PETR4", ttl_horas=0) is None


def test_cache_hit_devolve_tese_ready_recente() -> None:
    recente = _FakeTese("PETR4", "ready", dt.datetime.now(dt.UTC))
    s = _FakeQuerySession([recente])
    hit = tese_svc.buscar_tese_cache(s, "petr4", ttl_horas=24)
    assert hit is recente


def test_cache_miss_sem_linhas() -> None:
    s = _FakeQuerySession([])
    assert tese_svc.buscar_tese_cache(s, "PETR4", ttl_horas=24) is None


# --- Reaper de órfãs ---------------------------------------------------------
def test_reaper_desligado_nao_faz_nada() -> None:
    s = _FakeQuerySession([_FakeTese("PETR4", "processing", dt.datetime.now(dt.UTC))])
    assert tese_svc.reaper_teses_orfas(s, timeout_min=0) == 0
    assert s.committed is False


def test_reaper_marca_orfas_como_error() -> None:
    velha = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
    orfa = _FakeTese("PETR4", "processing", velha)
    s = _FakeQuerySession([orfa])
    n = tese_svc.reaper_teses_orfas(s, timeout_min=15)
    assert n == 1
    assert orfa.status == "error"
    assert s.committed is True
    assert len(s.added) == 1  # gravou uma TeseVersao com o erro


# --- Fidelidade numérica (proxy RAGAS/NLI-lite) ------------------------------
def test_faithfulness_todos_numeros_ancorados() -> None:
    md = "Receita = R$ 497.549.000.000,00 e Selic 14,25%."
    citacoes = [
        {"texto_citado": "Receita (3.01) = R$ 497.549.000.000,00 (ref. 2025-12-31)"},
        {"texto_citado": "Meta Selic 14,25% a.a. (SGS 432)"},
    ]
    assert _faithfulness_numerica(md, citacoes) == 1.0


def test_faithfulness_numero_inventado_baixa_score() -> None:
    md = "Receita = R$ 497.549.000.000,00 e um número inventado 88.888."
    citacoes = [{"texto_citado": "Receita (3.01) = R$ 497.549.000.000,00"}]
    score = _faithfulness_numerica(md, citacoes)
    assert score is not None and score < 1.0


def test_faithfulness_none_sem_numeros() -> None:
    assert _faithfulness_numerica("Texto sem números relevantes.", []) is None


def test_avaliar_tese_expoe_faithfulness() -> None:
    fonte = {"id": "1", "url": "https://dados.cvm.gov.br/x", "descricao": "CVM"}
    envelope = {
        "markdown": "## Fundamentos\nReceita = R$ 497.549.000.000,00 (CVM DFP 2025).",
        "citacoes": [{"texto_citado": "Receita = R$ 497.549.000.000,00", "fonte": fonte}],
        "fontes": [fonte],
        "lacunas": [],
    }
    laudo = avaliar_tese(envelope)
    assert laudo["faithfulness_numerica"] == 1.0
