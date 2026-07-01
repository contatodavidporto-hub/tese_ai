"""Testa a orquestração da ingestão das 5 dimensões com falha isolada por fonte."""

from __future__ import annotations

import pytest

from app.models.models import Empresa
from app.services import orquestracao


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

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
