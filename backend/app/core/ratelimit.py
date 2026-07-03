"""Rate limiter compartilhado (slowapi), num módulo próprio para evitar ciclo.

`main.py` registra este `limiter` no app e adiciona o middleware; os routers usam
`limiter.limit(...)` como decorator. Chave por IP de origem. Sem estado externo
(memória do processo) — suficiente para a defesa de v1; Redis é roadmap para
rate-limit distribuído multi-worker.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_global] if _settings.rate_limit_global else [],
    headers_enabled=True,
)
