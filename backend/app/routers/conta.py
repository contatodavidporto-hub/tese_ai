"""Endpoints de conta (missão "A Portaria", Onda 3) — chamados pelo BFF (Next), atrás
do perímetro X-Portaria + JWT verificado.

- 2FA: os passos de enroll/verify/unenroll do TOTP acontecem no BFF (GoTrue via
  @supabase/ssr). AQUI ficam só os que exigem o service_role ou o cofre de códigos:
  gerar códigos de recuperação, break-glass (perda do 2º fator) e LGPD (exportar/excluir).
- `exigir_aal2`: operação sensível de quem TEM fator TOTP verificado exige sessão aal2
  (um access token aal1 roubado não troca senha nem apaga a conta). Quem não tem 2FA
  passa com aal1 (é o nível máximo dele) — mesma lógica da policy `tem_fator_totp_verified`.

Sessão = engine de SISTEMA (postgres): o cofre é deny-all (só bypassrls acessa) e a
exportação é uma operação de servidor confiável escopada pelo `user_id` do JWT verificado.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Identidade, usuario_atual
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.ratelimit import limiter
from app.db.session import get_session
from app.models.models import HistoricoItem, Tese, TeseVersao
from app.schemas.conta import CodigosOut, OkOut, RecuperacaoIn
from app.services import mfa

logger = get_logger(__name__)
router = APIRouter(prefix="/conta", tags=["conta"])
_settings = get_settings()


def _uid(identidade: Identidade) -> uuid.UUID:
    return uuid.UUID(identidade.user_id)


def exigir_aal2(identidade: Identidade, session: Session) -> None:
    """403 se o usuário TEM fator TOTP verificado mas a sessão não é aal2."""
    if identidade.aal == "aal2":
        return
    if mfa.tem_fator_totp_verificado(session, _uid(identidade)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="requer verificação em dois fatores",
        )


def _senha_recente(identidade: Identidade, max_min: int = 15) -> bool:
    """True se o `amr` do JWT tem 'password' recente (re-auth p/ break-glass)."""
    agora = dt.datetime.now(dt.UTC).timestamp()
    for m in identidade.amr or []:
        if isinstance(m, dict) and m.get("method") == "password":
            ts = m.get("timestamp")
            if not isinstance(ts, (int, float)) or (agora - ts) <= max_min * 60:
                return True
    return False


def _rl_recuperacao():
    if not _settings.rate_limit_criar_tese:  # mesma chave de desligar em teste
        return lambda fn: fn
    return limiter.limit("5/hour")


@router.post("/mfa/codigos", response_model=CodigosOut)
def gerar_codigos_recuperacao(
    identidade: Annotated[Identidade, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
) -> CodigosOut:
    """Gera 10 códigos de recuperação (exige aal2). Devolve o plaintext UMA vez (no-store)."""
    exigir_aal2(identidade, session)
    return CodigosOut(codigos=mfa.gerar_codigos(session, _uid(identidade)))


@router.post("/mfa/recuperacao", response_model=OkOut)
@_rl_recuperacao()
def break_glass(
    request: Request,
    response: Response,
    body: RecuperacaoIn,
    identidade: Annotated[Identidade, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
) -> OkOut:
    """Perda do 2º fator: sessão aal1 com senha recente + código válido → remove os
    fatores TOTP (Admin API) → usuário volta a aal1 e re-enrola. NUNCA minta aal2."""
    if not _senha_recente(identidade):
        raise HTTPException(status_code=403, detail="reautenticação necessária")
    if not mfa.consumir_codigo(session, _uid(identidade), body.codigo):
        raise HTTPException(status_code=400, detail="código inválido")
    mfa.deletar_fatores_totp(_uid(identidade))
    mfa.apagar_codigos(session, _uid(identidade))
    return OkOut(ok=True)


@router.get("/exportar")
def exportar_dados(
    identidade: Annotated[Identidade, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    """LGPD (portabilidade): devolve TODOS os dados pessoais do usuário em JSON."""
    exigir_aal2(identidade, session)
    uid = _uid(identidade)
    teses = session.execute(select(Tese).where(Tese.user_id == uid)).scalars().all()
    saida_teses = []
    for t in teses:
        versao = session.execute(
            select(TeseVersao)
            .where(TeseVersao.tese_id == t.id)
            .order_by(TeseVersao.criado_em.desc())
            .limit(1)
        ).scalar_one_or_none()
        conteudo = None
        if versao and versao.conteudo:
            try:
                conteudo = json.loads(versao.conteudo)
            except json.JSONDecodeError:
                conteudo = {"markdown": versao.conteudo}
        saida_teses.append(
            {
                "id": str(t.id),
                "ticker": t.ticker,
                "classe_ativo": t.classe_ativo,
                "status": t.status,
                "criado_em": t.criado_em.isoformat() if t.criado_em else None,
                "conteudo": conteudo,
            }
        )
    historico = (
        session.execute(select(HistoricoItem).where(HistoricoItem.user_id == uid)).scalars().all()
    )
    return {
        "exportado_em": dt.datetime.now(dt.UTC).isoformat(),
        "perfil": {"user_id": str(uid), "email": identidade.email},
        "teses": saida_teses,
        "historico": [
            {"tese_id": str(h.tese_id), "origem": h.origem, "favorito": h.favorito}
            for h in historico
        ],
    }


@router.post("/excluir", response_model=OkOut)
def excluir_conta(
    identidade: Annotated[Identidade, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
) -> OkOut:
    """LGPD (apagamento): exclui a conta e cascateia todos os dados do usuário. O BFF
    já reautenticou a senha; aqui exigimos aal2 (para quem tem 2FA) como segunda trava."""
    exigir_aal2(identidade, session)
    uid = _uid(identidade)
    mfa.apagar_codigos(session, uid)
    mfa.deletar_usuario(uid)  # Admin API; FK CASCADE limpa teses/versões/elos/historico
    return OkOut(ok=True)
