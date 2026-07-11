"""Conector de proventos B3 — dividendos/JCP/rendimentos (fase "Tese Profunda", F1).

Endpoints INTERNOS (não documentados) do site de listados da B3, os mesmos que
alimentam a página do ativo em b3.com.br — ambos validados ao vivo em 2026-07-10
(fixtures congeladas em `tests/fixtures/proventos_b3/`):

- FII:   `fundsProxy/fundsCall/GetListedSupplementFunds/{payload}` —
  HGLG11: 20 cashDividends, rate '1,10000000000'.
- Ações: `listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{payload}` —
  ITUB: 34 itens (JCP mensal + dividendos); TAEE: 21 itens, com a unit
  TAEE11 (CDAM) pagando exatamente 3x a ON — coerente com 1 ON + 2 PN.

`payload` é um JSON em base64 na URL, construído SERVER-SIDE a partir do
cadastro (`fii_cadastro` para FII; raiz do ticker para ações) e validado antes
do GET — nunca aceitamos payload externo. Todo fato grava `Fonte` (URL completa
+ data da consulta); resposta fora do esperado vira log estruturado +
`DadoNaoEncontrado` ("alarme de schema" — endpoint não documentado pode mudar),
nunca 500. Valores monetários ('1,10000000000', vírgula decimal, 11 casas) são
convertidos com `Decimal`, nunca float direto.

Atribuição por espécie (nunca somar papéis distintos como se fossem o ticker):
- FII: só itens cujo `isinCode` é EXATAMENTE o ISIN do fundo no `fii_cadastro`
  (recibos de subscrição, ex. BRHGLGR24M19, ficam fora — somá-los dobraria o DY).
- Ações: espécie inferida do sufixo B3 do ticker (convenção pública: 3=ON/ACNOR,
  4=PN/ACNPR, 5=PNA/ACNPA, 6=PNB/ACNPB, 11=UNT/CDAM) casada com o miolo do ISIN;
  metodologia declarada na `Fonte`. Sufixo fora do mapa -> abstenção rotulada.

Itens distintos com a MESMA (tipo, data-com) são SOMADOS — fato real: TAEE11
teve 2 DIVIDENDOs aprovados em 29/04/2026. É aritmética determinística sobre
fatos da mesma fonte (o unique(ticker, tipo, data_com) do schema guarda 1 linha
por evento-data) e a soma é declarada na descrição da `Fonte`.

Staleness/cache: busca só quando a última consulta persistida (dt_referencia da
`Fonte`) tem mais de `staleness_dias` (35) — re-geração de tese não martela o
endpoint. Degradação sem tabela (correção A13): banco sem a migração 0006
degrada para abstenção rotulada (`DadoNaoEncontrado`), nunca 500 — o chamador
isola a falha por SAVEPOINT (padrão `orquestracao`).
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import NoReturn

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import FiiCadastro, Fonte, Provento
from app.services import http_client
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

B3_FUNDS_URL = (
    "https://sistemaswebb3-listados.b3.com.br/fundsProxy/fundsCall/"
    "GetListedSupplementFunds/{payload}"
)
B3_COMPANY_URL = (
    "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/"
    "GetListedSupplementCompany/{payload}"
)

STALENESS_DIAS_DEFAULT = 35

_TICKER_RE = re.compile(r"^([A-Z][A-Z0-9]{3})(\d{1,2})$")
_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

# Sufixo B3 -> miolo do ISIN da espécie (convenção pública ANNA/B3), validado
# ao vivo em 2026-07-10: ITUB4 -> BRITUBACNPR1; TAEE11 -> BRTAEECDAM10.
_ESPECIE_POR_SUFIXO = {
    "3": "ACNOR",  # ON
    "4": "ACNPR",  # PN
    "5": "ACNPA",  # PNA
    "6": "ACNPB",  # PNB
    "11": "CDAM",  # unit (certificado de depósito de ações)
}

# Rótulos da B3 -> tipo canônico do schema ('DIVIDENDO'|'JCP'|'RENDIMENTO'|...).
# Rótulo desconhecido entra normalizado (upper) — é fato da B3, não descartamos.
_TIPO_POR_LABEL = {
    "DIVIDENDO": "DIVIDENDO",
    "RENDIMENTO": "RENDIMENTO",
    "JRS CAP PROPRIO": "JCP",
    "JUROS SOBRE CAPITAL PROPRIO": "JCP",
    "AMORTIZACAO": "AMORTIZACAO",
}


@dataclass
class _ItemConsolidado:
    """Provento consolidado por (tipo, data-com): soma de valores + último pagamento."""

    valor: Decimal
    data_pagamento: dt.date | None


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------
def _abster(motivo: str, **contexto: object) -> NoReturn:
    """Log estruturado + abstenção rotulada — nunca inventamos nem deixamos virar 500."""
    logger.warning("proventos_b3_abstencao", motivo=motivo, **contexto)
    raise DadoNaoEncontrado(f"proventos B3: {motivo} — dado não encontrado")


def _decimal_ptbr(raw: str) -> Decimal | None:
    """'1,10000000000' -> Decimal('1.10000000000'). Sempre Decimal, nunca float
    direto (as 11 casas do rate estourariam a mantissa em somas repetidas)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw.replace(".", "").replace(",", ".") if "," in raw else raw)
    except InvalidOperation:
        return None


