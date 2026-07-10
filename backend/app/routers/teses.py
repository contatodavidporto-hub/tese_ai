"""Endpoints do motor de tese.

POST /teses {ticker}  -> cria a tese (status processing) e dispara o job assíncrono.
GET  /teses/{id}      -> devolve a tese + citações + fontes + lacunas (trilha auditável).
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.ratelimit import limiter
from app.db.session import SessionLocal, get_session
from app.models.models import Tese, TeseVersao
from app.schemas.tese import TeseCreateIn, TeseCreateOut, TeseOut
from app.services.ativos.identidade import resolver_classe
from app.services.dados import DadoNaoEncontrado
from app.services.tese import buscar_tese_cache, criar_tese, gerar_tese, reaper_teses_orfas

logger = get_logger(__name__)
router = APIRouter(prefix="/teses", tags=["teses"])

# Limite específico da criação de tese (dispara o LLM caro). No-op se desabilitado.
_settings = get_settings()


def _rate_limit_criar():
    """Decorator de rate-limit da criação (no-op se desabilitado no settings)."""
    if not _settings.rate_limit_criar_tese:
        return lambda fn: fn
    return limiter.limit(_settings.rate_limit_criar_tese)


def _run_generation(tese_id: uuid.UUID) -> None:
    """Executa o job num escopo de sessão próprio (fora da request)."""
    if SessionLocal is None:
        logger.warning("sem_banco_para_job", tese_id=str(tese_id))
        return
    session = SessionLocal()
    try:
        gerar_tese(session, tese_id)
    finally:
        session.close()


@router.post("", response_model=TeseCreateOut, status_code=202)
@_rate_limit_criar()
def post_tese(
    request: Request,
    response: Response,  # exigido pelo slowapi p/ injetar os headers X-RateLimit-*
    body: TeseCreateIn,
    background: BackgroundTasks,
    session: Annotated[Session, Depends(get_session)],
) -> TeseCreateOut:
    # Reaper oportunista: limpa teses `processing` órfãs (crash) — barato e indexado.
    reaper_teses_orfas(session, _settings.tese_processing_timeout_min)

    # Cache/idempotência: reaproveita uma tese `ready` recente do mesmo ticker em vez
    # de gastar o LLM de novo (custo + latência). Não dispara geração no hit.
    cache = buscar_tese_cache(session, body.ticker, _settings.tese_cache_horas)
    if cache is not None:
        logger.info("tese_cache_hit", tese_id=str(cache.id), ticker=cache.ticker)
        return TeseCreateOut(id=cache.id, ticker=cache.ticker, status=cache.status)

    # Identidade do ativo (D4/etapa 6): TD-* -> renda_fixa; sufixo 11-13 consulta
    # cvm_cadastro (units vencem) e depois fii_cadastro; demais sufixos -> ação.
    # Abstenção (DadoNaoEncontrado) NÃO muda o contrato do POST: o job de geração
    # abstém como sempre ("dado não encontrado") — comportamento legado intacto.
    classe: str | None = None
    try:
        classe, _payload = resolver_classe(body.ticker, session)
    except DadoNaoEncontrado as exc:
        logger.warning("classe_ativo_nao_resolvida", ticker=body.ticker, detalhe=str(exc))

    tese = criar_tese(session, body.ticker)
    if classe is not None and classe != "acao":
        # Grava só as classes NOVAS: NULL = 'acao' (migração 0005) mantém o
        # caminho legado da ação byte-idêntico (sem escrita/commit extra).
        tese.classe_ativo = classe
        session.commit()
    background.add_task(_run_generation, tese.id)
    logger.info("tese_enfileirada", tese_id=str(tese.id), ticker=tese.ticker, classe_ativo=classe)
    return TeseCreateOut(id=tese.id, ticker=tese.ticker, status=tese.status)


@router.get("/{tese_id}", response_model=TeseOut)
def get_tese(tese_id: uuid.UUID, session: Annotated[Session, Depends(get_session)]) -> TeseOut:
    tese = session.get(Tese, tese_id)
    if tese is None:
        raise HTTPException(status_code=404, detail="tese não encontrada")

    versao = session.execute(
        select(TeseVersao)
        .where(TeseVersao.tese_id == tese.id)
        .order_by(TeseVersao.criado_em.desc())
        .limit(1)
    ).scalar_one_or_none()

    out = TeseOut(
        id=tese.id,
        ticker=tese.ticker,
        status=tese.status,
        # getattr: robusto a teses fake/legadas sem o atributo (aditivo, D4).
        classe_ativo=getattr(tese, "classe_ativo", None),
        criado_em=tese.criado_em,
    )
    if versao is None or not versao.conteudo:
        return out

    try:
        env = json.loads(versao.conteudo)
    except json.JSONDecodeError:
        env = {"markdown": versao.conteudo}

    out.erro = env.get("erro")
    # Defesa em profundidade (achado MÉDIO do auditor-mor): se a tese foi reprovada
    # pelo gate ou falhou (status=error / envelope com 'erro'), NÃO servir o markdown
    # nem as citações — só o erro e as lacunas. Um conteúdo que vazou recomendação
    # não pode chegar ao cliente mesmo com o status sinalizando falha.
    if tese.status == "error" or env.get("erro"):
        out.lacunas = env.get("lacunas", []) or []
        return out

    out.markdown = env.get("markdown")
    out.citacoes = env.get("citacoes", []) or []
    out.fontes = env.get("fontes", []) or []
    out.lacunas = env.get("lacunas", []) or []
    out.uso = env.get("uso")
    return out
