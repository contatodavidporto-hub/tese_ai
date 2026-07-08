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
import uuid
import zipfile

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import Empresa, Fundamento, MacroSerie
from app.services import derivadas, http_client, planos_contas
from app.services.fontes import get_or_create_fonte
from app.services.planos_contas import _normalizar_ds  # canônico lá; reexport p/ compat

logger = get_logger(__name__)

# Compat: o User-Agent canônico agora mora em http_client (com e-mail de contato,
# exigido pela SEC). Reexportado aqui para não quebrar imports existentes.
_UA = {"User-Agent": http_client.UA}

# Registro mínimo ticker -> (CD_CVM, nome, setor). Sem heurística: se o ticker
# não está aqui, abstemos. Ampliar conforme novas empresas entram no slice.
TICKER_CD_CVM: dict[str, tuple[int, str, str]] = {
    "PETR4": (9512, "Petróleo Brasileiro S.A. - Petrobras", "Petróleo, Gás e Biocombustíveis"),
    "PETR3": (9512, "Petróleo Brasileiro S.A. - Petrobras", "Petróleo, Gás e Biocombustíveis"),
    "VALE3": (4170, "Vale S.A.", "Mineração"),
    "ITUB4": (19348, "Itaú Unibanco Holding S.A.", "Bancos"),
}

# Contas-alvo (validar sempre pelo DS_CONTA). Mapeia (demonstração padrão CVM, CD_CONTA).
# D1 aprofundado: além de Receita/Lucro/PL, extrai componentes p/ dívida, EBIT e FCO.
# Bancos/seguradoras têm plano de contas próprio → as contas abaixo não casam e as
# métricas derivadas ABSTÊM (achado M2), nunca inventam.
_CONTAS_DRE = {
    "3.01": "Receita de Venda de Bens e/ou Serviços",
    "3.05": "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)",
    # 3.06.x cobrem a lacuna "custo financeiro / despesa de juros" e ancoram os
    # elos câmbio→resultado financeiro e Selic→despesas financeiras (fase 3).
    "3.06": "Resultado Financeiro",
    "3.06.01": "Receitas Financeiras",
    "3.06.02": "Despesas Financeiras",
    "3.11": "Lucro/Prejuízo do período",
}
_CONTAS_BPP = {
    "2.01.04": "Empréstimos e Financiamentos (circulante)",
    "2.02.01": "Empréstimos e Financiamentos (não circulante)",
    "2.03": "Patrimônio líquido",
}
_CONTAS_BPA = {
    "1.01.01": "Caixa e Equivalentes de Caixa",
    "1.01.02": "Aplicações Financeiras",
}
_CONTAS_DFC = {"6.01": "Caixa Líquido das Atividades Operacionais (FCO)"}

# "MILHAR"/"MILHARES" = mil (achado A1 do red-team: sem eles, valor em MILHAR entraria
# 1000x menor — número errado COM fonte, pior que abster). "milhar" == mil por definição.
_ESCALAS = {
    "UNIDADE": 1,
    "MIL": 1_000,
    "MILHAR": 1_000,
    "MILHARES": 1_000,
    "MILHAO": 1_000_000,
    "MILHÃO": 1_000_000,
}

# Validação SEMÂNTICA pelo DS_CONTA (o comentário acima sempre exigiu; agora é
# código): bancos/seguradoras reusam os MESMOS códigos com outro significado
# (ex.: ITUB 3.05 = "Resultado antes dos Tributos" ≠ EBIT; 3.06 = "IR e CS" ≠
# resultado financeiro; BBDC 2.02.01 = "Depósitos" ≠ empréstimos). Sem esta
# checagem, derivadas e elos rotulariam número errado COM fonte — o pior
# resultado possível. Código com descrição divergente => linha descartada
# (abstenção); padrões comparados sem acento/caixa.
_DS_ESPERADO: dict[str, tuple[str, ...]] = {
    "3.01": ("receita",),
    "3.05": ("antes do resultado financeiro",),
    "3.06": ("resultado financeiro",),
    "3.06.01": ("receitas financeiras",),
    "3.06.02": ("despesas financeiras",),
    "3.11": ("lucro", "prejuizo"),
    "2.01.04": ("emprestimo", "financiamento"),
    "2.02.01": ("emprestimo", "financiamento"),
    "2.03": ("patrimonio",),
    "1.01.01": ("caixa",),
    "1.01.02": ("aplicac",),
}


