"""Métricas por setor/classe — registro DATA-DRIVEN (plano §2.6 + envelope v3 §5).

Este módulo LÊ fatos já persistidos (cada um com sua ``Fonte``) e monta
:class:`MetricaSetor` prontas para o envelope: nome + valor + unidade + fórmula
legível + fontes (descrição/URL/data) + o_que_mede + implicação NEUTRA (passa
pelo gate A5) + rótulos de metodologia + lacuna declarada quando abstém.

Regras inegociáveis:

- **Nunca inventar dado.** Componente ausente/stale/sem fonte -> ``valor=None``
  com ``lacuna`` explicando o motivo — nunca 0-fill, nunca estimativa.
- **Registro data-driven** chaveado por ``(classe, plano_contas, setor)``:
  a entrada MAIS específica vence (ordem do registro). Adicionar um setor novo
  (varejo/saneamento/seguros) é acrescentar especificações + uma linha no
  registro — configuração, não arquitetura (plano §1d).
- **Reuso, nunca duplicação:** ROE/EBITDA/dívida líquida são os fundamentos
  DERIVADOS já persistidos pelo ingestor DFP (`derivadas`/`planos_contas`);
  indicadores de FII passam por `fii_dados.indicadores_recentes` (staleness
  90d); a leitura atual de título usa `tesouro.titulo_atual`.
- **Degradação sem tabela (correção A13):** ``ProgrammingError``/
  ``OperationalError`` de tabela inexistente vira ``DadoNaoEncontrado``
  rotulado (métrica abstida), nunca 500; outra falha de SQL propaga.
- **Convenção de escala:** valores com unidade ``pct`` são FRAÇÃO decimal
  (0,15 = 15%), padrão do repositório (`FiiIndicador` PCT, ROE RAZAO). Taxas
  ANBIMA/STN chegam em % a.a. e são convertidas para fração com rótulo.
- ``num_acoes`` não existe nas tabelas ingeridas: P/L, P/VP e EV/EBITDA de
  ação só computam quando o chamador injeta ``num_acoes`` COM fonte no
  contexto; sem isso, abstêm com lacuna (nunca estimam free float/capital).
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import NoReturn

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import (
    BancoIndicador,
    CurvaSnapshot,
    Empresa,
    FiiCadastro,
    FiiIndicador,
    Fonte,
    Fundamento,
    PrecoDiario,
    Provento,
    SetorIndicador,
)
from app.services import derivadas, fii_dados, planos_contas, tesouro
from app.services.ativos.renda_fixa import TD_CODIGO_RE
from app.services.dados import DadoNaoEncontrado
from app.services.planos_contas import _normalizar_ds

logger = get_logger(__name__)

# Contas derivadas persistidas pelo ingestor DFP — o rótulo É a chave do
# registro `derivadas.DERIVADAS` (reuso; drift entre módulos quebraria aqui).
_CONTA_EBITDA = next(k for k in derivadas.DERIVADAS if k.startswith("EBITDA"))
_CONTA_DIVIDA_LIQUIDA = next(k for k in derivadas.DERIVADAS if k.startswith("Dívida líquida"))

# Indicador da RAP em `setor_indicadores` (conector ANEEL); aceita os dois
# códigos candidatos da F1 — o mais recente por competência vence.
_INDICADORES_RAP = ("RAP_CICLO", "RAP")

# Janela do DY a mercado (12 meses corridos por data-com).
_JANELA_DY_DIAS = 365

_ROTULO_NAO_AJUSTADO = "preços não ajustados por proventos"
_ROTULO_PCT_FRACAO = "fração decimal (0,15 = 15%)"

_LACUNA_CAP_RATE = (
    "cap rate de mercado não disponível publicamente (dado licenciado); aproximação "
    "contábil não calculada — receita anual de aluguel não consta dos informes CVM "
    "ingeridos — dado não encontrado"
)

# unidade tipada das tabelas de fatos -> unidade do envelope v3 (§5).
_UNIDADE_ENVELOPE = {"PCT": "pct", "BRL": "BRL", "RAZAO": "razao"}

# Nível-2 do plano de contas ("(3.11)"/"(2.03)") — matchers de rótulo de conta.
_RE_CONTA_DRE_N2 = re.compile(r"\(3\.\d{2}\)$")
_RE_CONTA_PL_N2 = re.compile(r"\(2\.\d{2}\)$")


# ---------------------------------------------------------------------------
# Contratos públicos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FonteMetrica:
    """Espelho do ``FonteRef`` do envelope: descrição + URL + data de referência."""

    descricao: str
    url: str | None = None
    dt_referencia: dt.date | None = None


@dataclass(frozen=True)
class ContextoMetricas:
    """Identidade do ativo para o cálculo — preenchida pela F3 (integração).

    ``classe`` None = 'acao' (legado). ``num_acoes`` só entra COM
    ``num_acoes_fonte`` (número sem fonte não é fato — é descartado com lacuna).
    """

    ticker: str
    classe: str | None = None
    plano_contas: str | None = None
    setor: str | None = None
    cd_cvm: int | None = None
    empresa_id: uuid.UUID | None = None
    fii_id: uuid.UUID | None = None
    num_acoes: Decimal | int | float | None = None
    num_acoes_fonte: FonteMetrica | None = None


@dataclass(frozen=True)
class MetricaSetor:
    """Métrica pronta para o envelope (contrato v3 §5) — abstenção via ``lacuna``."""

    nome: str
    valor: Decimal | None
    unidade: str  # 'pct' | 'BRL' | 'razao' | 'x'
    formula: str
    o_que_mede: str
    implicacao: str  # NEUTRA — varrida pelo gate (A5)
    fontes: tuple[FonteMetrica, ...] = ()
    rotulos: tuple[str, ...] = ()
    lacuna: str | None = None


# ---------------------------------------------------------------------------
# Infra interna do registro
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Resultado:
    """Saída de uma calculadora: valor + fontes + rótulos (ou lacuna)."""

    valor: Decimal | None
    fontes: tuple[FonteMetrica, ...] = ()
    rotulos: tuple[str, ...] = ()
    lacuna: str | None = None
    unidade: str | None = None  # sobrepõe a unidade estática da espec (ex.: IF.data)


_Calculadora = Callable[[Session, ContextoMetricas, dt.date], _Resultado]


@dataclass(frozen=True)
class _Espec:
    """Especificação DECLARATIVA de uma métrica do registro."""

    nome: str
    unidade: str
    formula: str
    o_que_mede: str
    implicacao: str
    calcular: _Calculadora = field(repr=False)


def _dec(valor: object) -> Decimal:
    """Converte Numeric/float/int para ``Decimal`` sem ruído binário."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def _degradar_tabela_ausente(exc: ProgrammingError | OperationalError) -> NoReturn:
    """Tabela inexistente (migração 0006 pendente) -> DadoNaoEncontrado rotulado (A13).

    Qualquer outro erro de SQL propaga — bug de programação nunca vira lacuna.
    """
    mensagem = str(getattr(exc, "orig", None) or exc).lower()
    ausente = any(
        marca in mensagem for marca in ("does not exist", "undefined table", "no such table")
    )
    if ausente:
        logger.warning("metricas_setor_tabela_ausente", erro=type(exc).__name__)
        raise DadoNaoEncontrado(
            "tabela de fatos indisponível (migração 0006 pendente?) — dado não encontrado"
        ) from exc
    raise exc


