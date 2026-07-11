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


# --- Fase 2 multiativo (etapa 14): --force e argv multiclasse -----------------


def test_force_ignora_cache_hit_e_regenera(monkeypatch) -> None:
    # Mesmo com HIT vigente, --force NÃO consulta o cache e regenera tudo.
    cache_chamadas: list[str] = []

    def _cache(_s, ticker, _h):
        cache_chamadas.append(ticker)
        return SimpleNamespace(id="hit", criado_em="2026-07-08")

    _prepara(monkeypatch)
    monkeypatch.setattr(wc, "buscar_tese_cache", _cache)
    gerados: list[str] = []
    monkeypatch.setattr(
        wc, "criar_tese", lambda _s, t: SimpleNamespace(id=f"t-{t}", status="ready")
    )
    monkeypatch.setattr(wc, "gerar_tese", lambda _s, tid: gerados.append(tid))
    monkeypatch.setattr(wc, "_custo_da_tese", lambda _s, _id: 0.34)

    resumo = wc.aquecer(["HGLG11", "TD-IPCA-2035"], force=True)

    assert cache_chamadas == []  # buscar_tese_cache foi PULADO
    assert gerados == ["t-HGLG11", "t-TD-IPCA-2035"]
    assert resumo == {"prontas": 2, "total": 2, "custo_usd": 0.68, "falhas": []}


def test_sem_force_cache_hit_continua_pulando(monkeypatch) -> None:
    # Contraste do --force: sem a flag, HIT pula a geração (comportamento fase 1).
    _prepara(monkeypatch, em_cache=SimpleNamespace(id="t1", criado_em="2026-07-08"))
    chamadas: list[str] = []
    monkeypatch.setattr(wc, "criar_tese", lambda *_a: chamadas.append("criar"))
    monkeypatch.setattr(wc, "gerar_tese", lambda *_a: chamadas.append("gerar"))

    resumo = wc.aquecer(["HGLG11"], force=False)

    assert chamadas == []
    assert resumo["prontas"] == 1


def test_parse_args_aceita_codigos_multiclasse_sem_validar_ibov() -> None:
    args = wc._parse_args(["--force", "HGLG11", "TD-IPCA-2035", "ITUB4"])
    assert args.force is True
    assert args.codigos == ["HGLG11", "TD-IPCA-2035", "ITUB4"]
    # códigos multiclasse NÃO precisam estar na lista IBOV (sem validação).
    ibov = {t for t, _ in wc.TICKERS_IBOV_TOP}
    assert "HGLG11" not in ibov
    assert "TD-IPCA-2035" not in ibov


def test_parse_args_default_sem_force_e_sem_codigos() -> None:
    args = wc._parse_args([])
    assert args.force is False
    assert args.codigos == []


def test_lote_default_e_ibov_top_mais_exemplos_multiativo() -> None:
    # Paridade CLI/scheduler: ambos aquecem o MESMO lote default — top 10 IBOV
    # + exemplos públicos adicionais da galeria (TAEE11 de energia/transmissão
    # — F6, DoD exige exemplo do setor — e FII/renda fixa).
    lote = wc.lote_default()
    assert lote == [t for t, _ in wc.TICKERS_IBOV_TOP] + wc.EXEMPLOS_MULTIATIVO
    assert lote[-3:] == ["TAEE11", "HGLG11", "TD-IPCA-2035"]
    assert len(lote) == len(set(lote)) == 13


def test_main_repassa_force_para_o_nucleo(monkeypatch) -> None:
    recebido: dict = {}

    def _aquecer(tickers, *, force=False, log_fn=None):
        recebido["tickers"] = list(tickers)
        recebido["force"] = force
        return {"prontas": 1, "total": 1, "custo_usd": 0.0, "falhas": []}

    monkeypatch.setattr(wc, "aquecer", _aquecer)

    rc = wc.main(["TD-IPCA-2035"], force=True)

    assert rc == 0
    assert recebido == {"tickers": ["TD-IPCA-2035"], "force": True}
