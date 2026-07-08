"""Rate limiter compartilhado (slowapi), num módulo próprio para evitar ciclo.

`main.py` registra este `limiter` no app e adiciona o middleware; os routers usam
`limiter.limit(...)` como decorator. Chave por IP de origem (ver `_chave_por_ip`).
Storage BEHIND-CONFIG: com `REDIS_URL` o bucket vive no Redis (compartilhado entre
instâncias/workers — escalar passa a valer); sem, memória do processo (defesa de
v1). Redis indisponível em runtime => fallback para memória (nunca derruba request
por causa do limiter).
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import Settings, get_settings

_settings = get_settings()


def _chave_por_ip(request: Request) -> str:
    """IP para a chave do rate-limit: o valor MAIS À DIREITA do X-Forwarded-For.

    Atrás de um edge-proxy, o único elemento do XFF que o cliente NÃO controla é
    o último — o peer TCP real que o edge viu ao apendar o header. Usar o mais à
    esquerda (como o uvicorn faz com FORWARDED_ALLOW_IPS=*) permitiria a quem
    fala direto com o host forjar a própria chave e evadir o limite rotacionando
    o header. Trocamos granularidade (clientes atrás do mesmo egress dividem
    bucket) por chave à prova de spoof; com login (roadmap), a chave passa a ser
    o usuário. Sem o header (dev local, testes), cai no IP visto pelo servidor.

    ATENÇÃO: isto pressupõe um edge-proxy na frente (que escreve o último valor).
    Exposto DIRETO na internet, o XFF é 100% controlado pelo cliente — não rode
    a imagem sem proxy (o FORWARDED_ALLOW_IPS só cobre scheme/logs, não a chave).
    """
    # getlist+join: linhas duplicadas do header não escapam da regra do "mais à
    # direita" (edges normais coalescem, mas não dependemos disso).
    xff = ", ".join(request.headers.getlist("x-forwarded-for"))
    if xff:
        ultimo = xff.rsplit(",", 1)[-1].strip()
        if ultimo:
            return ultimo
    return get_remote_address(request)


def criar_limiter(settings: Settings) -> Limiter:
    """Monta o Limiter conforme a config (testável sem tocar o singleton).

    Com `redis_url`: storage Redis + fallback em memória habilitado (Redis fora
    do ar degrada gracioso — o limite volta a ser por processo, mas a API segue
    servindo). Sem: memória do processo, comportamento de sempre.
    """
    extras: dict = {}
    if settings.redis_url:
        extras["storage_uri"] = settings.redis_url
        extras["in_memory_fallback_enabled"] = True
    return Limiter(
        key_func=_chave_por_ip,
        default_limits=[settings.rate_limit_global] if settings.rate_limit_global else [],
        headers_enabled=True,
        **extras,
    )


limiter = criar_limiter(_settings)
