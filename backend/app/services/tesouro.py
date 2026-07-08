"""Conector de renda fixa — Tesouro Direto (STN/Tesouro Transparente).

CSV oficial de preços e taxas diários por título (latin-1, ';', decimal vírgula,
datas DD/MM/AAAA). A STN autoriza uso comercial com citação — toda `Fonte` gravada
carrega 'STN' na descrição.

Regras anti-alucinação (veredito do conselho, etapa 8 + deltas 5/6 da reconciliação):
- O CSV NÃO é cronológico: a leitura "atual" usa max(Data Base) por (tipo,
  vencimento), NUNCA "última linha".
- Resolução TD-{FAMILIA}-{ANO} -> título por DISTINCT de 'Data Vencimento'
  (nunca contagem de linhas); 0 vencimentos -> DadoNaoEncontrado; 2+ vencimentos
  distintos no mesmo ano -> abstém (ambíguo).
- Staleness: Data Base mais recente > 30 dias corridos de `hoje` -> None
  (título fora de oferta; ex.: 'Tesouro IPCA+ 15/05/2035' teve série antiga
  encerrada em 2016 — número velho nunca sai como atual).
- Ingestão SÓ do título pedido, com janela diária limitada (últimos 24 meses)
  + amostra mensal (primeira Data Base de cada mês) até 5 anos, para o
  co-movimento — o histórico completo desde 2002 não entra cru.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import time
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import TituloPublico
from app.services import http_client
from app.services.dados import DadoNaoEncontrado, _parse_data, _parse_valor
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

URL_CSV = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

# Teto de download: o CSV real tem ~14 MB (173 mil linhas em 2026-07); 50 MB dá
# folga larga e barra resposta ilimitada (anti-DoS de memória).
_MAX_CSV_BYTES = 50 * 1024 * 1024

# Mapa completo sigla -> 'Tipo Titulo' oficial da STN (delta 5 da reconciliação,
# testado contra o CSV real). Comparação por IGUALDADE EXATA: 'Tesouro IPCA+'
# nunca casa 'Tesouro IPCA+ com Juros Semestrais'.
TIPO_POR_FAMILIA: dict[str, str] = {
    "PRE": "Tesouro Prefixado",
    "PREJ": "Tesouro Prefixado com Juros Semestrais",
    "SELIC": "Tesouro Selic",
    "IPCA": "Tesouro IPCA+",
    "IPCAJ": "Tesouro IPCA+ com Juros Semestrais",
    "IGPMJ": "Tesouro IGPM+ com Juros Semestrais",
    "RENDA": "Tesouro Renda+ Aposentadoria Extra",
    "EDUCA": "Tesouro Educa+",
}

JANELA_DIARIA_MESES = 24  # janela diária p/ marcação a mercado
HISTORICO_MESES = 60  # amostra mensal p/ co-movimento (5 anos)
STALENESS_DIAS = 30  # Data Base mais velha que isto -> abstém (fora de oferta)


def _tipo_da_familia(familia: str) -> str:
    tipo = TIPO_POR_FAMILIA.get((familia or "").strip().upper())
    if tipo is None:
        raise DadoNaoEncontrado(
            f"família de título desconhecida: {familia!r} — dado não encontrado"
        )
    return tipo


def parse_csv_tesouro(conteudo: bytes, tipos: set[str] | None = None) -> list[dict]:
    """CSV da STN -> [{tipo, data_vencimento, data_base, taxas, PUs}].

    Header real: 'Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;
    Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha'.
    Decimal vírgula -> float; DD/MM/AAAA -> date. Linha sem tipo/datas válidas é
    descartada (nunca inventa). `tipos` restringe a leitura (economia de memória:
    o CSV completo tem >170 mil linhas).
    """
    texto = io.TextIOWrapper(io.BytesIO(conteudo), encoding="latin-1", newline="")
    leitor = csv.DictReader(texto, delimiter=";")
    linhas: list[dict] = []
    for linha in leitor:
        tipo = (linha.get("Tipo Titulo") or "").strip()
        if not tipo or (tipos is not None and tipo not in tipos):
            continue
        vencimento = _parse_data(linha.get("Data Vencimento", ""))
        data_base = _parse_data(linha.get("Data Base", ""))
        if vencimento is None or data_base is None:
            continue
        linhas.append(
            {
                "tipo": tipo,
                "data_vencimento": vencimento,
                "data_base": data_base,
                "taxa_compra": _parse_valor(linha.get("Taxa Compra Manha", "")),
                "taxa_venda": _parse_valor(linha.get("Taxa Venda Manha", "")),
                "pu_compra": _parse_valor(linha.get("PU Compra Manha", "")),
                "pu_venda": _parse_valor(linha.get("PU Venda Manha", "")),
                "pu_base": _parse_valor(linha.get("PU Base Manha", "")),
            }
        )
    return linhas


def resolver_vencimento(linhas: list[dict], familia: str, ano: int) -> dt.date:
    """TD-{familia}-{ano} -> Data Vencimento, por DISTINCT (NUNCA contar linhas).

    0 vencimentos -> DadoNaoEncontrado; 2+ vencimentos DISTINTOS no mesmo ano ->
    abstém (ambíguo — historicamente NTN-B teve 15/05 e 15/08 no mesmo ano).
    N data_bases do MESMO vencimento não são ambiguidade.
    """
    tipo = _tipo_da_familia(familia)
    vencimentos = {
        linha["data_vencimento"]
        for linha in linhas
        if linha["tipo"] == tipo and linha["data_vencimento"].year == ano
    }
    if not vencimentos:
        raise DadoNaoEncontrado(
            f"nenhum título {tipo!r} com vencimento em {ano} — dado não encontrado"
        )
    if len(vencimentos) > 1:
        datas = ", ".join(str(v) for v in sorted(vencimentos))
        raise DadoNaoEncontrado(
            f"ambíguo: {len(vencimentos)} vencimentos distintos de {tipo!r} em {ano} "
            f"({datas}) — abstendo (dado não encontrado)"
        )
    return next(iter(vencimentos))


def _recuar_meses(data: dt.date, meses: int) -> dt.date:
    """Data N meses atrás (dia clampado a 28 — corte de janela, não aritmética exata)."""
    total = data.year * 12 + (data.month - 1) - meses
    ano, mes = divmod(total, 12)
    return dt.date(ano, mes + 1, min(data.day, 28))


def selecionar_janela(
    linhas: list[dict],
    hoje: dt.date,
    *,
    janela_diaria_meses: int = JANELA_DIARIA_MESES,
    historico_meses: int = HISTORICO_MESES,
) -> list[dict]:
    """Janela de persistência de UM título: diária recente + amostra mensal antiga.

    - Data Base nos últimos `janela_diaria_meses`: TODAS as linhas (marcação).
    - Entre `historico_meses` e a janela diária: só a PRIMEIRA Data Base de cada
      mês (co-movimento mensalizado — dado real, não média inventada).
    - Mais velho que `historico_meses`: descartado (não polui a base).
    """
    corte_diario = _recuar_meses(hoje, janela_diaria_meses)
    corte_historico = _recuar_meses(hoje, historico_meses)
    por_data: dict[dt.date, dict] = {}
    primeira_do_mes: dict[tuple[int, int], dict] = {}
    for linha in linhas:
        base = linha["data_base"]
        if base >= corte_diario:
            por_data[base] = linha
        elif base >= corte_historico:
            chave = (base.year, base.month)
            atual = primeira_do_mes.get(chave)
            if atual is None or base < atual["data_base"]:
                primeira_do_mes[chave] = linha
    for linha in primeira_do_mes.values():
        por_data.setdefault(linha["data_base"], linha)
    return [por_data[k] for k in sorted(por_data)]


def _upsert_titulo(session: Session, linha: dict, fonte_id: uuid.UUID) -> TituloPublico:
    """Idempotente por (tipo, data_vencimento, data_base)."""
    existente = session.execute(
        select(TituloPublico).where(
            TituloPublico.tipo == linha["tipo"],
            TituloPublico.data_vencimento == linha["data_vencimento"],
            TituloPublico.data_base == linha["data_base"],
        )
    ).scalar_one_or_none()
    if existente is None:
        titulo = TituloPublico(
            tipo=linha["tipo"],
            data_vencimento=linha["data_vencimento"],
            data_base=linha["data_base"],
            taxa_compra=linha["taxa_compra"],
            taxa_venda=linha["taxa_venda"],
            pu_compra=linha["pu_compra"],
            pu_venda=linha["pu_venda"],
            pu_base=linha["pu_base"],
            fonte_id=fonte_id,
        )
        session.add(titulo)
        return titulo
    existente.taxa_compra = linha["taxa_compra"]
    existente.taxa_venda = linha["taxa_venda"]
    existente.pu_compra = linha["pu_compra"]
    existente.pu_venda = linha["pu_venda"]
    existente.pu_base = linha["pu_base"]
    existente.fonte_id = fonte_id
    return existente


def ingest_titulo(
    session: Session,
    familia: str,
    ano: int,
    *,
    hoje: dt.date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[TituloPublico]:
    """Ingere SÓ o título resolvido de TD-{familia}-{ano}, com janela limitada.

    Cada linha persistida linka uma `Fonte` (URL do CSV + 'STN/Tesouro
    Transparente' + Data Base) — a STN autoriza uso comercial com citação.
    Não faz commit (o chamador controla a transação). Abstém (DadoNaoEncontrado)
    se o título não resolve de forma única.
    """
    hoje = hoje or dt.date.today()
    tipo = _tipo_da_familia(familia)
    t0 = time.perf_counter()
    conteudo = http_client.download_zip(
        URL_CSV, timeout=180.0, transport=transport, max_bytes=_MAX_CSV_BYTES
    )
    linhas = parse_csv_tesouro(conteudo, tipos={tipo})
    vencimento = resolver_vencimento(linhas, familia, ano)
    do_titulo = [ln for ln in linhas if ln["data_vencimento"] == vencimento]
    selecionadas = selecionar_janela(do_titulo, hoje)

    descricao = (
        f"STN/Tesouro Transparente — Tesouro Direto, preços e taxas diários: "
        f"{tipo}, vencimento {vencimento:%d/%m/%Y} "
        f"(uso comercial autorizado pela STN com citação da fonte)"
    )
    gravados: list[TituloPublico] = []
    for linha in selecionadas:
        fonte_id = get_or_create_fonte(
            session, url=URL_CSV, descricao=descricao, dt_referencia=linha["data_base"]
        )
        gravados.append(_upsert_titulo(session, linha, fonte_id))
    logger.info(
        "tesouro_persistido",
        familia=familia.upper(),
        ano=ano,
        vencimento=str(vencimento),
        linhas_titulo=len(do_titulo),
        persistidas=len(gravados),
        segundos=round(time.perf_counter() - t0, 2),
    )
    return gravados


def _linha_para_dict(titulo: TituloPublico) -> dict:
    def _f(valor: object) -> float | None:
        return None if valor is None else float(valor)  # Numeric -> Decimal no Postgres

    return {
        "tipo": titulo.tipo,
        "data_vencimento": titulo.data_vencimento,
        "data_base": titulo.data_base,
        "taxa_compra": _f(titulo.taxa_compra),
        "taxa_venda": _f(titulo.taxa_venda),
        "pu_compra": _f(titulo.pu_compra),
        "pu_venda": _f(titulo.pu_venda),
        "pu_base": _f(titulo.pu_base),
        "fonte_id": titulo.fonte_id,
    }


def escolher_atual(
    linhas: list[dict],
    familia: str,
    ano: int,
    hoje: dt.date,
    *,
    staleness_dias: int = STALENESS_DIAS,
) -> dict | None:
    """Linha "atual" = max(Data Base) do título resolvido; velha demais -> None.

    O CSV não é cronológico (delta 5): SEMPRE max(data_base), nunca "última
    linha". Data Base > `staleness_dias` corridos de `hoje` -> None (abstenção:
    título fora de oferta; a tese registra a lacuna, nunca serve número velho).
    """
    vencimento = resolver_vencimento(linhas, familia, ano)
    do_titulo = [ln for ln in linhas if ln["data_vencimento"] == vencimento]
    linha = max(do_titulo, key=lambda ln: ln["data_base"])
    idade_dias = (hoje - linha["data_base"]).days
    if idade_dias > staleness_dias:
        logger.info(
            "titulo_stale_abstido",
            familia=familia.upper(),
            ano=ano,
            data_base=str(linha["data_base"]),
            idade_dias=idade_dias,
        )
        return None
    return {**linha, "codigo": f"TD-{familia.upper().strip()}-{ano}"}


def titulo_atual(
    session: Session,
    familia: str,
    ano: int,
    hoje: dt.date | None = None,
    *,
    staleness_dias: int = STALENESS_DIAS,
) -> dict | None:
    """Leitura "atual" do título persistido (max Data Base + corte de staleness).

    Devolve dict com taxas/PUs/fonte_id/codigo, ou None se a Data Base mais
    recente for mais velha que `staleness_dias` (abstenção). Sem linha alguma
    do título -> DadoNaoEncontrado (mesma semântica da resolução).
    """
    hoje = hoje or dt.date.today()
    tipo = _tipo_da_familia(familia)
    titulos = (
        session.execute(select(TituloPublico).where(TituloPublico.tipo == tipo)).scalars().all()
    )
    linhas = [_linha_para_dict(t) for t in titulos]
    return escolher_atual(linhas, familia, ano, hoje, staleness_dias=staleness_dias)
