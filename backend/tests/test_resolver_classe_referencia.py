"""_resolver_classe_referencia: resolve a classe do ativo FORA da lane do usuario.

Regressao do fix Onda 4: a lane `authenticated` perdeu (menor-privilegio 0010) o grant em
cvm_cadastro/fii_cadastro; a criacao de tese resolve a classe numa sessao de referencia
separada (worker/sistema) e nunca 500 por permissao — o job reconfirma na geracao.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.routers import teses as teses_router
from app.services.dados import DadoNaoEncontrado


def test_acao_resolve_so_pela_gramatica_sem_banco(monkeypatch):
    # Sufixo 3-8: decide sem tocar o banco (nem worker nem sistema).
    monkeypatch.setattr(teses_router.rls, "SessionRLS", None)
    monkeypatch.setattr(teses_router, "SessionLocal", None)
    assert teses_router._resolver_classe_referencia("PETR4") == "acao"


def test_ambiguo_offline_propaga_abstencao(monkeypatch):
    # Sufixo 11 sem banco: nao ha como desambiguar unit x FII -> abstem (nunca chuta).
    monkeypatch.setattr(teses_router.rls, "SessionRLS", None)
    monkeypatch.setattr(teses_router, "SessionLocal", None)
    with pytest.raises(DadoNaoEncontrado):
        teses_router._resolver_classe_referencia("HGLG11")


def test_erro_de_permissao_no_cadastro_vira_none(monkeypatch):
    # Simula 42501 (lane sem grant em cvm_cadastro) ao consultar o cadastro:
    # a criacao NAO deve 500 — a classe fica None e o job reconfirma na geracao.
    monkeypatch.setattr(teses_router.rls, "SessionRLS", None)

    class _FakeSession:
        def close(self) -> None:
            pass

    monkeypatch.setattr(teses_router, "SessionLocal", lambda: _FakeSession())

    def _boom(ticker, session):
        if session is None:
            raise DadoNaoEncontrado("precisa do cadastro")
        raise OperationalError("select", {}, Exception("permission denied for table cvm_cadastro"))

    monkeypatch.setattr(teses_router, "resolver_classe", _boom)
    assert teses_router._resolver_classe_referencia("HGLG11") is None
