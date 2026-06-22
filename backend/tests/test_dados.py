"""Testes offline dos helpers puros de ingestão de dados (app.services.dados).

Nenhum acesso a rede/DB/segredos: só funções puras e a checagem de
abstenção em `ensure_empresa` (que rejeita ticker desconhecido ANTES de
tocar na sessão, então passamos session=None).
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.dados import (
    TICKER_CD_CVM,
    DadoNaoEncontrado,
    _aplicar_escala,
    _parse_data,
    _parse_valor,
    ensure_empresa,
)

# ---------------------------------------------------------------------------
# _parse_valor — decimal brasileiro
# ---------------------------------------------------------------------------


def test_parse_valor_decimal_brasileiro_com_milhar() -> None:
    assert _parse_valor("1.234,56") == 1234.56


def test_parse_valor_inteiro_sem_separador() -> None:
    assert _parse_valor("110605000") == 110605000.0


def test_parse_valor_vazio_retorna_none() -> None:
    assert _parse_valor("") is None


def test_parse_valor_none_retorna_none() -> None:
    # raw cai no `(raw or "")` -> vazio -> None.
    assert _parse_valor(None) is None  # type: ignore[arg-type]


def test_parse_valor_espacos_em_branco_retorna_none() -> None:
    assert _parse_valor("   ") is None


def test_parse_valor_lixo_retorna_none() -> None:
    assert _parse_valor("abc") is None


def test_parse_valor_negativo() -> None:
    assert _parse_valor("-1.234,56") == -1234.56


def test_parse_valor_decimal_simples_com_virgula() -> None:
    assert _parse_valor("0,10") == 0.10


def test_parse_valor_ponto_como_milhar_sem_virgula() -> None:
    # Sem ',', não há decimal: o ponto fica e vira float (caso de borda do
    # parser atual). Garante que pelo menos não explode e devolve número.
    valor = _parse_valor("1.234")
    assert isinstance(valor, float)


# ---------------------------------------------------------------------------
# _aplicar_escala — MIL/UNIDADE/desconhecido
# ---------------------------------------------------------------------------


def test_aplicar_escala_mil_multiplica_por_mil() -> None:
    assert _aplicar_escala(2.0, "MIL") == 2000.0


def test_aplicar_escala_unidade_mantem() -> None:
    assert _aplicar_escala(2.0, "UNIDADE") == 2.0


def test_aplicar_escala_desconhecida_multiplica_por_um() -> None:
    assert _aplicar_escala(2.0, "GOOGOL") == 2.0


def test_aplicar_escala_case_insensitive_e_trim() -> None:
    assert _aplicar_escala(3.0, "  mil  ") == 3000.0


def test_aplicar_escala_milhao_acentuado() -> None:
    assert _aplicar_escala(2.0, "MILHÃO") == 2_000_000.0


def test_aplicar_escala_valor_none_propaga_none() -> None:
    assert _aplicar_escala(None, "MIL") is None


def test_aplicar_escala_string_vazia_multiplica_por_um() -> None:
    assert _aplicar_escala(5.0, "") == 5.0


# ---------------------------------------------------------------------------
# _parse_data — ISO e BR
# ---------------------------------------------------------------------------


def test_parse_data_iso() -> None:
    assert _parse_data("2025-12-31") == dt.date(2025, 12, 31)


def test_parse_data_br() -> None:
    assert _parse_data("31/12/2025") == dt.date(2025, 12, 31)


def test_parse_data_invalida_retorna_none() -> None:
    assert _parse_data("não é data") is None


def test_parse_data_vazia_retorna_none() -> None:
    assert _parse_data("") is None


def test_parse_data_none_retorna_none() -> None:
    assert _parse_data(None) is None  # type: ignore[arg-type]


def test_parse_data_com_espacos_em_volta() -> None:
    assert _parse_data("  2025-01-02  ") == dt.date(2025, 1, 2)


# ---------------------------------------------------------------------------
# Registro CVM
# ---------------------------------------------------------------------------


def test_ticker_petr4_mapeia_para_cd_cvm_9512() -> None:
    cd_cvm, _nome, _setor = TICKER_CD_CVM["PETR4"]
    assert cd_cvm == 9512


# ---------------------------------------------------------------------------
# ensure_empresa — abstenção para ticker desconhecido (sem tocar na sessão)
# ---------------------------------------------------------------------------


def test_ensure_empresa_ticker_desconhecido_levanta_antes_da_sessao() -> None:
    # session=None comprova que a abstenção ocorre ANTES de usar o banco.
    with pytest.raises(DadoNaoEncontrado):
        ensure_empresa(None, "XXXX")  # type: ignore[arg-type]


def test_ensure_empresa_mensagem_indica_dado_nao_encontrado() -> None:
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        ensure_empresa(None, "zzzz")  # type: ignore[arg-type]
