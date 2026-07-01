"""Testes offline do conector keyless de commodities (Brent via fredgraph.csv)."""

from __future__ import annotations

import datetime as dt

from app.core.config import Settings
from app.services.commodities import (
    BRENT_FRED_ID,
    CODIGO_BRENT,
    FREDGRAPH_CSV_URL,
    parse_fredgraph_csv,
)


def test_parse_fredgraph_extrai_pontos_e_descarta_ausentes() -> None:
    csv_bytes = (
        b"DATE,DCOILBRENTEU\n"
        b"2026-06-15,82.10\n"
        b"2026-06-16,.\n"  # ausente -> descartado (nunca inventa)
        b"2026-06-17,83.45\n"
    )
    pontos = parse_fredgraph_csv(csv_bytes)
    assert pontos == [(dt.date(2026, 6, 15), 82.10), (dt.date(2026, 6, 17), 83.45)]
    # o último ponto (mais recente) é o que a ingestão persiste
    assert pontos[-1] == (dt.date(2026, 6, 17), 83.45)


def test_parse_fredgraph_aceita_observation_date_e_csv_vazio() -> None:
    assert parse_fredgraph_csv(b"observation_date,DCOILBRENTEU\n2026-01-02,75.0\n") == [
        (dt.date(2026, 1, 2), 75.0)
    ]
    assert parse_fredgraph_csv(b"") == []
    assert parse_fredgraph_csv(b"DATE,DCOILBRENTEU\n") == []


def test_url_do_brent_e_keyless() -> None:
    url = FREDGRAPH_CSV_URL.format(serie=BRENT_FRED_ID)
    assert "api_key" not in url and "fredgraph.csv" in url
    assert CODIGO_BRENT == "COMMODITY_BRENT"


def test_chaves_premium_sao_opcionais_behind_config() -> None:
    # Sem .env, os conectores com chave ficam None (no-op) — não bloqueiam nada.
    s = Settings(_env_file=None)
    assert s.fred_api_key is None
    assert s.eia_api_key is None
