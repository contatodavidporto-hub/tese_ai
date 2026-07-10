"""Conector de FIIs — informes mensais e trimestrais da CVM (Fase 2 multiativo).

Ingesta o cadastro (bloco "geral"), a série de indicadores (bloco "complemento")
e a vacância agregada (informe trimestral, por imóvel) de fundos imobiliários.
Princípio inegociável: **nunca inventar dado** — toda gravação cria/linka uma
`Fonte` (URL + data) e campo ausente vira abstenção, nunca estimativa.

Fontes oficiais (públicas, ODbL):
- CVM — Informe Mensal FII: https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/
- CVM — Informe Trimestral FII: https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/
  CSV em ZIP, encoding latin-1, separador ';'.

Decisões da reconciliação da Fase 2 (deltas 3, 4 e 7 — vencem o veredito):
- Ticker é HEURÍSTICA sobre o Código ISIN (raiz ISIN[2:6] + '11'), rotulada em
  `ticker_metodo='heuristica_isin'`; colisão de raiz entre CNPJs distintos ->
  ticker NULL para AMBOS (o fundo segue acessível por CNPJ), sem abortar o
  ingest; ISIN malformado -> ticker NULL. O mapa oficial é da B3 (licenciado).
- Valores do informe são R$ CRUS (sem ESCALA_MOEDA — diferente da DFP): nada de
  reescala. O PL do HGLG11 lê ~7,06 bi, nunca 7,06 tri (fixture prova).
- Vacância agregada = média de Percentual_Vacancia ponderada pela ÁREA (m²) dos
  imóveis (o peso financeiro `Percentual_Imovel_Total_Investido` vem VAZIO no
  dado real); imóvel sem vacância ou sem área -> aborta o agregado (abstenção).
- Staleness: `indicadores_recentes` só devolve competências a <=90 dias do
  "hoje" injetável; mais velho -> excluído (o motor rotula a defasagem).
- P/VP e DY a preço de mercado NÃO existem aqui (preço B3 é licenciado): a
  lacuna explícita é declarada pelo template no bloco do motor de tese.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import uuid
import zipfile
from collections.abc import Iterator

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import FiiCadastro, FiiIndicador
from app.services import http_client
from app.services.dados import DadoNaoEncontrado
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

CVM_FII_MENSAL_URL = (
    "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"
)
CVM_FII_TRIMESTRAL_URL = (
    "https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip"
)

# Candidatos de coluna: a Res. CVM 175 renomeou campos (Fundo -> Fundo_Classe)
# em datasets vizinhos; aceitar os dois nomes evita ingest zerado num rename.
_COLS_CNPJ = ("CNPJ_Fundo", "CNPJ_Fundo_Classe")
_COLS_NOME = ("Nome_Fundo", "Nome_Fundo_Classe")

# ISIN: 2 letras de país + 9 alfanuméricos + 1 dígito verificador.
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

_METODO_TICKER = "heuristica_isin"
_METODOLOGIA_AUTO = "auto-declarado pelo administrador; informe mensal CVM"
_METODOLOGIA_VACANCIA = (
    "média ponderada pela área (m²) dos imóveis; "
    "vacância auto-declarada por imóvel no informe trimestral CVM"
)

# (coluna do CSV "complemento", código canônico, unidade, metodologia).
# Percentuais entram como FRAÇÃO decimal, exatamente como vêm no CSV (ex.
# 0.006635 = 0,66% ao mês) — NUNCA anualizar nem converter (fato auto-declarado).
_INDICADORES_COMPLEMENTO: tuple[tuple[str, str, str, str | None], ...] = (
    ("Patrimonio_Liquido", "PL", "BRL", None),
    ("Valor_Patrimonial_Cotas", "VP_COTA", "BRL_POR_COTA", None),
    ("Cotas_Emitidas", "COTAS_EMITIDAS", "UN", None),
    ("Total_Numero_Cotistas", "COTISTAS", "UN", None),
    ("Percentual_Dividend_Yield_Mes", "DY_MES_INFORME", "PCT", _METODOLOGIA_AUTO),
    ("Percentual_Rentabilidade_Efetiva_Mes", "RENT_EFETIVA_MES", "PCT", _METODOLOGIA_AUTO),
)

STALENESS_DIAS_DEFAULT = 90


# ---------------------------------------------------------------------------
# Helpers puros (cópias locais de parsing: dados.py é bloco paralelo em edição
# concorrente — não importamos helpers privados de lá, só o contrato público
# DadoNaoEncontrado).
# ---------------------------------------------------------------------------
def _parse_num(raw: str) -> float | None:
    """Número do informe FII. O dataset usa decimal PONTO (ex. '7063626090.23');
    vírgula decimal brasileira é aceita defensivamente. Vazio/lixo -> None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_data(raw: str) -> dt.date | None:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _cnpj_digitos(cnpj: str | None) -> str:
    """Só os dígitos do CNPJ (comparação estável entre formatações)."""
    return "".join(c for c in (cnpj or "") if c.isdigit())