def _rodar(espec: _Espec, session: Session, ctx: ContextoMetricas, hoje: dt.date) -> MetricaSetor:
    """Executa a calculadora num SAVEPOINT; falha de dado vira abstenção rotulada."""
    try:
        with session.begin_nested():
            resultado = espec.calcular(session, ctx, hoje)
    except (ProgrammingError, OperationalError) as exc:
        try:
            _degradar_tabela_ausente(exc)
        except DadoNaoEncontrado as dne:
            resultado = _Resultado(valor=None, lacuna=str(dne))
    except DadoNaoEncontrado as exc:
        resultado = _Resultado(valor=None, lacuna=str(exc))
    return MetricaSetor(
        nome=espec.nome,
        valor=resultado.valor,
        unidade=resultado.unidade or espec.unidade,
        formula=espec.formula,
        o_que_mede=espec.o_que_mede,
        implicacao=espec.implicacao,
        fontes=resultado.fontes,
        rotulos=resultado.rotulos,
        lacuna=resultado.lacuna,
    )


# ---------------------------------------------------------------------------
# Leitores de fatos (cada valor volta COM a sua Fonte; ausência -> abstenção)
# ---------------------------------------------------------------------------


def _fonte_obrigatoria(session: Session, fonte_id: uuid.UUID | None, o_que: str) -> FonteMetrica:
    """Carrega a `Fonte` do fato; fato sem fonte não é fato -> abstém."""
    fonte = session.get(Fonte, fonte_id) if fonte_id is not None else None
    if fonte is None:
        raise DadoNaoEncontrado(f"{o_que} sem fonte registrada — dado não encontrado")
    return FonteMetrica(descricao=fonte.descricao, url=fonte.url, dt_referencia=fonte.dt_referencia)


def _preco_recente(session: Session, ticker: str) -> tuple[Decimal, dt.date, FonteMetrica]:
    """Último fechamento do ticker em `precos_diarios` (COTAHIST, não ajustado)."""
    linha = session.execute(
        select(PrecoDiario)
        .where(PrecoDiario.ticker == ticker, PrecoDiario.fechamento.is_not(None))
        .order_by(PrecoDiario.data_pregao.desc())
        .limit(1)
    ).scalar_one_or_none()
    if linha is None:
        raise DadoNaoEncontrado(
            f"{ticker}: sem preço de fechamento em precos_diarios (COTAHIST) — "
            "dado não encontrado"
        )
    fonte = _fonte_obrigatoria(session, linha.fonte_id, f"preço de {ticker}")
    return _dec(linha.fechamento), linha.data_pregao, fonte


def _proventos_12m(
    session: Session, ticker: str, hoje: dt.date
) -> tuple[Decimal, int, FonteMetrica]:
    """Soma dos proventos por ação/cota com data-com nos últimos 12 meses."""
    corte = hoje - dt.timedelta(days=_JANELA_DY_DIAS)
    linhas = (
        session.execute(
            select(Provento)
            .where(Provento.ticker == ticker, Provento.data_com > corte, Provento.data_com <= hoje)
            .order_by(Provento.data_com)
        )
        .scalars()
        .all()
    )
    if not linhas:
        raise DadoNaoEncontrado(
            f"{ticker}: nenhum provento com data-com nos últimos 12 meses em `proventos` "
            "(sem ingestão B3 ou sem distribuição no período) — dado não encontrado"
        )
    total = sum((_dec(p.valor) for p in linhas), Decimal(0))
    fonte = _fonte_obrigatoria(session, linhas[-1].fonte_id, f"proventos de {ticker}")
    return total, len(linhas), fonte


def _empresa_id(session: Session, ctx: ContextoMetricas) -> uuid.UUID:
    if ctx.empresa_id is not None:
        return ctx.empresa_id
    if ctx.cd_cvm is not None:
        eid = session.execute(
            select(Empresa.id).where(Empresa.cd_cvm == ctx.cd_cvm)
        ).scalar_one_or_none()
        if eid is not None:
            return eid
    raise DadoNaoEncontrado(
        f"{ctx.ticker}: empresa não resolvida (empresa_id/cd_cvm ausentes do cadastro) — "
        "dado não encontrado"
    )


def _cd_cvm(session: Session, ctx: ContextoMetricas) -> int:
    if ctx.cd_cvm is not None:
        return ctx.cd_cvm
    if ctx.empresa_id is not None:
        cd = session.execute(
            select(Empresa.cd_cvm).where(Empresa.id == ctx.empresa_id)
        ).scalar_one_or_none()
        if cd is not None:
            return cd
    raise DadoNaoEncontrado(
        f"{ctx.ticker}: CD_CVM não resolvido — indicadores IF.data indisponíveis — "
        "dado não encontrado"
    )


def _fundamento_recente(
    session: Session,
    ctx: ContextoMetricas,
    predicado: Callable[[Fundamento], bool],
    descricao: str,
) -> Fundamento:
    """Fundamento mais recente (max dt_refer) da empresa que casa o predicado."""
    eid = _empresa_id(session, ctx)
    linhas = session.execute(select(Fundamento).where(Fundamento.empresa_id == eid)).scalars()
    candidatos = [f for f in linhas if f.valor is not None and predicado(f)]
    if not candidatos:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: {descricao} não encontrado nos fundamentos ingeridos (DFP) — "
            "dado não encontrado"
        )
    return max(candidatos, key=lambda f: f.dt_refer)


