"""Macro/geopolítica GLOBAL keyless (D4) — World Bank + Treasury (via FRED público).

Traz contexto macro-global e proxies geopolíticos como SÉRIES FACTUAIS rastreáveis
(PIB, inflação, juro do Tesouro EUA), nunca como eventos afirmados. A interpretação
causal (evento -> commodity -> setor -> empresa) fica no motor de correlação e no
LLM, sempre com hedge — preservando a trava anti-alucinação e o gate geopolítico.

Fontes keyless:
- World Bank Indicators API (api.worldbank.org/v2) — JSON, CC-BY 4.0.
- Juro 10 anos do Tesouro EUA via fredgraph.csv público (id=DGS10), sem chave.
Toda série grava uma Fonte (URL + data); observação nula é descartada.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import MacroSerie
from app.services import http_client
from app.services.commodities import FREDGRAPH_CSV_URL, parse_fredgraph_csv
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

WORLD_BANK_URL = (
    "https://api.worldbank.org/v2/country/{pais}/indicator/{indicador}" "?format=json&per_page=60"
)

# codigo interno -> (país ISO3, indicador World Bank, rótulo humano sem ambiguidade)
INDICADORES_WB: dict[str, tuple[str, str, str]] = {
    "GLOBAL_PIB_BR": ("BRA", "NY.GDP.MKTP.CD", "PIB do Brasil (US$ correntes)"),
    "GLOBAL_PIB_US": ("USA", "NY.GDP.MKTP.CD", "PIB dos EUA (US$ correntes)"),
    "GLOBAL_INFLACAO_US": ("USA", "FP.CPI.TOTL.ZG", "Inflação anual EUA (% CPI a.a.)"),
}

TREASURY_10Y_FRED_ID = "DGS10"
CODIGO_TREASURY_10Y = "GLOBAL_TREASURY_10Y"
ROTULO_TREASURY_10Y = "Juro do Tesouro EUA 10 anos (% a.a.)"


def parse_world_bank(json_bytes: bytes) -> list[tuple[str, float]]:
    """World Bank Indicators -> [(ano, valor)] mais recente primeiro; nulos fora.

    Formato: `[metadados, [observações]]`. Observação com `value=null` é descartada
    (nunca inventa).
    """
    dados = json.loads(json_bytes)
    if not isinstance(dados, list) or len(dados) < 2 or not isinstance(dados[1], list):
        return []
    pontos: list[tuple[str, float]] = []
    for obs in dados[1]:
        valor = obs.get("value")
        ano = obs.get("date")
        if valor is None or not ano:
            continue
        try:
            pontos.append((str(ano), float(valor)))
        except (TypeError, ValueError):
            continue
    return pontos


def _ano_para_data(ano: str) -> dt.date | None:
    try:
        return dt.date(int(ano), 12, 31)
    except (TypeError, ValueError):
        return None


def _persistir(
    session: Session, codigo: str, data: dt.date, valor: float, url: str, descricao: str
) -> MacroSerie:
    fonte_id = get_or_create_fonte(session, url=url, descricao=descricao, dt_referencia=data)
    existente = session.execute(
        select(MacroSerie).where(MacroSerie.codigo == codigo, MacroSerie.data == data)
    ).scalar_one_or_none()
    if existente is None:
        ms = MacroSerie(codigo=codigo, data=data, valor=valor, fonte_id=fonte_id)
        session.add(ms)
        return ms
    existente.valor = valor
    existente.fonte_id = fonte_id
    return existente


def ingest_world_bank(session: Session) -> list[MacroSerie]:
    """Persiste o último ponto de cada indicador do World Bank. Falha isolada."""
    gravados: list[MacroSerie] = []
    for codigo, (pais, indicador, rotulo) in INDICADORES_WB.items():
        url = WORLD_BANK_URL.format(pais=pais, indicador=indicador)
        try:
            resp = http_client.get_keyless(url, timeout=30.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("world_bank_falhou", codigo=codigo, erro=type(exc).__name__)
            continue
        pontos = parse_world_bank(resp.content)
        # mais recente com valor: World Bank já vem desc, mas garantimos.
        ponto = next(((a, v) for a, v in pontos), None)
        if ponto is None:
            continue
        data = _ano_para_data(ponto[0])
        if data is None:
            continue
        gravados.append(
            _persistir(
                session,
                codigo,
                data,
                ponto[1],
                url,
                f"World Bank Indicators — {indicador} ({pais}): {rotulo}",
            )
        )
        logger.info("world_bank_persistido", codigo=codigo, ano=ponto[0])
    return gravados


def ingest_treasury_10y(session: Session) -> MacroSerie | None:
    """Juro 10y do Tesouro EUA via fredgraph público (keyless). Abstém em falha."""
    url = FREDGRAPH_CSV_URL.format(serie=TREASURY_10Y_FRED_ID)
    try:
        resp = http_client.get_keyless(url, timeout=30.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("treasury_10y_falhou", erro=type(exc).__name__)
        return None
    pontos = parse_fredgraph_csv(resp.content)
    if not pontos:
        return None
    data, valor = pontos[-1]
    return _persistir(
        session,
        CODIGO_TREASURY_10Y,
        data,
        valor,
        url,
        f"FRED, série {TREASURY_10Y_FRED_ID}: {ROTULO_TREASURY_10Y}",
    )
