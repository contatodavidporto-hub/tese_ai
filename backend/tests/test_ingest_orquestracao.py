"""Testa a orquestração da ingestão das 5 dimensões com falha isolada por fonte."""

from __future__ import annotations

import pytest

from app.models.models import Empresa
from app.services import orquestracao


class _FakeSavepoint:
    """Registra o destino do SAVEPOINT de cada passo (commit ou rollback)."""

    def __init__(self) -> None:
        self.rolled_back = False
        self.committed = False

    def __enter__(self) -> _FakeSavepoint:
        return self

    def __exit__(self, exc_type, *_exc) -> bool:
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True
        return False  # exceção propaga para o `passo` tratar


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.savepoints: list[_FakeSavepoint] = []

    def begin_nested(self) -> _FakeSavepoint:
        sp = _FakeSavepoint()
        self.savepoints.append(sp)
        return sp

    def commit(self) -> None:
        self.commits += 1


def test_ingest_completo_isola_falha_de_uma_fonte(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []

    def _reg(nome: str):
        def _fn(*_a, **_k):
            chamadas.append(nome)

        return _fn

    def _falha(*_a, **_k):
        raise RuntimeError("rede indisponível")

    monkeypatch.setattr(orquestracao.dados_svc, "ingest_fundamentos", _reg("fundamentos"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_usd_historico", _reg("usd_hist"))
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent", _falha)  # <- esta falha
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent_historico", _reg("brent_hist"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_world_bank", _reg("wb"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_treasury_10y", _reg("tr"))
    monkeypatch.setattr(orquestracao.sec, "ingest_pares", _reg("pares"))

    sess = _FakeSession()
    res = orquestracao.ingest_completo(sess, Empresa(nome="X", ticker="XXXX3"))

    # A fonte que falhou é isolada; as demais rodam mesmo assim.
    assert res["commodities_brent"].startswith("falha")
    assert res["fundamentos"] == "ok"
    assert res["macro_global_treasury"] == "ok"
    assert res["pares_globais"] == "ok"  # passo após a falha ainda rodou
    # Passos após a falha executaram (não abortou o conjunto).
    assert "pares" in chamadas
    # Commit único ao final, mesmo com falha isolada.
    assert sess.commits == 1
    # As 8 chaves (5 dimensões + históricos) estão no resultado.
    assert set(res) == {
        "fundamentos",
        "macro_br",
        "usd_historico",
        "commodities_brent",
        "brent_historico",
        "macro_global_wb",
        "macro_global_treasury",
        "pares_globais",
    }
    # Falha injetada no meio do conjunto: SÓ o passo que falhou volta ao
    # SAVEPOINT (o DML parcial dele — ex.: delete do snapshot — é desfeito);
    # os outros seguem para o commit único.
    assert len(sess.savepoints) == 8
    assert sum(sp.rolled_back for sp in sess.savepoints) == 1
    assert sum(sp.committed for sp in sess.savepoints) == 7


def test_ingest_macro_refresh_roda_so_series_globais(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []

    def _reg(nome: str):
        def _fn(*_a, **_k):
            chamadas.append(nome)

        return _fn

    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_usd_historico", _reg("usd_hist"))
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent", _reg("brent"))
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent_historico", _reg("brent_hist"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_world_bank", _reg("wb"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_treasury_10y", _reg("tr"))

    sess = _FakeSession()
    res = orquestracao.ingest_macro_refresh(sess)

    assert set(res) == {
        "macro_br",
        "usd_historico",
        "commodities_brent",
        "brent_historico",
        "macro_global_wb",
        "macro_global_treasury",
    }
    assert all(v == "ok" for v in res.values())
    # Ordem inclui os históricos; nada de empresa/pares aqui.
    assert chamadas == ["macro", "usd_hist", "brent", "brent_hist", "wb", "tr"]
    assert sess.commits == 1


# ---------------------------------------------------------------------------
# Ingest por classe (etapa 11/D) — mesmos passos isolados, escopo da classe
# ---------------------------------------------------------------------------
def test_ingest_fii_completo_passos_isolados(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []

    def _reg(nome: str):
        def _fn(*_a, **_k):
            chamadas.append(nome)

        return _fn

    def _falha(*_a, **_k):
        raise RuntimeError("Olinda fora do ar")

    monkeypatch.setattr(orquestracao.fii_dados, "ingest_indicadores", _reg("indicadores"))
    monkeypatch.setattr(orquestracao.fii_dados, "ingest_vacancia", _reg("vacancia"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.focus, "ingest_cdi", _reg("cdi"))
    monkeypatch.setattr(orquestracao.focus, "ingest_focus", _falha)  # <- Focus cai

    sess = _FakeSession()
    from app.models.models import FiiCadastro

    res = orquestracao.ingest_fii_completo(sess, FiiCadastro(cnpj="00", nome="FII X"))

    # Olinda caiu -> só o passo Focus degrada; indicadores/vacância/CDI seguem.
    assert res["focus"].startswith("falha")
    assert res["fii_indicadores"] == "ok"
    assert res["fii_vacancia"] == "ok"
    assert res["macro_br"] == "ok"
    assert res["cdi"] == "ok"
    assert chamadas == ["indicadores", "vacancia", "macro", "cdi"]
    assert sess.commits == 1
    assert set(res) == {"fii_indicadores", "fii_vacancia", "macro_br", "cdi", "focus"}


def test_ingest_renda_fixa_completo_so_o_titulo_pedido(monkeypatch: pytest.MonkeyPatch) -> None:
    capturas: list[tuple] = []

    def _titulo(_sess, familia, ano, **_k):
        capturas.append((familia, ano))

    def _reg(nome: str):
        def _fn(*_a, **_k):
            capturas.append((nome,))

        return _fn

    monkeypatch.setattr(orquestracao.tesouro, "ingest_titulo", _titulo)
    monkeypatch.setattr(orquestracao.focus, "ingest_cdi", _reg("cdi"))
    monkeypatch.setattr(orquestracao.focus, "ingest_focus", _reg("focus"))

    sess = _FakeSession()
    res = orquestracao.ingest_renda_fixa_completo(sess, "IPCA", 2035)

    # Só o título PEDIDO é ingerido (nunca o CSV inteiro) + CDI/Focus.
    assert capturas[0] == ("IPCA", 2035)
    assert set(res) == {"titulo_tesouro", "cdi", "focus"}
    assert all(v == "ok" for v in res.values())
    assert sess.commits == 1
