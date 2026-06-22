"""Endpoints do motor de tese.

POST /teses {ticker}  -> cria a tese (status processing) e dispara o job assíncrono.
GET  /teses/{id}      -> devolve a tese + citações + fontes + lacunas (trilha auditável).
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal, get_session
from app.models.models import Tese, TeseVersao
from app.schemas.tese import TeseCreateIn, TeseCreateOut, TeseOut
from app.services.tese import criar_tese, gerar_tese

logger = get_logger(__name__)
router = APIRouter(prefix="/teses", tags=["teses"])


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
def post_tese(
    body: TeseCreateIn,
    background: BackgroundTasks,
    session: Annotated[Session, Depends(get_session)],
) -> TeseCreateOut:
    tese = criar_tese(session, body.ticker)
    background.add_task(_run_generation, tese.id)
    logger.info("tese_enfileirada", tese_id=str(tese.id), ticker=tese.ticker)
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

    out = TeseOut(id=tese.id, ticker=tese.ticker, status=tese.status, criado_em=tese.criado_em)
    if versao is None or not versao.conteudo:
        return out

    try:
        env = json.loads(versao.conteudo)
    except json.JSONDecodeError:
        env = {"markdown": versao.conteudo}

    out.erro = env.get("erro")
    out.markdown = env.get("markdown")
    out.citacoes = env.get("citacoes", []) or []
    out.fontes = env.get("fontes", []) or []
    out.lacunas = env.get("lacunas", []) or []
    out.uso = env.get("uso")
    return out
