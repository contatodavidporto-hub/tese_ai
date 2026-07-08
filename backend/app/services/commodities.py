"""Commodities (D3/D4) — preço do Brent, keyless.

Fonte keyless-first: o endpoint público `fredgraph.csv` do FRED serve séries
individuais em CSV **sem chave** (ex.: `DCOILBRENTEU` — Brent, fonte primária EIA,
domínio público). Isso evita depender de XLSX/PDF do Pink Sheet do World Bank
(achado M1 do red-team: o Pink Sheet é XLSX/PDF e frágil de parsear).

O conector com CHAVE (FRED API / EIA API, maior frequência) fica BEHIND CONFIG:
sem `fred_api_key`/`eia_api_key` no `.env`, o fluxo keyless (fredgraph) segue e
nunca bloqueia. Se nem o keyless responder, abstém — nunca inventa preço.
"""

from __future__ import annotations

import csv
import datetime as dt
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import MacroSerie
from app.services import http_client
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

# fredgraph.csv é público (sem API key). id=DCOILBRENTEU -> Brent (US$/barril).
FREDGRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}"
BRENT_FRED_ID = "DCOILBRENTEU"
CODIGO_BRENT = "COMMODITY_BRENT"
ROTULO_BRENT = "Petróleo Brent (US$/barril)"


def parse_fredgraph_csv(csv_bytes: bytes) -> list[tuple[dt.date, float]]:
    """CSV do fredgraph: cabeçalho `DATE/observation_date,<serie>`; '.' = ausente.

    Devolve [(data, valor)] em ordem do arquivo, descartando observações sem valor
    (nunca inventa). Robusto ao nome da 1ª coluna (DATE vs observation_date).
    """
    texto = io.StringIO(csv_bytes.decode("utf-8", errors="replace"))
    leitor = csv.reader(texto)
    linhas = list(leitor)
    if not linhas:
        return []
    pontos: list[tuple[dt.date, float]] = []
    for linha in linhas[1:]:  # pula cabeçalho
        if len(linha) < 2:
            continue
        bruto_data, bruto_valor = linha[0].strip(), linha[1].strip()
        if not bruto_valor or bruto_valor == ".":
            continue
        try:
            data = dt.datetime.strptime(bruto_data, "%Y-%m-%d").date()
            valor = float(bruto_valor)
        except ValueError:
            continue
        pontos.append((data, valor))
    return pontos


def ingest_brent_historico(session: Session, meses: int = 36) -> int:
    """Persiste o histórico MENSAL do Brent (última observação de cada mês do
    mesmo CSV keyless do fredgraph). Alimenta o co-movimento (n>=24) do grafo.
    Idempotente por (código, data)."""
    from app.services.dados import mensalizar

    url = FREDGRAPH_CSV_URL.format(serie=BRENT_FRED_ID)
    try:
        resp = http_client.get_keyless(url, timeout=30.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("brent_historico_falhou", erro=type(exc).__name__)
        return 0
    mensais = mensalizar(parse_fredgraph_csv(resp.content))[-meses:]
    n_gravados = 0
    for data, valor in mensais:
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=(
                f"FRED (fonte primária EIA), série {BRENT_FRED_ID}: {ROTULO_BRENT}, "
                "última obs. do mês"
            ),
            dt_referencia=data,
        )
        existente = session.execute(
            select(MacroSerie).where(MacroSerie.codigo == CODIGO_BRENT, MacroSerie.data == data)
        ).scalar_one_or_none()
        if existente is None:
            session.add(MacroSerie(codigo=CODIGO_BRENT, data=data, valor=valor, fonte_id=fonte_id))
        else:
            existente.valor = valor
            existente.fonte_id = fonte_id
        n_gravados += 1
    logger.info("brent_historico_persistido", meses=len(mensais))
    return n_gravados


def ingest_brent(session: Session) -> MacroSerie | None:
    """Persiste o último ponto do Brent (keyless) em `macro_series`. Abstém em falha."""
    url = FREDGRAPH_CSV_URL.format(serie=BRENT_FRED_ID)
    try:
        resp = http_client.get_keyless(url, timeout=30.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("brent_falhou", erro=type(exc).__name__)
        return None

    pontos = parse_fredgraph_csv(resp.content)
    if not pontos:
        logger.warning("brent_sem_pontos")
        return None
    data, valor = pontos[-1]

    fonte_id = get_or_create_fonte(
        session,
        url=url,
        descricao=f"FRED (fonte primária EIA), série {BRENT_FRED_ID}: {ROTULO_BRENT}",
        dt_referencia=data,
    )
    existente = session.execute(
        select(MacroSerie).where(MacroSerie.codigo == CODIGO_BRENT, MacroSerie.data == data)
    ).scalar_one_or_none()
    if existente is None:
        ms = MacroSerie(codigo=CODIGO_BRENT, data=data, valor=valor, fonte_id=fonte_id)
        session.add(ms)
    else:
        existente.valor = valor
        existente.fonte_id = fonte_id
        ms = existente
    logger.info("brent_persistido", data=str(data), valor=valor)
    return ms
