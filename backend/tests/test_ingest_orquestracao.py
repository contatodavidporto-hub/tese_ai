"""Testa a orquestração da ingestão das 5 dimensões com falha isolada por fonte."""

from __future__ import annotations

from types import SimpleNamespace

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


class _FakeResult:
    """Resultado mínimo que satisfaz `.first()` e `.scalars().all()` — os
    dois formatos usados pelos guards de reingest (`orquestracao.
    _tem_fundamento` / `fii_dados.indicadores_recentes`)."""

    def __init__(self, linhas: list | None = None) -> None:
        self._linhas = linhas or []

    def first(self):
        return self._linhas[0] if self._linhas else None

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list:
        return self._linhas

    def scalar_one_or_none(self):
        return self._linhas[0] if self._linhas else None


class _FakeSession:
    def __init__(self, *, linhas_execute: list | None = None) -> None:
        self.commits = 0
        self.savepoints: list[_FakeSavepoint] = []
        # Linhas devolvidas por QUALQUER `.execute(...)` — usado pelos guards
        # de reingest (fundamento/indicador já persistido). Vazio por padrão:
        # espelha "empresa/fundo ainda sem NADA persistido", o cenário destes
        # testes pré-existentes (ingest roda normalmente).
        self._linhas_execute = linhas_execute or []

    def begin_nested(self) -> _FakeSavepoint:
        sp = _FakeSavepoint()
        self.savepoints.append(sp)
        return sp

    def execute(self, *_a, **_k) -> _FakeResult:
        return _FakeResult(self._linhas_execute)

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
    # Ingest AMPLIADO (F3, plano §2.1): COTAHIST (ticker + BOVA11 p/ β) e
    # proventos B3 rodam para toda ação/unit (empresa sem plano financeiro/
    # setor energia -> IF.data e ANEEL RAP NÃO disparam, achado do escopo).
    monkeypatch.setattr(orquestracao.cotahist, "ensure_precos", _reg("cotahist"))
    monkeypatch.setattr(orquestracao.proventos_b3, "ensure_proventos", _reg("proventos"))

    sess = _FakeSession()
    res = orquestracao.ingest_completo(sess, Empresa(nome="X", ticker="XXXX3"))

    # A fonte que falhou é isolada; as demais rodam mesmo assim.
    assert res["commodities_brent"].startswith("falha")
    assert res["fundamentos"] == "ok"
    assert res["macro_global_treasury"] == "ok"
    assert res["pares_globais"] == "ok"  # passo após a falha ainda rodou
    assert res["cotahist_precos"] == "ok"
    assert res["cotahist_bova11"] == "ok"
    assert res["proventos_b3"] == "ok"
    # Passos após a falha executaram (não abortou o conjunto).
    assert "pares" in chamadas
    # Sem plano financeiro/setor energia detectados: IF.data e ANEEL não entram.
    assert "ifdata_banco" not in res
    assert "aneel_rap" not in res
    # Commit único ao final, mesmo com falha isolada.
    assert sess.commits == 1
    # As 11 chaves (5 dimensões + históricos + ingest ampliado F3) estão no resultado.
    assert set(res) == {
        "fundamentos",
        "cotahist_precos",
        "cotahist_bova11",
        "proventos_b3",
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
    assert len(sess.savepoints) == 11
    assert sum(sp.rolled_back for sp in sess.savepoints) == 1
    assert sum(sp.committed for sp in sess.savepoints) == 10


def test_ingest_completo_dispara_ifdata_e_aneel_por_plano_e_setor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Achado do escopo (F3): IF.data só dispara com plano financeiro E cd_cvm
    resolvido; ANEEL RAP só dispara com setor energia/transmissão detectado."""
    chamadas: list[str] = []

    def _reg(nome: str):
        def _fn(*_a, **_k):
            chamadas.append(nome)

        return _fn

    for alvo, metodo, rotulo in (
        (orquestracao.dados_svc, "ingest_fundamentos", "fundamentos"),
        (orquestracao.dados_svc, "ingest_macro", "macro"),
        (orquestracao.dados_svc, "ingest_usd_historico", "usd_hist"),
        (orquestracao.commodities, "ingest_brent", "brent"),
        (orquestracao.commodities, "ingest_brent_historico", "brent_hist"),
        (orquestracao.macro_global, "ingest_world_bank", "wb"),
        (orquestracao.macro_global, "ingest_treasury_10y", "tr"),
        (orquestracao.sec, "ingest_pares", "pares"),
        (orquestracao.cotahist, "ensure_precos", "cotahist"),
        (orquestracao.proventos_b3, "ensure_proventos", "proventos"),
    ):
        monkeypatch.setattr(alvo, metodo, _reg(rotulo))
    monkeypatch.setattr(orquestracao.ifdata, "ensure_indicadores_banco", _reg("ifdata"))
    monkeypatch.setattr(orquestracao.aneel, "ensure_rap", _reg("aneel"))

    sess = _FakeSession()
    empresa = Empresa(
        nome="Banco Y", ticker="BBBB4", cd_cvm=123, plano_contas="banco", setor="Energia Elétrica"
    )
    res = orquestracao.ingest_completo(sess, empresa)

    assert res["ifdata_banco"] == "ok"
    assert res["aneel_rap"] == "ok"
    assert "ifdata" in chamadas and "aneel" in chamadas


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
    # Sem ticker (heurística de ISIN zerada por colisão): passos de B3
    # (COTAHIST/proventos) são PULADOS — nunca tentam consultar sem código.
    assert set(res) == {"fii_indicadores", "fii_vacancia", "macro_br", "cdi", "focus"}


def test_ingest_fii_completo_com_ticker_dispara_cotahist_e_proventos_em_ordem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingest AMPLIADO (F3): com ticker resolvido, COTAHIST/proventos rodam
    APÓS indicadores/vacância (isin do fii_cadastro já populado pelo informe)."""
    chamadas: list[str] = []

    def _reg(nome: str):
        def _fn(*_a, **_k):
            chamadas.append(nome)

        return _fn

    monkeypatch.setattr(orquestracao.fii_dados, "ingest_indicadores", _reg("indicadores"))
    monkeypatch.setattr(orquestracao.fii_dados, "ingest_vacancia", _reg("vacancia"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.focus, "ingest_cdi", _reg("cdi"))
    monkeypatch.setattr(orquestracao.focus, "ingest_focus", _reg("focus"))
    monkeypatch.setattr(orquestracao.cotahist, "ensure_precos", _reg("cotahist"))
    monkeypatch.setattr(orquestracao.proventos_b3, "ensure_proventos", _reg("proventos"))

    sess = _FakeSession()
    from app.models.models import FiiCadastro

    fundo = FiiCadastro(cnpj="00", nome="FII Y", ticker="HGLG11")
    res = orquestracao.ingest_fii_completo(sess, fundo)

    assert res["fii_cotahist_precos"] == "ok"
    assert res["fii_proventos_b3"] == "ok"
    assert chamadas.index("indicadores") < chamadas.index("cotahist")
    assert chamadas.index("cotahist") < chamadas.index("proventos")


def test_ingest_renda_fixa_completo_so_o_titulo_pedido(monkeypatch: pytest.MonkeyPatch) -> None:
    capturas: list[tuple] = []

    def _titulo(_sess, familia, ano, **_k):
        capturas.append((familia, ano))

    def _reg(nome: str):
        def _fn(*_a, **_k):
            capturas.append((nome,))

        return _fn

    monkeypatch.setattr(orquestracao.tesouro, "ingest_titulo", _titulo)
    monkeypatch.setattr(orquestracao.anbima_ettj, "ensure_snapshot", _reg("anbima_ettj"))
    monkeypatch.setattr(orquestracao.focus, "ingest_cdi", _reg("cdi"))
    monkeypatch.setattr(orquestracao.focus, "ingest_focus", _reg("focus"))

    sess = _FakeSession()
    res = orquestracao.ingest_renda_fixa_completo(sess, "IPCA", 2035)

    # Só o título PEDIDO é ingerido (nunca o CSV inteiro) + snapshot ANBIMA do
    # dia (ingest AMPLIADO F3) + CDI/Focus.
    assert capturas[0] == ("IPCA", 2035)
    assert set(res) == {"titulo_tesouro", "anbima_ettj", "cdi", "focus"}
    assert all(v == "ok" for v in res.values())
    assert sess.commits == 1


# ---------------------------------------------------------------------------
# Bug "tese legada silenciosa" (2026-07-11): reingest disparado só por preço
# stale NÃO pode re-baixar o passo mais caro (DFP/informe) — só os conectores
# que ainda faltam (que já se auto-noop quando frescos, ver `test_cotahist.py`
# e `test_fii_dados.py`).
# ---------------------------------------------------------------------------
def test_ingest_completo_pula_dfp_quando_empresa_ja_tem_fundamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas_dfp = 0

    def _dfp(*_a, **_k):
        nonlocal chamadas_dfp
        chamadas_dfp += 1

    def _reg(nome: str):
        def _fn(*_a, **_k):
            pass

        return _fn

    monkeypatch.setattr(orquestracao.dados_svc, "ingest_fundamentos", _dfp)
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_usd_historico", _reg("usd_hist"))
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent", _reg("brent"))
    monkeypatch.setattr(orquestracao.commodities, "ingest_brent_historico", _reg("brent_hist"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_world_bank", _reg("wb"))
    monkeypatch.setattr(orquestracao.macro_global, "ingest_treasury_10y", _reg("tr"))
    monkeypatch.setattr(orquestracao.sec, "ingest_pares", _reg("pares"))
    monkeypatch.setattr(orquestracao.cotahist, "ensure_precos", _reg("cotahist"))
    monkeypatch.setattr(orquestracao.proventos_b3, "ensure_proventos", _reg("proventos"))

    # `_linhas_execute` não-vazio -> `_tem_fundamento` acha uma linha (mesmo
    # formato de `select(Fundamento.id)...first()`).
    sess = _FakeSession(linhas_execute=[SimpleNamespace(id="fundamento-existente")])
    empresa = Empresa(nome="VALE3 LTDA", ticker="VALE3", cd_cvm=4170)

    res = orquestracao.ingest_completo(sess, empresa)

    # DFP NUNCA foi chamada (passo mais caro pulado)...
    assert chamadas_dfp == 0
    assert res["fundamentos"].startswith("pulado")
    # ...mas os conectores restantes (COTAHIST/proventos/macro/pares) rodam
    # normalmente — cada um já se auto-noop quando fresco por conta própria.
    assert res["cotahist_precos"] == "ok"
    assert res["cotahist_bova11"] == "ok"
    assert res["proventos_b3"] == "ok"
    assert res["pares_globais"] == "ok"
    assert sess.commits == 1


def test_ingest_fii_completo_pula_informe_quando_indicador_ja_fresco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas_informe: list[str] = []

    def _reg_informe(nome: str):
        def _fn(*_a, **_k):
            chamadas_informe.append(nome)

        return _fn

    def _reg(nome: str):
        def _fn(*_a, **_k):
            pass

        return _fn

    monkeypatch.setattr(orquestracao.fii_dados, "ingest_indicadores", _reg_informe("indicadores"))
    monkeypatch.setattr(orquestracao.fii_dados, "ingest_vacancia", _reg_informe("vacancia"))
    monkeypatch.setattr(orquestracao.dados_svc, "ingest_macro", _reg("macro"))
    monkeypatch.setattr(orquestracao.focus, "ingest_cdi", _reg("cdi"))
    monkeypatch.setattr(orquestracao.focus, "ingest_focus", _reg("focus"))
    monkeypatch.setattr(orquestracao.cotahist, "ensure_precos", _reg("cotahist"))
    monkeypatch.setattr(orquestracao.proventos_b3, "ensure_proventos", _reg("proventos"))

    # `_linhas_execute` não-vazio -> `fii_dados.indicadores_recentes` acha um
    # indicador (mesmo formato de `select(FiiIndicador)...scalars().all()`).
    sess = _FakeSession(linhas_execute=[SimpleNamespace(indicador="VP_COTA")])
    from app.models.models import FiiCadastro

    fundo = FiiCadastro(cnpj="00", nome="FII Z", ticker="HGLG11")

    res = orquestracao.ingest_fii_completo(sess, fundo)

    # Nenhum passo de informe (mensal/trimestral, os mais caros) foi chamado...
    assert chamadas_informe == []
    assert res["fii_indicadores"].startswith("pulado")
    assert res["fii_vacancia"].startswith("pulado")
    # ...mas COTAHIST/proventos (o gatilho real do reingest) rodam normalmente.
    assert res["fii_cotahist_precos"] == "ok"
    assert res["fii_proventos_b3"] == "ok"
    assert sess.commits == 1
