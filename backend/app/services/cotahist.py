"""Conector COTAHIST — preços diários de fim de dia da B3 (fase "Tese Profunda", F1).

Baixa os arquivos oficiais `COTAHIST_DddmmYYYY.ZIP` (diário) e `COTAHIST_MmmYYYY.ZIP`
(mensal, ~9 MB) de `bvmf.bmfbovespa.com.br/InstDados/SerHist/` e upserta OHLCV em
`precos_diarios`. Princípio inegociável: **nunca inventar dado** — toda gravação
cria/linka uma `Fonte` (URL do ZIP + data do pregão) e ausência vira abstenção
(`DadoNaoEncontrado`), nunca estimativa nem silêncio (correção A9).

Layout: posicional latin-1 (SeriesHistoricas_Layout.pdf, registro TIPREG=01), preços
com 2 decimais implícitos. Offsets VALIDADOS contra o pregão real de 09/07/2026
(PETR4 fechou 39,21; HGLG11 148,78 — fixture em tests/fixtures/cotahist/).

Regras duras:
- Filtro CODBDI ∈ {02, 12, 14} (lote padrão, FII, ETF — sonda A9) e TPMERC=010 (à vista).
- SOMENTE tickers rastreados (`tickers: set[str]` explícito) — NUNCA o mercado inteiro.
- Rótulo obrigatório na fonte: **preços não ajustados por proventos** (técnica/β
  "aproximados" no consumidor).
- Teto de download 64 MB: o mensal (~9 MB) cabe; o ANUAL (~89 MB) NÃO cabe — por
  desenho, este conector nunca usa o arquivo anual.
- Correção A13: tabela `precos_diarios` inexistente (migração 0006 não aplicada)
  degrada para abstenção rotulada (`ProgrammingError` -> `DadoNaoEncontrado`), nunca 500.
"""

from __future__ import annotations

import datetime as dt
import io
import uuid
import zipfile
from collections.abc import Iterable, Iterator
from typing import NamedTuple, NoReturn

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import PrecoDiario
from app.services import http_client
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

COTAHIST_DIARIO_URL = (
    "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{dia:02d}{mes:02d}{ano}.ZIP"
)
COTAHIST_MENSAL_URL = (
    "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_M{mes:02d}{ano}.ZIP"
)

# CODBDI: 02=lote-padrão (ações/units), 12=FII, 14=ETF (BOVA11) — sonda real 2026-07-10 (A9).
_CODBDI_PERMITIDOS = frozenset({2, 12, 14})
_TPMERC_VISTA = "010"  # mercado à vista; exclui opções/termo/fracionário
_TAMANHO_REGISTRO = 245  # bytes fixos do registro tipo 01 (layout oficial)

# Mensal ~9 MB cabe com folga; o ANUAL (~89 MB) NÃO cabe — nunca usar o anual.
_MAX_BYTES_ZIP = 64 * 1024 * 1024

# Teto do tamanho DESCOMPRIMIDO de um membro do ZIP (correção L1). O teto de
# `http_client.download_zip` só cobre o stream COMPRIMIDO — um zip-bomb (poucos
# KB comprimidos, GBs descomprimidos) passaria por ele e estouraria a RAM em
# `z.read()`. 1 GiB é folgado (o mensal real tem ~9 MB descomprimidos).
_MAX_DESCOMPRIMIDO = 1024 * 1024 * 1024


class ZipDescompactadoGrandeDemais(zipfile.BadZipFile):
    """Membro do ZIP excederia o teto descomprimido — tratado como zip inválido
    (subclasse de `BadZipFile`: o `except` que já existe em `_texto_do_zip`
    degrada para abstenção rotulada, nunca materializa o payload em RAM)."""


def _checar_tamanho_membro(info: zipfile.ZipInfo, *, teto: int = _MAX_DESCOMPRIMIDO) -> None:
    """Levanta `ZipDescompactadoGrandeDemais` se `info.file_size` (tamanho REAL
    após descompressão) exceder `teto`. Chamar ANTES de `z.read(...)` — checar
    depois já teria materializado o payload gigante em memória."""
    if info.file_size > teto:
        raise ZipDescompactadoGrandeDemais(
            f"{info.filename}: {info.file_size} bytes descomprimidos > teto {teto}"
        )


