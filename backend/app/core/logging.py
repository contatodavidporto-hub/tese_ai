"""Logging estruturado (structlog) com redação de segredos.

Garante que valores sensíveis (chaves, tokens, senhas, connection strings) nunca
sejam emitidos em log, mesmo se forem passados por engano no contexto do evento.
"""

from __future__ import annotations

import logging
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


def _redact_secrets(_logger, _method_name, event_dict):
    for field in list(event_dict.keys()):
        if any(hint in field.lower() for hint in _SENSITIVE_HINTS):
            event_dict[field] = "***redacted***"
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