def _conta_codigo(cd_conta: str) -> Callable[[Fundamento], bool]:
    sufixo = f"({cd_conta})"
    return lambda f: f.conta.endswith(sufixo)


def _conta_exata(conta: str) -> Callable[[Fundamento], bool]:
    return lambda f: f.conta == conta


def _e_lucro_periodo(f: Fundamento) -> bool:
    """Lucro/prejuízo do período (nível 2 da DRE); exclui 'antes dos tributos'."""
    ds = _normalizar_ds(f.conta)
    if "antes" in ds or not _RE_CONTA_DRE_N2.search(f.conta):
        return False
    return ("lucro" in ds or "prejuizo" in ds) and ("periodo" in ds or "exercicio" in ds)


def _e_patrimonio_liquido(f: Fundamento) -> bool:
    """Patrimônio líquido (nível 2 do BPP) — cobre padrão (2.03) e banco (2.07/2.08)."""
    return "patrimonio liquido" in _normalizar_ds(f.conta) and bool(_RE_CONTA_PL_N2.search(f.conta))


def _indicador_banco(session: Session, ctx: ContextoMetricas, indicador: str) -> BancoIndicador:
    """Indicador tipado do IF.data mais recente (por dt_referencia) do banco."""
    cd = _cd_cvm(session, ctx)
    linha = session.execute(
        select(BancoIndicador)
        .where(BancoIndicador.cd_cvm == cd, BancoIndicador.indicador == indicador)
        .order_by(BancoIndicador.dt_referencia.desc())
        .limit(1)
    ).scalar_one_or_none()
    if linha is None:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: indicador {indicador} não encontrado no IF.data ingerido "
            "(banco_indicadores) — dado não encontrado"
        )
    return linha


def _fii_do_contexto(session: Session, ctx: ContextoMetricas) -> FiiCadastro:
    if ctx.fii_id is not None:
        fii = session.get(FiiCadastro, ctx.fii_id)
        if fii is not None:
            return fii
    fii = session.execute(
        select(FiiCadastro).where(FiiCadastro.ticker == ctx.ticker)
    ).scalar_one_or_none()
    if fii is None:
        raise DadoNaoEncontrado(
            f"FII {ctx.ticker}: sem cadastro em fii_cadastro — dado não encontrado"
        )
    return fii


def _indicador_fii(
    session: Session, ctx: ContextoMetricas, codigo: str, hoje: dt.date
) -> FiiIndicador:
    """Indicador do informe com staleness de 90d (reuso de `indicadores_recentes`)."""
    fii = _fii_do_contexto(session, ctx)
    ind = fii_dados.indicadores_recentes(session, fii, hoje=hoje).get(codigo)
    if ind is None:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: indicador {codigo} sem competência recente "
            f"(≤{fii_dados.STALENESS_DIAS_DEFAULT} dias) no informe CVM — dado não encontrado"
        )
    return ind


def _num_acoes(ctx: ContextoMetricas) -> tuple[Decimal, FonteMetrica]:
    """Nº de ações do contexto — só entra COM fonte (número sem fonte não é fato)."""
    if ctx.num_acoes is None:
        raise DadoNaoEncontrado(
            "número de ações não disponível nas fontes ingeridas — dado não encontrado"
        )
    if ctx.num_acoes_fonte is None:
        raise DadoNaoEncontrado(
            "número de ações informado sem fonte — descartado — dado não encontrado"
        )
    n = _dec(ctx.num_acoes)
    if n <= 0:
        raise DadoNaoEncontrado("número de ações não positivo — dado não encontrado")
    return n, ctx.num_acoes_fonte


# --- Renda fixa: título atual (STN) + vértices do snapshot ANBIMA -----------


def _titulo_atual(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> dict:
    """Leitura atual do título TD-* (reuso de `tesouro.titulo_atual`)."""
    m = TD_CODIGO_RE.fullmatch((ctx.ticker or "").strip().upper())
    if m is None:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: código TD inválido para renda fixa — dado não encontrado"
        )
    atual = tesouro.titulo_atual(session, m.group(1), int(m.group(2)), hoje)
    if atual is None:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: leitura atual do título indisponível (Data Base mais recente "
            "além do corte de staleness) — dado não encontrado"
        )
    return atual


def _prazo_du(vencimento: dt.date, hoje: dt.date) -> int:
    """Prazo até o vencimento em dias ÚTEIS aproximados (×252/365) — proxy de duration."""
    dias = (vencimento - hoje).days
    if dias <= 0:
        raise DadoNaoEncontrado(
            "título no vencimento ou vencido — prazo não positivo — dado não encontrado"
        )
    return round(dias * 252 / 365)


def _vertice_proximo(
    session: Session, curva: str, prazo_du: int, *, com_implicita: bool = False
) -> CurvaSnapshot:
    """Vértice do ÚLTIMO snapshot da curva mais próximo (|Δdu|) do prazo dado."""
    condicoes = [CurvaSnapshot.curva == curva]
    if com_implicita:
        condicoes.append(CurvaSnapshot.inflacao_implicita.is_not(None))
    data_ref = session.execute(select(func.max(CurvaSnapshot.data_ref)).where(*condicoes)).scalar()
    if data_ref is None:
        raise DadoNaoEncontrado(
            f"curva_snapshot sem snapshot da curva {curva} (ANBIMA ETTJ) — dado não encontrado"
        )
    linhas = (
        session.execute(select(CurvaSnapshot).where(*condicoes, CurvaSnapshot.data_ref == data_ref))
        .scalars()
        .all()
    )
    return min(linhas, key=lambda v: abs(v.vertice_du - prazo_du))


# ---------------------------------------------------------------------------
# Calculadoras — banco (plano de contas 'banco' dentro de 'acao')
# ---------------------------------------------------------------------------