def _data_br(raw: str) -> dt.date | None:
    """'30/06/2026' -> date. Vazio/lixo/placeholder ('31/12/9999') -> None."""
    raw = (raw or "").strip()
    try:
        data = dt.datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError:
        return None
    return None if data.year > 2200 else data


def _cnpj_digitos(cnpj: str | None) -> str:
    """Só os dígitos do CNPJ (cópia local — padrão dos conectores paralelos)."""
    return "".join(c for c in (cnpj or "") if c.isdigit())


def _payload_b64(payload: dict[str, object]) -> str:
    """Base64 do payload JSON construído SERVER-SIDE, validado por round-trip.

    Nunca aceite payload externo: os campos vêm do cadastro/ticker já validados
    pelo chamador; aqui garantimos que o base64 gerado decodifica de volta ao
    mesmo JSON ASCII antes de ir para a URL.
    """
    bruto = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    codificado = base64.b64encode(bruto).decode("ascii")
    if not _B64_RE.fullmatch(codificado) or base64.b64decode(codificado) != bruto:
        _abster("payload interno inválido (base64 não valida)")
    return codificado


def _decodificar_json(corpo: bytes) -> object | None:
    """JSON dos bytes crus: UTF-8 com fallback latin-1 (o endpoint da B3 já
    serviu bytes fora de UTF-8 sob header utf-8). Não-JSON -> None."""
    try:
        texto = corpo.decode("utf-8")
    except UnicodeDecodeError:
        texto = corpo.decode("latin-1")
    try:
        return json.loads(texto)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# HTTP (sempre via http_client — allowlist anti-SSRF; transport injetável)
# ---------------------------------------------------------------------------
def _buscar_json(url: str, transport: httpx.BaseTransport | None) -> object:
    """GET keyless + parse. Falha de rede/status/JSON -> abstenção rotulada."""
    try:
        resp = http_client.get_keyless(url, timeout=30.0, transport=transport)
    except httpx.HTTPError as exc:
        _abster("falha HTTP no endpoint B3", url=url, erro=type(exc).__name__)
    if resp.status_code != 200:
        _abster("status inesperado do endpoint B3", url=url, status=resp.status_code)
    dados = _decodificar_json(resp.content)
    if dados is None:
        _abster("resposta não-JSON do endpoint B3 (alarme de schema)", url=url)
    return dados


# ---------------------------------------------------------------------------
# Caminho FII (fundsProxy) e caminho ações (listedCompaniesProxy)
# ---------------------------------------------------------------------------
def _itens_fii(
    fii: FiiCadastro, raiz: str, transport: httpx.BaseTransport | None
) -> tuple[list[dict], str, str]:
    """Itens de cashDividends do ISIN do fundo. Devolve (itens, url, metodologia)."""
    isin = (fii.isin or "").strip().upper()
    if not isin:
        _abster("FII sem ISIN no cadastro — proventos não atribuíveis ao ticker", cnpj=fii.cnpj)
    cnpj = _cnpj_digitos(fii.cnpj)
    if len(cnpj) != 14:
        _abster("CNPJ inválido no cadastro do FII", cnpj=fii.cnpj)
    payload: dict[str, object] = {"cnpj": cnpj, "identifierFund": raiz, "typeFund": 7}
    url = B3_FUNDS_URL.format(payload=_payload_b64(payload))
    dados = _buscar_json(url, transport)
    if not isinstance(dados, dict) or not isinstance(dados.get("cashDividends"), list):
        _abster("schema inesperado no fundsProxy (sem cashDividends)", url=url)
    cash: list = dados["cashDividends"]
    itens = [i for i in cash if str(i.get("isinCode") or "").strip().upper() == isin]
    if cash and not itens:
        _abster("nenhum provento atribuível ao ISIN do fundo", url=url, isin=isin)
    return itens, url, f"itens do ISIN {isin} (fii_cadastro/CVM)"


