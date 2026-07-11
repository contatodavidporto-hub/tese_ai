"""Orquestração da ingestão das 5 dimensões, com falha ISOLADA por fonte.

Uma fonte indisponível não derruba as demais (cada passo abstém e registra). A
ingestão dos PARES (a mais pesada) já é paralela internamente (sec.ingest_pares via
map_concorrente, respeitando 10 req/s da SEC). Persistência serial no orquestrador
(Session não é thread-safe — achado M4). Commit único ao final.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.models import Empresa, FiiCadastro, Fundamento
from app.services import (
    anbima_ettj,
    aneel,
    commodities,
    cotahist,
    fii_dados,
    focus,
    ifdata,
    macro_global,
    planos_contas,
    proventos_b3,
    sec,
    tesouro,
)
from app.services import dados as dados_svc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)

# Ticker do ETF de referência do Ibovespa (CODBDI 14, sonda A9) — série usada
# pelo motor (F3) para o β "aproximado" vs BOVA11 no COTAHIST (SGS 7/nível do
# Ibovespa está descontinuada). Backfillado junto com o ticker da tese: toda
# tese de ação/FII ganha a série de mercado necessária ao β sem passo extra.
TICKER_MERCADO_BETA = "BOVA11"


def _e_setor_energia_transmissao(setor: str | None) -> bool:
    """Mesma detecção por substring de `valuation._e_setor_energia` (v1 só tem
    a vertical energia/transmissão) — cópia local pequena e deliberada para
    não acoplar `orquestracao` (ingest) a `valuation` (cálculo determinístico
    puro), que são camadas diferentes do pipeline (plano §2.1)."""
    s = (setor or "").lower()
    return "energ" in s or "transmiss" in s or "eletric" in s or "elétric" in s


def _tem_fundamento(session: Session, empresa: Empresa) -> bool:
    """Mesma checagem de `acao.precisa_ingest` — duplicação pequena e
    deliberada (orquestracao é a camada INFERIOR; não importa `ativos.acao`,
    que já importa `orquestracao`). True quando a empresa já tem QUALQUER
    fundamento persistido.

    Usada para pular o passo mais caro do re-ingest (download multi-ano da
    DFP) quando o gatilho foi só preço stale (correção do bug "tese legada
    silenciosa", 2026-07-11): os demais conectores (COTAHIST/proventos/
    IF.data/ANEEL) já se auto-noop quando os próprios dados estão frescos —
    só a DFP baixava tudo de novo incondicionalmente."""
    return (
        session.execute(
            select(Fundamento.id).where(Fundamento.empresa_id == empresa.id).limit(1)
        ).first()
        is not None
    )


def _passos_isolados(
    session: Session, resultados: dict[str, str]
) -> Callable[[str, Callable[[], object]], None]:
    def passo(nome: str, fn: Callable[[], object]) -> None:
        try:
            # SAVEPOINT por passo (achado MÉDIO da auditoria da fase 1): uma
            # exceção no meio de um passo desfaz SÓ o DML dele — o snapshot
            # antigo sobrevive (ex.: delete+insert dos pares) e os passos que
            # já deram certo seguem para o commit único do chamador.
            with session.begin_nested():
                fn()
            resultados[nome] = "ok"
        except Exception as exc:  # falha isolada — não aborta o conjunto
            resultados[nome] = f"falha: {type(exc).__name__}"
            logger.warning("ingest_passo_falhou", passo=nome, erro=type(exc).__name__)

    return passo


def ingest_macro_refresh(session: Session) -> dict[str, str]:
    """Refresh das séries macro GLOBAIS (independentes de empresa): BCB (D3),
    Brent (D3), World Bank + Treasury (D4). Idempotente (upsert por série/data);
    é o corpo do job agendado `refresh_macro` e pode rodar sozinho num cron."""
    resultados: dict[str, str] = {}
    passo = _passos_isolados(session, resultados)

    passo("macro_br", lambda: dados_svc.ingest_macro(session))
    passo("usd_historico", lambda: dados_svc.ingest_usd_historico(session))
    passo("commodities_brent", lambda: commodities.ingest_brent(session))
    passo("brent_historico", lambda: commodities.ingest_brent_historico(session))
    passo("macro_global_wb", lambda: macro_global.ingest_world_bank(session))
    passo("macro_global_treasury", lambda: macro_global.ingest_treasury_10y(session))

    session.commit()
    logger.info("ingest_macro_refresh", resultados=resultados)
    return resultados


def ingest_completo(session: Session, empresa: Empresa) -> dict[str, str]:
    """Ingere fundamentos (D1) + macro BR (D3) + Brent (D3) + macro global (D4) +
    pares globais (D2) + ingest AMPLIADO da Fase "Tese Profunda" (F3, plano
    §2.1): COTAHIST (preço + BOVA11 p/ β aproximado) + proventos B3 (DY a
    mercado) sempre; IF.data quando o filing detectou plano financeiro
    (banco/seguradora — só banco tem mapa curado, IF.data abstém gracioso
    para seguradora); ANEEL RAP quando o setor é energia/transmissão. Cada
    passo é isolado (SAVEPOINT); falha de conector NUNCA derruba a tese —
    vira lacuna rotulada, lida a jusante pelo motor (`tese.py`)."""
    resultados: dict[str, str] = {}
    passo = _passos_isolados(session, resultados)

    if _tem_fundamento(session, empresa):
        # Reingest disparado só por preço stale (`perfil.precisa_ingest`,
        # F3): a DFP já foi baixada e persistida — pula o passo mais caro
        # (download multi-ano da CVM) e deixa os conectores restantes
        # (COTAHIST/proventos/IF.data/ANEEL/macro/pares) disparar
        # normalmente, cada um já auto-noop quando fresco.
        resultados["fundamentos"] = "pulado: empresa já tem fundamento persistido"
    else:
        passo("fundamentos", lambda: dados_svc.ingest_fundamentos(session, empresa))
    # A partir daqui `empresa.plano_contas`/`empresa.setor` já refletem o filing
    # (setados por `ingest_fundamentos`/identidade antes deste ponto) — SÓ quando
    # o passo rodou; num reingest pulado, os dois já vêm do filing anterior.
    ticker = (empresa.ticker or "").strip().upper()
    if ticker:
        passo("cotahist_precos", lambda: cotahist.ensure_precos(session, ticker))
        passo("cotahist_bova11", lambda: cotahist.ensure_precos(session, TICKER_MERCADO_BETA))
        passo("proventos_b3", lambda: proventos_b3.ensure_proventos(session, ticker))
    if empresa.plano_contas in planos_contas.PLANOS_FINANCEIROS and empresa.cd_cvm is not None:
        passo(
            "ifdata_banco",
            lambda: ifdata.ensure_indicadores_banco(session, empresa.cd_cvm),
        )
    if ticker and _e_setor_energia_transmissao(empresa.setor):
        passo("aneel_rap", lambda: aneel.ensure_rap(session, ticker))
    passo("macro_br", lambda: dados_svc.ingest_macro(session))
    passo("usd_historico", lambda: dados_svc.ingest_usd_historico(session))
    passo("commodities_brent", lambda: commodities.ingest_brent(session))
    passo("brent_historico", lambda: commodities.ingest_brent_historico(session))
    passo("macro_global_wb", lambda: macro_global.ingest_world_bank(session))
    passo("macro_global_treasury", lambda: macro_global.ingest_treasury_10y(session))
    passo("pares_globais", lambda: sec.ingest_pares(session, empresa))

    session.commit()
    logger.info("ingest_completo", ticker=empresa.ticker, resultados=resultados)
    return resultados


def ingest_fii_completo(session: Session, fii: FiiCadastro) -> dict[str, str]:
    """Ingestão da classe FII (etapa 11/D): informes mensais (indicadores) +
    vacância trimestral + ingest AMPLIADO (F3, plano §2.1) — COTAHIST (preço
    de mercado da cota) e proventos B3 (DY a mercado), NESTA ORDEM (informes
    ANTES de proventos: `fii_cadastro.isin`, exigido pelo conector de
    proventos, é populado pelo informe geral já resolvido em `ensure_ativo`/
    `fii_indicadores`) — + macro BR (Selic/IPCA) + CDI + Focus. Cada passo é
    isolado (SAVEPOINT): Olinda fora do ar degrada para as séries factuais do
    SGS sem derrubar a tese. Sem ticker (heurística de ISIN zerada por
    colisão) os passos de B3 são pulados — não há como consultar COTAHIST/
    proventos sem o código de negociação. Commit único ao final."""
    resultados: dict[str, str] = {}
    passo = _passos_isolados(session, resultados)

    if fii_dados.indicadores_recentes(session, fii):
        # Reingest disparado só por preço stale (`perfil.precisa_ingest`,
        # F3): o informe mensal já está fresco — pula os dois passos de
        # informe (mensal/trimestral, os mais caros: multi-ano da CVM) e
        # deixa COTAHIST/proventos disparar normalmente.
        resultados["fii_indicadores"] = "pulado: indicador já fresco"
        resultados["fii_vacancia"] = "pulado: indicador já fresco"
    else:
        passo("fii_indicadores", lambda: fii_dados.ingest_indicadores(session, fii))
        passo("fii_vacancia", lambda: fii_dados.ingest_vacancia(session, fii))
    ticker = (fii.ticker or "").strip().upper()
    if ticker:
        passo("fii_cotahist_precos", lambda: cotahist.ensure_precos(session, ticker))
        passo("fii_proventos_b3", lambda: proventos_b3.ensure_proventos(session, ticker))
    passo("macro_br", lambda: dados_svc.ingest_macro(session))
    passo("cdi", lambda: focus.ingest_cdi(session))
    passo("focus", lambda: focus.ingest_focus(session))

    session.commit()
    logger.info("ingest_fii_completo", cnpj=fii.cnpj, ticker=fii.ticker, resultados=resultados)
    return resultados


def ingest_renda_fixa_completo(session: Session, familia: str, ano: int) -> dict[str, str]:
    """Ingestão da classe RENDA_FIXA (etapa 11/D): SÓ o título pedido (janela
    limitada — o CSV completo da STN nunca entra cru) + CDI (fato, SGS) +
    Focus (expectativa, Olinda; falha degrada para o SGS) + ingest AMPLIADO
    (F3, plano §2.1): snapshot ANBIMA ETTJ do dia (inflação implícita/proxy da
    curva soberana — TRAVA ToS: nunca série histórica, `ensure_snapshot`
    ingere só o dia). Passos isolados, commit único ao final."""
    resultados: dict[str, str] = {}
    passo = _passos_isolados(session, resultados)

    passo("titulo_tesouro", lambda: tesouro.ingest_titulo(session, familia, ano))
    passo("anbima_ettj", lambda: anbima_ettj.ensure_snapshot(session))
    passo("cdi", lambda: focus.ingest_cdi(session))
    passo("focus", lambda: focus.ingest_focus(session))

    session.commit()
    logger.info(
        "ingest_renda_fixa_completo",
        familia=familia.upper(),
        ano=ano,
        resultados=resultados,
    )
    return resultados