def _ds_conta_valida(
    cd_conta: str,
    ds_conta: str,
    ds_esperado: dict[str, tuple[str, ...]] = _DS_ESPERADO,
) -> bool:
    """Valida o DS_CONTA contra os padrões esperados de `ds_esperado`.

    Parametrizada (Fase 2 multiativo) para reuso com outros planos de contas;
    o DEFAULT é o dict global do plano padrão — comportamento legado intocado.
    """
    padroes = ds_esperado.get(cd_conta)
    if not padroes:
        return True
    ds = _normalizar_ds(ds_conta)
    return any(p in ds for p in padroes)


CVM_DFP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip"
BCB_SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"
)
BCB_SGS_RANGE_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={ini}&dataFinal={fim}"
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
    """Idempotente. Resolve o ticker via cadastro CVM UNIVERSAL (cache + seed);
    abstém (DadoNaoEncontrado) se desconhecido — funciona para qualquer empresa B3."""
    # Import tardio: quebra o ciclo dados <-> cvm_cadastro (que importa deste módulo).
    from app.services import cvm_cadastro

    ticker = ticker.upper().strip()
    cd_cvm, cnpj, nome, setor = cvm_cadastro.resolve_ticker(session, ticker)

    empresa = session.execute(select(Empresa).where(Empresa.cd_cvm == cd_cvm)).scalar_one_or_none()
    if empresa is None:
        empresa = Empresa(cd_cvm=cd_cvm, ticker=ticker, nome=nome, setor=setor, cnpj=cnpj)
        session.add(empresa)
        session.flush()
        logger.info("empresa_criada", ticker=ticker, cd_cvm=cd_cvm)
    else:
        if empresa.ticker != ticker:
            empresa.ticker = ticker
        if cnpj and not empresa.cnpj:
            empresa.cnpj = cnpj
    return empresa


# ---------------------------------------------------------------------------
# MACRO — BCB SGS
# ---------------------------------------------------------------------------
def bcb_sgs(codigo: int, n: int = 1) -> list[dict]:
    """Últimos N pontos de uma série do SGS. Devolve [{data, valor}]."""
    url = BCB_SGS_URL.format(codigo=codigo, n=n)
    resp = http_client.get_keyless(url, timeout=30.0)
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
        # D3 ampliado — inflação doméstica (rótulos sem ambiguidade de unidade).
        "IPCA_MENSAL": (433, "IPCA - variação mensal (% a.m.)"),
        "IGP_M_MENSAL": (189, "IGP-M - variação mensal (% a.m.)"),
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


def mensalizar(pontos: list[tuple[dt.date, float]]) -> list[tuple[dt.date, float]]:
    """Última observação de cada mês (dado real, não média inventada)."""
    por_mes: dict[tuple[int, int], tuple[dt.date, float]] = {}
    for data, valor in pontos:
        chave = (data.year, data.month)
        atual = por_mes.get(chave)
        if atual is None or data > atual[0]:
            por_mes[chave] = (data, valor)
    return [por_mes[k] for k in sorted(por_mes)]


