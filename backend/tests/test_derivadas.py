"""Testes offline das métricas derivadas (app.services.derivadas).

Foco anti-alucinação: abstém (None) quando falta componente; NUNCA 0-fill.
"""

from __future__ import annotations

from app.services.derivadas import (
    DERIVADAS,
    caixa_e_aplicacoes,
    divida_bruta,
    divida_liquida,
)


def test_divida_bruta_soma_emprestimos_circulante_e_nao_circulante() -> None:
    valor, codigos = divida_bruta({"2.01.04": 100.0, "2.02.01": 400.0})
    assert valor == 500.0
    assert codigos == ["2.01.04", "2.02.01"]


def test_divida_bruta_abstem_se_faltar_um_componente() -> None:
    # Só circulante presente -> None (não trata o não-circulante ausente como 0).
    valor, _ = divida_bruta({"2.01.04": 100.0})
    assert valor is None


def test_caixa_e_aplicacoes_soma() -> None:
    valor, _ = caixa_e_aplicacoes({"1.01.01": 50.0, "1.01.02": 150.0})
    assert valor == 200.0


def test_divida_liquida_bruta_menos_caixa() -> None:
    contas = {"2.01.04": 100.0, "2.02.01": 400.0, "1.01.01": 50.0, "1.01.02": 150.0}
    valor, codigos = divida_liquida(contas)
    assert valor == 300.0  # 500 - 200
    assert set(codigos) == {"2.01.04", "2.02.01", "1.01.01", "1.01.02"}


def test_divida_liquida_abstem_sem_caixa() -> None:
    valor, _ = divida_liquida({"2.01.04": 100.0, "2.02.01": 400.0})
    assert valor is None


def test_divida_liquida_pode_ser_negativa_caixa_liquido() -> None:
    # Caixa > dívida => dívida líquida negativa (posição de caixa líquido). Válido.
    contas = {"2.01.04": 10.0, "2.02.01": 20.0, "1.01.01": 100.0, "1.01.02": 0.0}
    valor, _ = divida_liquida(contas)
    assert valor == -70.0


def test_registro_derivadas_nao_inclui_ebitda_nem_fcf_livre() -> None:
    # EBITDA (precisa D&A) e FCF livre (precisa CapEx) permanecem LACUNA explícita.
    nomes = " ".join(DERIVADAS).lower()
    assert "ebitda" not in nomes
    assert "fcf" not in nomes and "livre" not in nomes
