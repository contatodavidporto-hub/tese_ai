"""Expectativas Focus (BCB/Olinda, OData) + CDI (BCB SGS) — cenário de juros.

Séries de EXPECTATIVA (Focus) são sempre rotuladas como "expectativa de mercado,
não fato realizado" (rótulos canônicos em `rotulos.ROTULOS_MACRO`); CDI é fato
realizado do SGS. Tudo em `macro_series`, upsert idempotente por (código, data).

⚠️ Olinda exige OData PERCENT-ENCODED (delta 6 da reconciliação): `httpx`
`params=` codifica espaço como '+' e o Olinda responde 400. A query string é
construída JÁ percent-encoded (%24filter com %20/%27) — NUNCA passar `params=`.
Falha do Olinda levanta `FocusIndisponivel` (exceção limpa): o chamador isola o
passo e degrada para as séries factuais do SGS (Selic/CDI/IPCA) — a falha NUNCA
derruba a ingestão inteira.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import MacroSerie
from app.services import http_client
from app.services.dados import _parse_data, _parse_valor, bcb_sgs_intervalo, mensalizar
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

OLINDA_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
RECURSO_SELIC_REUNIOES = "ExpectativasMercadoSelic"
RECURSO_ANUAIS = "ExpectativasMercadoAnuais"

# Quantas reuniões futuras do Copom persistir (a mais próxima = FOCUS_SELIC_COPOM;
# as seguintes = FOCUS_SELIC_COPOM_2..4). O endpoint publica, por data de pesquisa,
# só reuniões FUTURAS — ordenamos por (ano, número) e tomamos as 4 primeiras.
N_REUNIOES = 4

# Dias para trás no filtro `Data ge` — o Focus é semanal; 45 dias garantem pegar
# a última pesquisa mesmo com feriados, sem varrer o histórico inteiro.
_JANELA_PESQUISA_DIAS = 45

_REUNIAO_RE = re.compile(r"^R(\d+)/(\d{4})$")

# codigo -> (série SGS, rótulo humano). CDI é FATO (SGS), não expectativa.
CDI_SERIES: dict[str, tuple[int, str]] = {
    "CDI_DIARIO": (12, "CDI diário (% a.d.)"),
    "CDI_ANUAL": (4389, "CDI anualizado (% a.a.)"),
}

# O SGS rejeita consultas por intervalo acima de 10 anos — fatiamos quando preciso.
_MAX_DIAS_CONSULTA_SGS = 10 * 365


class FocusIndisponivel(Exception):
    """Olinda fora do ar / resposta inválida — exceção limpa para o chamador isolar."""


def _url_odata(recurso: str, filtro: str, top: int = 100) -> str:
    """Query OData JÁ percent-encoded (%24top/%24format/%24filter, espaço=%20).

    NUNCA usar `params=` do httpx aqui: ele codifica espaço como '+', que o
    Olinda rejeita com 400 (verificado ao vivo em 2026-07-03).
    """
    return (
        f"{OLINDA_BASE}/{recurso}"
        f"?%24top={top}&%24format=json&%24filter={quote(filtro, safe='')}"
    )


def _consultar(url: str, transport: httpx.BaseTransport | None = None) -> list[dict]:
    """GET no Olinda -> lista de linhas do campo `value`; falha -> FocusIndisponivel."""
    try:
        resp = http_client.get_keyless(url, timeout=30.0, transport=transport)
        resp.raise_for_status()
        corpo = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise FocusIndisponivel(f"Olinda indisponível: {type(exc).__name__}") from exc
    valores = corpo.get("value") if isinstance(corpo, dict) else None
    if not isinstance(valores, list):
        raise FocusIndisponivel("Olinda: resposta sem o campo 'value'")
    return valores


def _para_float(valor: object) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, int | float):
        return float(valor)
    return _parse_valor(str(valor))


def _persistir(
    session: Session, codigo: str, data: dt.date, valor: float, url: str, descricao: str
) -> MacroSerie:
    """Upsert idempotente por (código, data), sempre com Fonte (URL + data)."""
    fonte_id = get_or_create_fonte(session, url=url, descricao=descricao, dt_referencia=data)
    existente = session.execute(
        select(MacroSerie).where(MacroSerie.codigo == codigo, MacroSerie.data == data)
    ).scalar_one_or_none()
    if existente is None:
        serie = MacroSerie(codigo=codigo, data=data, valor=valor, fonte_id=fonte_id)
        session.add(serie)
        return serie
    existente.valor = valor
    existente.fonte_id = fonte_id
    return existente


def _linhas_da_ultima_pesquisa(linhas: list[dict]) -> tuple[dt.date | None, list[dict]]:
    """Filtra baseCalculo=0 (defesa em profundidade além do filtro OData) e
    devolve (data da pesquisa mais recente, linhas dessa pesquisa)."""
    com_data = [
        (data, linha)
        for linha in linhas
        if linha.get("baseCalculo") == 0
        and (data := _parse_data(str(linha.get("Data") or ""))) is not None
    ]
    if not com_data:
        return None, []
    data_pesquisa = max(data for data, _ in com_data)
    return data_pesquisa, [linha for data, linha in com_data if data == data_pesquisa]


def _ingest_selic_reunioes(
    session: Session, hoje: dt.date, transport: httpx.BaseTransport | None
) -> list[MacroSerie]:
    corte = (hoje - dt.timedelta(days=_JANELA_PESQUISA_DIAS)).isoformat()
    filtro = f"Data ge '{corte}' and baseCalculo eq 0"
    url = _url_odata(RECURSO_SELIC_REUNIOES, filtro, top=200)
    data_pesquisa, da_pesquisa = _linhas_da_ultima_pesquisa(_consultar(url, transport))
    if data_pesquisa is None:
        logger.warning("focus_selic_sem_pesquisa_recente")
        return []

    reunioes: list[tuple[tuple[int, int], str, float]] = []
    for linha in da_pesquisa:
        m = _REUNIAO_RE.match(str(linha.get("Reuniao") or ""))
        mediana = _para_float(linha.get("Mediana"))
        if m is None or mediana is None:
            continue  # linha sem reunião/mediana válida -> descartada, nunca inventada
        reunioes.append(((int(m.group(2)), int(m.group(1))), m.group(0), mediana))
    reunioes.sort(key=lambda r: r[0])

    gravados: list[MacroSerie] = []
    for i, (_, rotulo_reuniao, mediana) in enumerate(reunioes[:N_REUNIOES]):
        codigo = "FOCUS_SELIC_COPOM" if i == 0 else f"FOCUS_SELIC_COPOM_{i + 1}"
        descricao = (
            f"BCB Focus (Olinda) — ExpectativasMercadoSelic: mediana da Selic esperada "
            f"para a reunião {rotulo_reuniao} do Copom (baseCalculo=0); "
            f"expectativa de mercado, não fato realizado"
        )
        gravados.append(_persistir(session, codigo, data_pesquisa, mediana, url, descricao))
    logger.info("focus_selic_copom_persistido", pesquisa=str(data_pesquisa), n=len(gravados))
    return gravados


def _ingest_anuais(
    session: Session,
    indicador: str,
    codigos: tuple[str, str],
    hoje: dt.date,
    transport: httpx.BaseTransport | None,
) -> list[MacroSerie]:
    """Medianas de fim de ano (ano corrente e seguinte) de um indicador anual."""
    corte = (hoje - dt.timedelta(days=_JANELA_PESQUISA_DIAS)).isoformat()
    filtro = f"Indicador eq '{indicador}' and Data ge '{corte}' and baseCalculo eq 0"
    url = _url_odata(RECURSO_ANUAIS, filtro, top=200)
    linhas = [
        linha
        for linha in _consultar(url, transport)
        if str(linha.get("Indicador") or "") == indicador
    ]
    data_pesquisa, da_pesquisa = _linhas_da_ultima_pesquisa(linhas)
    if data_pesquisa is None:
        logger.warning("focus_anuais_sem_pesquisa_recente", indicador=indicador)
        return []

    por_ano: dict[int, float] = {}
    for linha in da_pesquisa:
        try:
            ano_ref = int(str(linha.get("DataReferencia") or ""))
        except ValueError:
            continue
        mediana = _para_float(linha.get("Mediana"))
        if mediana is not None:
            por_ano[ano_ref] = mediana

    gravados: list[MacroSerie] = []
    for codigo, ano_ref in zip(codigos, (hoje.year, hoje.year + 1), strict=True):
        if ano_ref not in por_ano:
            continue  # abstém — nunca estima o ano ausente
        descricao = (
            f"BCB Focus (Olinda) — ExpectativasMercadoAnuais: mediana de {indicador} "
            f"esperada para o fim de {ano_ref} (baseCalculo=0); "
            f"expectativa de mercado, não fato realizado"
        )
        gravados.append(
            _persistir(session, codigo, data_pesquisa, por_ano[ano_ref], url, descricao)
        )
    logger.info(
        "focus_anuais_persistido", indicador=indicador, pesquisa=str(data_pesquisa), n=len(gravados)
    )
    return gravados


def ingest_focus(
    session: Session,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[MacroSerie]:
    """Medianas Focus em `macro_series` (sempre rotuladas como expectativa).

    - FOCUS_SELIC_COPOM (+ _2.._4): medianas das 4 próximas reuniões do Copom
      (ExpectativasMercadoSelic, baseCalculo=0; data = Data da pesquisa).
    - FOCUS_SELIC_FIM_ANO / FOCUS_SELIC_FIM_ANO_SEGUINTE (ExpectativasMercadoAnuais).
    - FOCUS_IPCA_ANO / FOCUS_IPCA_ANO_SEGUINTE (ExpectativasMercadoAnuais, IPCA).

    Falha do Olinda -> FocusIndisponivel (o chamador isola o passo; a tese
    degrada para as séries factuais do SGS). Não faz commit.
    """
    hoje = hoje or dt.date.today()
    gravados: list[MacroSerie] = []
    gravados.extend(_ingest_selic_reunioes(session, hoje, transport))
    codigos_selic = ("FOCUS_SELIC_FIM_ANO", "FOCUS_SELIC_FIM_ANO_SEGUINTE")
    gravados.extend(_ingest_anuais(session, "Selic", codigos_selic, hoje, transport))
    gravados.extend(
        _ingest_anuais(
            session, "IPCA", ("FOCUS_IPCA_ANO", "FOCUS_IPCA_ANO_SEGUINTE"), hoje, transport
        )
    )
    return gravados


def _intervalos_sgs(
    inicio: dt.date, fim: dt.date, max_dias: int = _MAX_DIAS_CONSULTA_SGS
) -> list[tuple[dt.date, dt.date]]:
    """Fatia [inicio, fim] em janelas de até `max_dias` (o SGS limita a 10 anos)."""
    intervalos: list[tuple[dt.date, dt.date]] = []
    ini = inicio
    while ini <= fim:
        parcial = min(ini + dt.timedelta(days=max_dias - 1), fim)
        intervalos.append((ini, parcial))
        ini = parcial + dt.timedelta(days=1)
    return intervalos


def ingest_cdi(session: Session, meses: int = 60, *, hoje: dt.date | None = None) -> int:
    """CDI diário (SGS 12) e anualizado (SGS 4389) mensalizados em `macro_series`.

    Padrão SGS de `dados.py` (última observação de cada mês — dado real, não
    média inventada), respeitando o teto de 10 anos por consulta ao SGS. Falha
    de uma série é isolada (a outra segue). Devolve o nº de pontos persistidos.
    """
    hoje = hoje or dt.date.today()
    inicio = hoje - dt.timedelta(days=meses * 32)
    n_gravados = 0
    for codigo, (sgs, rotulo) in CDI_SERIES.items():
        pontos_raw: list[dict] = []
        try:
            for ini, fim in _intervalos_sgs(inicio, hoje):
                pontos_raw.extend(bcb_sgs_intervalo(sgs, ini, fim))
        except httpx.HTTPError as exc:
            logger.warning("cdi_falhou", codigo=codigo, sgs=sgs, erro=type(exc).__name__)
            continue
        pontos = [
            (data, valor)
            for p in pontos_raw
            if (data := _parse_data(str(p.get("data", "")))) is not None
            and (valor := _parse_valor(str(p.get("valor", "")))) is not None
        ]
        mensais = mensalizar(pontos)[-meses:]
        # URL ESTÁVEL da série (o intervalo consultado muda a cada rodada).
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{sgs}/dados"
        for data, valor in mensais:
            _persistir(
                session,
                codigo,
                data,
                valor,
                url,
                f"Banco Central — API SGS série {sgs}: {rotulo}, última obs. do mês",
            )
            n_gravados += 1
        logger.info("cdi_persistido", codigo=codigo, meses=len(mensais))
    return n_gravados
