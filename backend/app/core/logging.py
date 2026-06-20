"""Logging estruturado (structlog) com redação de segredos.

Garante que valores sensíveis (chaves, tokens, senhas, connection strings) nunca
sejam emitidos em log, mesmo se forem passados por engano no contexto do evento.
"""

from __future__ import annotations

import logging
import re
import sys

import structlog

_SENSITIVE_HINTS = (
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "database_url",
    "api_key",
)

# Redige segredos que aparecem dentro de VALORES (não só em nomes de campo):
# connection strings com credenciais, chaves secretas e JWTs.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^:\s]+:[^@\s]+@", re.IGNORECASE),
    re.compile(r"sb_secret_[A-Za-z0-9_]{6,}"),
    re.compile(r"sk-[A-Za-z0-9-]{12,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
)


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(hint in lowered for hint in _SENSITIVE_HINTS)


def _scrub_value(value: object) -> object:
    if isinstance(value, str):
        scrubbed = value
        for pattern in _SECRET_VALUE_PATTERNS:
            scrubbed = pattern.sub("***redacted***", scrubbed)
        return scrubbed
    if isinstance(value, dict):
        return {
            k: ("***redacted***" if _is_sensitive_key(k) else _scrub_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_scrub_value(v) for v in value)
    return value


def _redact_secrets(_logger, _method_name, event_dict):
    """Redige por NOME de campo sensível e por PADRÃO de valor (recursivo)."""
    for field in list(event_dict.keys()):
        if _is_sensitive_key(field):
            event_dict[field] = "***redacted***"
        else:
            event_dict[field] = _scrub_value(event_dict[field])
    return event_dict


def configure_logging(app_env: str = "development") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_secrets,
    ]
    if app_env == "development":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