STALENESS_DIAS_UTEIS = 5  # série mais velha que 5 dias úteis = stale -> backfill
MESES_BACKFILL_DEFAULT = 14  # ~14 meses cobrem >=252 pregões com folga
JANELA_PREGOES_DEFAULT = 252


class _Registro(NamedTuple):
    """Registro tipo 01 do COTAHIST já filtrado (CODBDI/TPMERC) e decodificado."""

    ticker: str
    data_pregao: dt.date
    abertura: float | None
    maxima: float | None
    minima: float | None
    fechamento: float | None
    volume: float | None
    negocios: int | None
    codbdi: int


# ---------------------------------------------------------------------------
# Parser posicional (latin-1) — offsets do SeriesHistoricas_Layout.pdf da B3
# ---------------------------------------------------------------------------
def _preco(raw: str) -> float | None:
    """Campo de preço (11)V99: 2 decimais implícitos. Não-numérico -> None."""
    raw = raw.strip()
    if not raw.isdigit():
        return None
    return int(raw) / 100.0


def _inteiro(raw: str) -> int | None:
    raw = raw.strip()
    return int(raw) if raw.isdigit() else None


def _data_pregao(raw: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_registros(texto: str) -> Iterator[_Registro]:
    """Registros elegíveis do COTAHIST: TIPREG=01, CODBDI ∈ {02,12,14}, TPMERC=010.

    Header (00), trailer (99), linhas curtas e campos malformados são pulados —
    o arquivo é externo e não-confiável; linha ruim nunca derruba o lote.
    """
    for linha in texto.splitlines():
        if not linha.startswith("01") or len(linha) < _TAMANHO_REGISTRO:
            continue
        codbdi = _inteiro(linha[10:12])
        if codbdi is None or codbdi not in _CODBDI_PERMITIDOS:
            continue
        if linha[24:27] != _TPMERC_VISTA:
            continue
        data = _data_pregao(linha[2:10])
        if data is None:
            continue
        ticker = linha[12:24].strip().upper()
        if not ticker:
            continue
        yield _Registro(
            ticker=ticker,
            data_pregao=data,
            abertura=_preco(linha[56:69]),  # PREABE
            maxima=_preco(linha[69:82]),  # PREMAX
            minima=_preco(linha[82:95]),  # PREMIN
            fechamento=_preco(linha[108:121]),  # PREULT
            volume=_preco(linha[170:188]),  # VOLTOT (16)V99, em R$
            negocios=_inteiro(linha[147:152]),  # TOTNEG
            codbdi=codbdi,
        )


# ---------------------------------------------------------------------------
# Download / ZIP — sempre via http_client (anti-SSRF, teto de bytes)
# ---------------------------------------------------------------------------
def _baixar_zip(url: str, transport: httpx.BaseTransport | None) -> bytes | None:
    """ZIP do COTAHIST. 404 = feriado/fim de semana/mês sem arquivo -> None sem erro."""
    try:
        return http_client.download_zip(
            url, timeout=180.0, transport=transport, max_bytes=_MAX_BYTES_ZIP
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.info("cotahist_zip_404", url=url)
        else:
            logger.warning("cotahist_zip_status", url=url, status=exc.response.status_code)
        return None
    except httpx.HTTPError as exc:
        logger.warning("cotahist_zip_falhou", url=url, erro=type(exc).__name__)
        return None


def _texto_do_zip(conteudo: bytes) -> str | None:
    """Conteúdo latin-1 do membro .TXT do ZIP; ZIP corrompido/vazio -> None.

    Correção L1: checa `ZipInfo.file_size` (tamanho descomprimido) contra o
    teto ANTES de `z.read()` — um zip-bomb nunca chega a ser materializado.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            nomes = z.namelist()
            if not nomes:
                logger.warning("cotahist_zip_vazio")
                return None
            alvo = next((n for n in nomes if n.upper().endswith(".TXT")), nomes[0])
            # `teto=` explícito (não o default do parâmetro): lê `_MAX_DESCOMPRIMIDO`
            # do módulo NO MOMENTO da chamada, para que testes (monkeypatch) e uma
            # eventual config futura enxerguem o valor atual, não o congelado na
            # definição da função.
            _checar_tamanho_membro(z.getinfo(alvo), teto=_MAX_DESCOMPRIMIDO)
            return z.read(alvo).decode("latin-1")
    except ZipDescompactadoGrandeDemais as exc:
        logger.warning("cotahist_zip_bomba", detalhe=str(exc))
        return None
    except zipfile.BadZipFile:
        logger.warning("cotahist_zip_corrompido")
        return None


# ---------------------------------------------------------------------------
# Persistência — todo fato com Fonte (URL do ZIP + data do pregão)
# ---------------------------------------------------------------------------
def _descricao_fonte(data_pregao: dt.date) -> str:
    return (
        f"B3 — COTAHIST (dados de fim de dia), pregão {data_pregao.isoformat()}: "
        "preços não ajustados por proventos"
    )


def _upsert_preco(session: Session, reg: _Registro, fonte_id: uuid.UUID) -> bool:
    """Idempotente por (ticker, data_pregao) — espelha o UNIQUE da 0006. True = linha nova."""
    existente = session.execute(
        select(PrecoDiario).where(
            PrecoDiario.ticker == reg.ticker, PrecoDiario.data_pregao == reg.data_pregao
        )
    ).scalar_one_or_none()
    if existente is None:
        session.add(
            PrecoDiario(
                ticker=reg.ticker,
                data_pregao=reg.data_pregao,
                abertura=reg.abertura,
                maxima=reg.maxima,
                minima=reg.minima,
                fechamento=reg.fechamento,
                volume=reg.volume,
                negocios=reg.negocios,
                codbdi=reg.codbdi,
                fonte_id=fonte_id,
            )
        )
        return True
    existente.abertura = reg.abertura
    existente.maxima = reg.maxima
    existente.minima = reg.minima
    existente.fechamento = reg.fechamento
    existente.volume = reg.volume
    existente.negocios = reg.negocios
    existente.codbdi = reg.codbdi
    existente.fonte_id = fonte_id
    return False


def _normalizar_tickers(tickers: Iterable[str]) -> set[str]:
    return {t.upper().strip() for t in tickers if t and t.strip()}


def _ingest_texto(session: Session, texto: str, url: str, alvo: set[str]) -> int:
    """Upserta os registros dos tickers rastreados; devolve linhas gravadas (novas+atualizadas)."""
    gravados = 0
    fontes: dict[dt.date, uuid.UUID] = {}
    for reg in _parse_registros(texto):
        if reg.ticker not in alvo:
            continue  # NUNCA o mercado inteiro — só o conjunto explícito
        fonte_id = fontes.get(reg.data_pregao)
        if fonte_id is None:
            fonte_id = get_or_create_fonte(
                session,
                url=url,
                descricao=_descricao_fonte(reg.data_pregao),
                dt_referencia=reg.data_pregao,
            )
            fontes[reg.data_pregao] = fonte_id
        _upsert_preco(session, reg, fonte_id)
        gravados += 1
    return gravados


# ---------------------------------------------------------------------------
# Degradação sem tabela (correção A13) — abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
def _degradar_tabela_ausente(exc: ProgrammingError) -> NoReturn:
    """`precos_diarios` inexistente -> DadoNaoEncontrado; outro ProgrammingError propaga."""
    mensagem = str(getattr(exc, "orig", None) or exc).lower()
    ausente = any(
        marca in mensagem for marca in ("does not exist", "undefined table", "no such table")
    )
    if ausente:
        raise DadoNaoEncontrado(
            "precos_diarios indisponível (tabela ausente — aplicar migração 0006) — "
            "dado não encontrado"
        ) from exc
    raise exc


# ---------------------------------------------------------------------------
# Leitura / staleness
# ---------------------------------------------------------------------------
def _dias_uteis_atras(hoje: dt.date, n: int) -> dt.date:
    """Data `n` dias ÚTEIS (seg-sex) antes de `hoje` — feriados não contam (heurística)."""
    data = hoje
    while n > 0:
        data -= dt.timedelta(days=1)
        if data.weekday() < 5:
            n -= 1
    return data


def _ler_precos(session: Session, ticker: str, janela_pregoes: int) -> list[PrecoDiario]:
    """Últimos `janela_pregoes` pregões do ticker, em ordem ASCENDENTE de data."""
    linhas = (
        session.execute(
            select(PrecoDiario)
            .where(PrecoDiario.ticker == ticker)
            .order_by(PrecoDiario.data_pregao.desc())
            .limit(janela_pregoes)
        )
        .scalars()
        .all()
    )
    return list(reversed(linhas))


def _contagem_pregoes(session: Session, ticker: str) -> int:
    return session.execute(
        select(func.count()).select_from(PrecoDiario).where(PrecoDiario.ticker == ticker)
    ).scalar_one()


def _ultimo_pregao(session: Session, ticker: str) -> dt.date | None:
    return session.execute(
        select(func.max(PrecoDiario.data_pregao)).where(PrecoDiario.ticker == ticker)
    ).scalar()


def _contagens_ok(session: Session, alvo: set[str], janela_pregoes: int) -> bool:
    return all(_contagem_pregoes(session, t) >= janela_pregoes for t in alvo)


def _todos_frescos(session: Session, alvo: set[str], hoje: dt.date) -> bool:
    corte = _dias_uteis_atras(hoje, STALENESS_DIAS_UTEIS)
    for ticker in alvo:
        ultimo = _ultimo_pregao(session, ticker)
        if ultimo is None or ultimo < corte:
            return False
    return True


def precos_frescos(session: Session, ticker: str, *, hoje: dt.date | None = None) -> bool:
    """True quando o ticker tem série de preço com o pregão mais recente
    DENTRO da janela de staleness (`STALENESS_DIAS_UTEIS` dias úteis) — MESMA
    regra usada por `ensure_precos` para decidir se dispara o backfill.

    Exposta para os perfis de classe (`acao.precisa_ingest`/`fii.precisa_
    ingest`, correção do bug 'tese legada silenciosa', 2026-07-11): sem
    linha alguma OU pregão mais velho que o corte -> False (precisa
    ingerir), mesmo que fundamentos/indicadores da empresa já existam —
    reusa a MESMA regra em vez de duplicá-la. Tabela ausente (migração 0006
    pendente/teste offline) -> False (degrada para "precisa ingerir", nunca
    derruba o chamador com um erro de schema)."""
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return False
    try:
        return _todos_frescos(session, {ticker}, hoje or dt.date.today())
    except (ProgrammingError, OperationalError):
        return False


def _meses_para_tras(hoje: dt.date, n: int) -> Iterator[tuple[int, int]]:
    """(ano, mês) do mês corrente para trás, `n` meses no total."""
    ano, mes = hoje.year, hoje.month
    for _ in range(n):
        yield ano, mes
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def ingest_arquivo_diario(
    session: Session,
    data: dt.date,
    *,
    tickers: set[str],
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Ingesta o COTAHIST diário de `data` para os tickers RASTREADOS. Idempotente.

    404 = feriado/fim de semana -> devolve 0 sem erro (o scheduler tolera).
    `tickers` vazio -> 0 sem tocar a rede (nunca o mercado inteiro).
    """
    alvo = _normalizar_tickers(tickers)
    if not alvo:
        logger.info("cotahist_diario_sem_tickers", data=str(data))
        return 0
    url = COTAHIST_DIARIO_URL.format(dia=data.day, mes=data.month, ano=data.year)
    conteudo = _baixar_zip(url, transport)
    if conteudo is None:
        return 0
    texto = _texto_do_zip(conteudo)
    if texto is None:
        return 0
    try:
        gravados = _ingest_texto(session, texto, url, alvo)
    except ProgrammingError as exc:
        _degradar_tabela_ausente(exc)
    logger.info("cotahist_diario_persistido", data=str(data), gravados=gravados)
    return gravados


def _backfill(
    session: Session,
    alvo: set[str],
    *,
    meses: int,
    janela_pregoes: int,
    hoje: dt.date,
    transport: httpx.BaseTransport | None,
) -> tuple[int, int]:
    """Miolo do backfill mensal. Devolve (linhas gravadas, arquivos processados OK).

    Anda do mês corrente para trás e PARA quando todos os tickers têm
    >= `janela_pregoes` pregões E (a série está fresca OU já processamos ao menos
    um arquivo nesta rodada — o mais novo disponível; os anteriores só teriam
    dados mais velhos). `arquivos_ok` alimenta o alarme A9 do chamador.
    """
    gravados = 0
    arquivos_ok = 0
    for ano, mes in _meses_para_tras(hoje, meses):
        if _contagens_ok(session, alvo, janela_pregoes) and (
            arquivos_ok > 0 or _todos_frescos(session, alvo, hoje)
        ):
            break
        url = COTAHIST_MENSAL_URL.format(mes=mes, ano=ano)
        conteudo = _baixar_zip(url, transport)
        if conteudo is None:
            continue  # mês sem arquivo (404) -> tenta o anterior
        texto = _texto_do_zip(conteudo)
        if texto is None:
            continue
        arquivos_ok += 1
        gravados += _ingest_texto(session, texto, url, alvo)
    return gravados, arquivos_ok


def ingest_backfill(
    session: Session,
    tickers: set[str],
    *,
    meses: int = MESES_BACKFILL_DEFAULT,
    janela_pregoes: int = JANELA_PREGOES_DEFAULT,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Backfill com os arquivos MENSAIS (COTAHIST_MmmYYYY.ZIP, ~9 MB) até cobrir
    >= `janela_pregoes` pregões por ticker (o ANUAL de ~89 MB nunca é usado).

    Idempotente; 404 de mês sem arquivo é tolerado. Devolve linhas gravadas.
    """
    alvo = _normalizar_tickers(tickers)
    if not alvo:
        return 0
    hoje = hoje or dt.date.today()
    try:
        gravados, arquivos_ok = _backfill(
            session,
            alvo,
            meses=meses,
            janela_pregoes=janela_pregoes,
            hoje=hoje,
            transport=transport,
        )
    except ProgrammingError as exc:
        _degradar_tabela_ausente(exc)
    logger.info(
        "cotahist_backfill", tickers=sorted(alvo), gravados=gravados, arquivos_ok=arquivos_ok
    )
    return gravados


def ensure_precos(
    session: Session,
    ticker: str,
    *,
    janela_pregoes: int = JANELA_PREGOES_DEFAULT,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
    meses: int = MESES_BACKFILL_DEFAULT,
) -> list[PrecoDiario]:
    """Série de preços do ticker (últimos `janela_pregoes` pregões, ascendente).

    Lê do banco; se vazia ou stale (> 5 dias úteis), dispara o
    backfill mensal direcionado. Se após o backfill houver linhas, devolve-as (série
    ainda stale é devolvida e a defasagem é rotulada pelo consumidor). Se o ticker
    não aparece em NENHUM arquivo processado (arquivo ok, 0 linhas) -> alarme A9:
    `DadoNaoEncontrado` "sem série de preço na B3" — nunca silêncio. Sem nenhum
    arquivo acessível -> abstenção por indisponibilidade. Tabela ausente (A13) ->
    abstenção rotulada, nunca 500.
    """
    ticker = ticker.upper().strip()
    hoje = hoje or dt.date.today()
    try:
        precos = _ler_precos(session, ticker, janela_pregoes)
        if precos and precos[-1].data_pregao >= _dias_uteis_atras(hoje, STALENESS_DIAS_UTEIS):
            return precos
        _, arquivos_ok = _backfill(
            session,
            {ticker},
            meses=meses,
            janela_pregoes=janela_pregoes,
            hoje=hoje,
            transport=transport,
        )
        precos = _ler_precos(session, ticker, janela_pregoes)
    except ProgrammingError as exc:
        _degradar_tabela_ausente(exc)
    if precos:
        return precos
    if arquivos_ok > 0:
        raise DadoNaoEncontrado(f"{ticker}: sem série de preço na B3 — dado não encontrado")
    raise DadoNaoEncontrado(
        f"{ticker}: COTAHIST indisponível (nenhum arquivo da B3 acessível) — dado não encontrado"
    )
