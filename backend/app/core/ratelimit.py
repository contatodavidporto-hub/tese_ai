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


def _chave_por_ip(request: Request, hops: int = 1) -> str:
    """IP para a chave do rate-limit: o valor na posição `hops` a partir da direita
    do X-Forwarded-For (config `rate_limit_trusted_proxy_hops`, default 1).

    Cada proxy CONFIÁVEL apenda exatamente 1 entrada ao XFF — o peer TCP que ele
    viu ao encaminhar a request. Com `hops` proxies confiáveis em cadeia entre o
    cliente e a app, a entrada apendada pelo PRIMEIRO deles (o mais perto do
    cliente) é o IP real do cliente, e ela cai na posição `hops` contada a partir
    da direita (hops=1 -> a última entrada; hops=2 -> a penúltima; etc.). Usar uma
    posição mais à esquerda do que a topologia real permite (como o uvicorn faz
    com FORWARDED_ALLOW_IPS=*) permitiria a quem fala direto com o host forjar a
    própria chave e evadir o limite rotacionando o header.

    FAIL-CLOSED: se o XFF tiver MENOS que `hops` entradas (ou não existir), NUNCA
    confia num XFF curto/forjado — cai para o IP visto pelo servidor
    (`get_remote_address`), que é sempre o peer TCP real, não-spoofável por quem
    fala direto com o host. Isso troca granularidade (clientes atrás do mesmo
    egress dividem bucket) por uma chave à prova de spoof; com login (roadmap), a
    chave passa a ser o usuário.

    ATENÇÃO: isto pressupõe exatamente `hops` proxies confiáveis na frente que
    ANEXAM (nunca reescrevem) o header — `hops` deve bater com a contagem REAL de
    proxies confiáveis na topologia. Exposto DIRETO na internet (0 proxies), o
    XFF é 100% controlado pelo cliente — não rode a imagem sem proxy (o
    FORWARDED_ALLOW_IPS só cobre scheme/logs, não a chave).
    """
    # getlist+join: linhas duplicadas do header não escapam da regra da posição
    # (edges normais coalescem, mas não dependemos disso).
    xff = ", ".join(request.headers.getlist("x-forwarded-for"))
    if xff and hops >= 1:
        partes = [p.strip() for p in xff.split(",") if p.strip()]
        if len(partes) >= hops:
            return partes[-hops]
    return get_remote_address(request)


def criar_limiter(settings: Settings) -> Limiter:
    """Monta o Limiter conforme a config (testável sem tocar o singleton).

    Com `redis_url`: storage Redis + fallback em memória habilitado (Redis fora
    do ar degrada gracioso — o limite volta a ser por processo, mas a API segue
    servindo). Sem: memória do processo, comportamento de sempre.

    `hops` (nº de proxies confiáveis) vem de `settings.rate_limit_trusted_proxy_hops`
    — `getattr` com default 1 tolera settings de teste que não modelam o campo
    (ex.: `SimpleNamespace` avulso) sem quebrar o comportamento anterior. Clampado
    em >= 1: um valor 0/negativo seria PIOR que o default (index inválido em
    `_chave_por_ip`), nunca aceito.
    """
    extras: dict = {}
    if settings.redis_url:
        extras["storage_uri"] = settings.redis_url
        extras["in_memory_fallback_enabled"] = True
    hops = max(1, getattr(settings, "rate_limit_trusted_proxy_hops", 1) or 1)
    return Limiter(
        key_func=lambda request: _chave_por_ip(request, hops),
        default_limits=[settings.rate_limit_global] if settings.rate_limit_global else [],
        headers_enabled=True,
        **extras,
    )


limiter = criar_limiter(_settings)