def bcb_sgs_intervalo(codigo: int, inicio: dt.date, fim: dt.date) -> list[dict]:
    """Pontos de uma série SGS num intervalo de datas. A forma `/ultimos/{n}`
    rejeita N grande (400) — para histórico, o SGS exige dataInicial/dataFinal."""
    url = BCB_SGS_RANGE_URL.format(
        codigo=codigo, ini=inicio.strftime("%d/%m/%Y"), fim=fim.strftime("%d/%m/%Y")
    )
    resp = http_client.get_keyless(url, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def ingest_usd_historico(session: Session, meses: int = 36) -> int:
    """Persiste o histórico MENSAL do dólar (SGS 1, última observação de cada mês).

    Alimenta o co-movimento (Pearson) do grafo causal — que exige n>=24 e antes
    nunca disparava (só havia 1-2 pontos por série). Idempotente por (código, data).
    """
    hoje = dt.date.today()
    try:
        pontos_raw = bcb_sgs_intervalo(1, hoje - dt.timedelta(days=meses * 32), hoje)
    except httpx.HTTPError as exc:
        logger.warning("usd_historico_falhou", erro=type(exc).__name__)
        return 0
    pontos = [
        (d, v)
        for p in pontos_raw
        if (d := _parse_data(str(p.get("data", "")))) is not None
        and (v := _parse_valor(str(p.get("valor", "")))) is not None
    ]
    mensais = mensalizar(pontos)[-meses:]
    # Fonte com a URL ESTÁVEL da série (o intervalo consultado muda a cada rodada).
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{1}/dados"
    n_gravados = 0
    for data, valor in mensais:
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao="Banco Central — API SGS série 1: Dólar venda (R$/US$), última obs. do mês",
            dt_referencia=data,
        )
        existente = session.execute(
            select(MacroSerie).where(MacroSerie.codigo == "USD_VENDA", MacroSerie.data == data)
        ).scalar_one_or_none()
        if existente is None:
            session.add(MacroSerie(codigo="USD_VENDA", data=data, valor=valor, fonte_id=fonte_id))
        else:
            existente.valor = valor
            existente.fonte_id = fonte_id
        n_gravados += 1
    logger.info("usd_historico_persistido", meses=len(mensais))
    return n_gravados


# ---------------------------------------------------------------------------
# FUNDAMENTOS — CVM DFP
# ---------------------------------------------------------------------------
def _baixar_dfp_zip(ano: int) -> bytes:
    url = CVM_DFP_URL.format(ano=ano)
    return http_client.download_zip(url, timeout=180.0)


_ORDENS_ULTIMO = ("ÚLTIMO", "ULTIMO")
_ORDENS_PENULTIMO = ("PENÚLTIMO", "PENULTIMO")


def _extrair_contas(
    conteudo_zip: bytes,
    ano: int,
    cd_cvm: int,
    membro: str,
    contas: dict[str, str],
) -> list[dict]:
    """Lê um CSV (latin-1, ';') do ZIP e extrai as contas-alvo dos exercícios
    ÚLTIMO **e** PENÚLTIMO (a DFP publica os dois — o penúltimo dá a tendência
    ano-contra-ano com fonte, cobrindo a lacuna "dados históricos").

    Devolve [{cd_conta, ds_conta, valor, dt_refer, ordem}]. Nunca inventa: só
    retorna o que existe na fonte.
    """
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as z:
        if membro not in z.namelist():
            return []
        achados: list[dict] = []
        with z.open(membro) as raw:
            texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            for linha in leitor:
                ordem = linha.get("ORDEM_EXERC", "").strip().upper()
                if ordem in _ORDENS_ULTIMO:
                    ordem = "ULTIMO"
                elif ordem in _ORDENS_PENULTIMO:
                    ordem = "PENULTIMO"
                else:
                    continue
                try:
                    if int(linha.get("CD_CVM", "0")) != cd_cvm:
                        continue
                except ValueError:
                    continue
                cd_conta = linha.get("CD_CONTA", "").strip()
                if cd_conta not in contas:
                    continue
                ds_conta = linha.get("DS_CONTA", "").strip()
                if not _ds_conta_valida(cd_conta, ds_conta):
                    # Mesmo código, OUTRO significado (plano de contas de banco/
                    # seguradora) -> abstém; nunca rótulo errado com fonte.
                    logger.info(
                        "conta_semantica_divergente_abstida",
                        cd_conta=cd_conta,
                        ds_conta=ds_conta[:80],
                        cd_cvm=cd_cvm,
                    )
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
                        "ds_conta": ds_conta,
                        "valor": valor,
                        "dt_refer": dt_refer,
                        "ano": ano,
                        "ordem": ordem,
                    }
                )
    return achados