def _itens_acao(
    raiz: str, sufixo: str, transport: httpx.BaseTransport | None
) -> tuple[list[dict], str, str]:
    """Itens de cashDividends da espécie do sufixo. Devolve (itens, url, metodologia)."""
    especie = _ESPECIE_POR_SUFIXO.get(sufixo)
    if especie is None:
        _abster(f"proventos de ações: sufixo {sufixo} sem espécie mapeada", raiz=raiz)
    payload: dict[str, object] = {"issuingCompany": raiz, "language": "pt-br"}
    url = B3_COMPANY_URL.format(payload=_payload_b64(payload))
    dados = _buscar_json(url, transport)
    if not isinstance(dados, list):
        _abster("schema inesperado no listedCompaniesProxy (raiz não é lista)", url=url)
    if not dados or not isinstance(dados[0], dict):
        _abster("emissor sem dados no listedCompaniesProxy", url=url, raiz=raiz)
    if not isinstance(dados[0].get("cashDividends"), list):
        _abster("schema inesperado no listedCompaniesProxy (sem cashDividends)", url=url)
    cash: list = dados[0]["cashDividends"]

    def _da_especie(item: dict) -> bool:
        isin = str(item.get("isinCode") or "").strip().upper()
        return isin[2:6] == raiz and isin[6:].startswith(especie)

    itens = [i for i in cash if _da_especie(i)]
    if cash and not itens:
        _abster("nenhum provento atribuível à espécie do ticker", url=url, especie=especie)
    return itens, url, f"espécie {especie} inferida do sufixo B3 {sufixo} (convenção pública)"


def _consolidar(itens: list[dict], ticker: str) -> dict[tuple[str, dt.date], _ItemConsolidado]:
    """Consolida itens por (tipo, data-com); soma duplicatas; abstém item inválido.

    Item sem data-com/valor válido é pulado com log (alarme por item — o schema
    do endpoint pode mudar); valor <= 0 é pulado (não é provento pagável).
    """
    consolidado: dict[tuple[str, dt.date], _ItemConsolidado] = {}
    for item in itens:
        rotulo = str(item.get("label") or "").strip().upper()
        tipo = _TIPO_POR_LABEL.get(rotulo, rotulo)
        if not tipo:
            logger.info("proventos_b3_item_sem_label", ticker=ticker)
            continue
        data_com = _data_br(str(item.get("lastDatePrior") or ""))
        if data_com is None:
            logger.info("proventos_b3_item_sem_data_com", ticker=ticker, tipo=tipo)
            continue
        valor = _decimal_ptbr(str(item.get("rate") or ""))
        if valor is None or valor <= 0:
            logger.info(
                "proventos_b3_item_sem_valor", ticker=ticker, tipo=tipo, data_com=str(data_com)
            )
            continue
        pagamento = _data_br(str(item.get("paymentDate") or ""))
        atual = consolidado.get((tipo, data_com))
        if atual is None:
            consolidado[(tipo, data_com)] = _ItemConsolidado(valor, pagamento)
            continue
        atual.valor += valor  # fato real: 2 DIVIDENDOs TAEE11 na mesma data-com (29/04/2026)
        if pagamento is not None and (
            atual.data_pagamento is None or pagamento > atual.data_pagamento
        ):
            atual.data_pagamento = pagamento
        logger.info(
            "proventos_b3_mesma_data_com_somada", ticker=ticker, tipo=tipo, data_com=str(data_com)
        )
    return consolidado


# ---------------------------------------------------------------------------
# Degradação sem tabela (correção A13) — abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
def _degradar_tabela_ausente(exc: OperationalError | ProgrammingError, ticker: str) -> NoReturn:
    """`proventos` inexistente -> DadoNaoEncontrado; outro erro de banco propaga.

    Inspeciona a mensagem (padrão de `cotahist._degradar_tabela_ausente`): só a
    tabela ausente vira abstenção — erro de sintaxe/conexão nunca é rotulado
    como "migração pendente".
    """
    mensagem = str(getattr(exc, "orig", None) or exc).lower()
    ausente = any(
        marca in mensagem for marca in ("does not exist", "undefined table", "no such table")
    )
    if not ausente:
        raise exc
    logger.warning("proventos_b3_tabela_ausente", ticker=ticker, erro=type(exc).__name__)
    raise DadoNaoEncontrado(
        "proventos B3: tabela `proventos` ausente no banco (migração 0006 "
        "não aplicada) — dado não encontrado"
    ) from exc


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------
def _dt_ultima_busca(session: Session, ticker: str) -> dt.date | None:
    """Data (dt_referencia da Fonte) da última consulta persistida do ticker."""
    stmt = (
        select(func.max(Fonte.dt_referencia))
        .join_from(Provento, Fonte, Provento.fonte_id == Fonte.id)
        .where(Provento.ticker == ticker)
    )
    return session.execute(stmt).scalar()


