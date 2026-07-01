"""Testes offline da resolução universal de ticker B3 (app.services.cvm_cadastro).

Sem rede/DB: parsers puros sobre fixtures latin-1 (';') + resolução em listas.
Cobre o achado A2 do red-team: `comneg` vem só do valor mobiliário, o JOIN é por
cd_cvm, e multi-classe (PETR3/PETR4) resolve para o mesmo cd_cvm sem colisão.
"""

from __future__ import annotations

import pytest

from app.services.cvm_cadastro import (
    montar_linhas_cadastro,
    parse_cad_cia_aberta,
    parse_valor_mobiliario,
    resolve_ticker,
    resolver_ticker_em_linhas,
)
from app.services.dados import DadoNaoEncontrado, ensure_empresa

# Fixtures latin-1 (separador ';'). CAD tem CD_CVM+razão social+setor; NÃO tem ticker.
_CAD_CSV = (
    "CNPJ_CIA;DENOM_SOCIAL;SIT;CD_CVM;SETOR_ATIV\n"
    "33.000.167/0001-01;PETROLEO BRASILEIRO S.A. PETROBRAS;ATIVO;9512;Petróleo\n"
    "33.592.510/0001-54;VALE S.A.;ATIVO;4170;Mineração\n"
).encode("latin-1")

# FCA valor mobiliário: tem o CODIGO_NEGOCIACAO (ticker). PETR3 e PETR4 = 2 COMNEG,
# mesma empresa (CD_CVM 9512).
_VM_CSV = (
    "CNPJ_Companhia;CD_CVM;Valor_Mobiliario;Codigo_Negociacao;DT_REFER\n"
    "33.000.167/0001-01;9512;Ações Ordinárias;PETR3;2026-05-01\n"
    "33.000.167/0001-01;9512;Ações Preferenciais;PETR4;2026-05-01\n"
    "33.592.510/0001-54;4170;Ações Ordinárias;VALE3;2026-05-01\n"
).encode("latin-1")


# ---------------------------------------------------------------------------
# Parsers puros
# ---------------------------------------------------------------------------
def test_parse_cad_indexa_por_cd_cvm() -> None:
    idx = parse_cad_cia_aberta(_CAD_CSV)
    assert set(idx) == {9512, 4170}
    assert idx[9512]["setor"] == "Petróleo"
    assert idx[9512]["denom_social"].startswith("PETROLEO BRASILEIRO")
    assert "COMNEG" not in idx[9512]  # CAD não traz ticker


def test_parse_valor_mobiliario_extrai_ticker_e_cd_cvm() -> None:
    linhas = parse_valor_mobiliario(_VM_CSV)
    tickers = {ln["comneg"] for ln in linhas}
    assert tickers == {"PETR3", "PETR4", "VALE3"}
    petr4 = next(ln for ln in linhas if ln["comneg"] == "PETR4")
    assert petr4["cd_cvm"] == 9512


def test_parse_valor_mobiliario_descarta_linha_sem_ticker() -> None:
    csv_ruim = ("CD_CVM;Codigo_Negociacao\n" "9512;PETR4\n" "4170;\n" ";VALE3\n").encode("latin-1")
    linhas = parse_valor_mobiliario(csv_ruim)
    assert [ln["comneg"] for ln in linhas] == ["PETR4"]  # sem ticker OU sem cd_cvm caem fora


def test_montar_faz_join_por_cd_cvm_nao_por_razao_social() -> None:
    idx = parse_cad_cia_aberta(_CAD_CSV)
    vm = parse_valor_mobiliario(_VM_CSV)
    montadas = montar_linhas_cadastro(vm, idx)
    petr4 = next(m for m in montadas if m["comneg"] == "PETR4")
    assert petr4["cd_cvm"] == 9512
    assert petr4["setor"] == "Petróleo"  # enriquecido pelo CAD via cd_cvm
    assert petr4["denom_social"].startswith("PETROLEO BRASILEIRO")


# ---------------------------------------------------------------------------
# Resolução (A2: multi-classe + abstenção)
# ---------------------------------------------------------------------------
def _linhas_montadas() -> list[dict]:
    return montar_linhas_cadastro(parse_valor_mobiliario(_VM_CSV), parse_cad_cia_aberta(_CAD_CSV))


def test_multiclasse_petr3_e_petr4_resolvem_para_mesmo_cd_cvm() -> None:
    linhas = _linhas_montadas()
    r3 = resolver_ticker_em_linhas(linhas, "PETR3")
    r4 = resolver_ticker_em_linhas(linhas, "PETR4")
    assert r3 is not None and r4 is not None
    assert r3[0] == r4[0] == 9512  # mesmo CD_CVM, sem colisão


def test_resolver_devolve_tupla_completa() -> None:
    cd_cvm, cnpj, denom, setor = resolver_ticker_em_linhas(_linhas_montadas(), "VALE3")
    assert cd_cvm == 4170
    assert setor == "Mineração"
    assert denom == "VALE S.A."
    assert cnpj == "33.592.510/0001-54"


def test_resolver_ticker_inexistente_devolve_none() -> None:
    assert resolver_ticker_em_linhas(_linhas_montadas(), "ZZZZ9") is None


def test_resolver_prefere_registro_ativo() -> None:
    linhas = [
        {"cd_cvm": 1, "comneg": "AAAA3", "sit_reg": "CANCELADA", "denom_social": "Velha"},
        {"cd_cvm": 2, "comneg": "AAAA3", "sit_reg": "ATIVO", "denom_social": "Ativa"},
    ]
    assert resolver_ticker_em_linhas(linhas, "AAAA3")[0] == 2


# ---------------------------------------------------------------------------
# resolve_ticker com fallback de seed (sem DB) + integração com ensure_empresa
# ---------------------------------------------------------------------------
def test_resolve_ticker_sem_sessao_usa_seed_para_ticker_conhecido() -> None:
    # session=None pula o cache; cai no seed TICKER_CD_CVM (PETR4 conhecido).
    cd_cvm, _cnpj, nome, _setor = resolve_ticker(None, "PETR4")
    assert cd_cvm == 9512
    assert "Petrobras" in nome


def test_resolve_ticker_sem_sessao_e_sem_seed_abstem() -> None:
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        resolve_ticker(None, "ZZZZ9")


def test_ensure_empresa_ticker_desconhecido_abstem_antes_da_sessao() -> None:
    # Regressão: continua abstendo (agora via resolve_ticker) sem tocar o banco.
    with pytest.raises(DadoNaoEncontrado):
        ensure_empresa(None, "ZZZZ9")  # type: ignore[arg-type]