def _campo(linha: dict, *nomes: str) -> str:
    """Primeiro campo presente e não-vazio entre os nomes candidatos."""
    for nome in nomes:
        valor = (linha.get(nome) or "").strip()
        if valor:
            return valor
    return ""


def _ticker_do_isin(isin: str | None) -> str | None:
    """HEURÍSTICA rotulada (nunca fato oficial): raiz ISIN[2:6] + '11'.

    Ex.: BRHGLGCTF004 -> HGLG11. ISIN malformado -> None (ticker NULL; o fundo
    resolve só por CNPJ). Sufixos 12/13 e o mapa oficial são da B3 (licenciado).
    """
    isin = (isin or "").strip().upper()
    if not _ISIN_RE.fullmatch(isin):
        return None
    return isin[2:6] + "11"


def _anos_informe(hoje: dt.date | None = None) -> tuple[int, int]:
    """Ano corrente com fallback ano-1 (padrão da cascata `_ANOS_DFP` de dados.py)."""
    ano = (hoje or dt.date.today()).year
    return (ano, ano - 1)


def _baixar_zip(url: str, transport: httpx.BaseTransport | None = None) -> bytes | None:
    """Download com teto de bytes (http_client). Falha HTTP -> None (cascata segue)."""
    try:
        return http_client.download_zip(url, timeout=180.0, transport=transport)
    except httpx.HTTPError as exc:
        logger.warning("fii_zip_falhou", url=url, erro=type(exc).__name__)
        return None


def _ler_membro_csv(conteudo_zip: bytes, membro: str) -> Iterator[dict]:
    """Linhas de um CSV (latin-1, ';') dentro do ZIP; membro ausente -> vazio."""
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as z:
        if membro not in z.namelist():
            logger.info("fii_membro_ausente", membro=membro)
            return
        with z.open(membro) as raw:
            texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            yield from csv.DictReader(texto, delimiter=";")


# ---------------------------------------------------------------------------
# Cadastro (bloco "geral" do informe mensal)
# ---------------------------------------------------------------------------
def _parse_geral(conteudo_zip: bytes, ano: int) -> dict[str, dict]:
    """Cadastro por CNPJ: fica a linha de Data_Referencia mais recente (maior
    Versao desempata — reentrega do informe vence). Linha sem CNPJ ou sem nome
    é descartada (abstenção; `nome` é NOT NULL no schema)."""
    membro = f"inf_mensal_fii_geral_{ano}.csv"
    por_cnpj: dict[str, tuple[tuple, dict]] = {}
    for linha in _ler_membro_csv(conteudo_zip, membro):
        cnpj = _campo(linha, *_COLS_CNPJ)
        nome = _campo(linha, *_COLS_NOME)
        if not cnpj or not nome:
            continue
        data_ref = _parse_data(_campo(linha, "Data_Referencia"))
        versao = _parse_num(_campo(linha, "Versao")) or 1.0
        ordem = (data_ref or dt.date.min, versao)
        atual = por_cnpj.get(cnpj)
        if atual is not None and ordem < atual[0]:
            continue
        por_cnpj[cnpj] = (
            ordem,
            {
                "cnpj": cnpj,
                "nome": nome,
                "isin": _campo(linha, "Codigo_ISIN") or None,
                "segmento": _campo(linha, "Segmento_Atuacao") or None,
                "mandato": _campo(linha, "Mandato") or None,
                "tipo_gestao": _campo(linha, "Tipo_Gestao") or None,
                "mercado_bolsa": _campo(linha, "Mercado_Negociacao_Bolsa") or None,
                "dt_referencia": data_ref,
            },
        )
    return {cnpj: cad for cnpj, (_ordem, cad) in por_cnpj.items()}


