"""Warm-cache (núcleo `aquecer`): cache hit não gasta, falha não derruba o lote.

Sem banco e sem LLM: sessões e serviços fake. O contrato é o do job do
scheduler — hit pulado (custo zero), geração conta custo, um ticker quebrado
entra em `falhas` e o lote segue, e sem DATABASE_URL o núcleo levanta erro
(o CLI traduz para mensagem; o job registra "erro" no ledger).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.scripts import warm_cache as wc


class _FakeSession:
    def close(self) -> None:  # pragma: no cover - trivial
        pass

    def expire_all(self) -> None:
        pass

    def refresh(self, _obj) -> None:
        pass


def _prepara(monkeypatch, *, em_cache=None) -> None:
    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(wc, "get_settings", lambda: SimpleNamespace(tese_cache_horas=24))
    monkeypatch.setattr(wc, "buscar_tese_cache", lambda _s, _t, _h: em_cache)


def test_cache_hit_pula_a_geracao_e_conta_como_pronta(monkeypatch) -> None:
    _prepara(monkeypatch, em_cache=SimpleNamespace(id="t1", criado_em="2026-07-08"))
    chamadas: list[str] = []
    monkeypatch.setattr(wc, "criar_tese", lambda *_a: chamadas.append("criar"))
    monkeypatch.setattr(wc, "gerar_tese", lambda *_a: chamadas.append("gerar"))

    resumo = wc.aquecer(["VALE3"])

    assert resumo == {"prontas": 1, "total": 1, "custo_usd": 0.0, "falhas": []}
    assert chamadas == []  # hit NÃO chama o LLM — custo zero


def test_geracao_ready_soma_custo(monkeypatch) -> None:
    _prepara(monkeypatch, em_cache=None)
    tese = SimpleNamespace(id="t2", status="ready")
    monkeypatch.setattr(wc, "criar_tese", lambda _s, _t: tese)
    monkeypatch.setattr(wc, "gerar_tese", lambda _s, _id: None)
    monkeypatch.setattr(wc, "_custo_da_tese", lambda _s, _id: 0.27)

    resumo = wc.aquecer(["PETR4"])

    assert resumo["prontas"] == 1
    assert resumo["custo_usd"] == 0.27
    assert resumo["falhas"] == []


def test_ticker_quebrado_nao_derruba_o_lote(monkeypatch) -> None:
    _prepara(monkeypatch, em_cache=None)

    def _criar(_s, ticker):
        if ticker == "RUIM3":
            raise RuntimeError("fonte fora do ar")
        return SimpleNamespace(id="t3", status="ready")

    monkeypatch.setattr(wc, "criar_tese", _criar)
    monkeypatch.setattr(wc, "gerar_tese", lambda _s, _id: None)
    monkeypatch.setattr(wc, "_custo_da_tese", lambda _s, _id: None)

    resumo = wc.aquecer(["RUIM3", "VALE3"])

    assert resumo["prontas"] == 1  # o lote seguiu após a falha
    assert resumo["falhas"] == ["RUIM3"]


def test_geracao_nao_ready_entra_em_falhas(monkeypatch) -> None:
    # Gate reprovou / teto de custo abstém => status != ready: registrado como
    # falha no resumo (vai para o detalhe do ledger), sem exceção.
    _prepara(monkeypatch, em_cache=None)
    monkeypatch.setattr(wc, "criar_tese", lambda _s, _t: SimpleNamespace(id="t4", status="error"))
    monkeypatch.setattr(wc, "gerar_tese", lambda _s, _id: None)
    monkeypatch.setattr(wc, "_custo_da_tese", lambda _s, _id: None)

    resumo = wc.aquecer(["WEGE3"])

    assert resumo["prontas"] == 0
    assert resumo["falhas"] == ["WEGE3"]


def test_sem_database_url_levanta_erro(monkeypatch) -> None:
    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", None)
    with pytest.raises(RuntimeError):
        wc.aquecer(["VALE3"])
