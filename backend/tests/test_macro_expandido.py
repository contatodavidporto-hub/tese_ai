"""Testa que a camada macro doméstica (D3) foi ampliada com IPCA e IGP-M.

Sem rede: inspeciona o mapa de séries usado por ingest_macro (via introspecção
do código-fonte da função) para garantir os códigos SGS corretos e sem
ambiguidade, e exercita a robustez a corpo inesperado do SGS com `bcb_sgs`
monkeypatchado + sessão fake (sem banco).
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from app.services import dados


def test_ingest_macro_inclui_ipca_433_e_igpm_189() -> None:
    fonte = inspect.getsource(dados.ingest_macro)
    # IPCA série 433 e IGP-M série 189 (códigos SGS estáveis do BCB).
    assert '"IPCA_MENSAL": (433,' in fonte
    assert '"IGP_M_MENSAL": (189,' in fonte


def test_ingest_macro_mantem_selic_diaria_separada_da_meta() -> None:
    # Anti-alucinação: a Selic diária (% a.d.) não pode ser confundida com a meta anual.
    fonte = inspect.getsource(dados.ingest_macro)
    assert '"SELIC_DIARIA": (11,' in fonte
    assert '"SELIC_META_ANUAL": (432,' in fonte


# ---------------------------------------------------------------------------
# Robustez do refresh_macro: BCB SGS respondendo 200 com corpo dict
# (erro/manutenção) estourava KeyError(-1) em `pontos[-1]` e derrubava as 5
# séries do passo. Corpo inesperado = falha SÓ daquela série (log + continue).
# ---------------------------------------------------------------------------


class _FakeMacroSession:
    """Sessão fake mínima: upsert sempre cai no INSERT (sem banco)."""

    def __init__(self) -> None:
        self.added: list = []

    def execute(self, _stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def add(self, obj) -> None:
        self.added.append(obj)


def test_ingest_macro_corpo_dict_do_sgs_nao_derruba_o_passo(monkeypatch) -> None:
    # Todas as séries respondem 200 com corpo dict: nenhuma exceção, zero gravados.
    monkeypatch.setattr(dados, "bcb_sgs", lambda _c, n=1: {"erro": "em manutenção"})
    sess = _FakeMacroSession()

    gravados = dados.ingest_macro(sess)

    assert gravados == []
    assert sess.added == []


def test_ingest_macro_corpo_dict_falha_so_a_serie_e_o_lote_segue(monkeypatch) -> None:
    # Só a Selic diária (código 11) vem com corpo dict: as outras 4 séries
    # persistem normalmente — a falha é DA série, não do passo.
    def _fake_sgs(codigo: int, n: int = 1):
        if codigo == 11:
            return {"status": 503, "mensagem": "indisponível"}
        return [{"data": "08/07/2026", "valor": "14,15"}]

    monkeypatch.setattr(dados, "bcb_sgs", _fake_sgs)
    monkeypatch.setattr(dados, "get_or_create_fonte", lambda _s, **_kw: 1)
    sess = _FakeMacroSession()

    gravados = dados.ingest_macro(sess)

    codigos = {ms.codigo for ms in gravados}
    assert "SELIC_DIARIA" not in codigos
    assert codigos == {"SELIC_META_ANUAL", "USD_VENDA", "IPCA_MENSAL", "IGP_M_MENSAL"}
    assert len(sess.added) == 4
