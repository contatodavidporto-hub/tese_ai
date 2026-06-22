"""Ingestão de dados REAIS e rastreáveis (CVM Dados Abertos + BCB SGS).

Implementa o método da skill `extrair-dados-cvm` como serviço do backend.
Princípio inegociável: **nunca inventar dado**. Toda gravação cria/linka uma
`Fonte` (URL + data); quando a conta/empresa não é encontrada, abstemos
("dado não encontrado") em vez de estimar.

Fontes oficiais (públicas, redistribuíveis com atribuição):
- CVM — DFP (anual): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/
  CSV em ZIP, encoding latin-1, separador ';', decimal ','. Licença ODbL.
- BCB — API SGS: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
  Selic = código 11 · Dólar venda = código 1.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import zipfile

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import Empresa, Fundamento, MacroSerie
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

_UA = {"User-Agent": "tese-ai/0.1 (+https://github.com/contatodavidporto-hub/tese_ai)"}

# Registro mínimo ticker -> (CD_CVM, nome, setor). Sem heurística: se o ticker
# não está aqui, abstemos. Ampliar conforme novas empresas entram no slice.
TICKER_CD_CVM: dict[str, tuple[int, str, str]] = {
    "PETR4": (9512, "Petróleo Brasileiro S.A. - Petrobras", "Petróleo, Gás e Biocombustíveis"),
    "PETR3": (9512, "Petróleo Brasileiro S.A. - Petrobras", "Petróleo, Gás e Biocombustíveis"),
    "VALE3": (4170, "Vale S.A.", "Mineração"),
    "ITUB4": (19348, "Itaú Unibanco Holding S.A.", "Bancos"),
}

# Contas-alvo (validar sempre pelo DS_CONTA). Mapeia (demonstração, CD_CONTA).
_CONTAS_DRE = {"3.01": "Receita", "3.11": "Lucro/Prejuízo do período"}
_CONTAS_BPP = {"2.03": "Patrimônio líquido"}

_ESCALAS = {"UNIDADE": 1, "MIL": 1_000, "MILHAO": 1_000_000, "MILHÃO": 1_000_000}

CVM_DFP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip"
BCB_SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"
)

# Anos a tentar para a DFP (mais recente primeiro). DFP é anual.
_ANOS_DFP = (2025, 2024, 2023)


class DadoNaoEncontrado(Exception):
    """Levantada quando não há dado real para o pedido — nunca inventamos."""


def _parse_valor(raw: str) -> float | None:
    """Converte VL_CONTA (decimal brasileiro) em float. Vazio -> None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    # Decimal ','. Se houver '.', é separador de milhar -> remover.
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _aplicar_escala(valor: float | None, escala: str) -> float | None:
    if valor is None:
        return None
    return valor * _ESCALAS.get((escala or "").strip().upper(), 1)


def _parse_data(raw: str) -> dt.date | None:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Empresa
# ---------------------------------------------------------------------------
def ensure_empresa(session: Session, ticker: str) -> Empresa:
    """Idempotente. Abstém (DadoNaoEncontrado) se o ticker não é conhecido."""
    ticker = ticker.upper().strip()
    info = TICKER_CD_CVM.get(ticker)
    if info is None:
        raise DadoNaoEncontrado(
            f"ticker {ticker} não está no registro CVM do slice (dado não encontrado)"
        )
    cd_cvm, nome, setor = info

    empresa = session.execute(select(Empresa).where(Empresa.cd_cvm == cd_cvm)).scalar_one_or_none()
    if empresa is None:
        empresa = Empresa(cd_cvm=cd_cvm, ticker=ticker, nome=nome, setor=setor)
        session.add(empresa)
        session.flush()
        logger.info("empresa_criada", ticker=ticker, cd_cvm=cd_cvm)
    elif empresa.ticker != ticker:
        empresa.ticker = ticker
    return empresa