def _ler_linhas_membro(conteudo_zip: bytes, cd_cvm: int, membro: str) -> list[dict]:
    """Lê TODAS as linhas da empresa num membro do ZIP (latin-1, ';'), com a
    escala aplicada (regra A1) e SEM filtro de conta — a extração por plano de
    contas (`planos_contas`) decide o que usar. Inclui ST_CONTA_FIXA porque a
    localização por DS prefere contas fixas ('S'). Membro ausente -> [].
    """
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as z:
        if membro not in z.namelist():
            return []
        linhas: list[dict] = []
        with z.open(membro) as raw:
            texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            for linha in leitor:
                ordem = linha.get("ORDEM_EXERC", "").strip().upper()
                if ordem in _ORDENS_ULTIMO:
                    ordem = "ULTIMO"
                elif ordem in _ORDENS_PENULTIMO:
                    ordem = "PENULTIMO"
                else:
                    continue
                try:
                    if int(linha.get("CD_CVM", "0")) != cd_cvm:
                        continue
                except ValueError:
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
                linhas.append(
                    {
                        "cd_conta": linha.get("CD_CONTA", "").strip(),
                        "ds_conta": linha.get("DS_CONTA", "").strip(),
                        "st_conta_fixa": (linha.get("ST_CONTA_FIXA") or "").strip().upper(),
                        "valor": valor,
                        "dt_refer": dt_refer,
                        "ordem": ordem,
                    }
                )
    return linhas


# D&A não tem CD_CONTA padronizado entre empresas (é sub-linha dos ajustes da DFC,
# ex.: 6.01.01.02 na Petrobras). Localizamos por DESCRIÇÃO dentro de 6.01.01.*.
# O padrão cobre TODAS as formas do add-back (achado M2 da auditoria da fase 3:
# só "deprecia" pegaria D&A PARCIAL — número subestimado COM fonte — em empresa
# que fragmenta depreciação/amortização/exaustão em linhas separadas).
_DA_PREFIXO = "6.01.01."
_DA_PADROES = ("deprecia", "amortiz", "exaust", "deple")


def _consolidar_da(linhas: list[dict]) -> dict | None:
    """Consolida as linhas de D&A de UM exercício num único achado.

    - 1 linha -> ela mesma (caso comum: "Depreciação, depleção e amortização").
    - 2+ linhas IRMÃS (sem relação ancestral e mesma dt_refer) -> SOMA, com
      rótulo composto — todas são add-backs não-caixa do mesmo bloco.
    - Linha ancestral de outra (subtotal + componente => dupla contagem) ou
      datas divergentes -> None (ambíguo: abstém, nunca estima).
    """
    if not linhas:
        return None
    if len(linhas) == 1:
        return linhas[0]
    for a in linhas:
        for b in linhas:
            if a is not b and b["cd_conta"].startswith(a["cd_conta"] + "."):
                return None  # subtotal + componente: somar dobraria a conta
    if len({linha["dt_refer"] for linha in linhas}) != 1:
        return None
    ordenadas = sorted(linhas, key=lambda x: x["cd_conta"])
    base = dict(ordenadas[0])
    base["cd_conta"] = "+".join(x["cd_conta"] for x in ordenadas)
    base["ds_conta"] = " + ".join(x["ds_conta"] for x in ordenadas)
    base["valor"] = float(sum(x["valor"] for x in ordenadas))
    return base


