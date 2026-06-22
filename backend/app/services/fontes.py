"""Coração da auditoria: toda gravação de fato cria/linka uma `Fonte`.

Uma fonte é (URL + descrição + data de referência). Nenhum `Fundamento` ou
`MacroSerie` é persistido sem um `fonte_id` — é o que garante rastreabilidade e
sustenta a regra de ouro "nenhum número sem fonte".
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Fonte


def get_or_create_fonte(
    session: Session,
    *,
    url: str | None,
    descricao: str,
    dt_referencia: dt.date | None = None,
) -> uuid.UUID:
    """Idempotente por (url, descricao, dt_referencia). Devolve o `fonte_id`.

    Não faz commit — o chamador controla a transação.
    """
    stmt = select(Fonte).where(
        Fonte.url.is_(url) if url is None else Fonte.url == url,
        Fonte.descricao == descricao,
        (
            Fonte.dt_referencia.is_(dt_referencia)
            if dt_referencia is None
            else Fonte.dt_referencia == dt_referencia
        ),
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing.id

    fonte = Fonte(url=url, descricao=descricao, dt_referencia=dt_referencia)
    session.add(fonte)
    session.flush()  # popula fonte.id sem encerrar a transação
    return fonte.id
