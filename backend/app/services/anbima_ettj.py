"""Conector ANBIMA — ETTJ (estrutura a termo da taxa de juros), SNAPSHOT diário.

Ingere a curva de juros do dia (vértices em dias úteis, taxas spot Svensson em
% a.a.) via POST em `CZ-down.asp` (saída CSV: latin-1, ';', decimal com
vírgula, vértice com separador de milhar — ex. '1.008'). Parseia SOMENTE a
tabela "ETTJ Inflação Implícita (IPCA)" (colunas ETTJ IPCA / ETTJ PREF /
Inflação Implícita); os blocos de parâmetros Svensson, Circular 3.361 e erros
título a título são ignorados.

TRAVA ToS ANBIMA (inegociável): este conector ingere SOMENTE o snapshot do
dia consultado — NUNCA faz loop histórico nem monta série sistemática. A
função pública não aceita intervalo de datas (teste dedicado prova); a
regressão de até 5 dias úteis existe só para achar o ÚLTIMO snapshot
publicado (staleness alvo D-1), e persiste UM único dia por chamada.
Reprodução com atribuição: toda linha gravada linka uma `Fonte` ANBIMA.

Decisões documentadas:
- `inflacao_implicita` é gravada SÓ na linha da curva IPCA: é o diferencial
  do PAR (IPCA × PRE) apresentado pela ANBIMA na tabela IPCA; gravar nas duas
  linhas duplicaria o mesmo fato sob duas chaves (risco de divergência em
  atualização parcial). Consumidores leem a implícita na linha IPCA.
- Vértices longos (> 2520 du) só têm curva IPCA no arquivo real: a linha PRE
  e a implícita ficam ausentes (abstenção, nunca extrapolação).
- Dia sem dado (fim de semana/feriado) = HTTP 200 com corpo VAZIO (verificado
  ao vivo em 2026-07-10 com Dt_Ref de domingo); cabeçalho diferente do
  esperado = ALARME de layout (log + abstenção, nunca parse "esperto").
- Tabela `curva_snapshot` inexistente (deploy fora de ordem — correção A13):
  degrada para `DadoNaoEncontrado` (abstenção rotulada), nunca 500.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
import uuid
from typing import NamedTuple

import httpx
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import CurvaSnapshot
from app.services import http_client
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

ANBIMA_ETTJ_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"

DESCRICAO_FONTE = "ANBIMA — ETTJ (estrutura a termo), reprodução com atribuição"

# Regressão máxima quando data_ref=None: dia útil mais recente + 5 dias úteis
# para trás (staleness alvo D-1; a ANBIMA publica o snapshot no fim do dia).
MAX_REGRESSAO_DIAS_UTEIS = 5

# Cabeçalho esperado da tabela de vértices (normalizado sem acento/caixa).
# Mudou na fonte -> alarme de layout + abstenção (nunca adivinhar coluna).
_CABECALHO_VERTICES = ("vertices", "ettj ipca", "ettj pref", "inflacao implicita")


class _LinhaVertice(NamedTuple):
    """Uma linha da tabela de vértices do CSV (valores ausentes = None)."""

    vertice_du: int
    taxa_ipca: float | None
    taxa_pre: float | None
    inflacao_implicita: float | None


# ---------------------------------------------------------------------------
# Helpers puros de parsing
# ---------------------------------------------------------------------------
def _sem_acentos(texto: str) -> str:
    """Minúsculas sem acentos — comparação de cabeçalho estável em latin-1."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _parse_taxa(raw: str) -> float | None:
    """Taxa em % a.a. com vírgula decimal (ex. '13,8285'). Vazio/lixo -> None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _parse_vertice(raw: str) -> int | None:
    """Vértice em dias úteis; '.' é separador de MILHAR (ex. '1.008' -> 1008)."""
    raw = (raw or "").strip().replace(".", "")
    if not raw.isdigit():
        return None
    return int(raw)


def _parse_data_arquivo(cell: str) -> dt.date | None:
    """Data de referência da 1ª linha do CSV ('09/07/2026'). Lixo -> None."""
    try:
        return dt.datetime.strptime(cell.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _alarme_layout(motivo: str) -> DadoNaoEncontrado:
    """Alarme de mudança de layout da fonte: log + abstenção rotulada."""
    logger.warning("anbima_ettj_layout_inesperado", motivo=motivo)
    return DadoNaoEncontrado(f"ANBIMA ETTJ: layout inesperado no CSV ({motivo}) — snapshot abstido")


def _parse_csv(texto: str) -> tuple[dt.date, list[_LinhaVertice]] | None:
    """Extrai (data do arquivo, linhas de vértice) do CSV da ANBIMA.

    Devolve None quando o corpo não é um CSV de ETTJ (sem data na 1ª linha —
    dia sem dado, a regressão tenta o candidato anterior). CSV com data mas
    sem a tabela/ cabeçalho esperado -> alarme de layout (DadoNaoEncontrado).
    """
    linhas = [linha.split(";") for linha in texto.splitlines()]
    primeiras = [cels for cels in linhas if any(c.strip() for c in cels)]
    if not primeiras:
        return None
    data_arquivo = _parse_data_arquivo(primeiras[0][0])
    if data_arquivo is None:
        return None

    inicio = next(
        (i for i, cels in enumerate(linhas) if _sem_acentos(cels[0]).startswith("ettj infla")),
        None,
    )
    if inicio is None or inicio + 1 >= len(linhas):
        raise _alarme_layout("tabela 'ETTJ Inflação Implícita (IPCA)' ausente")
    cabecalho = tuple(_sem_acentos(c) for c in linhas[inicio + 1][:4])
    if cabecalho != _CABECALHO_VERTICES:
        raise _alarme_layout(f"cabeçalho de vértices mudou: {cabecalho!r}")

    vertices: list[_LinhaVertice] = []
    for cels in linhas[inicio + 2 :]:
        vertice = _parse_vertice(cels[0])
        if vertice is None:
            break  # linha em branco ou próximo bloco: fim da tabela
        cels = list(cels) + ["", "", ""]  # colunas ausentes viram vazio
        vertices.append(
            _LinhaVertice(
                vertice_du=vertice,
                taxa_ipca=_parse_taxa(cels[1]),
                taxa_pre=_parse_taxa(cels[2]),
                inflacao_implicita=_parse_taxa(cels[3]),
            )
        )
    if not vertices:
        raise _alarme_layout("tabela de vértices sem nenhuma linha numérica")
    return data_arquivo, vertices


# ---------------------------------------------------------------------------
# Rede — 1 POST por dia-candidato, sempre via http_client (nunca httpx direto)
# ---------------------------------------------------------------------------
def _baixar_dia(data: dt.date, transport: httpx.BaseTransport | None) -> str | None:
    """CSV do dia via POST keyless; sem dado/erro HTTP -> None (candidato falha)."""
    corpo = {"Idioma": "PT", "Dt_Ref": data.strftime("%d/%m/%Y"), "saida": "csv"}
    try:
        resp = http_client.post_keyless(
            ANBIMA_ETTJ_URL, data=corpo, timeout=60.0, transport=transport
        )
    except httpx.HTTPError as exc:
        logger.warning("anbima_ettj_falha_http", dia=str(data), erro=type(exc).__name__)
        return None
    if resp.status_code != 200:
        logger.info("anbima_ettj_status_nao_ok", dia=str(data), status=resp.status_code)
        return None
    texto = resp.content.decode("latin-1")
    if not texto.strip():
        # Forma real do "sem dado" (fim de semana/feriado): 200 com corpo vazio.
        logger.info("anbima_ettj_dia_sem_dado", dia=str(data))
        return None
    return texto


def _dias_uteis_candidatos(hoje: dt.date) -> list[dt.date]:
    """Dia útil mais recente <= hoje + até MAX_REGRESSAO_DIAS_UTEIS regressões.

    Fins de semana são pulados sem requisição (parcimônia com a fonte); a
    lista é LIMITADA — nunca vira varredura histórica (trava ToS).
    """
    candidatos: list[dt.date] = []
    dia = hoje
    while len(candidatos) < MAX_REGRESSAO_DIAS_UTEIS + 1:
        if dia.weekday() < 5:  # 0..4 = seg..sex
            candidatos.append(dia)
        dia -= dt.timedelta(days=1)
    return candidatos


def snapshot_recente(session: Session, *, hoje: dt.date | None = None) -> bool:
    """True quando já existe snapshot ANBIMA ETTJ dentro da MESMA janela de
    regressão aceita por `ensure_snapshot` (`MAX_REGRESSAO_DIAS_UTEIS` dias
    úteis) — reusa `_dias_uteis_candidatos` em vez de duplicar a regra.

    Exposta para `renda_fixa.precisa_ingest` (correção do bug "tese legada
    silenciosa", 2026-07-11): o snapshot do dia é alimentado principalmente
    pelo job diário do scheduler (`scheduler._job_anbima_ettj`) — esta
    checagem é o FALLBACK on-demand para o caso raro de o job ainda não ter
    rodado. Tabela ausente (migração 0006 pendente/teste offline) -> False
    (degrada para "precisa ingerir", nunca derruba o chamador)."""
    candidatos = _dias_uteis_candidatos(hoje or dt.date.today())
    corte = min(candidatos)
    try:
        return (
            session.execute(
                select(CurvaSnapshot.id).where(CurvaSnapshot.data_ref >= corte).limit(1)
            ).first()
            is not None
        )
    except (ProgrammingError, OperationalError):
        return False


# ---------------------------------------------------------------------------
# Persistência — upsert idempotente por (data_ref, curva, vertice_du)
# ---------------------------------------------------------------------------
def _upsert(
    session: Session,
    data_ref: dt.date,
    curva: str,
    vertice_du: int,
    taxa: float,
    inflacao_implicita: float | None,
    fonte_id: uuid.UUID,
) -> CurvaSnapshot:
    """Idempotente por (data_ref, curva, vertice_du) — espelha o UNIQUE da 0006."""
    existente = session.execute(
        select(CurvaSnapshot).where(
            CurvaSnapshot.data_ref == data_ref,
            CurvaSnapshot.curva == curva,
            CurvaSnapshot.vertice_du == vertice_du,
        )
    ).scalar_one_or_none()
    if existente is None:
        linha = CurvaSnapshot(
            data_ref=data_ref,
            curva=curva,
            vertice_du=vertice_du,
            taxa=taxa,
            inflacao_implicita=inflacao_implicita,
            fonte_id=fonte_id,
        )
        session.add(linha)
        return linha
    existente.taxa = taxa
    existente.inflacao_implicita = inflacao_implicita
    existente.fonte_id = fonte_id
    return existente


def _persistir(
    session: Session, data_ref: dt.date, vertices: list[_LinhaVertice]
) -> list[CurvaSnapshot]:
    """Grava as curvas PRE e IPCA do dia num SAVEPOINT (degradação A13).

    Tabela `curva_snapshot` inexistente (migração 0006 ainda não aplicada) ->
    o savepoint é desfeito e a falha vira DadoNaoEncontrado (abstenção
    rotulada) — a transação externa segue utilizável, nunca 500.
    """
    try:
        with session.begin_nested():
            fonte_id = get_or_create_fonte(
                session, url=ANBIMA_ETTJ_URL, descricao=DESCRICAO_FONTE, dt_referencia=data_ref
            )
            gravados: list[CurvaSnapshot] = []
            for v in vertices:
                if v.taxa_ipca is not None:
                    gravados.append(
                        _upsert(
                            session,
                            data_ref,
                            "IPCA",
                            v.vertice_du,
                            v.taxa_ipca,
                            v.inflacao_implicita,
                            fonte_id,
                        )
                    )
                if v.taxa_pre is not None:
                    # Implícita fica SÓ na linha IPCA (decisão no docstring do módulo).
                    gravados.append(
                        _upsert(session, data_ref, "PRE", v.vertice_du, v.taxa_pre, None, fonte_id)
                    )
            session.flush()
    except (ProgrammingError, OperationalError) as exc:
        logger.warning(
            "anbima_ettj_tabela_indisponivel", data_ref=str(data_ref), erro=type(exc).__name__
        )
        raise DadoNaoEncontrado(
            "ANBIMA ETTJ: tabela curva_snapshot indisponível (migração 0006 pendente?) "
            "— snapshot abstido, dado não encontrado"
        ) from exc
    logger.info("anbima_ettj_snapshot_persistido", data_ref=str(data_ref), linhas=len(gravados))
    return gravados


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def ensure_snapshot(
    session: Session,
    data_ref: dt.date | None = None,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[CurvaSnapshot]:
    """Ingere o snapshot ETTJ de UM único dia e devolve as linhas gravadas.

    TRAVA ToS ANBIMA: SOMENTE o snapshot do dia consultado — a função não
    aceita intervalo de datas e cada chamada persiste UM dia. Com `data_ref`
    explícita: 1 única requisição, sem regressão. Com `data_ref=None`: tenta
    o dia útil mais recente (<= `hoje`, injetável p/ teste) e regride até 5
    dias úteis quando o dia não tem dado (corpo vazio/404) — staleness D-1.

    Se a fonte devolver o arquivo de OUTRO dia, a data DO ARQUIVO vence
    (rotulagem honesta, com log). Upsert idempotente por
    (data_ref, curva, vertice_du); toda linha linka a `Fonte` ANBIMA do dia.
    Sem dado em nenhum candidato, ou tabela ausente (A13) ->
    DadoNaoEncontrado (abstenção rotulada, nunca 500).
    """
    if data_ref is not None:
        candidatos = [data_ref]
    else:
        candidatos = _dias_uteis_candidatos(hoje or dt.date.today())

    for dia in candidatos:
        texto = _baixar_dia(dia, transport)
        if texto is None:
            continue
        parsed = _parse_csv(texto)
        if parsed is None:
            logger.info("anbima_ettj_corpo_nao_reconhecido", dia=str(dia))
            continue
        data_arquivo, vertices = parsed
        if data_arquivo != dia:
            logger.warning(
                "anbima_ettj_data_divergente", pedido=str(dia), arquivo=str(data_arquivo)
            )
        return _persistir(session, data_arquivo, vertices)

    raise DadoNaoEncontrado(
        "ANBIMA ETTJ: sem snapshot publicado nos dias consultados — dado não encontrado"
    )