def _proventos_do_ticker(session: Session, ticker: str) -> list[Provento]:
    """Proventos persistidos do ticker, mais recentes primeiro."""
    return list(
        session.execute(
            select(Provento)
            .where(Provento.ticker == ticker)
            .order_by(Provento.data_com.desc(), Provento.tipo)
        )
        .scalars()
        .all()
    )


def _upsert_provento(
    session: Session,
    ticker: str,
    tipo: str,
    data_com: dt.date,
    item: _ItemConsolidado,
    fonte_id: uuid.UUID,
) -> Provento:
    """Idempotente por (ticker, tipo, data_com) — espelha o UNIQUE da 0006."""
    existente = session.execute(
        select(Provento).where(
            Provento.ticker == ticker, Provento.tipo == tipo, Provento.data_com == data_com
        )
    ).scalar_one_or_none()
    if existente is None:
        provento = Provento(
            ticker=ticker,
            tipo=tipo,
            valor=item.valor,
            data_com=data_com,
            data_pagamento=item.data_pagamento,
            fonte_id=fonte_id,
        )
        session.add(provento)
        return provento
    existente.valor = item.valor
    existente.data_pagamento = item.data_pagamento
    existente.fonte_id = fonte_id
    return existente


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def ensure_proventos(
    session: Session,
    ticker: str,
    *,
    hoje: dt.date | None = None,
    staleness_dias: int = STALENESS_DIAS_DEFAULT,
    transport: httpx.BaseTransport | None = None,
) -> list[Provento]:
    """Proventos (cashDividends B3) do ticker, persistidos com Fonte. Idempotente.

    FII (ticker presente em `fii_cadastro`) via fundsProxy — payload com o CNPJ
    do cadastro; ações via listedCompaniesProxy — espécie inferida do sufixo B3
    (metodologia declarada na Fonte). Consulta a rede só quando a última busca
    persistida tem mais de `staleness_dias`; devolve os proventos do ticker,
    mais recentes primeiro. Qualquer falha (tabela ausente — correção A13 —,
    rede, schema inesperado, espécie não atribuível) degrada para
    `DadoNaoEncontrado`, nunca 500. `hoje` e `transport` injetáveis p/ teste.
    """
    ticker = ticker.upper().strip()
    casamento = _TICKER_RE.fullmatch(ticker)
    if casamento is None:
        _abster("ticker inválido", ticker=ticker)
    raiz, sufixo = casamento.group(1), casamento.group(2)
    hoje = hoje or dt.date.today()

    try:
        ultima_busca = _dt_ultima_busca(session, ticker)
    except (OperationalError, ProgrammingError) as exc:
        # Correção A13: código novo + banco sem a 0006 -> abstenção, nunca 500.
        _degradar_tabela_ausente(exc, ticker)
    if ultima_busca is not None and (hoje - ultima_busca).days <= staleness_dias:
        logger.info("proventos_b3_cache_fresco", ticker=ticker, ultima_busca=str(ultima_busca))
        return _proventos_do_ticker(session, ticker)

    fii = session.execute(
        select(FiiCadastro).where(FiiCadastro.ticker == ticker)
    ).scalar_one_or_none()
    if fii is not None:
        itens, url, metodologia = _itens_fii(fii, raiz, transport)
        endpoint = "GetListedSupplementFunds"
    else:
        itens, url, metodologia = _itens_acao(raiz, sufixo, transport)
        endpoint = "GetListedSupplementCompany"

    if not itens:
        # Endpoint respondeu com zero proventos listados: fato ("nenhum item"),
        # não erro — nada é persistido e o consumidor declara a lacuna de DY.
        logger.info("proventos_b3_sem_itens", ticker=ticker, url=url)
        return []
    consolidado = _consolidar(itens, ticker)
    if not consolidado:
        _abster("todos os itens vieram sem data-com/valor válidos (alarme de schema)", url=url)

    fonte_id = get_or_create_fonte(
        session,
        url=url,
        descricao=(
            f"B3 — proventos (cashDividends) de {ticker} via {endpoint}; {metodologia}; "
            "itens com a mesma data-com somados"
        ),
        dt_referencia=hoje,
    )
    for (tipo, data_com), item in sorted(consolidado.items(), key=lambda kv: kv[0][1]):
        _upsert_provento(session, ticker, tipo, data_com, item, fonte_id)
    session.flush()
    logger.info("proventos_b3_persistidos", ticker=ticker, n=len(consolidado))
    return _proventos_do_ticker(session, ticker)
