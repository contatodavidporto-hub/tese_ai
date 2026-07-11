"""Conector ANEEL SIGET — RAP homologada de transmissoras (fase "Tese Profunda", F1).

Consulta o CKAN datastore de dados abertos da ANEEL (resource SIGET "RAP por
função de transmissão") e agrega a Receita Anual Permitida do GRUPO econômico
do ticker: soma de `VlrRAPCiclo` dos registros com situação vigente
(`DcsSitRAP` = "Ativa") no ciclo tarifário mais recente (`DatRefCiclo`),
upsertada em `setor_indicadores` (indicador `RAP_CICLO`, unidade BRL,
competência = data do ciclo). Todo fato linka uma `Fonte` ANEEL (URL do
recurso + `DatGeracaoConjuntoDados`); atribuição ODbL declarada.

Correção A8 (inegociável): o SIGET lista RAP por CONCESSIONÁRIA, e um emissor
listado agrega VÁRIAS concessões com siglas/CNPJs próprios. O escopo vem de um
MAPA CURADO versionado (`_GRUPOS_RAP_V1`) ticker -> siglas do grupo, com o
critério declarado na metodologia da métrica. NUNCA a RAP de uma subsidiária é
apresentada como "a RAP" do emissor; ticker fora do mapa -> `None` (sem rede).

Regras duras:
- Fail-closed: registro vigente do ciclo-alvo com valor malformado, ciclo
  ilegível ou CNPJ fora do mapa curado (sigla possivelmente reatribuída — a
  ANEEL renomeia siglas em rebranding) -> abstenção com alarme, NUNCA soma
  parcial "esperta".
- Zero registros para as siglas do grupo -> abstenção rotulada (mapa curado
  possivelmente desatualizado), nunca RAP = 0.
- Rede indisponível -> devolve o último agregado já persistido (fato com
  fonte); sem histórico -> abstenção.
- Correção A13: tabela `setor_indicadores` inexistente (migração 0006 não
  aplicada) degrada para `DadoNaoEncontrado`, nunca 500.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from decimal import Decimal
from typing import Any, NamedTuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import SetorIndicador
from app.services import http_client
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

ANEEL_DATASTORE_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
RESOURCE_ID_RAP = "5e4e4916-fd70-44c7-a0eb-92bfb4efad6b"  # SIGET — RAP por função de transmissão
DATASET_URL = f"{ANEEL_DATASTORE_URL}?resource_id={RESOURCE_ID_RAP}"

DESCRICAO_FONTE = (
    "ANEEL — SIGET, RAP homologada por concessionária (dados abertos, licença ODbL; "
    "reprodução com atribuição)"
)

INDICADOR_RAP = "RAP_CICLO"
UNIDADE_RAP = "BRL"

_SITUACAO_VIGENTE = "ativa"  # DcsSitRAP normalizado; "Prevista" (obra) fica fora da soma
_PAGE_LIMIT = 500
_MAX_PAGINAS = 40  # trava anti-loop (40×500 = 20k registros >> qualquer grupo real)
_MAX_ATOS_METODOLOGIA = 10  # atos legais citados por extenso; o restante vira "+N outros"

# Campos requisitados ao datastore (payload mínimo). Campo removido/renomeado na
# fonte -> o CKAN responde erro -> alarme de layout (abstenção, nunca adivinhar).
_CAMPOS = (
    "SigConcessionariaReceita",
    "NumCNPJConcessionariaUsr",
    "VlrRAPCiclo",
    "DatRefCiclo",
    "DcsSitRAP",
    "NumAtoRAP",
    "DatGeracaoConjuntoDados",
    "QtdAnosCcoTar",
)

# Valor pt-BR do SIGET: decimal com vírgula, "." SÓ como separador de milhar.
_VALOR_BRL_RE = re.compile(r"^-?\d+(?:\.\d{3})*(?:,\d+)?$")


class GrupoRap(NamedTuple):
    """Escopo curado de um grupo de transmissão (correção A8)."""

    nome: str
    versao: str  # versão do mapa curado, citada na metodologia
    siglas: tuple[str, ...]  # SigConcessionariaReceita EXATAS no SIGET
    cnpjs: frozenset[str]  # NumCNPJConcessionariaUsr esperados (checagem de reatribuição)
    criterio: str  # frase do critério de inclusão/exclusão, citada na metodologia


# MAPA CURADO v1 (2026-07-10) — descoberta empírica no dataset (varredura completa das
# 301 siglas de SigConcessionariaReceita) CRUZADA com a lista pública de concessões da
# Taesa (institucional.taesa.com.br > A Companhia > Nosso Negócio, consultada em
# 2026-07-10): entram SOMENTE as concessões com participação 100,00% —
# (i) 14 concessões da holding sob a sigla "TAESA" (CNPJ 07.859.971/0001-30: TSN,
#     Novatrans, ETEO, GTESA, PATESA, Munirah, NTE, STE, ATE, ATE II, ATE III,
#     Miracema, Saíra e Sant'Ana, já incorporadas à Taesa S.A.);
# (ii) 11 investidas integrais com sigla/CNPJ próprios no SIGET (Brasnorte,
#      São Gotardo, São João, São Pedro, Mariana, Janaúba, Lagoa Nova, Ananaí,
#      Pitiguari, Tangará e Juruá).
# FICAM FORA (participação parcial — incluí-las superestimaria a RAP do emissor):
# ETAU 75,62%, EBTE 74,49%, Transmineiras (Translestre/Transudeste/Transirapé 54%),
# grupo AIE (Aimorés/Paraguaçu/Ivaí 50%, ESTE 49,98%) e grupo TBE (EATE/ENTE/ERTE/
# ETEP/ECTE/ETSE/ESDE/EDTE/STC/Lumitrans, 19,09%–49,99%).
_GRUPOS_RAP_V1: dict[str, GrupoRap] = {
    "TAEE11": GrupoRap(
        nome="Taesa",
        versao="v1 (2026-07-10)",
        siglas=(
            "TAESA",  # holding (07859971000130) — 14 concessões incorporadas
            "BRASNORTE",  # 09274998000197
            "SÃO GOTARDO",  # 15867360000162
            "SJT/SÃO JOÃO",  # 18314074000168
            "SPT/SÃO PEDRO",  # 18707010000127
            "MARIANA",  # 19486977000199
            "JANAUBA",  # 26617923000180
            "LAGOA NOVA",  # 27965273000127
            "ANANAI",  # 42215683000144
            "PITIGUARI",  # 45661917000175
            "TANGARÁ TRANSMIS",  # 45690276000187
            "JURUA",  # 42215810000105 (em construção — registros "Prevista")
        ),
        cnpjs=frozenset(
            {
                "07859971000130",
                "09274998000197",
                "15867360000162",
                "18314074000168",
                "18707010000127",
                "19486977000199",
                "26617923000180",
                "27965273000127",
                "42215683000144",
                "45661917000175",
                "45690276000187",
                "42215810000105",
            }
        ),
        criterio=(
            "concessões com participação 100% do grupo Taesa (holding + investidas "
            "integrais, conforme lista pública da companhia em 2026-07-10); exclui "
            "participações parciais (ETAU, EBTE, Transmineiras, grupos AIE e TBE)"
        ),
    ),
}


class _Agregado(NamedTuple):
    """Resultado da agregação do grupo no ciclo mais recente."""

    valor: Decimal
    ciclo: dt.date
    rotulo_ciclo: str  # ex. "2026-2027" (QtdAnosCcoTar) ou ISO do ciclo
    n_registros: int
    atos: tuple[str, ...]  # NumAtoRAP distintos, ordenados
    data_geracao: dt.date | None  # DatGeracaoConjuntoDados do dataset


# ---------------------------------------------------------------------------
# Helpers puros de parsing
# ---------------------------------------------------------------------------
def _parse_valor_brl(raw: str | None) -> Decimal | None:
    """`VlrRAPCiclo` pt-BR ('26244,99', '1.234.567,89', '-12,5'). Fora do formato -> None."""
    raw = (raw or "").strip()
    if not _VALOR_BRL_RE.match(raw):
        return None
    return Decimal(raw.replace(".", "").replace(",", "."))


def _parse_ciclo(raw: str | None) -> dt.date | None:
    """`DatRefCiclo` ('2026-06-01 00:00:00') -> data do ciclo. Lixo -> None."""
    raw = (raw or "").strip()
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_data_geracao(raw: str | None) -> dt.date | None:
    """`DatGeracaoConjuntoDados` ('2026-07-10') -> data. Lixo -> None."""
    try:
        return dt.date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def _alarme(motivo: str) -> DadoNaoEncontrado:
    """Alarme de contrato/layout da fonte: log + abstenção rotulada, nunca chute."""
    logger.warning("aneel_rap_alarme", motivo=motivo)
    return DadoNaoEncontrado(f"ANEEL SIGET: {motivo} — RAP abstida, dado não encontrado")


# ---------------------------------------------------------------------------
# Rede — CKAN datastore paginado, sempre via http_client (nunca httpx direto)
# ---------------------------------------------------------------------------
def _url_pagina(grupo: GrupoRap, offset: int) -> str:
    """URL do datastore_search com filtro exato pelas siglas do grupo."""
    params = {
        "resource_id": RESOURCE_ID_RAP,
        "filters": json.dumps({"SigConcessionariaReceita": list(grupo.siglas)}),
        "fields": ",".join(_CAMPOS),
        "limit": _PAGE_LIMIT,
        "offset": offset,
    }
    return f"{ANEEL_DATASTORE_URL}?{urlencode(params)}"


def _baixar_pagina(
    grupo: GrupoRap, offset: int, transport: httpx.BaseTransport | None
) -> dict[str, Any]:
    """Uma página do datastore; erro de rede/HTTP/JSON -> abstenção rotulada."""
    try:
        resp = http_client.get_keyless(
            _url_pagina(grupo, offset), timeout=90.0, transport=transport
        )
    except httpx.HTTPError as exc:
        logger.warning("aneel_rap_falha_http", offset=offset, erro=type(exc).__name__)
        raise DadoNaoEncontrado(
            "ANEEL SIGET: datastore indisponível (falha de rede) — dado não encontrado"
        ) from exc
    if resp.status_code != 200:
        raise _alarme(f"datastore respondeu HTTP {resp.status_code}")
    try:
        corpo = resp.json()
    except ValueError as exc:
        raise _alarme("resposta não é JSON") from exc
    if not isinstance(corpo, dict) or corpo.get("success") is not True:
        # Também cobre campo removido/renomeado: o CKAN devolve success=false.
        raise _alarme("resposta sem success=true (layout/campos do recurso mudaram?)")
    resultado = corpo.get("result") or {}
    if not isinstance(resultado.get("records"), list):
        raise _alarme("resposta sem lista de records")
    return resultado


def _coletar_registros(
    grupo: GrupoRap, transport: httpx.BaseTransport | None
) -> list[dict[str, Any]]:
    """Todos os registros do grupo (paginação até `total`, com trava anti-loop)."""
    registros: list[dict[str, Any]] = []
    for pagina in range(_MAX_PAGINAS):
        resultado = _baixar_pagina(grupo, pagina * _PAGE_LIMIT, transport)
        lote = resultado["records"]
        registros.extend(lote)
        total = resultado.get("total")
        if not lote or not isinstance(total, int) or len(registros) >= total:
            break
    if not registros:
        raise _alarme(
            f"nenhum registro para as siglas do grupo {grupo.nome} "
            f"(mapa curado {grupo.versao} possivelmente desatualizado)"
        )
    return registros


# ---------------------------------------------------------------------------
# Agregação — vigentes no ciclo mais recente, fail-closed em anomalia
# ---------------------------------------------------------------------------
def _so_digitos(raw: str | None) -> str:
    return re.sub(r"\D", "", raw or "")


def _agregar(grupo: GrupoRap, registros: list[dict[str, Any]]) -> _Agregado:
    """Soma `VlrRAPCiclo` dos registros vigentes do ciclo mais recente.

    Fail-closed: anomalia em QUALQUER registro do ciclo-alvo (ciclo ilegível,
    valor malformado, CNPJ fora do mapa curado) -> abstenção com alarme —
    nunca um agregado parcial apresentado como total.
    """
    vigentes = [
        r for r in registros if str(r.get("DcsSitRAP") or "").strip().lower() == _SITUACAO_VIGENTE
    ]
    if not vigentes:
        raise _alarme(f"grupo {grupo.nome} sem registro vigente (DcsSitRAP) no dataset")

    ciclos: list[dt.date] = []
    for r in vigentes:
        ciclo = _parse_ciclo(str(r.get("DatRefCiclo") or ""))
        if ciclo is None:
            raise _alarme("registro vigente com DatRefCiclo ilegível")
        ciclos.append(ciclo)
    ciclo_max = max(ciclos)
    alvo = [r for r, c in zip(vigentes, ciclos, strict=True) if c == ciclo_max]

    soma = Decimal(0)
    atos: set[str] = set()
    rotulos: set[str] = set()
    geracoes: list[dt.date] = []
    for r in alvo:
        cnpj = _so_digitos(str(r.get("NumCNPJConcessionariaUsr") or ""))
        if cnpj and cnpj not in grupo.cnpjs:
            raise _alarme(
                f"registro da sigla {r.get('SigConcessionariaReceita')!r} com CNPJ {cnpj} "
                f"fora do mapa curado {grupo.versao} (sigla reatribuída? atualizar o mapa)"
            )
        valor = _parse_valor_brl(str(r.get("VlrRAPCiclo") or ""))
        if valor is None:
            raise _alarme(f"VlrRAPCiclo malformado ({r.get('VlrRAPCiclo')!r}) no ciclo-alvo")
        soma += valor
        ato = str(r.get("NumAtoRAP") or "").strip()
        if ato:
            atos.add(ato)
        rotulo = str(r.get("QtdAnosCcoTar") or "").strip()
        if rotulo:
            rotulos.add(rotulo)
        geracao = _parse_data_geracao(str(r.get("DatGeracaoConjuntoDados") or ""))
        if geracao is not None:
            geracoes.append(geracao)

    rotulo_ciclo = rotulos.pop() if len(rotulos) == 1 else ciclo_max.isoformat()
    return _Agregado(
        valor=soma,
        ciclo=ciclo_max,
        rotulo_ciclo=rotulo_ciclo,
        n_registros=len(alvo),
        atos=tuple(sorted(atos)),
        data_geracao=max(geracoes) if geracoes else None,
    )


def _metodologia(grupo: GrupoRap, ag: _Agregado) -> str:
    """Metodologia declarada da métrica (correção A8) — escopo, ciclo, atos, ODbL."""
    citados = ag.atos[:_MAX_ATOS_METODOLOGIA]
    resto = len(ag.atos) - len(citados)
    atos_txt = ", ".join(citados) + (f" (+{resto} outros atos)" if resto > 0 else "")
    return (
        f"RAP agregada das concessões do grupo {grupo.nome} — critério: mapa curado "
        f"{grupo.versao}: {grupo.criterio}; siglas SIGET: {', '.join(grupo.siglas)}; "
        f"soma de VlrRAPCiclo dos {ag.n_registros} registros com situação 'Ativa' no ciclo "
        f"{ag.rotulo_ciclo} (DatRefCiclo {ag.ciclo.isoformat()}); fonte: ANEEL SIGET "
        f"(dados abertos, ODbL), atos legais (NumAtoRAP): {atos_txt}"
    )


# ---------------------------------------------------------------------------
# Persistência — upsert idempotente por (ticker, indicador, competencia)
# ---------------------------------------------------------------------------
def _persistir(session: Session, ticker: str, grupo: GrupoRap, ag: _Agregado) -> SetorIndicador:
    """Grava o agregado num SAVEPOINT; tabela ausente (A13) -> abstenção rotulada."""
    try:
        with session.begin_nested():
            fonte_id = get_or_create_fonte(
                session,
                url=DATASET_URL,
                descricao=DESCRICAO_FONTE,
                dt_referencia=ag.data_geracao or ag.ciclo,
            )
            linha = _upsert(session, ticker, ag, _metodologia(grupo, ag), fonte_id)
            session.flush()
    except (ProgrammingError, OperationalError) as exc:
        logger.warning("aneel_rap_tabela_indisponivel", ticker=ticker, erro=type(exc).__name__)
        raise DadoNaoEncontrado(
            "ANEEL SIGET: tabela setor_indicadores indisponível (migração 0006 pendente?) "
            "— RAP abstida, dado não encontrado"
        ) from exc
    logger.info(
        "aneel_rap_persistido",
        ticker=ticker,
        ciclo=str(ag.ciclo),
        registros=ag.n_registros,
        valor=str(ag.valor),
    )
    return linha


def _upsert(
    session: Session, ticker: str, ag: _Agregado, metodologia: str, fonte_id: uuid.UUID
) -> SetorIndicador:
    """Idempotente por (ticker, indicador, competencia) — espelha o UNIQUE da 0006."""
    existente = session.execute(
        select(SetorIndicador).where(
            SetorIndicador.ticker == ticker,
            SetorIndicador.indicador == INDICADOR_RAP,
            SetorIndicador.competencia == ag.ciclo,
        )
    ).scalar_one_or_none()
    if existente is None:
        linha = SetorIndicador(
            ticker=ticker,
            indicador=INDICADOR_RAP,
            valor=ag.valor,
            unidade=UNIDADE_RAP,
            competencia=ag.ciclo,
            metodologia=metodologia,
            fonte_id=fonte_id,
        )
        session.add(linha)
        return linha
    existente.valor = ag.valor
    existente.unidade = UNIDADE_RAP
    existente.metodologia = metodologia
    existente.fonte_id = fonte_id
    return existente


def _ler_ultimo(session: Session, ticker: str) -> SetorIndicador | None:
    """Último agregado persistido do ticker (competência mais recente), se houver."""
    try:
        return session.execute(
            select(SetorIndicador)
            .where(SetorIndicador.ticker == ticker, SetorIndicador.indicador == INDICADOR_RAP)
            .order_by(SetorIndicador.competencia.desc())
            .limit(1)
        ).scalar_one_or_none()
    except (ProgrammingError, OperationalError):
        return None  # tabela ausente (A13): sem histórico para degradar


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def ensure_rap(
    session: Session,
    ticker: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> SetorIndicador | None:
    """RAP agregada do grupo do `ticker` no ciclo mais recente, como fato com fonte.

    Ticker fora do mapa curado (`_GRUPOS_RAP_V1`) -> `None` SEM tocar a rede
    (abstenção de escopo, não erro: só transmissoras mapeadas têm RAP aqui).
    Com mapa: consulta o CKAN da ANEEL (filtro exato por sigla, paginado), soma
    os registros vigentes do ciclo mais recente e upserta em `setor_indicadores`
    com metodologia declarada (correção A8) e `Fonte` ANEEL/ODbL.

    Consulta falhou (rede/contrato do datastore) -> devolve o último agregado
    já persistido (fato datado, com log); sem histórico, anomalia nos registros
    do ciclo-alvo ou tabela ausente (A13) -> `DadoNaoEncontrado` (abstenção
    rotulada, nunca 500 nem soma parcial).
    """
    ticker = ticker.upper().strip()
    grupo = _GRUPOS_RAP_V1.get(ticker)
    if grupo is None:
        logger.info("aneel_rap_fora_do_mapa", ticker=ticker)
        return None
    try:
        registros = _coletar_registros(grupo, transport)
    except DadoNaoEncontrado:
        anterior = _ler_ultimo(session, ticker)
        if anterior is not None:
            logger.warning(
                "aneel_rap_usando_ultimo_persistido",
                ticker=ticker,
                competencia=str(anterior.competencia),
            )
            return anterior
        raise
    agregado = _agregar(grupo, registros)
    return _persistir(session, ticker, grupo, agregado)
