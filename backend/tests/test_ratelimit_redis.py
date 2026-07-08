"""Rate-limit distribuído behind-config: Redis quando REDIS_URL, memória sem.

A prova de "bucket compartilhado" usa fakeredis (um FakeServer = um Redis):
dois limiters (simulando duas instâncias/workers) apontando para a mesma URL
dividem o MESMO orçamento — o que o storage em memória não faz.
"""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis
import pytest
import redis

from app.core.ratelimit import criar_limiter


def _settings(redis_url: str | None) -> SimpleNamespace:
    return SimpleNamespace(redis_url=redis_url, rate_limit_global="120/minute")


def test_sem_redis_url_mantem_memoria_do_processo() -> None:
    limiter = criar_limiter(_settings(None))
    assert type(limiter.limiter.storage).__name__ == "MemoryStorage"


def test_com_redis_url_usa_storage_redis_com_fallback() -> None:
    limiter = criar_limiter(_settings("redis://localhost:6379/0"))
    assert type(limiter.limiter.storage).__name__ == "RedisStorage"
    # Redis fora do ar em runtime => degrada para memória, não derruba request.
    assert limiter._in_memory_fallback_enabled is True


def test_bucket_compartilhado_entre_instancias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duas instâncias do limiter com a mesma REDIS_URL dividem o bucket."""
    from limits import RateLimitItemPerMinute

    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        redis, "from_url", lambda url, **kw: fakeredis.FakeStrictRedis(server=server)
    )

    instancia_a = criar_limiter(_settings("redis://localhost:6379/0"))
    instancia_b = criar_limiter(_settings("redis://localhost:6379/0"))
    item = RateLimitItemPerMinute(3)

    # A instância A consome o orçamento inteiro...
    assert all(instancia_a.limiter.hit(item, "ip-1") for _ in range(3))
    # ...e a instância B (outro worker/instância) vê o MESMO bucket estourado.
    assert instancia_b.limiter.hit(item, "ip-1") is False
    # Chave diferente (outro IP) tem orçamento próprio.
    assert instancia_b.limiter.hit(item, "ip-2") is True


def test_memoria_nao_compartilha_entre_instancias() -> None:
    """Contraprova: sem Redis, cada instância tem bucket próprio (limite multiplica)."""
    from limits import RateLimitItemPerMinute

    instancia_a = criar_limiter(_settings(None))
    instancia_b = criar_limiter(_settings(None))
    item = RateLimitItemPerMinute(3)

    assert all(instancia_a.limiter.hit(item, "ip-1") for _ in range(3))
    # A instância B NÃO vê o consumo da A — por isso Redis importa ao escalar.
    assert instancia_b.limiter.hit(item, "ip-1") is True