def _extrair_da_dfc(conteudo_zip: bytes, ano: int, cd_cvm: int, membro: str) -> list[dict]:
    """Extrai a(s) linha(s) de Depreciação/Amortização/Exaustão dos ajustes da
    DFC (ÚLTIMO e PENÚLTIMO) e consolida por exercício. Sem match ou com match
    ambíguo (hierarquia/datas) -> abstém."""
    with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as z:
        if membro not in z.namelist():
            return []
        candidatos: dict[str, list[dict]] = {}
        with z.open(membro) as raw:
            texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            for linha in leitor:
                ordem = linha.get("ORDEM_EXERC", "").strip().upper()
                if ordem in _ORDENS_ULTIMO:
                    ordem = "ULTIMO"
                elif ordem in _ORDENS_PENULTIMO:
                    ordem = "PENULTIMO"
                else:
                    continue
                try:
                    if int(linha.get("CD_CVM", "0")) != cd_cvm:
                        continue
                except ValueError:
                    continue
                cd_conta = linha.get("CD_CONTA", "").strip()
                ds_conta = linha.get("DS_CONTA", "").strip()
                if not cd_conta.startswith(_DA_PREFIXO):
                    continue
                if not any(p in ds_conta.lower() for p in _DA_PADROES):
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
                candidatos.setdefault(ordem, []).append(
                    {
                        "cd_conta": cd_conta,
                        "ds_conta": ds_conta,
                        "valor": valor,
                        "dt_refer": dt_refer,
                        "ano": ano,
                        "ordem": ordem,
                        "papel": "DA",
                    }
                )
    achados: list[dict] = []
    for ordem, linhas in candidatos.items():
        consolidada = _consolidar_da(linhas)
        if consolidada is None:
            logger.info("da_dfc_ambigua_abstida", ordem=ordem, n=len(linhas), cd_cvm=cd_cvm)
            continue
        achados.append(consolidada)
    return achados