def _mapear_tickers(cadastros: dict[str, dict]) -> dict[str, str | None]:
    """cnpj -> ticker heurístico do lote. Colisão de raiz entre CNPJs distintos
    -> None para TODOS (nunca chutamos o dono da raiz); malformado -> ausente."""
    candidatos: dict[str, list[str]] = {}
    for cnpj, cad in cadastros.items():
        ticker = _ticker_do_isin(cad["isin"])
        if ticker is not None:
            candidatos.setdefault(ticker, []).append(cnpj)
    mapa: dict[str, str | None] = {}
    for ticker, cnpjs in candidatos.items():
        if len(cnpjs) == 1:
            mapa[cnpjs[0]] = ticker
        else:
            logger.warning("fii_ticker_colisao_isin", ticker=ticker, cnpjs=sorted(cnpjs))
            for cnpj in cnpjs:
                mapa[cnpj] = None
    return mapa


def _gravar_cadastro(session: Session, cad: dict, ticker: str | None, fonte_id: uuid.UUID):
    """Cria/atualiza o FiiCadastro do CNPJ com os campos do informe (sem flush)."""
    metodo = _METODO_TICKER if ticker is not None else None
    campos = {
        "nome": cad["nome"],
        "isin": cad["isin"],
        "segmento": cad["segmento"],
        "mandato": cad["mandato"],
        "tipo_gestao": cad["tipo_gestao"],
        "mercado_bolsa": cad["mercado_bolsa"],
        "dt_referencia": cad["dt_referencia"],
        "fonte_id": fonte_id,
    }
    existente = session.execute(
        select(FiiCadastro).where(FiiCadastro.cnpj == cad["cnpj"])
    ).scalar_one_or_none()
    if existente is None:
        fii = FiiCadastro(cnpj=cad["cnpj"], ticker=ticker, ticker_metodo=metodo, **campos)
        session.add(fii)
        return fii
    for chave, valor in campos.items():
        setattr(existente, chave, valor)
    existente.ticker = ticker
    existente.ticker_metodo = metodo
    return existente


def _upsert_cadastro(
    session: Session, cad: dict, ticker: str | None, url: str, ano: int
) -> FiiCadastro:
    """Upsert por CNPJ. Nunca regride para competência mais velha (cascata do
    ano-1 não sobrescreve dado mais novo). Colisão de ticker com fundo JÁ
    persistido de outro CNPJ -> ticker NULL para AMBOS; o UNIQUE(ticker) é
    ainda capturado no flush (savepoint) como rede de segurança — o ingest do
    lote nunca aborta por causa da heurística."""
    existente = session.execute(
        select(FiiCadastro).where(FiiCadastro.cnpj == cad["cnpj"])
    ).scalar_one_or_none()
    if (
        existente is not None
        and existente.dt_referencia is not None
        and cad["dt_referencia"] is not None
        and cad["dt_referencia"] < existente.dt_referencia
    ):
        return existente

    if ticker is not None:
        conflito = session.execute(
            select(FiiCadastro).where(FiiCadastro.ticker == ticker, FiiCadastro.cnpj != cad["cnpj"])
        ).scalar_one_or_none()
        if conflito is not None:
            logger.warning(
                "fii_ticker_colisao_persistida",
                ticker=ticker,
                cnpj_novo=cad["cnpj"],
                cnpj_existente=conflito.cnpj,
            )
            conflito.ticker = None
            conflito.ticker_metodo = None
            ticker = None

    fonte_id = get_or_create_fonte(
        session,
        url=url,
        descricao=(
            f"CVM — Informe Mensal FII {ano} (bloco geral): "
            "dados cadastrais auto-declarados pelo administrador"
        ),
        dt_referencia=cad["dt_referencia"],
    )
    try:
        with session.begin_nested():
            fii = _gravar_cadastro(session, cad, ticker, fonte_id)
            session.flush()
        return fii
    except IntegrityError:
        logger.warning("fii_ticker_unique_capturado", cnpj=cad["cnpj"], ticker=ticker)
        with session.begin_nested():
            fii = _gravar_cadastro(session, cad, None, fonte_id)
            session.flush()
        return fii


