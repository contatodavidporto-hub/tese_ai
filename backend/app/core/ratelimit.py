"""Rate limiter compartilhado (slowapi), num módulo próprio para evitar ciclo.

`main.py` registra este `limiter` no app e adiciona o middleware; os routers usam
`limiter.limit(...)` como decorator. Chave por IP de origem (ver `_chave_por_ip`).
Sem estado externo (memória do processo) — suficiente para a defesa de v1; Redis
é roadmap para rate-limit distribuído multi-worker.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings

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


limiter = Limiter(
    key_func=_chave_por_ip,
    default_limits=[_settings.rate_limit_global] if _settings.rate_limit_global else [],
    headers_enabled=True,
)