def ingest_fundamentos(session: Session, empresa: Empresa) -> list[Fundamento]:
    """Baixa a DFP mais recente e persiste contas-chave com fonte, MULTI-PLANO.

    O plano de contas é detectado pelo PRÓPRIO filing (DS da conta fixa 3.01 do
    DRE — decisão D2; SETOR_ATIV é telemetria no log, nunca decide) e despacha:
    banco/seguradora → extração por DS (`planos_contas`); senão → plano padrão
    (comportamento legado intocado). O plano detectado é persistido em
    `empresas.plano_contas`. Abstém (DadoNaoEncontrado) se nenhum exercício
    recente tem dados da empresa.
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

        linhas_dre = _ler_linhas_membro(conteudo, cd_cvm, f"dfp_cia_aberta_DRE_con_{ano}.csv")
        plano = planos_contas.detectar_plano(linhas_dre)
        logger.info(
            "plano_contas_detectado",
            cd_cvm=cd_cvm,
            plano=plano,
            setor_telemetria=empresa.setor,  # nunca decide (D2)
        )

        if plano in planos_contas.PLANOS_FINANCEIROS:
            gravados = _ingest_financeira(session, empresa, conteudo, ano, plano, linhas_dre)
        else:
            gravados = _ingest_padrao(session, empresa, conteudo, ano)
        if not gravados:
            logger.info("dfp_sem_dados_empresa", ano=ano, cd_cvm=cd_cvm, plano=plano)
            continue

        empresa.plano_contas = plano
        logger.info("fundamentos_persistidos", ano=ano, cd_cvm=cd_cvm, n=len(gravados), plano=plano)
        return gravados

    raise DadoNaoEncontrado(
        f"sem DFP recente para {empresa.ticker} (CD_CVM {cd_cvm}) — dado não encontrado"
    )


def _ingest_padrao(
    session: Session, empresa: Empresa, conteudo: bytes, ano: int
) -> list[Fundamento]:
    """Extração do plano PADRÃO (legado, byte-idêntico): contas fixas validadas
    por DS + D&A da DFC + derivadas (dívida/EBITDA). Sem achados -> []."""
    cd_cvm = empresa.cd_cvm
    # DRE + BPP + BPA + DFC (método indireto ou direto). Cada empresa filia
    # só um método de DFC; o membro ausente devolve [] (não quebra).
    membros = {
        f"dfp_cia_aberta_DRE_con_{ano}.csv": _CONTAS_DRE,
        f"dfp_cia_aberta_BPP_con_{ano}.csv": _CONTAS_BPP,
        f"dfp_cia_aberta_BPA_con_{ano}.csv": _CONTAS_BPA,
        f"dfp_cia_aberta_DFC_MI_con_{ano}.csv": _CONTAS_DFC,
        f"dfp_cia_aberta_DFC_MD_con_{ano}.csv": _CONTAS_DFC,
    }
    achados: list[dict] = []
    for membro, contas in membros.items():
        achados.extend(_extrair_contas(conteudo, ano, cd_cvm, membro, contas))
    # D&A (por descrição, nos ajustes da DFC) — habilita o EBITDA derivado.
    for membro in (
        f"dfp_cia_aberta_DFC_MI_con_{ano}.csv",
        f"dfp_cia_aberta_DFC_MD_con_{ano}.csv",
    ):
        achados.extend(_extrair_da_dfc(conteudo, ano, cd_cvm, membro))
    if not achados:
        return []

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
        gravados.append(
            _upsert_fundamento(session, empresa, conta_label, a["valor"], a["dt_refer"], fonte_id)
        )

    # Métricas derivadas (dívida bruta/líquida, EBITDA). SÓ do exercício
    # ÚLTIMO — misturar exercícios geraria um número quimera. Abstêm se
    # faltar componente — nunca gravam estimativa.
    achados_ultimo = [a for a in achados if a.get("ordem", "ULTIMO") == "ULTIMO"]
    gravados.extend(_persistir_derivadas(session, empresa, achados_ultimo, ano, url))
    return gravados


def _ingest_financeira(
    session: Session,
    empresa: Empresa,
    conteudo: bytes,
    ano: int,
    plano: str,
    linhas_dre: list[dict],
) -> list[Fundamento]:
    """Extração de BANCO/SEGURADORA: métricas localizadas por DS (posição varia
    por emissor) + ROE derivado (unidade='RAZAO', fonte composta). As derivadas
    do plano padrão (dívida/EBITDA/D&A) NÃO se aplicam a estes planos —
    abstenção ESTRUTURAL logada, nunca silenciosa. Sem achados -> []."""
    cd_cvm = empresa.cd_cvm
    linhas = {
        "DRE": linhas_dre,
        "BPP": _ler_linhas_membro(conteudo, cd_cvm, f"dfp_cia_aberta_BPP_con_{ano}.csv"),
        "BPA": _ler_linhas_membro(conteudo, cd_cvm, f"dfp_cia_aberta_BPA_con_{ano}.csv"),
    }
    achados = planos_contas.extrair_financeira(plano, linhas)
    if not achados:
        return []

    url = CVM_DFP_URL.format(ano=ano)
    gravados: list[Fundamento] = []
    for a in achados:
        if a["dt_refer"] is None:
            logger.info("fato_sem_dt_refer_abstido", cd_conta=a["cd_conta"], cd_cvm=cd_cvm)
            continue
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=(
                f"CVM DFP {ano} (consolidado) — {empresa.nome} "
                f"[{a['cd_conta']} {a['ds_conta']}], valores em reais"
            ),
            dt_referencia=a["dt_refer"],
        )
        # Rótulo = DS REAL do filing (nunca 'EBIT' em banco/seguradora).
        conta_label = f"{a['ds_conta']} ({a['cd_conta']})"
        gravados.append(
            _upsert_fundamento(session, empresa, conta_label, a["valor"], a["dt_refer"], fonte_id)
        )

    # Derivadas do plano PADRÃO não rodam aqui (plano de contas incompatível):
    # abstenção estrutural LOGADA — a lacuna aparece na tese, nunca um número.
    logger.info(
        "derivadas_padrao_abstidas_estruturalmente",
        plano=plano,
        cd_cvm=cd_cvm,
        derivadas=list(derivadas.DERIVADAS),
    )

    # ROE derivado do plano financeiro: lucro/PL consolidados do MESMO exercício
    # ÚLTIMO; guarda PL>0 e datas iguais dentro de roe_derivado.
    achados_ultimo = [a for a in achados if a["ordem"] == "ULTIMO"]
    roe, componentes = planos_contas.roe_derivado(achados_ultimo)
    if roe is None:
        logger.info("roe_derivado_abstido", cd_cvm=cd_cvm, plano=plano)
    else:
        dt_refer = next(a["dt_refer"] for a in achados_ultimo if a["papel"] == "LUCRO_CONSOLIDADO")
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=(
                f"CVM DFP {ano} (consolidado) — {empresa.nome} "
                f"[ROE = função das contas {'+'.join(componentes)}], derivado; "
                f"metodologia: {planos_contas.ROE_METODOLOGIA}"
            ),
            dt_referencia=dt_refer,
        )
        gravados.append(
            _upsert_fundamento(
                session,
                empresa,
                planos_contas.ROE_CONTA,
                roe,
                dt_refer,
                fonte_id,
                unidade="RAZAO",
            )
        )
    return gravados


def _upsert_fundamento(
    session: Session,
    empresa: Empresa,
    conta_label: str,
    valor: float | None,
    dt_refer: dt.date,
    fonte_id: uuid.UUID,
    unidade: str | None = None,
) -> Fundamento:
    """Idempotente por (empresa, conta, dt_refer).

    `unidade` NULL = BRL (legado byte-idêntico — achado B2); 'RAZAO' para o ROE
    derivado (fração decimal), formatada pelo coletor da tese por unidade.
    """
    existente = session.execute(
        select(Fundamento).where(
            Fundamento.empresa_id == empresa.id,
            Fundamento.conta == conta_label,
            Fundamento.dt_refer == dt_refer,
        )
    ).scalar_one_or_none()
    if existente is None:
        f = Fundamento(
            empresa_id=empresa.id,
            conta=conta_label,
            valor=valor,
            dt_refer=dt_refer,
            fonte_id=fonte_id,
            unidade=unidade,
        )
        session.add(f)
        return f
    existente.valor = valor
    existente.fonte_id = fonte_id
    existente.unidade = unidade
    return existente


def _persistir_derivadas(
    session: Session, empresa: Empresa, achados: list[dict], ano: int, url: str
) -> list[Fundamento]:
    """Calcula e persiste as métricas derivadas com fonte COMPOSTA (contas-base).

    Abstém (não grava) qualquer métrica cujo componente falte — a lacuna aparece
    na tese como "dado não encontrado". Nunca usa 0 implícito (achado A1).
    """
    contas = {a["cd_conta"]: a["valor"] for a in achados if a["valor"] is not None}
    # D&A entra sob chave própria (o CD_CONTA dela varia entre empresas).
    da = next((a for a in achados if a.get("papel") == "DA" and a["valor"] is not None), None)
    if da is not None:
        contas[derivadas.CHAVE_DA] = da["valor"]
    dt_refer = next((a["dt_refer"] for a in achados if a["dt_refer"] is not None), None)
    if dt_refer is None:
        return []

    gravados: list[Fundamento] = []
    for nome, fn in derivadas.DERIVADAS.items():
        valor, codigos = fn(contas)
        if valor is None:
            continue  # abstém — nunca estima
        fonte_id = get_or_create_fonte(
            session,
            url=url,
            descricao=(
                f"CVM DFP {ano} (consolidado) — {empresa.nome} "
                f"[{nome} = função das contas {'+'.join(codigos)}], derivado, em reais"
            ),
            dt_referencia=dt_refer,
        )
        gravados.append(_upsert_fundamento(session, empresa, nome, valor, dt_refer, fonte_id))
    return gravados


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
