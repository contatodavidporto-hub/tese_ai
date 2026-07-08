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
        "9512;2.01.04;Exercicio anterior (ignorar);999;MILHAR;PENÚLTIMO;2024-12-31\n"
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
