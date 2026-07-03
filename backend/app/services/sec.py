"""Pares globais via SEC EDGAR (companyfacts XBRL) — keyless, domínio público.

Traz fundamentos de comparáveis internacionais do setor (D2/D4). Endpoints públicos
(sem chave), rate-limit 10 req/s + User-Agent com e-mail obrigatório (achado B1, já
no http_client). Distingue o padrão contábil (us-gaap 10-K x ifrs-full 20-F) no
rótulo do conceito — nunca compara padrões diferentes sem ressalva. Conceito ausente
=> abstém (DadoNaoEncontrado), nunca estima.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import Empresa, Par, ParFundamento
from app.services import http_client, setores
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte
from app.services.paralelo import host_de_url, map_concorrente

logger = get_logger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SEC_HOST = "data.sec.gov"

# Conceito humano -> candidatos (taxonomia, conceito XBRL), tentados em ordem.
_CONCEITOS_XBRL: dict[str, list[tuple[str, str]]] = {
    "Receita": [
        ("us-gaap", "Revenues"),
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("ifrs-full", "Revenue"),
    ],
    "Lucro líquido": [("us-gaap", "NetIncomeLoss"), ("ifrs-full", "ProfitLoss")],
    "Ativo total": [("us-gaap", "Assets"), ("ifrs-full", "Assets")],
    "Patrimônio líquido": [("us-gaap", "StockholdersEquity"), ("ifrs-full", "Equity")],
}
_FORMS_ANUAIS = ("10-K", "20-F")


def parse_company_tickers(json_bytes: bytes) -> dict[str, str]:
    """company_tickers.json -> {TICKER: CIK(10 dígitos, zero-pad)}."""
    dados = json.loads(json_bytes)
    linhas = dados.values() if isinstance(dados, dict) else dados
    mapa: dict[str, str] = {}
    for linha in linhas:
        ticker = str(linha.get("ticker", "")).upper().strip()
        cik = linha.get("cik_str")
        if ticker and cik is not None:
            mapa[ticker] = str(cik).zfill(10)
    return mapa


def _ultimo_anual(bloco: dict) -> dict | None:
    """De um bloco de conceito XBRL, devolve o último fato ANUAL (10-K/20-F)."""
    units = bloco.get("units") or {}
    if not units:
        return None
    moeda = "USD" if "USD" in units else next(iter(units))
    serie = units.get("USD") or units[moeda]
    anuais = [
        p
        for p in serie
        if p.get("val") is not None
        and p.get("end")
        and (p.get("form") in _FORMS_ANUAIS or p.get("fp") == "FY")
    ]
    if not anuais:
        return None
    ultimo = max(anuais, key=lambda p: p["end"])
    return {"valor": float(ultimo["val"]), "moeda": moeda, "dt_refer": ultimo["end"]}


def extrair_fundamentos(facts_json: bytes | dict) -> list[dict]:
    """companyfacts -> [{conceito rotulado, valor, moeda, dt_refer, taxonomia}].

    Para cada conceito humano, tenta os candidatos em ordem (us-gaap -> ifrs-full);
    o primeiro que resolve vence. Conceito sem dado é omitido (abstenção).
    """
    facts = facts_json if isinstance(facts_json, dict) else json.loads(facts_json)
    disponiveis = facts.get("facts") or {}
    achados: list[dict] = []
    for nome, candidatos in _CONCEITOS_XBRL.items():
        for taxonomia, conceito in candidatos:
            bloco = (disponiveis.get(taxonomia) or {}).get(conceito)
            if not bloco:
                continue
            fato = _ultimo_anual(bloco)
            if fato is None:
                continue
            achados.append(
                {
                    "conceito": f"{nome} ({taxonomia})",
                    "valor": fato["valor"],
                    "moeda": fato["moeda"],
                    "dt_refer": fato["dt_refer"],
                    "taxonomia": taxonomia,
                }
            )
            break  # candidato resolvido -> não tenta os demais para este conceito
    return achados


# ---------------------------------------------------------------------------
# Ingestão (IO)
# ---------------------------------------------------------------------------
def _resolver_ciks(tickers: list[str]) -> dict[str, str]:
    try:
        resp = http_client.get_keyless(COMPANY_TICKERS_URL, timeout=30.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("sec_company_tickers_falhou", erro=type(exc).__name__)
        return {}
    mapa = parse_company_tickers(resp.content)
    return {t: mapa[t] for t in tickers if t in mapa}


def ingest_pares(session: Session, empresa: Empresa) -> list[Par]:
    """Seleciona pares do setor (interpretação) e ingere seus fundamentos SEC.

    Abstém (retorna []) se o setor é ambíguo/sem lista curada (achado A3).
    """
    info, motivo = setores.selecionar_pares(empresa.setor)
    if info is None:
        logger.info("pares_abstidos", ticker=empresa.ticker, motivo=motivo)
        return []

    sic = info["sic"]
    tickers = [t for t, _ in info["pares"]]
    ciks = _resolver_ciks(tickers)

    # Fonte do CRITÉRIO (não a SEC): marca a seleção como interpretação (A3).
    fonte_criterio = get_or_create_fonte(
        session,
        url=None,
        descricao=setores.criterio_selecao(sic),
        dt_referencia=None,
    )

    pares: list[Par] = []
    for ticker_ext, nome_ext in info["pares"]:
        cik = ciks.get(ticker_ext)
        par = session.execute(
            select(Par).where(Par.empresa_id == empresa.id, Par.ticker_ext == ticker_ext)
        ).scalar_one_or_none()
        if par is None:
            par = Par(
                empresa_id=empresa.id,
                cik=cik,
                ticker_ext=ticker_ext,
                nome_ext=nome_ext,
                sic=sic,
                criterio_selecao=setores.criterio_selecao(sic),
                fonte_id=fonte_criterio,
            )
            session.add(par)
            session.flush()
        else:
            par.cik = cik or par.cik
        pares.append(par)

    # Ingestão dos fundamentos dos pares em PARALELO (workers só fazem I/O;
    # persistência aqui, no orquestrador — achado M4), respeitando 10 req/s da SEC.
    com_cik = [p for p in pares if p.cik]
    resultados = map_concorrente(
        [COMPANYFACTS_URL.format(cik=p.cik) for p in com_cik],
        _baixar_companyfacts,
        max_workers=6,
        host_de=host_de_url,
        por_host_limite=5,
    )
    for par, res in zip(com_cik, resultados, strict=False):
        if not res.ok or res.valor is None:
            logger.warning("companyfacts_falhou", ticker=par.ticker_ext, erro=res.erro)
            continue
        _persistir_par_fundamentos(session, par, res.valor)
    return pares


def _baixar_companyfacts(url: str) -> bytes | None:
    resp = http_client.get_keyless(url, timeout=30.0)
    resp.raise_for_status()
    return resp.content


def _persistir_par_fundamentos(session: Session, par: Par, facts_bytes: bytes) -> None:
    url = COMPANYFACTS_URL.format(cik=par.cik)
    for f in extrair_fundamentos(facts_bytes):
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=f"SEC EDGAR companyfacts — {par.nome_ext} [{f['conceito']}]",
            dt_referencia=_data(f["dt_refer"]),
        )
        pf = ParFundamento(
            par_id=par.id,
            conceito=f["conceito"],
            valor=f["valor"],
            moeda=f["moeda"],
            dt_refer=_data(f["dt_refer"]),
            fonte_id=fonte_id,
        )
        session.add(pf)


def _data(iso: str):
    import datetime as _dt

    try:
        return _dt.date.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


def resolver_cik(ticker: str) -> str:
    """Utilitário: CIK de um ticker US (abstém se não achar)."""
    ciks = _resolver_ciks([ticker.upper()])
    cik = ciks.get(ticker.upper())
    if not cik:
        raise DadoNaoEncontrado(f"CIK não encontrado para {ticker} (dado não encontrado)")
    return cik