# ---------------------------------------------------------------------------
# MACRO — BCB SGS
# ---------------------------------------------------------------------------
def bcb_sgs(codigo: int, n: int = 1) -> list[dict]:
    """Últimos N pontos de uma série do SGS. Devolve [{data, valor}]."""
    url = BCB_SGS_URL.format(codigo=codigo, n=n)
    resp = httpx.get(url, headers=_UA, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def ingest_macro(session: Session) -> list[MacroSerie]:
    """Persiste o último ponto das séries macro do BCB SGS, com rótulos sem ambiguidade.

    Importante: a série 11 é a Selic **diária** (% a.d.) — pequena por definição;
    a 432 é a **Meta Selic** anual (% a.a.), o número de manchete. Rotulamos as duas
    para que o motor de tese narre o macro corretamente (anti-alucinação).
    """
    # nome -> (código SGS, rótulo humano)
    series: dict[str, tuple[int, str]] = {
        "SELIC_DIARIA": (11, "Selic diária (% a.d.)"),
        "SELIC_META_ANUAL": (432, "Meta Selic - Copom (% a.a.)"),
        "USD_VENDA": (1, "Dólar venda (R$/US$)"),
    }
    gravados: list[MacroSerie] = []
    for nome, (codigo, rotulo) in series.items():
        try:
            pontos = bcb_sgs(codigo, n=1)
        except httpx.HTTPError as exc:
            logger.warning("bcb_falhou", serie=nome, codigo=codigo, erro=type(exc).__name__)
            continue
        if not pontos:
            continue
        ponto = pontos[-1]
        data = _parse_data(ponto.get("data", ""))
        valor = _parse_valor(str(ponto.get("valor", "")))
        if data is None or valor is None:
            continue
        url = BCB_SGS_URL.format(codigo=codigo, n=1)
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=f"Banco Central — API SGS série {codigo}: {rotulo}",
            dt_referencia=data,
        )
        existente = session.execute(
            select(MacroSerie).where(MacroSerie.codigo == nome, MacroSerie.data == data)
        ).scalar_one_or_none()
        if existente is None:
            ms = MacroSerie(codigo=nome, data=data, valor=valor, fonte_id=fonte_id)
            session.add(ms)
            gravados.append(ms)
        else:
            existente.valor = valor
            existente.fonte_id = fonte_id
            gravados.append(existente)
        logger.info("macro_persistido", serie=nome, data=str(data), valor=valor)
    return gravados


