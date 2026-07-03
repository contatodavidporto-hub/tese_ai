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
# Layout REAL do FCA 2026 (verificado ao vivo em 2026-07-02): o valor_mobiliario
# NÃO publica CD_CVM — o join é por CNPJ (dígitos) contra o CAD. Regressão do
# bug que zerava o bootstrap (0 linhas persistidas).
# ---------------------------------------------------------------------------
_VM_CSV_REAL_2026 = (
    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;"
    "Valor_Mobiliario;Sigla_Classe_Acao_Preferencial;Classe_Acao_Preferencial;"
    "Codigo_Negociacao;Composicao_BDR_Unit;Mercado;Sigla_Entidade_Administradora;"
    "Entidade_Administradora;Data_Inicio_Negociacao;Data_Fim_Negociacao;Segmento;"
    "Data_Inicio_Listagem;Data_Fim_Listagem\n"
    "33.000.167/0001-01;2026-01-01;1;156276;PETROLEO BRASILEIRO S.A. PETROBRAS;"
    "Ações Ordinárias;;;PETR3;;Bolsa;B3;B3 S.A.;2018-05-14;;Nível 2;1977-07-20;\n"
    "33.000.167/0001-01;2026-01-01;1;156276;PETROLEO BRASILEIRO S.A. PETROBRAS;"
    "Ações Preferenciais;;;PETR4;;Bolsa;B3;B3 S.A.;2018-05-14;;Nível 2;1977-07-20;\n"
    "99.999.999/0001-99;2026-01-01;1;1;EMPRESA SEM CAD;"
    "Ações Ordinárias;;;XXXX3;;Bolsa;B3;B3 S.A.;2020-01-01;;Básico;2020-01-01;\n"
).encode("latin-1")


def test_parse_vm_layout_real_2026_sem_cd_cvm_captura_cnpj() -> None:
    linhas = parse_valor_mobiliario(_VM_CSV_REAL_2026)
    assert {ln["comneg"] for ln in linhas} == {"PETR3", "PETR4", "XXXX3"}
    petr4 = next(ln for ln in linhas if ln["comneg"] == "PETR4")
    assert petr4["cd_cvm"] is None  # o VM real não publica CD_CVM
    assert petr4["cnpj"] == "33.000.167/0001-01"
    assert petr4["nome_empresarial"].startswith("PETROLEO BRASILEIRO")


def test_parse_vm_descarta_placeholder_nao_ha() -> None:
    # O FCA real usa "NÃO HÁ" p/ papéis não negociados; várias empresas compartilham
    # esse valor e colidiriam no unique (comneg, especie). Não é ticker -> descarta.
    csv_real = (
        "CNPJ_Companhia;Valor_Mobiliario;Codigo_Negociacao\n"
        "00.249.786/0001-85;Ações Ordinárias;NÃO HÁ\n"
        "11.111.111/0001-11;Ações Ordinárias;NÃO HÁ\n"
        "33.000.167/0001-01;Ações Preferenciais;PETR4\n"
    ).encode("latin-1")
    linhas = parse_valor_mobiliario(csv_real)
    assert [ln["comneg"] for ln in linhas] == ["PETR4"]


def test_parse_vm_aceita_formatos_reais_de_ticker() -> None:
    csv_ok = (
        "CNPJ_Companhia;Codigo_Negociacao\n"
        "1;B3SA3\n"  # raiz com dígito
        "2;TAEE11\n"  # unit
        "3;AAPL34\n"  # BDR
        "4;EQMA3B\n"  # balcão organizado, sufixo B (achado médio do auditor-mor)
        "5;FRRN5B\n"  # idem
    ).encode("latin-1")
    assert {ln["comneg"] for ln in parse_valor_mobiliario(csv_ok)} == {
        "B3SA3",
        "TAEE11",
        "AAPL34",
        "EQMA3B",
        "FRRN5B",
    }


def test_montar_join_por_cnpj_quando_vm_nao_tem_cd_cvm() -> None:
    idx = parse_cad_cia_aberta(_CAD_CSV)
    montadas = montar_linhas_cadastro(parse_valor_mobiliario(_VM_CSV_REAL_2026), idx)
    petr4 = next(m for m in montadas if m["comneg"] == "PETR4")
    assert petr4["cd_cvm"] == 9512  # derivado do CAD via CNPJ em dígitos
    assert petr4["setor"] == "Petróleo"
    assert petr4["denom_social"].startswith("PETROLEO BRASILEIRO")


def test_montar_abstem_quando_cnpj_nao_esta_no_cad() -> None:
    idx = parse_cad_cia_aberta(_CAD_CSV)
    montadas = montar_linhas_cadastro(parse_valor_mobiliario(_VM_CSV_REAL_2026), idx)
    assert all(m["comneg"] != "XXXX3" for m in montadas)  # sem join -> descartada


def test_montar_poe_listagem_ativa_por_ultimo_para_upsert_last_wins() -> None:
    vm = [
        {
            "cd_cvm": 1,
            "comneg": "AAAA3",
            "especie": "ON",
            "fim_negociacao": False,
            "dt_referencia": None,
            "cnpj": None,
            "nome_empresarial": "Ativa",
        },
        {
            "cd_cvm": 2,
            "comneg": "AAAA3",
            "especie": "ON",
            "fim_negociacao": True,
            "dt_referencia": None,
            "cnpj": None,
            "nome_empresarial": "Encerrada",
        },
    ]
    montadas = montar_linhas_cadastro(vm, {})
    assert [m["cd_cvm"] for m in montadas] == [2, 1]  # encerrada antes; ativa vence


def test_montar_desempata_por_dt_referencia_mais_recente_por_ultimo() -> None:
    # Tie-break do last-wins (achado baixo do auditor-mor): entre duas listagens
    # ativas, a de dt_referencia mais RECENTE deve vir por último (vence no upsert).
    import datetime as dt

    vm = [
        {
            "cd_cvm": 1,
            "comneg": "AAAA3",
            "especie": "ON",
            "fim_negociacao": False,
            "dt_referencia": dt.date(2026, 1, 1),
            "cnpj": None,
            "nome_empresarial": "Nova",
        },
        {
            "cd_cvm": 2,
            "comneg": "AAAA3",
            "especie": "ON",
            "fim_negociacao": False,
            "dt_referencia": dt.date(2025, 1, 1),
            "cnpj": None,
            "nome_empresarial": "Velha",
        },
    ]
    montadas = montar_linhas_cadastro(vm, {})
    assert [m["cd_cvm"] for m in montadas] == [2, 1]  # 2025 antes; 2026 vence


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
