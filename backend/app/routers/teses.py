"""Endpoints do motor de tese.

POST /teses {ticker}  -> exige conta; cria a tese PRIVADA do usuário (status
                         processing) e dispara o job de geração (lane worker).
                         Cache: acervo público da vitrine OU a própria tese recente.
GET  /teses/{id}      -> público-ou-do-dono: tese pública renderiza para qualquer um
                         (vitrine 100% pública), tese privada só para o dono (o IDOR
                         de antes está morto). RLS (lane) é a camada A; o filtro
                         explícito aqui é a camada B.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Identidade, usuario_atual
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.ratelimit import limiter
from app.db import rls
from app.db.session import SessionLocal
from app.models.models import Tese, TeseVersao
from app.schemas.tese import TeseCreateIn, TeseCreateOut, TeseOut
from app.services.ativos.identidade import resolver_classe
from app.services.dados import DadoNaoEncontrado
from app.services.tese import buscar_tese_do_usuario, buscar_tese_publica, criar_tese, gerar_tese

logger = get_logger(__name__)
router = APIRouter(prefix="/teses", tags=["teses"])

# Limite específico da criação de tese (dispara o LLM caro). No-op se desabilitado.
_settings = get_settings()


def _rate_limit_criar():
    """Decorator de rate-limit da criação (no-op se desabilitado no settings)."""
    if not _settings.rate_limit_criar_tese:
        return lambda fn: fn
    return limiter.limit(_settings.rate_limit_criar_tese)


def _run_generation(tese_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
    """Executa o job de geração fora da request.

    Preferência: lane `app_worker` (NOBYPASSRLS; escreve referência + dados do
    usuário via policies `worker_all_*`). Sem a lane de RLS configurada
    (dev/CI sem `app_backend`), cai no engine de sistema (`SessionLocal`). O
    `user_id` já está gravado na `Tese`; o job herda dono/visibilidade da tese-mãe.
    """
    if rls.SessionRLS is not None:
        with rls.nova_sessao_worker() as session:
            gerar_tese(session, tese_id)
        return
    if SessionLocal is not None:
        session = SessionLocal()
        try:
            gerar_tese(session, tese_id)
        finally:
            session.close()
        return
    logger.warning("sem_banco_para_job", tese_id=str(tese_id))


@router.post("", response_model=TeseCreateOut, status_code=202)
@_rate_limit_criar()
def post_tese(
    request: Request,
    response: Response,  # exigido pelo slowapi p/ injetar os headers X-RateLimit-*
    body: TeseCreateIn,
    background: BackgroundTasks,
    identidade: Annotated[Identidade, Depends(usuario_atual)],
    session: Annotated[Session, Depends(rls.get_session_usuario)],
) -> TeseCreateOut:
    user_id = uuid.UUID(identidade.user_id)

    # Cache (sob a lane do usuário, que enxerga público ∪ próprio): 1) acervo público
    # da vitrine (compartilhado por desenho); 2) a própria tese recente do usuário.
    # Nunca serve tese privada de OUTRO usuário (o cache por ticker cross-user morreu).
    publica = buscar_tese_publica(session, body.ticker, _settings.tese_cache_horas)
    if publica is not None:
        logger.info("tese_cache_hit_publica", tese_id=str(publica.id), ticker=publica.ticker)
        return TeseCreateOut(id=publica.id, ticker=publica.ticker, status=publica.status)
    propria = buscar_tese_do_usuario(session, user_id, body.ticker, _settings.tese_cache_horas)
    if propria is not None:
        logger.info("tese_cache_hit_propria", tese_id=str(propria.id), ticker=propria.ticker)
        return TeseCreateOut(id=propria.id, ticker=propria.ticker, status=propria.status)

    # Identidade do ativo (D4/etapa 6): resolve a classe p/ gravar as classes NOVAS.
    # Abstenção (DadoNaoEncontrado) NÃO muda o contrato do POST (o job abstém).
    classe: str | None = None
    try:
        classe, _payload = resolver_classe(body.ticker, session)
    except DadoNaoEncontrado as exc:
        logger.warning("classe_ativo_nao_resolvida", ticker=body.ticker, detalhe=str(exc))

    # Miss: cria tese PRIVADA do usuário (visibilidade='privada' — a policy restrictive
    # impede que o caminho `authenticated` crie pública).
    tese = criar_tese(session, body.ticker, user_id=user_id, visibilidade="privada")
    if classe is not None and classe != "acao":
        # NULL = 'acao' (migração 0005) mantém o caminho legado byte-idêntico.
        tese.classe_ativo = classe
        session.commit()
    background.add_task(_run_generation, tese.id, user_id)
    logger.info("tese_enfileirada", tese_id=str(tese.id), ticker=tese.ticker, classe_ativo=classe)
    return TeseCreateOut(id=tese.id, ticker=tese.ticker, status=tese.status)


@router.get("/{tese_id}", response_model=TeseOut)
def get_tese(
    tese_id: uuid.UUID,
    session: Annotated[Session, Depends(rls.get_session_leitura)],
    request: Request,
) -> TeseOut:
    tese = session.get(Tese, tese_id)
    if tese is None:
        raise HTTPException(status_code=404, detail="tese não encontrada")

    # Camada B (o filtro explícito; a RLS da lane é a camada A): tese pública renderiza
    # para qualquer um; tese privada só para o dono. 404 UNIFORME com inexistente
    # (nunca 403) — sem oráculo de existência de UUID.
    identidade = getattr(request.state, "identidade", None)
    e_publica = getattr(tese, "visibilidade", None) == "publica"
    e_do_dono = (
        identidade is not None
        and getattr(tese, "user_id", None) is not None
        and str(tese.user_id) == identidade.user_id
    )
    if not (e_publica or e_do_dono):
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
    # Blocos novos ("Tese Profunda", contrato-envelope-v3.md) — só chegam a
    # este ponto quando status != error e o envelope não tem 'erro' (o `if`
    # acima já retornou antes disso) — fail-closed já garantido pela guarda
    # de cima; aqui só espelha `env.get(...)` (ausência = tese legada/sem
    # dado novo, seção correspondente não aparece na UI).
    out.graficos = env.get("graficos", []) or []
    out.tecnica = env.get("tecnica")
    out.valuation = env.get("valuation")
    out.consenso = env.get("consenso")
    out.metricas_setor = env.get("metricas_setor", []) or []
    return out
