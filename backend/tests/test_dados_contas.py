"""Testes offline da extração ampliada de contas CVM (BPP/BPA/DFC) + escala MILHAR.

Cobre o achado A1 do red-team: ESCALA_MOEDA='MILHAR' deve multiplicar por 1000
(sem isso, o valor entraria 1000x menor — número errado COM fonte).
"""

from __future__ import annotations

import io
import zipfile

from app.services.dados import _CONTAS_BPP, _aplicar_escala, _extrair_contas


def test_aplicar_escala_milhar_multiplica_por_mil() -> None:
    assert _aplicar_escala(2.0, "MILHAR") == 2000.0
    assert _aplicar_escala(2.0, "MILHARES") == 2000.0
    assert _aplicar_escala(2.0, "  milhar ") == 2000.0  # case/trim


def _zip_com(membro: str, csv_texto: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(membro, csv_texto.encode("latin-1"))
    return buf.getvalue()


def test_extrair_contas_bpp_novas_contas_de_divida_com_escala_milhar() -> None:
    membro = "dfp_cia_aberta_BPP_con_2025.csv"
    csv_texto = (
        "CD_CVM;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC\n"
        "9512;2.01.04;Emprestimos e Financiamentos;100;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;2.02.01;Emprestimos e Financiamentos;400;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;2.03;Patrimonio Liquido Consolidado;5000;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;2.01.04;Emprestimos e Financiamentos;999;MILHAR;PENÚLTIMO;2024-12-31\n"
        "4170;2.01.04;Outra empresa (ignorar);1;MILHAR;ÚLTIMO;2025-12-31\n"
    )
    achados = _extrair_contas(_zip_com(membro, csv_texto), 2025, 9512, membro, _CONTAS_BPP)
    ultimo = {a["cd_conta"]: a["valor"] for a in achados if a["ordem"] == "ULTIMO"}

    assert set(ultimo) == {"2.01.04", "2.02.01", "2.03"}
    assert ultimo["2.01.04"] == 100_000.0  # 100 * MILHAR (A1)
    assert ultimo["2.02.01"] == 400_000.0
    assert ultimo["2.03"] == 5_000_000.0
    # PENÚLTIMO agora ENTRA (tendência ano-contra-ano com fonte), rotulado com a
    # data do exercício anterior; outra empresa (4170) segue descartada.
    penultimo = [a for a in achados if a["ordem"] == "PENULTIMO"]
    assert len(penultimo) == 1
    assert penultimo[0]["cd_conta"] == "2.01.04"
    assert penultimo[0]["valor"] == 999_000.0
    assert str(penultimo[0]["dt_refer"]) == "2024-12-31"
    assert all(a["dt_refer"] is not None for a in achados)


def test_extrair_contas_membro_ausente_devolve_vazio() -> None:
    # DFC de método não filiado pela empresa: membro não existe no ZIP -> [].
    zip_bytes = _zip_com("dfp_cia_aberta_BPP_con_2025.csv", "CD_CVM;CD_CONTA\n9512;2.03\n")
    ausente = _extrair_contas(
        zip_bytes, 2025, 9512, "dfp_cia_aberta_DFC_MI_con_2025.csv", {"6.01": "FCO"}
    )
    assert ausente == []


# ---------------------------------------------------------------------------
# D&A da DFC (achados M2/M3 da auditoria da fase 3): localizar por descrição,
# somar irmãs, abster no ambíguo — nunca D&A parcial (número errado COM fonte)
# ---------------------------------------------------------------------------
_MEMBRO_DFC = "dfp_cia_aberta_DFC_MI_con_2025.csv"
_CAB_DFC = "CD_CVM;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC\n"


def _extrai_da(csv_texto: str):
    from app.services.dados import _extrair_da_dfc

    return _extrair_da_dfc(_zip_com(_MEMBRO_DFC, _CAB_DFC + csv_texto), 2025, 9512, _MEMBRO_DFC)


def test_da_dfc_linha_unica_combinada_extrai() -> None:
    achados = _extrai_da(
        "9512;6.01.01.02;Depreciacao, Deplecao e Amortizacao;70;MILHAR;ÚLTIMO;2025-12-31\n"
    )
    assert len(achados) == 1
    assert achados[0]["valor"] == 70_000.0
    assert achados[0]["papel"] == "DA"


def test_da_dfc_linhas_irmas_somam_sem_dupla_contagem() -> None:
    # Caso VALE3-like (M2): depreciação, amortização e exaustão FRAGMENTADAS.
    # Só "deprecia" pegaria D&A parcial => EBITDA subestimado COM fonte.
    achados = _extrai_da(
        "9512;6.01.01.02;Depreciacao;50;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;6.01.01.03;Amortizacao;20;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;6.01.01.04;Exaustao;10;MILHAR;ÚLTIMO;2025-12-31\n"
    )
    assert len(achados) == 1
    assert achados[0]["valor"] == 80_000.0  # soma das 3 irmãs
    assert "+" in achados[0]["cd_conta"]  # rótulo composto auditável


def test_da_dfc_hierarquia_ancestral_abstem() -> None:
    # Subtotal + componente: somar dobraria a conta -> ambíguo -> abstém.
    achados = _extrai_da(
        "9512;6.01.01.02;Depreciacao e Amortizacao;70;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;6.01.01.02.01;Depreciacao de ativos;50;MILHAR;ÚLTIMO;2025-12-31\n"
    )
    assert achados == []


def test_da_dfc_datas_divergentes_abstem() -> None:
    achados = _extrai_da(
        "9512;6.01.01.02;Depreciacao;50;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;6.01.01.03;Amortizacao;20;MILHAR;ÚLTIMO;2025-06-30\n"
    )
    assert achados == []


def test_da_dfc_fora_dos_ajustes_e_ignorada() -> None:
    # "Depreciação" fora de 6.01.01.* (ex.: seção de investimento) não entra.
    achados = _extrai_da("9512;6.02.01;Depreciacao;50;MILHAR;ÚLTIMO;2025-12-31\n")
    assert achados == []


def test_da_dfc_ultimo_e_penultimo_consolidam_separados() -> None:
    achados = _extrai_da(
        "9512;6.01.01.02;Depreciacao, Deplecao e Amortizacao;70;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;6.01.01.02;Depreciacao, Deplecao e Amortizacao;65;MILHAR;PENÚLTIMO;2024-12-31\n"
    )
    por_ordem = {a["ordem"]: a["valor"] for a in achados}
    assert por_ordem == {"ULTIMO": 70_000.0, "PENULTIMO": 65_000.0}


def test_mensalizar_pega_ultima_observacao_de_cada_mes() -> None:
    import datetime as dt

    from app.services.dados import mensalizar

    pontos = [
        (dt.date(2026, 5, 10), 5.0),
        (dt.date(2026, 5, 28), 5.2),  # última de maio vence
        (dt.date(2026, 6, 3), 5.4),
        (dt.date(2026, 4, 30), 4.9),
    ]
    assert mensalizar(pontos) == [
        (dt.date(2026, 4, 30), 4.9),
        (dt.date(2026, 5, 28), 5.2),
        (dt.date(2026, 6, 3), 5.4),
    ]


def test_conta_de_banco_com_mesmo_codigo_e_outro_significado_abstem() -> None:
    # Plano de contas de banco reusa códigos com OUTRO significado (caso real
    # ITUB/BBDC): 3.05="Resultado antes dos Tributos" (≠ EBIT), 3.06="IR e CS"
    # (≠ resultado financeiro), 2.02.01="Depósitos" (≠ empréstimos). Sem a
    # validação por DS_CONTA, derivadas/elos rotulariam número errado COM fonte.
    from app.services.dados import _CONTAS_DRE

    membro = "dfp_cia_aberta_DRE_con_2025.csv"
    csv_texto = (
        "CD_CVM;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC\n"
        "19348;3.05;Resultado antes dos Tributos sobre o Lucro;50250;MILHAR;ÚLTIMO;2025-12-31\n"
        "19348;3.06;Imposto de Renda e Contribuição Social sobre o Lucro;"
        "-4401;MILHAR;ÚLTIMO;2025-12-31\n"
        "19348;3.06.02;Diferido;6294;MILHAR;ÚLTIMO;2025-12-31\n"
        "19348;3.11;Lucro/Prejuízo Consolidado do Período;110;MILHAR;ÚLTIMO;2025-12-31\n"
    )
    achados = _extrair_contas(_zip_com(membro, csv_texto), 2025, 19348, membro, _CONTAS_DRE)
    contas = {a["cd_conta"] for a in achados}
    # 3.05/3.06/3.06.02 divergem semanticamente -> abstidos; 3.11 é lucro mesmo.
    assert contas == {"3.11"}


def test_conta_padrao_nao_financeira_passa_na_validacao_semantica() -> None:
    from app.services.dados import _CONTAS_DRE

    membro = "dfp_cia_aberta_DRE_con_2025.csv"
    csv_texto = (
        "CD_CVM;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC\n"
        "9512;3.05;Resultado Antes do Resultado Financeiro e dos Tributos;"
        "145;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;3.06;Resultado Financeiro;-30;MILHAR;ÚLTIMO;2025-12-31\n"
        "9512;3.06.02;Despesas Financeiras;-45;MILHAR;ÚLTIMO;2025-12-31\n"
    )
    achados = _extrair_contas(_zip_com(membro, csv_texto), 2025, 9512, membro, _CONTAS_DRE)
    assert {a["cd_conta"] for a in achados} == {"3.05", "3.06", "3.06.02"}
