"""2FA — códigos de recuperação (nossos, o GoTrue não tem nativos) e break-glass.

Os códigos são gerados AQUI (um único gerador auditável), hasheados na aplicação
(SHA-256 de 80 bits CSPRNG) e guardados no cofre deny-all `codigos_recuperacao`.
Perda do 2º fator = break-glass: código válido → remover os fatores TOTP verificados
via Admin API (service_role, só no backend) → o usuário volta a aal1 e re-enrola.
Um código NUNCA minta sessão aal2 (não há API para isso; forjar JWT é vetado).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid

import httpx
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import CodigoRecuperacao

logger = get_logger(__name__)

QTD_CODIGOS = 10
BYTES_POR_CODIGO = 10  # 80 bits CSPRNG


def _formatar(codigo_hex: str) -> str:
    """20 hex -> 'XXXX-XXXX-XXXX-XXXX-XXXX' (legível; o hash ignora os hífens)."""
    s = codigo_hex.upper()
    return "-".join(s[i : i + 4] for i in range(0, len(s), 4))


def _hash(codigo: str) -> bytes:
    """Normaliza (sem hífen, maiúsculo) e faz SHA-256. O plaintext nunca vai ao banco."""
    normal = codigo.replace("-", "").replace(" ", "").strip().upper()
    return hashlib.sha256(normal.encode("ascii")).digest()


def gerar_codigos(session: Session, user_id: uuid.UUID) -> list[str]:
    """Gera 10 códigos novos (apaga o lote anterior) e devolve o plaintext UMA vez."""
    codigos = [secrets.token_hex(BYTES_POR_CODIGO) for _ in range(QTD_CODIGOS)]
    lote = uuid.uuid4()
    # Regerar substitui o lote anterior (invalida os antigos).
    session.query(CodigoRecuperacao).filter(CodigoRecuperacao.user_id == user_id).delete()
    session.add_all(
        CodigoRecuperacao(user_id=user_id, codigo_hash=_hash(c), lote=lote) for c in codigos
    )
    session.commit()
    logger.info("mfa_codigos_gerados", user_id=str(user_id), qtd=len(codigos), lote=str(lote))
    return [_formatar(c) for c in codigos]


def consumir_codigo(session: Session, user_id: uuid.UUID, codigo: str) -> bool:
    """Marca um código do usuário como usado (single-use). True se consumiu.

    UPDATE ... WHERE usado_em IS NULL RETURNING é atômico (reavalia o WHERE após o
    lock) — nunca SELECT-then-UPDATE (corrida permitiria consumo duplo).
    """
    resultado = session.execute(
        update(CodigoRecuperacao)
        .where(
            CodigoRecuperacao.user_id == user_id,
            CodigoRecuperacao.codigo_hash == _hash(codigo),
            CodigoRecuperacao.usado_em.is_(None),
        )
        .values(usado_em=dt.datetime.now(dt.UTC))
        .returning(CodigoRecuperacao.id)
    )
    consumiu = resultado.first() is not None
    session.commit()
    if consumiu:
        logger.info("mfa_codigo_consumido", user_id=str(user_id))
    return consumiu


def contar_codigos_ativos(session: Session, user_id: uuid.UUID) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(CodigoRecuperacao)
            .where(CodigoRecuperacao.user_id == user_id, CodigoRecuperacao.usado_em.is_(None))
        ).scalar_one()
    )


def apagar_codigos(session: Session, user_id: uuid.UUID) -> None:
    session.query(CodigoRecuperacao).filter(CodigoRecuperacao.user_id == user_id).delete()
    session.commit()


def tem_fator_totp_verificado(session: Session, user_id: uuid.UUID) -> bool:
    """Usa a função SECURITY DEFINER (fonte única; a policy aal2 usa a mesma)."""
    return bool(
        session.execute(
            text("select public.tem_fator_totp_verified(:uid)"), {"uid": str(user_id)}
        ).scalar()
    )


def _admin_headers() -> dict[str, str]:
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_role_key):
        raise RuntimeError("Supabase URL/service_role ausentes — break-glass indisponível.")
    return {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def deletar_fatores_totp(user_id: uuid.UUID) -> int:
    """Break-glass: remove TODOS os fatores TOTP verificados do usuário via Admin API
    (service_role — só no backend, nunca responde ao navegador diretamente). Desloga
    todas as sessões do fator. Devolve quantos removeu.
    """
    base = get_settings().supabase_url.rstrip("/")  # type: ignore[union-attr]
    headers = _admin_headers()
    with httpx.Client(timeout=30.0) as cli:
        usuario = cli.get(f"{base}/auth/v1/admin/users/{user_id}", headers=headers)
        usuario.raise_for_status()
        fatores = usuario.json().get("factors") or []
        removidos = 0
        for f in fatores:
            if f.get("factor_type") == "totp" and f.get("status") == "verified":
                r = cli.delete(
                    f"{base}/auth/v1/admin/users/{user_id}/factors/{f['id']}", headers=headers
                )
                r.raise_for_status()
                removidos += 1
    logger.info("mfa_break_glass", user_id=str(user_id), fatores_removidos=removidos)
    return removidos


def deletar_usuario(user_id: uuid.UUID) -> None:
    """Exclusão de conta (LGPD): apaga o usuário via Admin API. A FK ON DELETE CASCADE
    limpa teses/versões/elos/documentos/chunks/historico/códigos do usuário.
    """
    base = get_settings().supabase_url.rstrip("/")  # type: ignore[union-attr]
    with httpx.Client(timeout=30.0) as cli:
        r = cli.delete(f"{base}/auth/v1/admin/users/{user_id}", headers=_admin_headers())
        r.raise_for_status()
    logger.info("conta_excluida", user_id=str(user_id))
