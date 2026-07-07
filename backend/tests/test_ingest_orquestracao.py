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
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent", _falha)  # <- esta falha
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
    # As 6 chaves (5 dimensões) estão no resultado.
    assert set(res) == {
        "fundamentos",
        "macro_br",
        "commodities_brent",
        "macro_global_wb",
        "macro_global_treasury",
        "pares_globais",
    }
    # Falha injetada no meio do conjunto: SÓ o passo que falhou volta ao
    # SAVEPOINT (o DML parcial dele — ex.: delete do snapshot — é desfeito);
    # os outros 5 seguem para o commit único.
    assert len(sess.savepoints) == 6
    assert sum(sp.rolled_back for sp in sess.savepoints) == 1
    assert sum(sp.committed for sp in sess.savepoints) == 5


def test_ingest_macro_refresh_roda_so_series_globais(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[str] = []

    def _reg(nome: str):
        def _fn(*_a, **_k):
            chamadas.append(nome)

        return _fn

    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent", _reg("brent"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_world_bank", _reg("wb"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_treasury_10y", _reg("tr"))

    sess = _FakeSession()
    res = orquestracao.ingest_macro_refresh(sess)

    assert set(res) == {"macro_br", "commodities_brent", "macro_global_wb", "macro_global_treasury"}
    assert all(v == "ok" for v in res.values())
    assert chamadas == ["macro", "brent", "wb", "tr"]  # nada de empresa/pares aqui
    assert sess.commits == 1