def _ingest_lote_geral(session: Session, conteudo_zip: bytes, url: str, ano: int) -> int:
    """Upserta o cadastro de TODOS os fundos do bloco "geral" de um zip anual.

    Miolo compartilhado entre `ensure_fii` (ticker-alvo) e `bootstrap_fiis`
    (universo, achado A2). A colisão de raiz ISIN só é detectável olhando o
    lote inteiro. Devolve o nº de fundos do lote (0 = membro geral vazio).
    """
    cadastros = _parse_geral(conteudo_zip, ano)
    if not cadastros:
        logger.info("fii_geral_vazio", ano=ano)
        return 0
    tickers = _mapear_tickers(cadastros)
    for cnpj, cad in cadastros.items():
        _upsert_cadastro(session, cad, tickers.get(cnpj), url, ano)
    return len(cadastros)


def bootstrap_fiis(
    session: Session,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Popula `fii_cadastro` com o UNIVERSO do informe mensal CVM (achado A2).

    Passo de bootstrap para banco fresco: sem ticker-alvo, upserta o lote
    inteiro do bloco "geral" (mesma cascata ano corrente -> ano-1 do
    `ensure_fii`; o primeiro ano com dados vence — o ano-1 não regride
    competência mais nova, regra do `_upsert_cadastro`). Idempotente.
    Nenhum zip/lote disponível -> DadoNaoEncontrado (abstenção, nunca seed
    inventado). `hoje` e `transport` injetáveis para teste offline.
    """
    for ano in _anos_informe(hoje):
        url = CVM_FII_MENSAL_URL.format(ano=ano)
        conteudo = _baixar_zip(url, transport)
        if conteudo is None:
            continue
        n = _ingest_lote_geral(session, conteudo, url, ano)
        if n:
            logger.info("fii_bootstrap_universo", ano=ano, fundos=n)
            return n
    raise DadoNaoEncontrado(
        "informe mensal FII indisponível em todos os anos da cascata — dado não encontrado"
    )


def ensure_fii(
    session: Session,
    ticker: str,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FiiCadastro:
    """Resolve `ticker` -> FiiCadastro via informe mensal CVM. Idempotente.

    Baixa inf_mensal_fii_{ano}.zip (ano corrente, fallback ano-1), upserta o
    cadastro de TODOS os fundos do bloco "geral" (`_ingest_lote_geral`) e
    devolve o fundo do ticker pedido. Abstém (DadoNaoEncontrado) quando o
    ticker não resolve — inclusive quando a colisão de raiz zera a heurística
    (o fundo segue acessível por CNPJ). `hoje` e `transport` são injetáveis
    para teste offline.
    """
    ticker = ticker.upper().strip()
    for ano in _anos_informe(hoje):
        url = CVM_FII_MENSAL_URL.format(ano=ano)
        conteudo = _baixar_zip(url, transport)
        if conteudo is None:
            continue
        if _ingest_lote_geral(session, conteudo, url, ano) == 0:
            continue
        fii = session.execute(
            select(FiiCadastro).where(FiiCadastro.ticker == ticker)
        ).scalar_one_or_none()
        if fii is not None:
            logger.info("fii_resolvido", ticker=ticker, cnpj=fii.cnpj, ano=ano)
            return fii
        logger.info("fii_ticker_nao_resolvido_no_ano", ticker=ticker, ano=ano)
    raise DadoNaoEncontrado(
        f"FII {ticker}: sem cadastro resolvível no informe mensal CVM — dado não encontrado"
    )


# ---------------------------------------------------------------------------
# Indicadores (bloco "complemento" do informe mensal) — R$ CRUS, sem escala
# ---------------------------------------------------------------------------
def _linhas_complemento(conteudo_zip: bytes, ano: int, cnpj_digitos: str) -> dict[dt.date, dict]:
    """Linhas do fundo por Data_Referencia (maior Versao vence — reentrega)."""
    membro = f"inf_mensal_fii_complemento_{ano}.csv"
    por_dt: dict[dt.date, tuple[float, dict]] = {}
    for linha in _ler_membro_csv(conteudo_zip, membro):
        if _cnpj_digitos(_campo(linha, *_COLS_CNPJ)) != cnpj_digitos:
            continue
        data_ref = _parse_data(_campo(linha, "Data_Referencia"))
        if data_ref is None:
            continue
        versao = _parse_num(_campo(linha, "Versao")) or 1.0
        atual = por_dt.get(data_ref)
        if atual is None or versao >= atual[0]:
            por_dt[data_ref] = (versao, linha)
    return {data_ref: linha for data_ref, (_versao, linha) in por_dt.items()}


def _upsert_indicador(
    session: Session,
    fii: FiiCadastro,
    indicador: str,
    valor: float,
    unidade: str,
    metodologia: str | None,
    dt_referencia: dt.date,
    fonte_id: uuid.UUID,
) -> FiiIndicador:
    """Idempotente por (fii, indicador, dt_referencia) — espelha o UNIQUE da 0005."""
    existente = session.execute(
        select(FiiIndicador).where(
            FiiIndicador.fii_id == fii.id,
            FiiIndicador.indicador == indicador,
            FiiIndicador.dt_referencia == dt_referencia,
        )
    ).scalar_one_or_none()
    if existente is None:
        ind = FiiIndicador(
            fii_id=fii.id,
            indicador=indicador,
            valor=valor,
            unidade=unidade,
            metodologia=metodologia,
            dt_referencia=dt_referencia,
            fonte_id=fonte_id,
        )
        session.add(ind)
        return ind
    existente.valor = valor
    existente.unidade = unidade
    existente.metodologia = metodologia
    existente.fonte_id = fonte_id
    return existente


def ingest_indicadores(
    session: Session,
    fii: FiiCadastro,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[FiiIndicador]:
    """Grava a série de indicadores do fundo por competência (histórico).

    TODAS as Data_Referencia disponíveis nos zips do ano corrente E do anterior
    entram (série para o co-movimento futuro, ex. DY x Selic). Valores em R$
    CRUS — o informe NÃO carrega ESCALA_MOEDA; reescalar aqui produziria número
    errado COM fonte. Campo vazio/não-numérico -> não grava (abstenção).
    Idempotente por (fii, indicador, dt_referencia). Nenhum zip disponível ->
    DadoNaoEncontrado (abstenção dura, nunca série inventada).
    """
    cnpj_alvo = _cnpj_digitos(fii.cnpj)
    gravados: list[FiiIndicador] = []
    algum_zip = False
    for ano in _anos_informe(hoje):
        url = CVM_FII_MENSAL_URL.format(ano=ano)
        conteudo = _baixar_zip(url, transport)
        if conteudo is None:
            continue
        algum_zip = True
        for data_ref, linha in sorted(_linhas_complemento(conteudo, ano, cnpj_alvo).items()):
            fonte_id: uuid.UUID | None = None
            for coluna, indicador, unidade, metodologia in _INDICADORES_COMPLEMENTO:
                valor = _parse_num(_campo(linha, coluna))
                if valor is None:
                    # Abstenção: campo vazio/não-numérico não vira 0 nem estimativa.
                    logger.info(
                        "fii_indicador_abstido",
                        cnpj=fii.cnpj,
                        indicador=indicador,
                        dt=str(data_ref),
                    )
                    continue
                if fonte_id is None:
                    fonte_id = get_or_create_fonte(
                        session,
                        url=url,
                        descricao=(
                            f"CVM — Informe Mensal FII {ano} (bloco complemento) — "
                            f"{fii.nome}, valores em R$ correntes (sem escala)"
                        ),
                        dt_referencia=data_ref,
                    )
                gravados.append(
                    _upsert_indicador(
                        session, fii, indicador, valor, unidade, metodologia, data_ref, fonte_id
                    )
                )
    if not algum_zip:
        raise DadoNaoEncontrado(
            f"informe mensal FII indisponível para {fii.cnpj} — dado não encontrado"
        )
    logger.info("fii_indicadores_persistidos", cnpj=fii.cnpj, n=len(gravados))
    return gravados


# ---------------------------------------------------------------------------
# Vacância (informe trimestral, por imóvel) — média ponderada pela ÁREA
# ---------------------------------------------------------------------------
def ingest_vacancia(
    session: Session,
    fii: FiiCadastro,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FiiIndicador | None:
    """Vacância agregada do ÚLTIMO trimestre disponível do fundo.

    Média de `Percentual_Vacancia` ponderada por `Area` (m²) dos imóveis do
    trimestre — vacância FÍSICA (o peso financeiro vem vazio no dado real).
    Abstenção ESTRITA (devolve None, nada é gravado) quando qualquer imóvel do
    trimestre vem sem Percentual_Vacancia, ou com Area vazia/zero em imóvel com
    vacância informada: agregado parcial seria número enganoso COM fonte.
    Idempotente por (fii, 'VACANCIA_AGREGADA', dt_referencia).

    UNIDADE — fonte da verdade (achado A3 do red-team, só documentação):
    `Percentual_Vacancia` do inf_trimestral vem como FRAÇÃO decimal, não como
    percentual. Evidência empírica: valor cru '0.181971821162028' para o
    imóvel Master Labs (HGLG11, Data_Referencia 2025-12-31), verificado por
    download real do zip da CVM em 2026-07-08 (≈18,2% de vacância — coerente
    com o fato público). O agregado é gravado como fração, unidade 'PCT'
    (fração decimal, padrão dos indicadores do informe), sem multiplicar por
    100 — o formatador do motor é quem converte para exibição.
    """
    cnpj_alvo = _cnpj_digitos(fii.cnpj)
    for ano in _anos_informe(hoje):
        url = CVM_FII_TRIMESTRAL_URL.format(ano=ano)
        conteudo = _baixar_zip(url, transport)
        if conteudo is None:
            continue
        membro = f"inf_trimestral_fii_imovel_{ano}.csv"
        linhas_fundo = [
            linha
            for linha in _ler_membro_csv(conteudo, membro)
            if _cnpj_digitos(_campo(linha, *_COLS_CNPJ)) == cnpj_alvo
        ]
        datas = [
            data
            for linha in linhas_fundo
            if (data := _parse_data(_campo(linha, "Data_Referencia"))) is not None
        ]
        if not datas:
            continue  # sem trimestre deste ano -> tenta o anterior
        ultima = max(datas)
        imoveis = [
            linha
            for linha in linhas_fundo
            if _parse_data(_campo(linha, "Data_Referencia")) == ultima
        ]
        versao_max = max((_parse_num(_campo(li, "Versao")) or 1.0) for li in imoveis)
        imoveis = [li for li in imoveis if (_parse_num(_campo(li, "Versao")) or 1.0) == versao_max]

        soma_ponderada = 0.0
        soma_area = 0.0
        for imovel in imoveis:
            vacancia = _parse_num(_campo(imovel, "Percentual_Vacancia"))
            if vacancia is None:
                logger.info(
                    "fii_vacancia_abstida_imovel_sem_percentual", cnpj=fii.cnpj, dt=str(ultima)
                )
                return None
            area = _parse_num(_campo(imovel, "Area"))
            if area is None or area <= 0:
                logger.info("fii_vacancia_abstida_area_invalida", cnpj=fii.cnpj, dt=str(ultima))
                return None
            soma_ponderada += vacancia * area
            soma_area += area
        if soma_area <= 0:
            return None
        agregada = soma_ponderada / soma_area

        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=(
                f"CVM — Informe Trimestral FII {ano} (imóveis) — {fii.nome}: "
                "vacância auto-declarada por imóvel"
            ),
            dt_referencia=ultima,
        )
        ind = _upsert_indicador(
            session,
            fii,
            "VACANCIA_AGREGADA",
            agregada,
            "PCT",
            _METODOLOGIA_VACANCIA,
            ultima,
            fonte_id,
        )
        logger.info("fii_vacancia_persistida", cnpj=fii.cnpj, dt=str(ultima), valor=agregada)
        return ind
    logger.info("fii_vacancia_sem_informe", cnpj=fii.cnpj)
    return None


# ---------------------------------------------------------------------------
# Seleção para a tese — staleness de 90 dias (delta 4 da reconciliação)
# ---------------------------------------------------------------------------
def indicadores_recentes(
    session: Session,
    fii: FiiCadastro,
    *,
    hoje: dt.date | None = None,
    staleness_dias: int = STALENESS_DIAS_DEFAULT,
) -> dict[str, FiiIndicador]:
    """Último valor POR indicador com Data_Referencia a <=`staleness_dias` do
    `hoje` (injetável para teste; default = date.today()).

    Competência mais velha que o corte -> EXCLUÍDA (abstenção; o motor de tese
    rotula a defasagem como lacuna). P/VP e DY a preço de mercado NÃO existem
    neste conector (preço B3 é licenciado) — quem declara essa lacuna é o
    template da classe FII no bloco do motor.
    """
    hoje = hoje or dt.date.today()
    corte = hoje - dt.timedelta(days=staleness_dias)
    linhas = (
        session.execute(
            select(FiiIndicador)
            .where(FiiIndicador.fii_id == fii.id, FiiIndicador.dt_referencia >= corte)
            .order_by(FiiIndicador.dt_referencia)
        )
        .scalars()
        .all()
    )
    recentes: dict[str, FiiIndicador] = {}
    for ind in linhas:
        recentes[ind.indicador] = ind  # ordem ascendente: o mais novo vence
    return recentes