# ---------------------------------------------------------------------------
# FUNDAMENTOS — CVM DFP
# ---------------------------------------------------------------------------
def _baixar_dfp_zip(ano: int) -> bytes:
    url = CVM_DFP_URL.format(ano=ano)
    resp = httpx.get(url, headers=_UA, timeout=180.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _extrair_contas(
    conteudo_zip: bytes,
    ano: int,
    cd_cvm: int,
    membro: str,
    contas: dict[str, str],
) -> list[dict]:
    """Lê um CSV (latin-1, ';') do ZIP e extrai as contas-alvo do exercício ÚLTIMO.

    Devolve [{cd_conta, ds_conta, valor, dt_refer}]. Nunca inventa: só retorna o
    que existe na fonte.
    """
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as z:
        if membro not in z.namelist():
            return []
        achados: list[dict] = []
        with z.open(membro) as raw:
            texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            for linha in leitor:
                if linha.get("ORDEM_EXERC", "").strip().upper() not in ("ÚLTIMO", "ULTIMO"):
                    continue
                try:
                    if int(linha.get("CD_CVM", "0")) != cd_cvm:
                        continue
                except ValueError:
                    continue
                cd_conta = linha.get("CD_CONTA", "").strip()
                if cd_conta not in contas:
                    continue
                valor = _aplicar_escala(
                    _parse_valor(linha.get("VL_CONTA", "")),
                    linha.get("ESCALA_MOEDA", ""),
                )
                if valor is None:
                    continue
                dt_refer = _parse_data(linha.get("DT_FIM_EXERC", "")) or _parse_data(
                    linha.get("DT_REFER", "")
                )
                achados.append(
                    {
                        "cd_conta": cd_conta,
                        "ds_conta": linha.get("DS_CONTA", "").strip(),
                        "valor": valor,
                        "dt_refer": dt_refer,
                        "ano": ano,
                    }
                )
    return achados


def ingest_fundamentos(session: Session, empresa: Empresa) -> list[Fundamento]:
    """Baixa a DFP mais recente disponível e persiste contas-chave com fonte.

    Abstém (DadoNaoEncontrado) se nenhum exercício recente tem dados da empresa.
    """
    cd_cvm = empresa.cd_cvm
    if cd_cvm is None:
        raise DadoNaoEncontrado(f"empresa {empresa.ticker} sem CD_CVM")

    for ano in _ANOS_DFP:
        try:
            conteudo = _baixar_dfp_zip(ano)
        except httpx.HTTPError as exc:
            logger.warning("dfp_falhou", ano=ano, erro=type(exc).__name__)
            continue

        dre = _extrair_contas(
            conteudo, ano, cd_cvm, f"dfp_cia_aberta_DRE_con_{ano}.csv", _CONTAS_DRE
        )
        bpp = _extrair_contas(
            conteudo, ano, cd_cvm, f"dfp_cia_aberta_BPP_con_{ano}.csv", _CONTAS_BPP
        )
        achados = dre + bpp
        if not achados:
            logger.info("dfp_sem_dados_empresa", ano=ano, cd_cvm=cd_cvm)
            continue

        url = CVM_DFP_URL.format(ano=ano)
        gravados: list[Fundamento] = []
        for a in achados:
            fonte_id = get_or_create_fonte(
                session,
                url=url,
                descricao=(
                    f"CVM DFP {ano} (consolidado) — {empresa.nome} "
                    f"[{a['cd_conta']} {a['ds_conta']}], valores em reais"
                ),
                dt_referencia=a["dt_refer"],
            )
            conta_label = f"{a['ds_conta']} ({a['cd_conta']})"
            existente = session.execute(
                select(Fundamento).where(
                    Fundamento.empresa_id == empresa.id,
                    Fundamento.conta == conta_label,
                    Fundamento.dt_refer == a["dt_refer"],
                )
            ).scalar_one_or_none()
            if existente is None:
                f = Fundamento(
                    empresa_id=empresa.id,
                    conta=conta_label,
                    valor=a["valor"],
                    dt_refer=a["dt_refer"],
                    fonte_id=fonte_id,
                )
                session.add(f)
                gravados.append(f)
            else:
                existente.valor = a["valor"]
                existente.fonte_id = fonte_id
                gravados.append(existente)
        logger.info("fundamentos_persistidos", ano=ano, cd_cvm=cd_cvm, n=len(gravados))
        return gravados

    raise DadoNaoEncontrado(
        f"sem DFP recente para {empresa.ticker} (CD_CVM {cd_cvm}) — dado não encontrado"
    )


# ---------------------------------------------------------------------------
# Orquestração de ingestão
# ---------------------------------------------------------------------------
def ingest_ticker(session: Session, ticker: str) -> dict:
    """Ingestão ponta-a-ponta de 1 ticker: empresa + fundamentos + macro.

    Faz commit ao final. Devolve um resumo. Macro é compartilhada (não falha o
    ticker se o BCB estiver indisponível).
    """
    empresa = ensure_empresa(session, ticker)
    fundamentos = ingest_fundamentos(session, empresa)
    macro = ingest_macro(session)
    session.commit()
    resumo = {
        "ticker": empresa.ticker,
        "cd_cvm": empresa.cd_cvm,
        "fundamentos": len(fundamentos),
        "macro": len(macro),
    }
    logger.info("ingest_concluida", **resumo)
    return resumo
