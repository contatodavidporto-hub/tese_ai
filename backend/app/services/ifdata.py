"""Conector IF.data (BCB) — indicadores prudenciais de bancos (fase "Tese Profunda", F1).

REST interno NÃO documentado `www3.bcb.gov.br/ifdata/rest` (o mesmo que alimenta
ifdata.bcb.gov.br), sondado ao vivo em 2026-07-10 (fixtures congeladas em
`tests/fixtures/ifdata/`):

- `GET /relatorios2025a2030` lista as datas-base publicadas da janela
  quinquenal ([202503..202603] na sonda) com os arquivos de cada uma. O nome do
  endpoint é POR JANELA — quando a janela rolar (2031+), a listagem some e o
  conector alarma (abstenção rotulada), nunca chuta a janela seguinte.
- `GET /arquivos?nomeArquivo=<caminho da listagem>` devolve cada arquivo JSON.
  Arquivo desconhecido = HTTP **200** com corpo "Erro interno - Internal error"
  (comportamento real da API) — todo corpo não-JSON vira alarme de schema.

Esquema descoberto empiricamente (id de conceito ESTÁVEL entre datas-base —
verificado 202512 × 202603 na sonda):

- `info{dt}.json`: conceitos `{id, n (nome), lid, a (nº do arquivo de dados)}`.
  Resolvemos cada indicador pelo `id` e VALIDAMOS o nome (`n`) — id apontando
  para outro conceito é alarme, nunca número errado com fonte.
- `dados{dt}_{a}.json`: `{"id": a, "values": [{"e": <código IF.data>,
  "v": [{"i": <lid>, "v": <valor>}]}]}`.
- `cadastro{dt}_1009.json`: instituições da base prudencial (c0=código,
  c2=nome). Usado para validar que o código curado ainda é a instituição
  esperada (alarme de remapeamento).

Decisões documentadas:
- **Valores em R$ CORRENTES** — o site divide por mil na exibição ("R$ mil").
  Validado na sonda: PL Itaú 1T2026 = R$232,45 bi; Basileia Itaú = 14,77%.
- **Base prudencial** (cadastro tipo 1009, conglomerados prudenciais) ≠
  consolidação societária das demonstrações financeiras — declarado na
  metodologia de todo indicador (Res. CMN 4.966/2021 vigente desde 2025).
- **Basileia**: o REST devolve FRAÇÃO (0,1477); gravamos em % (×100), com a
  conversão declarada na metodologia.
- **LL_ANUALIZADO**: a DRE do IF.data acumula por SEMESTRE (Lei 4.595,
  apuração obrigatória em 30/06 e 31/12; nota do próprio relatório 116):
  mar/set = 1º trimestre do semestre (×4), jun/dez = semestre (×2).
  Anualização LINEAR declarada na metodologia — aproximação, não projeção.
- **Mapa curado** cd_cvm -> código IF.data (5 bancos listados). Fora do mapa =
  `DadoNaoEncontrado` (lacuna honesta v1). **Caixa** (IF.data 1000080738) NÃO
  tem registro de companhia aberta na CVM (sonda cad_cia_aberta 2026-07-10) —
  sem cd_cvm, fica FORA do mapa; código exportado em `IFDATA_CODIGO_CAIXA`
  para uso futuro (comparação de pares). BB descoberto no cadastro prudencial:
  1000080329 ("BB - PRUDENCIAL").
- Staleness: re-consulta a fonte quando a última extração persistida tem mais
  de `STALENESS_CONSULTA_DIAS` (30); o DADO em si fica ~100 dias defasado
  (trimestral + atraso de publicação) — o consumidor rotula a defasagem pelo
  `dt_referencia` (fim do mês da data-base). Fonte indisponível com dado
  persistido -> serve o persistido (defasagem honesta), nunca inventa.
- Correção A13: tabela `banco_indicadores` ausente (migração 0006 não
  aplicada) degrada para `DadoNaoEncontrado`, nunca 500.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import unicodedata
import uuid
from typing import NamedTuple, NoReturn

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import BancoIndicador, Fonte
from app.services import http_client
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

IFDATA_REST_BASE = "https://www3.bcb.gov.br/ifdata/rest"
# Endpoint por janela quinquenal (sonda 2026-07-10). Janela nova -> alarme, não chute.
IFDATA_RELATORIOS_URL = f"{IFDATA_REST_BASE}/relatorios2025a2030"
IFDATA_ARQUIVO_URL = IFDATA_REST_BASE + "/arquivos?nomeArquivo={nome}"

BASE_PRUDENCIAL = "prudencial"
TIPO_CADASTRO_PRUDENCIAL = 1009  # conglomerados prudenciais e instituições independentes

# Re-consulta a fonte após 30 dias (publicação trimestral com atraso ~50d);
# a defasagem do DADO (~100d) é rotulada pelo consumidor via dt_referencia.
STALENESS_CONSULTA_DIAS = 30

# Mapa CURADO cd_cvm -> (código IF.data, rótulo esperado no cadastro prudencial).
# cd_cvm confirmados na CVM (cad_cia_aberta.csv, sonda 2026-07-10); códigos
# IF.data confirmados no cadastro tipo 1009 da data-base 202603. O rótulo é
# validado contra o campo c2 do cadastro a cada colheita (alarme de remapeamento).
MAPA_CVM_IFDATA: dict[int, tuple[int, str]] = {
    19348: (1000080099, "ITAU"),  # Itaú Unibanco Holding S.A.
    906: (1000080075, "BRADESCO"),  # Banco Bradesco S.A.
    20532: (1000080185, "SANTANDER"),  # Banco Santander (Brasil) S.A.
    1023: (1000080329, "BB"),  # Banco do Brasil S.A. — descoberto no cadastro
    22616: (1000080336, "BTG PACTUAL"),  # Banco BTG Pactual S.A.
}

# Caixa Econômica Federal: SEM registro de cia aberta na CVM (sem cd_cvm) ->
# fora do mapa acima por honestidade; código IF.data guardado p/ uso futuro.
IFDATA_CODIGO_CAIXA = 1000080738


class _Conceito(NamedTuple):
    """Conceito do `info{dt}.json`: id estável + validação de nome + unidade."""

    info_id: int
    nome_esperado: str  # substring normalizada (sem acento/caixa) do campo `n`
    unidade: str  # 'PCT' | 'BRL'


# Indicadores extraídos (chaves do dict devolvido). ids verificados estáveis
# entre 202512 e 202603 (mesmos lid/arquivo); o nome é validado a cada colheita.
_CONCEITOS: dict[str, _Conceito] = {
    "BASILEIA": _Conceito(79664, "indice de basileia", "PCT"),
    "PR": _Conceito(79699, "patrimonio de referencia", "BRL"),
    "RWA": _Conceito(79665, "ativos ponderados pelo risco", "BRL"),
    "CARTEIRA_CREDITO": _Conceito(79854, "carteira de credito", "BRL"),
    "ATIVOS_PROBLEMATICOS": _Conceito(79875, "ativos problematicos", "BRL"),
    "LL_ANUALIZADO": _Conceito(79852, "lucro liquido", "BRL"),
}

INDICADORES = tuple(_CONCEITOS)

_NOTA_BASE = (
    "Base prudencial (cadastro IF.data tipo 1009 — conglomerados prudenciais e "
    "instituições independentes), que difere da consolidação societária das "
    "demonstrações financeiras. Critérios contábeis da Res. CMN 4.966/2021 "
    "(vigente desde 2025). Valores monetários em R$ correntes."
)


class _ValorColhido(NamedTuple):
    """Um indicador já convertido, com metodologia e URL do arquivo de origem."""

    valor: float
    unidade: str
    metodologia: str
    url: str


class _Colheita(NamedTuple):
    """Resultado da colheita de rede de UMA instituição em UMA data-base."""

    data_base: int  # AAAAMM
    dt_referencia: dt.date  # fim do mês da data-base
    instituicao: str  # nome no cadastro prudencial (c2)
    valores: dict[str, _ValorColhido]


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------
def _abster(motivo: str, **contexto: object) -> NoReturn:
    """Log estruturado + abstenção rotulada — nunca inventamos nem viramos 500."""
    logger.warning("ifdata_abstencao", motivo=motivo, **contexto)
    raise DadoNaoEncontrado(f"IF.data: {motivo} — dado não encontrado")


def _sem_acentos(texto: str) -> str:
    """Minúsculas, sem acentos, espaços colapsados — comparação de nomes estável."""
    nfkd = unicodedata.normalize("NFKD", texto)
    plano = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(plano.lower().split())


def _regra_anualizacao(data_base: int) -> tuple[int, str]:
    """(fator, período acumulado) da DRE do IF.data para a data-base AAAAMM.

    A DRE acumula por SEMESTRE (Lei 4.595; nota do relatório 116): mar/set =
    1º trimestre do semestre, jun/dez = semestre. Mês fora do calendário
    trimestral = a fonte mudou -> alarme.
    """
    regras = {3: (4, "jan-mar"), 6: (2, "jan-jun"), 9: (4, "jul-set"), 12: (2, "jul-dez")}
    regra = regras.get(data_base % 100)
    if regra is None:
        _abster(f"data-base {data_base} fora do calendário trimestral", data_base=data_base)
    return regra


def _fim_do_mes(data_base: int) -> dt.date:
    """Data-base AAAAMM -> último dia do mês (dt_referencia do fato)."""
    ano, mes = divmod(data_base, 100)
    if not 1 <= mes <= 12:
        _abster(f"data-base {data_base} com mês inválido", data_base=data_base)
    return dt.date(ano, mes, calendar.monthrange(ano, mes)[1])


def _metodologia(indicador: str, data_base: int) -> str:
    """Metodologia DECLARADA por indicador (conversões e regras explícitas)."""
    especificas = {
        "BASILEIA": (
            "Índice de Basileia (PR/RWA); o REST devolve fração, convertida " "para % (×100)."
        ),
        "PR": "Patrimônio de Referência para comparação com o RWA.",
        "RWA": "Ativos Ponderados pelo Risco (RWA).",
        "CARTEIRA_CREDITO": "Carteira de Crédito (relatório Resumo do IF.data).",
        "ATIVOS_PROBLEMATICOS": (
            "Ativos problemáticos conforme definição da Res. CMN 4.966/2021 "
            "(relatório de carteira de crédito ativa do IF.data)."
        ),
    }
    if indicador == "LL_ANUALIZADO":
        fator, periodo = _regra_anualizacao(data_base)
        especifica = (
            f"Lucro líquido acumulado no período {periodo} anualizado ×{fator} "
            "(anualização LINEAR declarada; Lei 4.595: apuração semestral "
            "obrigatória — mar/set acumulam o 1º trimestre do semestre, "
            "jun/dez o semestre). Aproximação, não projeção."
        )
    else:
        especifica = especificas[indicador]
    return f"{especifica} BCB IF.data, data-base {data_base}. {_NOTA_BASE}"


# ---------------------------------------------------------------------------
# Rede — sempre via http_client (anti-SSRF); nunca httpx direto
# ---------------------------------------------------------------------------
def _arquivo_url(nome: str) -> str:
    return IFDATA_ARQUIVO_URL.format(nome=nome)


def _buscar_json(url: str, transport: httpx.BaseTransport | None) -> object:
    """GET keyless + parse JSON. Rede/status/corpo não-JSON -> abstenção rotulada.

    O endpoint devolve 200 com "Erro interno - Internal error" para arquivo
    desconhecido (comportamento real) — por isso o parse é o alarme de schema.
    """
    try:
        resp = http_client.get_keyless(url, timeout=180.0, transport=transport)
    except httpx.HTTPError as exc:
        _abster("falha HTTP no REST do IF.data", url=url, erro=type(exc).__name__)
    if resp.status_code != 200:
        _abster("status inesperado do REST do IF.data", url=url, status=resp.status_code)
    try:
        return json.loads(resp.content)
    except (ValueError, UnicodeDecodeError):
        _abster(
            "resposta não-JSON do REST do IF.data (alarme de schema — endpoint "
            "interno pode ter mudado)",
            url=url,
            inicio=resp.content[:60].decode("utf-8", errors="replace"),
        )


def _arquivos_da_base(listagem: object, data_base: int | None) -> tuple[int, dict[str, str]]:
    """(data-base escolhida, {nome-base: caminho}) da listagem de relatórios.

    Sem `data_base` explícita usa a MAIS RECENTE publicada. `data_base` pedida
    e não publicada -> abstenção (nunca aproximamos para outra data-base).
    """
    if not isinstance(listagem, list) or not listagem:
        _abster("listagem de relatórios vazia ou com formato inesperado")
    por_dt: dict[int, list] = {}
    for item in listagem:
        if isinstance(item, dict) and isinstance(item.get("dt"), int):
            por_dt[item["dt"]] = item.get("files") or []
    if not por_dt:
        _abster("listagem de relatórios sem datas-base reconhecíveis")
    if data_base is None:
        escolhida = max(por_dt)
    elif data_base in por_dt:
        escolhida = data_base
    else:
        _abster(f"data-base {data_base} não publicada no IF.data", publicadas=sorted(por_dt))
    caminhos: dict[str, str] = {}
    for arq in por_dt[escolhida]:
        caminho = arq.get("f") if isinstance(arq, dict) else None
        if isinstance(caminho, str) and caminho:
            caminhos[caminho.rsplit("/", 1)[-1]] = caminho
    return escolhida, caminhos


def _caminho_requerido(caminhos: dict[str, str], nome: str, data_base: int) -> str:
    caminho = caminhos.get(nome)
    if caminho is None:
        _abster(f"arquivo {nome} ausente da listagem da data-base {data_base}")
    return caminho


def _resolver_conceitos(info: object, data_base: int) -> dict[str, tuple[int, int]]:
    """indicador -> (lid, nº do arquivo de dados), validando o NOME do conceito.

    Conceito ausente ou com nome divergente do esperado = alarme (id remapeado
    viraria número errado COM fonte — o pior resultado possível).
    """
    if not isinstance(info, list):
        _abster(f"info{data_base}.json com formato inesperado")
    por_id = {e["id"]: e for e in info if isinstance(e, dict) and isinstance(e.get("id"), int)}
    resolvidos: dict[str, tuple[int, int]] = {}
    for indicador, conceito in _CONCEITOS.items():
        entrada = por_id.get(conceito.info_id)
        if entrada is None:
            _abster(
                f"conceito {indicador} (id {conceito.info_id}) ausente do info",
                data_base=data_base,
            )
        nome = _sem_acentos(str(entrada.get("n") or ""))
        if conceito.nome_esperado not in nome:
            _abster(
                f"conceito {indicador} (id {conceito.info_id}) com nome divergente",
                nome_encontrado=nome[:80],
                nome_esperado=conceito.nome_esperado,
            )
        lid, arquivo = entrada.get("lid"), entrada.get("a")
        if not isinstance(lid, int) or lid <= 0 or not isinstance(arquivo, int) or arquivo < 1:
            _abster(
                f"conceito {indicador} sem lid/arquivo válidos",
                lid=lid,
                arquivo=arquivo,
            )
        resolvidos[indicador] = (lid, arquivo)
    return resolvidos


def _validar_cadastro(cadastro: object, codigo: int, rotulo: str, data_base: int) -> str:
    """Nome (c2) da instituição no cadastro prudencial, validado contra o rótulo.

    Código ausente ou nome que não contém o rótulo curado = alarme de
    remapeamento (o código pode ter trocado de instituição na fonte).
    """
    if not isinstance(cadastro, list):
        _abster(f"cadastro{data_base}_{TIPO_CADASTRO_PRUDENCIAL}.json com formato inesperado")
    alvo = str(codigo)
    for entrada in cadastro:
        if isinstance(entrada, dict) and str(entrada.get("c0")) == alvo:
            nome = str(entrada.get("c2") or "")
            if _sem_acentos(rotulo) not in _sem_acentos(nome):
                _abster(
                    f"código IF.data {codigo} não corresponde ao rótulo curado",
                    nome_no_cadastro=nome[:80],
                    rotulo_esperado=rotulo,
                )
            return nome
    _abster(
        f"código IF.data {codigo} ausente do cadastro prudencial",
        data_base=data_base,
    )


def _valores_da_instituicao(dados: object, arquivo: int, codigo: int, url: str) -> dict[int, float]:
    """{lid: valor} da instituição no `dados{dt}_{arquivo}.json`.

    Instituição sem bloco no arquivo -> dict vazio (abstenção PARCIAL, com
    log); formato fora do esperado -> alarme de schema.
    """
    if not isinstance(dados, dict) or dados.get("id") != arquivo:
        _abster(f"arquivo de dados {arquivo} com formato inesperado", url=url)
    blocos = dados.get("values")
    if not isinstance(blocos, list):
        _abster(f"arquivo de dados {arquivo} sem lista `values`", url=url)
    for bloco in blocos:
        if isinstance(bloco, dict) and bloco.get("e") == codigo:
            pontos = bloco.get("v")
            if not isinstance(pontos, list):
                _abster(f"bloco da instituição sem lista `v` no arquivo {arquivo}", url=url)
            return {
                p["i"]: float(p["v"])
                for p in pontos
                if isinstance(p, dict)
                and isinstance(p.get("i"), int)
                and isinstance(p.get("v"), int | float)
                and not isinstance(p.get("v"), bool)
            }
    logger.info("ifdata_instituicao_sem_bloco", codigo=codigo, arquivo=arquivo)
    return {}


def _colher(
    codigo: int,
    rotulo: str,
    *,
    data_base: int | None,
    transport: httpx.BaseTransport | None,
) -> _Colheita:
    """Colheita de rede: listagem -> info -> cadastro -> arquivos de dados.

    Devolve os indicadores encontrados JÁ convertidos (Basileia em %, LL
    anualizado). Indicador sem valor na fonte fica FORA do dict (abstenção
    parcial); nenhum valor -> abstenção total.
    """
    listagem = _buscar_json(IFDATA_RELATORIOS_URL, transport)
    escolhida, caminhos = _arquivos_da_base(listagem, data_base)

    info = _buscar_json(
        _arquivo_url(_caminho_requerido(caminhos, f"info{escolhida}.json", escolhida)), transport
    )
    conceitos = _resolver_conceitos(info, escolhida)

    nome_cadastro = f"cadastro{escolhida}_{TIPO_CADASTRO_PRUDENCIAL}.json"
    cadastro = _buscar_json(
        _arquivo_url(_caminho_requerido(caminhos, nome_cadastro, escolhida)), transport
    )
    instituicao = _validar_cadastro(cadastro, codigo, rotulo, escolhida)

    arquivos_necessarios = sorted({arquivo for _, arquivo in conceitos.values()})
    valores_por_arquivo: dict[int, dict[int, float]] = {}
    url_por_arquivo: dict[int, str] = {}
    for arquivo in arquivos_necessarios:
        nome = f"dados{escolhida}_{arquivo}.json"
        url = _arquivo_url(_caminho_requerido(caminhos, nome, escolhida))
        dados = _buscar_json(url, transport)
        valores_por_arquivo[arquivo] = _valores_da_instituicao(dados, arquivo, codigo, url)
        url_por_arquivo[arquivo] = url

    valores: dict[str, _ValorColhido] = {}
    for indicador, (lid, arquivo) in conceitos.items():
        bruto = valores_por_arquivo[arquivo].get(lid)
        if bruto is None:
            logger.info("ifdata_indicador_sem_valor", indicador=indicador, codigo=codigo, lid=lid)
            continue
        if indicador == "BASILEIA":
            valor = bruto * 100.0  # fração -> % (declarado na metodologia)
        elif indicador == "LL_ANUALIZADO":
            fator, _ = _regra_anualizacao(escolhida)
            valor = bruto * fator
        else:
            valor = bruto
        valores[indicador] = _ValorColhido(
            valor=valor,
            unidade=_CONCEITOS[indicador].unidade,
            metodologia=_metodologia(indicador, escolhida),
            url=url_por_arquivo[arquivo],
        )
    if not valores:
        _abster(
            f"instituição {codigo} sem nenhum indicador na data-base {escolhida}",
            instituicao=instituicao,
        )
    return _Colheita(
        data_base=escolhida,
        dt_referencia=_fim_do_mes(escolhida),
        instituicao=instituicao,
        valores=valores,
    )


# ---------------------------------------------------------------------------
# Degradação sem tabela (correção A13) — abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
def _degradar_tabela_ausente(exc: OperationalError | ProgrammingError, cd_cvm: int) -> NoReturn:
    """`banco_indicadores` inexistente -> DadoNaoEncontrado; outro erro propaga."""
    mensagem = str(getattr(exc, "orig", None) or exc).lower()
    ausente = any(
        marca in mensagem for marca in ("does not exist", "undefined table", "no such table")
    )
    if not ausente:
        raise exc
    logger.warning("ifdata_tabela_ausente", cd_cvm=cd_cvm, erro=type(exc).__name__)
    raise DadoNaoEncontrado(
        "IF.data: tabela `banco_indicadores` ausente no banco (migração 0006 "
        "não aplicada) — dado não encontrado"
    ) from exc


# ---------------------------------------------------------------------------
# Persistência / leitura
# ---------------------------------------------------------------------------
def _dt_ultima_extracao(session: Session, cd_cvm: int) -> dt.date | None:
    """Data (dt_referencia da Fonte) da última extração persistida do banco."""
    stmt = (
        select(func.max(Fonte.dt_referencia))
        .join_from(BancoIndicador, Fonte, BancoIndicador.fonte_id == Fonte.id)
        .where(BancoIndicador.cd_cvm == cd_cvm)
    )
    return session.execute(stmt).scalar()


def _indicadores_persistidos(session: Session, cd_cvm: int) -> dict[str, BancoIndicador]:
    """Indicadores da data-base mais recente persistida, chaveados pelo nome."""
    mais_recente = session.execute(
        select(func.max(BancoIndicador.dt_referencia)).where(
            BancoIndicador.cd_cvm == cd_cvm, BancoIndicador.base == BASE_PRUDENCIAL
        )
    ).scalar()
    if mais_recente is None:
        return {}
    linhas = (
        session.execute(
            select(BancoIndicador).where(
                BancoIndicador.cd_cvm == cd_cvm,
                BancoIndicador.base == BASE_PRUDENCIAL,
                BancoIndicador.dt_referencia == mais_recente,
            )
        )
        .scalars()
        .all()
    )
    return {linha.indicador: linha for linha in linhas}


def _upsert(
    session: Session,
    cd_cvm: int,
    indicador: str,
    dt_referencia: dt.date,
    colhido: _ValorColhido,
    fonte_id: uuid.UUID,
) -> BancoIndicador:
    """Idempotente por (cd_cvm, indicador, dt_referencia, base) — UNIQUE da 0006."""
    existente = session.execute(
        select(BancoIndicador).where(
            BancoIndicador.cd_cvm == cd_cvm,
            BancoIndicador.indicador == indicador,
            BancoIndicador.dt_referencia == dt_referencia,
            BancoIndicador.base == BASE_PRUDENCIAL,
        )
    ).scalar_one_or_none()
    if existente is None:
        linha = BancoIndicador(
            cd_cvm=cd_cvm,
            indicador=indicador,
            valor=colhido.valor,
            unidade=colhido.unidade,
            base=BASE_PRUDENCIAL,
            dt_referencia=dt_referencia,
            metodologia=colhido.metodologia,
            fonte_id=fonte_id,
        )
        session.add(linha)
        return linha
    existente.valor = colhido.valor
    existente.unidade = colhido.unidade
    existente.metodologia = colhido.metodologia
    existente.fonte_id = fonte_id
    return existente


def _descricao_fonte(data_base: int, extraido_em: dt.date) -> str:
    return (
        f"BCB IF.data, data-base {data_base} — indicadores prudenciais de bancos "
        f"(extraído em {extraido_em.isoformat()})"
    )


def _persistir(
    session: Session, cd_cvm: int, colheita: _Colheita, extraido_em: dt.date
) -> dict[str, BancoIndicador]:
    """Grava os indicadores num SAVEPOINT (degradação A13 preserva a transação)."""
    try:
        with session.begin_nested():
            fontes: dict[str, uuid.UUID] = {}
            resultado: dict[str, BancoIndicador] = {}
            for indicador, colhido in colheita.valores.items():
                fonte_id = fontes.get(colhido.url)
                if fonte_id is None:
                    fonte_id = get_or_create_fonte(
                        session,
                        url=colhido.url,
                        descricao=_descricao_fonte(colheita.data_base, extraido_em),
                        dt_referencia=extraido_em,
                    )
                    fontes[colhido.url] = fonte_id
                resultado[indicador] = _upsert(
                    session, cd_cvm, indicador, colheita.dt_referencia, colhido, fonte_id
                )
            session.flush()
    except (OperationalError, ProgrammingError) as exc:
        _degradar_tabela_ausente(exc, cd_cvm)
    logger.info(
        "ifdata_indicadores_persistidos",
        cd_cvm=cd_cvm,
        instituicao=colheita.instituicao,
        data_base=colheita.data_base,
        indicadores=sorted(resultado),
    )
    return resultado


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def ensure_indicadores_banco(
    session: Session,
    cd_cvm: int,
    *,
    data_base: int | None = None,
    hoje: dt.date | None = None,
    staleness_dias: int = STALENESS_CONSULTA_DIAS,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, BancoIndicador]:
    """Indicadores prudenciais do banco (IF.data BCB), persistidos com Fonte.

    Devolve {indicador: BancoIndicador} com as chaves de `INDICADORES`
    (BASILEIA em %, PR/RWA/CARTEIRA_CREDITO/ATIVOS_PROBLEMATICOS em R$
    correntes, LL_ANUALIZADO pela regra declarada) — indicador sem valor na
    fonte fica fora do dict (abstenção parcial). `cd_cvm` fora do MAPA CURADO
    -> `DadoNaoEncontrado` (lacuna honesta v1). Consulta a rede só quando a
    última extração persistida tem mais de `staleness_dias`; fonte
    indisponível com dado persistido -> serve o persistido (defasagem honesta
    pelo `dt_referencia`). `data_base` explícita (AAAAMM) força a colheita da
    data-base pedida. Tabela ausente (correção A13) -> abstenção rotulada,
    nunca 500. `hoje` e `transport` injetáveis p/ teste.
    """
    entrada = MAPA_CVM_IFDATA.get(cd_cvm)
    if entrada is None:
        raise DadoNaoEncontrado(
            f"IF.data: cd_cvm {cd_cvm} fora do mapa curado de bancos "
            "(lacuna honesta v1) — dado não encontrado"
        )
    codigo, rotulo = entrada
    hoje = hoje or dt.date.today()

    try:
        ultima_extracao = _dt_ultima_extracao(session, cd_cvm)
    except (OperationalError, ProgrammingError) as exc:
        _degradar_tabela_ausente(exc, cd_cvm)
    if (
        data_base is None
        and ultima_extracao is not None
        and (hoje - ultima_extracao).days <= staleness_dias
    ):
        persistidos = _indicadores_persistidos(session, cd_cvm)
        if persistidos:
            logger.info("ifdata_cache_fresco", cd_cvm=cd_cvm, ultima_extracao=str(ultima_extracao))
            return persistidos

    try:
        colheita = _colher(codigo, rotulo, data_base=data_base, transport=transport)
    except DadoNaoEncontrado:
        if data_base is None:
            persistidos = _indicadores_persistidos(session, cd_cvm)
            if persistidos:
                logger.warning(
                    "ifdata_fonte_indisponivel_servindo_persistido",
                    cd_cvm=cd_cvm,
                    dt_referencia=str(next(iter(persistidos.values())).dt_referencia),
                )
                return persistidos
        raise
    return _persistir(session, cd_cvm, colheita, hoje)