def _calc_basileia(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    linha = _indicador_banco(session, ctx, "BASILEIA")
    fonte = _fonte_obrigatoria(session, linha.fonte_id, "Índice de Basileia")
    rotulos = [f"base {linha.base}", f"data-base {linha.dt_referencia.isoformat()}"]
    if linha.metodologia:
        rotulos.append(linha.metodologia)
    rotulos.append(_ROTULO_PCT_FRACAO)
    # Reconciliação de escala (F3, notas-integracao-f3.md): o IF.data grava a
    # BASILEIA já em PONTOS PERCENTUAIS (14.77 = 14,77%; ver ifdata.py:
    # "o REST devolve FRAÇÃO (0,1477); gravamos em % (×100)"). A CONVENÇÃO
    # INTERNA deste módulo (todo `unidade='pct'` = fração decimal, ver
    # docstring do topo e `_ROTULO_PCT_FRACAO`) exige normalizar de volta para
    # fração aqui — é a ÚNICA leitura com esse desvio de escala (checado
    # chave a chave contra os demais `_calc_*`, todos já fração). A
    # serialização do envelope (`metricas_para_envelope`) reconverte fração ->
    # pontos percentuais de forma UNIFORME para todo `unidade='pct'`.
    return _Resultado(
        valor=_dec(linha.valor) / 100,
        fontes=(fonte,),
        rotulos=tuple(rotulos),
        unidade=_UNIDADE_ENVELOPE.get(linha.unidade, "razao"),
    )


def _calc_roe(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    linha = _fundamento_recente(
        session, ctx, _conta_exata(planos_contas.ROE_CONTA), "ROE (derivado)"
    )
    fonte = _fonte_obrigatoria(session, linha.fonte_id, "ROE")
    return _Resultado(
        valor=_dec(linha.valor),
        fontes=(fonte,),
        rotulos=(
            planos_contas.ROE_METODOLOGIA,
            "derivado reutilizado do ingestor DFP",
            f"exercício {linha.dt_refer.isoformat()}",
            _ROTULO_PCT_FRACAO,
        ),
    )


def _calc_nim(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    resultado_bruto = _fundamento_recente(
        session,
        ctx,
        _conta_codigo("3.03"),
        "resultado bruto da intermediação financeira (conta 3.03)",
    )
    carteira = _indicador_banco(session, ctx, "CARTEIRA_CREDITO")
    if _dec(carteira.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: carteira de crédito não positiva no IF.data — NIM não "
            "interpretável — dado não encontrado"
        )
    fonte_num = _fonte_obrigatoria(session, resultado_bruto.fonte_id, "conta 3.03")
    fonte_den = _fonte_obrigatoria(session, carteira.fonte_id, "carteira de crédito")
    return _Resultado(
        valor=_dec(resultado_bruto.valor) / _dec(carteira.valor),
        fontes=(fonte_num, fonte_den),
        rotulos=(
            "aprox.",
            "numerador da DFP (exercício) e denominador do IF.data (data-base própria) — "
            "datas distintas declaradas nas fontes",
            f"exercício {resultado_bruto.dt_refer.isoformat()} × "
            f"data-base {carteira.dt_referencia.isoformat()} (base {carteira.base})",
            _ROTULO_PCT_FRACAO,
        ),
    )


def _calc_ativos_problematicos(
    session: Session, ctx: ContextoMetricas, hoje: dt.date
) -> _Resultado:
    linha = _indicador_banco(session, ctx, "ATIVOS_PROBLEMATICOS")
    fonte = _fonte_obrigatoria(session, linha.fonte_id, "ativos problemáticos")
    rotulos = [
        "definição da Res. CMN 4.966 — base a partir de 2025, não comparável a séries "
        "anteriores à resolução",
        f"base {linha.base}",
        f"data-base {linha.dt_referencia.isoformat()}",
    ]
    if linha.metodologia:
        rotulos.append(linha.metodologia)
    return _Resultado(
        valor=_dec(linha.valor),
        fontes=(fonte,),
        rotulos=tuple(rotulos),
        unidade=_UNIDADE_ENVELOPE.get(linha.unidade, "razao"),
    )


# ---------------------------------------------------------------------------
# Calculadoras — ação (genérica e energia/transmissão)
# ---------------------------------------------------------------------------


def _calc_pvp_acao(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    preco, data_pregao, fonte_preco = _preco_recente(session, ctx.ticker)
    n, fonte_n = _num_acoes(ctx)
    pl = _fundamento_recente(session, ctx, _e_patrimonio_liquido, "patrimônio líquido")
    if _dec(pl.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: patrimônio líquido não positivo — P/VP não interpretável — "
            "dado não encontrado"
        )
    fonte_pl = _fonte_obrigatoria(session, pl.fonte_id, "patrimônio líquido")
    return _Resultado(
        valor=preco * n / _dec(pl.valor),
        fontes=(fonte_preco, fonte_pl, fonte_n),
        rotulos=(
            _ROTULO_NAO_AJUSTADO,
            f"point-in-time: pregão {data_pregao.isoformat()} × DFP {pl.dt_refer.isoformat()}",
        ),
    )


def _calc_pl_acao(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    preco, data_pregao, fonte_preco = _preco_recente(session, ctx.ticker)
    n, fonte_n = _num_acoes(ctx)
    lucro = _fundamento_recente(session, ctx, _e_lucro_periodo, "lucro líquido do período")
    if _dec(lucro.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: lucro do exercício não positivo — P/L não interpretável — "
            "dado não encontrado"
        )
    fonte_lucro = _fonte_obrigatoria(session, lucro.fonte_id, "lucro do período")
    return _Resultado(
        valor=preco * n / _dec(lucro.valor),
        fontes=(fonte_preco, fonte_lucro, fonte_n),
        rotulos=(
            _ROTULO_NAO_AJUSTADO,
            "lucro do exercício da DFP mais recente (não é LTM)",
            f"point-in-time: pregão {data_pregao.isoformat()} × DFP {lucro.dt_refer.isoformat()}",
        ),
    )


def _calc_ev_ebitda(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    preco, data_pregao, fonte_preco = _preco_recente(session, ctx.ticker)
    n, fonte_n = _num_acoes(ctx)
    ebitda = _fundamento_recente(session, ctx, _conta_exata(_CONTA_EBITDA), "EBITDA (derivado)")
    divida = _fundamento_recente(
        session, ctx, _conta_exata(_CONTA_DIVIDA_LIQUIDA), "dívida líquida (derivada)"
    )
    if ebitda.dt_refer != divida.dt_refer:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: EBITDA e dívida líquida de exercícios distintos — EV não "
            "computado — dado não encontrado"
        )
    if _dec(ebitda.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: EBITDA não positivo — EV/EBITDA não interpretável — "
            "dado não encontrado"
        )
    fonte_ebitda = _fonte_obrigatoria(session, ebitda.fonte_id, "EBITDA")
    fonte_divida = _fonte_obrigatoria(session, divida.fonte_id, "dívida líquida")
    ev = preco * n + _dec(divida.valor)
    return _Resultado(
        valor=ev / _dec(ebitda.valor),
        fontes=(fonte_preco, fonte_ebitda, fonte_divida, fonte_n),
        rotulos=(
            _ROTULO_NAO_AJUSTADO,
            "EBITDA e dívida líquida derivados da DFP (reuso do ingestor)",
            f"point-in-time: pregão {data_pregao.isoformat()} × DFP {ebitda.dt_refer.isoformat()}",
        ),
    )


def _calc_divliq_ebitda(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    ebitda = _fundamento_recente(session, ctx, _conta_exata(_CONTA_EBITDA), "EBITDA (derivado)")
    divida = _fundamento_recente(
        session, ctx, _conta_exata(_CONTA_DIVIDA_LIQUIDA), "dívida líquida (derivada)"
    )
    if ebitda.dt_refer != divida.dt_refer:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: EBITDA e dívida líquida de exercícios distintos — razão não "
            "computada — dado não encontrado"
        )
    if _dec(ebitda.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: EBITDA não positivo — dívida líquida/EBITDA não interpretável — "
            "dado não encontrado"
        )
    fonte_ebitda = _fonte_obrigatoria(session, ebitda.fonte_id, "EBITDA")
    fonte_divida = _fonte_obrigatoria(session, divida.fonte_id, "dívida líquida")
    return _Resultado(
        valor=_dec(divida.valor) / _dec(ebitda.valor),
        fontes=(fonte_divida, fonte_ebitda),
        rotulos=(
            "derivadas da DFP (reuso do ingestor)",
            f"exercício {ebitda.dt_refer.isoformat()}",
        ),
    )


def _calc_margem_liquida(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    lucro = _fundamento_recente(session, ctx, _e_lucro_periodo, "lucro líquido do período")
    receita = _fundamento_recente(session, ctx, _conta_codigo("3.01"), "receita líquida (3.01)")
    if lucro.dt_refer != receita.dt_refer:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: lucro e receita de exercícios distintos — margem não computada — "
            "dado não encontrado"
        )
    if _dec(receita.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: receita não positiva — margem líquida não interpretável — "
            "dado não encontrado"
        )
    fonte_lucro = _fonte_obrigatoria(session, lucro.fonte_id, "lucro do período")
    fonte_receita = _fonte_obrigatoria(session, receita.fonte_id, "receita líquida")
    return _Resultado(
        valor=_dec(lucro.valor) / _dec(receita.valor),
        fontes=(fonte_lucro, fonte_receita),
        rotulos=(f"exercício {lucro.dt_refer.isoformat()}", _ROTULO_PCT_FRACAO),
    )


def _calc_dy_12m_mercado(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    total, n_pagamentos, fonte_prov = _proventos_12m(session, ctx.ticker, hoje)
    preco, data_pregao, fonte_preco = _preco_recente(session, ctx.ticker)
    if preco <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: preço de fechamento não positivo — DY não interpretável — "
            "dado não encontrado"
        )
    corte = hoje - dt.timedelta(days=_JANELA_DY_DIAS)
    return _Resultado(
        valor=total / preco,
        fontes=(fonte_prov, fonte_preco),
        rotulos=(
            "metodologia: soma dos proventos por ação/cota com data-com nos últimos 12 "
            "meses ÷ fechamento do pregão mais recente",
            f"janela {corte.isoformat()} a {hoje.isoformat()} ({n_pagamentos} pagamento(s)); "
            f"pregão {data_pregao.isoformat()}",
            _ROTULO_NAO_AJUSTADO,
            _ROTULO_PCT_FRACAO,
        ),
    )


def _calc_rap(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    linhas = (
        session.execute(
            select(SetorIndicador)
            .where(
                SetorIndicador.ticker == ctx.ticker,
                SetorIndicador.indicador.in_(_INDICADORES_RAP),
            )
            .order_by(SetorIndicador.competencia.desc())
        )
        .scalars()
        .all()
    )
    if not linhas:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: RAP não encontrada em setor_indicadores (sem mapa curado "
            "ANEEL para o ticker ou ingestão pendente) — dado não encontrado"
        )
    linha = linhas[0]
    if not linha.metodologia:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: RAP registrada sem metodologia/escopo de agregação declarado — "
            "abstida — dado não encontrado"
        )
    fonte = _fonte_obrigatoria(session, linha.fonte_id, "RAP")
    return _Resultado(
        valor=_dec(linha.valor),
        fontes=(fonte,),
        rotulos=(linha.metodologia, f"competência {linha.competencia.isoformat()}"),
        unidade=_UNIDADE_ENVELOPE.get(linha.unidade, "BRL"),
    )


# ---------------------------------------------------------------------------
# Calculadoras — FII
# ---------------------------------------------------------------------------


def _calc_pvp_fii(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    preco, data_pregao, fonte_preco = _preco_recente(session, ctx.ticker)
    vp_cota = _indicador_fii(session, ctx, "VP_COTA", hoje)
    if _dec(vp_cota.valor) <= 0:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: VP por cota não positivo — P/VP não interpretável — "
            "dado não encontrado"
        )
    fonte_vp = _fonte_obrigatoria(session, vp_cota.fonte_id, "VP por cota")
    return _Resultado(
        valor=preco / _dec(vp_cota.valor),
        fontes=(fonte_preco, fonte_vp),
        rotulos=(
            _ROTULO_NAO_AJUSTADO,
            "nota de defasagem: preço do pregão "
            f"{data_pregao.isoformat()} × VP por cota da competência "
            f"{vp_cota.dt_referencia.isoformat()} — datas distintas",
        ),
    )


def _calc_dy_informe_fii(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    ind = _indicador_fii(session, ctx, "DY_MES_INFORME", hoje)
    fonte = _fonte_obrigatoria(session, ind.fonte_id, "DY mensal do informe")
    rotulos = [
        "percentual MENSAL em fração decimal — não anualizado",
        f"competência {ind.dt_referencia.isoformat()}",
    ]
    if ind.metodologia:
        rotulos.insert(0, ind.metodologia)
    return _Resultado(valor=_dec(ind.valor), fontes=(fonte,), rotulos=tuple(rotulos))


def _calc_vacancia_fii(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    ind = _indicador_fii(session, ctx, "VACANCIA_AGREGADA", hoje)
    fonte = _fonte_obrigatoria(session, ind.fonte_id, "vacância agregada")
    rotulos = [f"competência {ind.dt_referencia.isoformat()}", _ROTULO_PCT_FRACAO]
    if ind.metodologia:
        rotulos.insert(0, ind.metodologia)
    return _Resultado(valor=_dec(ind.valor), fontes=(fonte,), rotulos=tuple(rotulos))


def _calc_cap_rate_fii(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    """Cap rate: lacuna consciente — nem o de mercado nem a aproximação contábil
    são computáveis com as fontes públicas ingeridas (plano §7)."""
    return _Resultado(valor=None, lacuna=_LACUNA_CAP_RATE)


# ---------------------------------------------------------------------------
# Calculadoras — renda fixa (Tesouro Direto × ETTJ ANBIMA)
# ---------------------------------------------------------------------------


def _calc_inflacao_implicita_rf(
    session: Session, ctx: ContextoMetricas, hoje: dt.date
) -> _Resultado:
    titulo = _titulo_atual(session, ctx, hoje)
    prazo = _prazo_du(titulo["data_vencimento"], hoje)
    vertice = _vertice_proximo(session, "IPCA", prazo, com_implicita=True)
    fonte = _fonte_obrigatoria(session, vertice.fonte_id, "inflação implícita (ETTJ)")
    return _Resultado(
        valor=_dec(vertice.inflacao_implicita) / 100,
        fontes=(fonte,),
        rotulos=(
            f"ANBIMA — ETTJ, snapshot de {vertice.data_ref.isoformat()}",
            f"vértice de {vertice.vertice_du} du — o mais próximo da duration aproximada "
            f"({prazo} du)",
            "duration aproximada pelo prazo até o vencimento (aprox.; exata apenas para "
            "título sem cupom)",
            "convertida de % a.a. (fonte) para fração decimal a.a.",
        ),
    )


def _calc_spread_pre_rf(session: Session, ctx: ContextoMetricas, hoje: dt.date) -> _Resultado:
    titulo = _titulo_atual(session, ctx, hoje)
    if titulo["taxa_compra"] is None:
        raise DadoNaoEncontrado(
            f"{ctx.ticker}: taxa de compra indisponível na Data Base atual (título fora "
            "da janela de oferta) — dado não encontrado"
        )
    prazo = _prazo_du(titulo["data_vencimento"], hoje)
    vertice = _vertice_proximo(session, "PRE", prazo)
    fonte_titulo = _fonte_obrigatoria(session, titulo["fonte_id"], "taxa do título (STN)")
    fonte_vertice = _fonte_obrigatoria(session, vertice.fonte_id, "vértice PRE (ETTJ)")
    spread = (_dec(titulo["taxa_compra"]) - _dec(vertice.taxa)) / 100
    return _Resultado(
        valor=spread,
        fontes=(fonte_titulo, fonte_vertice),
        rotulos=(
            "proxy — comparação entre medidas de naturezas distintas",
            "para título indexado à inflação, a taxa do título é REAL e o vértice PRE é "
            "NOMINAL — a diferença não é prêmio de risco",
            f"Data Base do título {titulo['data_base'].isoformat()} × vértice PRE de "
            f"{vertice.vertice_du} du (snapshot {vertice.data_ref.isoformat()})",
            "convertido de % a.a. para fração decimal a.a.",
        ),
    )


# ---------------------------------------------------------------------------
# Especificações (nome + unidade + fórmula + leitura NEUTRA) e registro
# ---------------------------------------------------------------------------

_ESPEC_BASILEIA = _Espec(
    nome="Índice de Basileia",
    unidade="pct",
    formula="PR / RWA (patrimônio de referência ÷ ativos ponderados pelo risco)",
    o_que_mede="Mede o capital regulatório disponível em relação aos ativos ponderados "
    "pelo risco.",
    implicacao="Quanto maior o índice na data-base, maior a folga de capital frente à "
    "exigência regulatória do BCB; leitura descritiva do dado prudencial.",
    calcular=_calc_basileia,
)

_ESPEC_ROE = _Espec(
    nome="ROE",
    unidade="pct",
    formula="lucro líquido consolidado / patrimônio líquido consolidado (fim de período)",
    o_que_mede="Mede a rentabilidade gerada sobre o patrimônio líquido no exercício.",
    implicacao="ROE mais alto descreve maior lucro por unidade de patrimônio no exercício "
    "coberto pela DFP; leitura descritiva de resultado passado.",
    calcular=_calc_roe,
)

_ESPEC_NIM = _Espec(
    nome="NIM (aproximada)",
    unidade="pct",
    formula="resultado bruto da intermediação financeira (conta 3.03 da DFP) / carteira "
    "de crédito (IF.data)",
    o_que_mede="Aproxima a margem da intermediação financeira sobre a carteira de crédito.",
    implicacao="Valores maiores descrevem margem de intermediação mais alta sobre a "
    "carteira nas datas declaradas; aproximação descritiva, não métrica oficial.",
    calcular=_calc_nim,
)

_ESPEC_ATIVOS_PROBLEMATICOS = _Espec(
    nome="Ativos problemáticos",
    unidade="pct",
    formula="ativos problemáticos conforme definição da Res. CMN 4.966 (IF.data)",
    o_que_mede="Mede o estoque de ativos com deterioração relevante de risco de crédito "
    "na data-base.",
    implicacao="A evolução desse estoque entre datas-base descreve a qualidade da "
    "carteira de crédito; leitura descritiva do dado prudencial.",
    calcular=_calc_ativos_problematicos,
)

_ESPEC_PVP_ACAO = _Espec(
    nome="P/VP",
    unidade="x",
    formula="(preço de fechamento × nº de ações) / patrimônio líquido (DFP)",
    o_que_mede="Compara o valor de mercado da companhia com o patrimônio líquido contábil.",
    implicacao="Acima de 1, o mercado precifica a companhia acima do patrimônio contábil "
    "nas datas comparadas; abaixo de 1, abaixo dele — leitura descritiva point-in-time.",
    calcular=_calc_pvp_acao,
)

_ESPEC_PL_ACAO = _Espec(
    nome="P/L",
    unidade="x",
    formula="(preço de fechamento × nº de ações) / lucro líquido do exercício (DFP)",
    o_que_mede="Compara o valor de mercado com o lucro anual reportado.",
    implicacao="P/L mais alto descreve preço maior por unidade de lucro reportado nas "
    "datas comparadas; leitura descritiva point-in-time.",
    calcular=_calc_pl_acao,
)

_ESPEC_EV_EBITDA = _Espec(
    nome="EV/EBITDA",
    unidade="x",
    formula="(preço de fechamento × nº de ações + dívida líquida) / EBITDA " "(EBIT + D&A da DFC)",
    o_que_mede="Compara o valor da firma (equity + dívida líquida) com a geração "
    "operacional aproximada de caixa.",
    implicacao="Múltiplos maiores descrevem valor de firma mais alto por unidade de "
    "EBITDA nas datas comparadas; leitura descritiva point-in-time.",
    calcular=_calc_ev_ebitda,
)

_ESPEC_DIVLIQ_EBITDA = _Espec(
    nome="Dívida líquida/EBITDA",
    unidade="x",
    formula="dívida líquida (derivada da DFP) / EBITDA (derivado da DFP)",
    o_que_mede="Mede quantos anos de EBITDA equivalem à dívida líquida do exercício.",
    implicacao="Razões maiores descrevem endividamento líquido mais alto em relação à "
    "geração operacional do exercício; leitura descritiva de alavancagem.",
    calcular=_calc_divliq_ebitda,
)

_ESPEC_MARGEM_LIQUIDA = _Espec(
    nome="Margem líquida",
    unidade="pct",
    formula="lucro líquido do exercício / receita líquida (mesmo exercício da DFP)",
    o_que_mede="Mede a fração da receita que se converteu em lucro no exercício.",
    implicacao="Margens maiores descrevem conversão mais alta de receita em lucro no "
    "exercício reportado; leitura descritiva de resultado passado.",
    calcular=_calc_margem_liquida,
)

_ESPEC_DY_12M_MERCADO = _Espec(
    nome="Dividend yield 12m a mercado",
    unidade="pct",
    formula="Σ proventos por ação/cota com data-com nos últimos 12 meses / último preço "
    "de fechamento",
    o_que_mede="Mede o rendimento distribuído nos últimos 12 meses em relação ao preço "
    "corrente.",
    implicacao="DY maior descreve distribuição maior relativa ao preço no período "
    "observado; é retrato do passado, não estimativa de rendimento futuro.",
    calcular=_calc_dy_12m_mercado,
)

_ESPEC_RAP = _Espec(
    nome="RAP (Receita Anual Permitida)",
    unidade="BRL",
    formula="RAP homologada pela ANEEL para as concessões do grupo, agregada conforme a "
    "metodologia declarada",
    o_que_mede="Mede a receita regulada de transmissão homologada para o ciclo tarifário.",
    implicacao="A RAP descreve o teto de receita regulada do ciclo homologado; contexto "
    "regulatório com reajuste definido em contrato, não projeção.",
    calcular=_calc_rap,
)

_ESPEC_PVP_FII = _Espec(
    nome="P/VP a mercado",
    unidade="x",
    formula="preço de fechamento (COTAHIST) / valor patrimonial por cota (informe mensal " "CVM)",
    o_que_mede="Compara o preço de mercado da cota com o valor patrimonial declarado no "
    "informe.",
    implicacao="Acima de 1, a cota negocia acima do valor patrimonial declarado nas datas "
    "comparadas; abaixo de 1, abaixo dele — leitura descritiva com defasagem declarada.",
    calcular=_calc_pvp_fii,
)

_ESPEC_DY_INFORME_FII = _Espec(
    nome="Dividend yield mensal (informe)",
    unidade="pct",
    formula="dividend yield do mês auto-declarado pelo administrador no informe mensal CVM",
    o_que_mede="Mede o rendimento distribuído no mês de competência do informe.",
    implicacao="O valor descreve a distribuição de um único mês, conforme declarado pelo "
    "administrador; não é anualizado nem é promessa de recorrência.",
    calcular=_calc_dy_informe_fii,
)

_ESPEC_VACANCIA_FII = _Espec(
    nome="Vacância agregada",
    unidade="pct",
    formula="média das vacâncias por imóvel ponderada pela área (m²) — informe trimestral " "CVM",
    o_que_mede="Mede a fração da área dos imóveis do fundo sem ocupação no trimestre.",
    implicacao="Vacância maior descreve menor ocupação física do portfólio no trimestre "
    "reportado; leitura descritiva do dado auto-declarado.",
    calcular=_calc_vacancia_fii,
)

_ESPEC_CAP_RATE_FII = _Espec(
    nome="Cap rate",
    unidade="pct",
    formula="receita anual de aluguel / valor do portfólio (aproximação contábil: / "
    "patrimônio líquido)",
    o_que_mede="Mediria o rendimento operacional dos imóveis em relação ao valor do " "portfólio.",
    implicacao="Sem dado público disponível, nenhuma leitura é feita — a lacuna é "
    "declarada em vez de estimada.",
    calcular=_calc_cap_rate_fii,
)

_ESPEC_INFLACAO_IMPLICITA_RF = _Espec(
    nome="Inflação implícita (vértice ANBIMA)",
    unidade="pct",
    formula="inflação implícita do vértice da ETTJ (ANBIMA) mais próximo da duration "
    "aproximada do título",
    o_que_mede="Mede a inflação embutida na diferença entre as curvas PRE e IPCA no "
    "prazo do título.",
    implicacao="O valor descreve a inflação precificada pelo mercado no snapshot e no "
    "vértice declarados; leitura descritiva, não previsão própria.",
    calcular=_calc_inflacao_implicita_rf,
)

_ESPEC_SPREAD_PRE_RF = _Espec(
    nome="Diferencial vs vértice PRE (proxy)",
    unidade="pct",
    formula="taxa de compra do título (STN) − taxa do vértice PRE da ETTJ (ANBIMA) mais "
    "próximo do prazo",
    o_que_mede="Mede a distância entre a taxa contratável do título e o vértice "
    "prefixado da curva de referência.",
    implicacao="O diferencial descreve o posicionamento da taxa do título frente ao "
    "vértice comparável nas datas declaradas; leitura descritiva de um proxy.",
    calcular=_calc_spread_pre_rf,
)

# Chave: (classe, plano_contas | None = qualquer, setor-chave | None = qualquer).
# A PRIMEIRA entrada que casa vence (ordem = precedência, mais específica antes).
_Chave = tuple[str, str | None, str | None]

_REGISTRO: tuple[tuple[_Chave, tuple[_Espec, ...]], ...] = (
    (
        ("acao", "banco", None),
        (_ESPEC_BASILEIA, _ESPEC_ROE, _ESPEC_NIM, _ESPEC_ATIVOS_PROBLEMATICOS, _ESPEC_PVP_ACAO),
    ),
    (
        ("acao", None, "energia_transmissao"),
        (_ESPEC_RAP, _ESPEC_DY_12M_MERCADO, _ESPEC_PL_ACAO),
    ),
    (
        ("acao", None, None),
        (
            _ESPEC_PL_ACAO,
            _ESPEC_EV_EBITDA,
            _ESPEC_DIVLIQ_EBITDA,
            _ESPEC_MARGEM_LIQUIDA,
            _ESPEC_PVP_ACAO,
        ),
    ),
    (
        ("fii", None, None),
        (
            _ESPEC_PVP_FII,
            _ESPEC_DY_INFORME_FII,
            _ESPEC_DY_12M_MERCADO,
            _ESPEC_VACANCIA_FII,
            _ESPEC_CAP_RATE_FII,
        ),
    ),
    (
        ("renda_fixa", None, None),
        (_ESPEC_INFLACAO_IMPLICITA_RF, _ESPEC_SPREAD_PRE_RF),
    ),
)


def _chave_setor(setor: str | None) -> str | None:
    """Normaliza o setor livre (B3/CVM) para a chave do registro.

    Mesma detecção por substring de `valuation._e_setor_energia` — v1 só tem a
    vertical energia/transmissão; setor sem chave própria cai na entrada genérica.
    """
    ds = _normalizar_ds(setor or "")
    if any(p in ds for p in ("energ", "eletric", "transmiss")):
        return "energia_transmissao"
    return None


def _resolver_especs(ctx: ContextoMetricas) -> tuple[_Espec, ...]:
    """Entrada mais específica do registro para (classe, plano, setor)."""
    classe = (ctx.classe or "acao").strip().lower()
    plano = (ctx.plano_contas or "").strip().lower() or None
    setor = _chave_setor(ctx.setor)
    for (chave_classe, chave_plano, chave_setor), especs in _REGISTRO:
        if chave_classe != classe:
            continue
        if chave_plano is not None and chave_plano != plano:
            continue
        if chave_setor is not None and chave_setor != setor:
            continue
        return especs
    return ()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def calcular(
    session: Session,
    contexto: ContextoMetricas,
    *,
    hoje: dt.date | None = None,
) -> list[MetricaSetor]:
    """Métricas do setor/classe do contexto — abstenção rotulada, nunca exceção de dado.

    Resolve a entrada do registro por (classe, plano_contas, setor) e roda cada
    calculadora isolada num SAVEPOINT: dado ausente/stale/sem fonte vira
    ``valor=None`` + ``lacuna``; tabela inexistente degrada (A13); classe sem
    entrada no registro devolve lista vazia (a F3 decide). ``hoje`` é injetável
    para teste (default: ``date.today()``).
    """
    hoje = hoje or dt.date.today()
    especs = _resolver_especs(contexto)
    if not especs:
        logger.info(
            "metricas_setor_sem_registro",
            ticker=contexto.ticker,
            classe=contexto.classe,
            plano=contexto.plano_contas,
            setor=contexto.setor,
        )
        return []
    metricas = [_rodar(espec, session, contexto, hoje) for espec in especs]
    logger.info(
        "metricas_setor_calculadas",
        ticker=contexto.ticker,
        total=len(metricas),
        com_valor=sum(1 for m in metricas if m.valor is not None),
        lacunas=sum(1 for m in metricas if m.lacuna is not None),
    )
    return metricas


def metricas_para_envelope(metricas: list[MetricaSetor]) -> list[dict]:
    """Serializa para o bloco `metricas_setor` do envelope v3 (§5): Decimal ->
    number, datas -> ISO, tuplas -> listas.

    Reconciliação de escala (decisão do maestro, 2026-07-10): internamente
    `unidade='pct'` é SEMPRE fração decimal (0,15 = 15%, convenção deste
    módulo — ver `_calc_basileia`, já normalizada). NO ENVELOPE, `pct` é
    PONTOS PERCENTUAIS (contrato v3: 14.77 -> exibe "14,77%") — o frontend
    NÃO multiplica por 100. Esta função faz a ÚNICA conversão fração->pontos,
    de forma UNIFORME para toda métrica `unidade='pct'` com valor presente.
    """

    def _fonte(f: FonteMetrica) -> dict:
        return {
            "descricao": f.descricao,
            "url": f.url,
            "dt_referencia": f.dt_referencia.isoformat() if f.dt_referencia else None,
        }

    def _valor_envelope(m: MetricaSetor) -> float | None:
        if m.valor is None:
            return None
        if m.unidade == "pct":
            # Multiplica ainda em Decimal (exato) antes de converter — evita
            # arredondamento duplo do float (Decimal("0.168")*100 == 16.800
            # exato; `float(m.valor) * 100` já parte de um float arredondado).
            return float(m.valor * 100)
        return float(m.valor)

    return [
        {
            "nome": m.nome,
            "valor": _valor_envelope(m),
            "unidade": m.unidade,
            "formula": m.formula,
            "o_que_mede": m.o_que_mede,
            "implicacao": m.implicacao,
            "fontes": [_fonte(f) for f in m.fontes],
            "rotulos": list(m.rotulos),
            "lacuna": m.lacuna,
        }
        for m in metricas
    ]
