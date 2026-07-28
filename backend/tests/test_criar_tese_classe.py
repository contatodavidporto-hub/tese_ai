"""criar_tese resolve a classe do ativo (fonte única — scripts sem router).

Regressão do bug do E2E da Fase 2: warm_cache/gerar_e_avaliar chamam criar_tese
direto e a tese de FII/renda fixa caía no caminho de ação ('não encontrado no
cadastro CVM'). Casos DB-free: a gramática TD- e o sufixo de ação resolvem antes
de qualquer consulta; sessão fake sem side effects.
"""

from __future__ import annotations

import pytest

from app.services import tese as tese_svc


class _FakeSession:
    def add(self, obj) -> None:  # noqa: ANN001
        self.obj = obj

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:  # noqa: ANN001
        pass


def _criar(ticker: str):
    # Scripts (warm_cache/gerar_e_avaliar) geram o acervo do SISTEMA (público, sem dono);
    # estes casos só checam a resolução de classe, então a visibilidade é irrelevante.
    return tese_svc.criar_tese(_FakeSession(), ticker, user_id=None, visibilidade="publica")


def test_criar_tese_td_resolve_renda_fixa() -> None:
    tese = _criar("td-ipca-2035")
    assert tese.ticker == "TD-IPCA-2035"
    assert tese.classe_ativo == "renda_fixa"


def test_criar_tese_acao_mantem_null_legado() -> None:
    tese = _criar("PETR4")
    assert tese.classe_ativo is None  # NULL = 'acao' (caminho legado byte-idêntico)


def test_criar_tese_identidade_nao_resolvida_deixa_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sufixo 11 sem cadastro nenhum: loga e segue (motor de ação abstém depois)."""
    from app.services.ativos import identidade
    from app.services.dados import DadoNaoEncontrado

    def _explode(codigo: str, session) -> tuple[str, dict]:  # noqa: ANN001
        raise DadoNaoEncontrado(f"ticker {codigo} não encontrado")

    monkeypatch.setattr(identidade, "resolver_classe", _explode)
    tese = _criar("XXXX11")
    assert tese.classe_ativo is None
