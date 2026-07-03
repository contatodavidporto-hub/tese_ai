"""Testes offline do macro global keyless (World Bank + Treasury via FRED)."""

from __future__ import annotations

import datetime as dt
import json

from app.services.macro_global import (
    CODIGO_TREASURY_10Y,
    INDICADORES_WB,
    _ano_para_data,
    parse_world_bank,
)


def test_parse_world_bank_descarta_nulos_e_le_valores() -> None:
    payload = [
        {"page": 1, "pages": 1},
        [
            {"indicator": {"id": "NY.GDP.MKTP.CD"}, "date": "2024", "value": None},
            {"indicator": {"id": "NY.GDP.MKTP.CD"}, "date": "2023", "value": 2173665655836.0},
            {"indicator": {"id": "NY.GDP.MKTP.CD"}, "date": "2022", "value": 1920095774229.0},
        ],
    ]
    pontos = parse_world_bank(json.dumps(payload).encode())
    # 2024 (null) descartado; 2023 é o mais recente com valor.
    assert pontos[0] == ("2023", 2173665655836.0)
    assert all(v is not None for _, v in pontos)
    assert len(pontos) == 2


def test_parse_world_bank_payload_degenerado_devolve_vazio() -> None:
    assert parse_world_bank(json.dumps([{"message": "erro"}]).encode()) == []
    assert parse_world_bank(json.dumps([{"m": 1}, None]).encode()) == []


def test_ano_para_data_fim_de_exercicio() -> None:
    assert _ano_para_data("2023") == dt.date(2023, 12, 31)
    assert _ano_para_data("lixo") is None


def test_indicadores_incluem_pib_e_inflacao_globais() -> None:
    assert "GLOBAL_PIB_BR" in INDICADORES_WB
    assert "GLOBAL_PIB_US" in INDICADORES_WB
    assert "GLOBAL_INFLACAO_US" in INDICADORES_WB
    # códigos com prefixo GLOBAL_ (convenção p/ macro global em macro_series)
    assert all(c.startswith("GLOBAL_") for c in INDICADORES_WB)
    assert CODIGO_TREASURY_10Y.startswith("GLOBAL_")
