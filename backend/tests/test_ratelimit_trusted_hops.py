"""Regressão M1 — hop de proxy confiável CONFIGURÁVEL no rate-limit (fail-closed).

Antes, `_chave_por_ip` sempre pegava o valor MAIS À DIREITA do X-Forwarded-For —
só anti-spoof se existir EXATAMENTE 1 edge confiável escrevendo o último hop.
Com mais de um proxy confiável na cadeia (ex.: CDN + load balancer), o último
hop é o IP de um dos proxies, não do cliente. Agora `hops` é configurável
(`rate_limit_trusted_proxy_hops`) e a chave fail-closed cai para
`get_remote_address` sempre que o XFF for mais curto que `hops` (nunca confia
num XFF forjado/curto). Cobre: hops=1 (default, comportamento anterior
preservado), hops=2 (posição correta) e o fallback fail-closed nos dois casos.
"""

from __future__ import annotations

from types import SimpleNamespace

from starlette.requests import Request as StarletteRequest

from app.core.config import Settings
from app.core.ratelimit import _chave_por_ip, criar_limiter


def _req(headers: dict[str, str], client_ip: str = "10.0.0.9") -> StarletteRequest:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": (client_ip, 1234),
        "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
    }
    return StarletteRequest(scope)


# ---------------------------------------------------------------------------
# Default (hops=1) — comportamento ANTERIOR preservado byte-idêntico
# ---------------------------------------------------------------------------
def test_hops1_default_deriva_o_valor_mais_a_direita() -> None:
    assert _chave_por_ip(_req({"x-forwarded-for": "forjado-1, 8.8.8.8"})) == "8.8.8.8"
    assert _chave_por_ip(_req({"x-forwarded-for": "203.0.113.7"})) == "203.0.113.7"
    assert _chave_por_ip(_req({})) == "10.0.0.9"  # sem XFF: IP do socket


def test_hops1_explicito_e_equivalente_ao_default() -> None:
    req = _req({"x-forwarded-for": "forjado-1, forjado-2, 8.8.8.8"})
    assert _chave_por_ip(req) == _chave_por_ip(req, hops=1) == "8.8.8.8"


# ---------------------------------------------------------------------------
# hops=2 — deriva a posição correta (2ª a partir da direita), NÃO a última
# ---------------------------------------------------------------------------
def test_hops2_deriva_a_segunda_posicao_a_partir_da_direita() -> None:
    # XFF forjado com 3 entradas: se hops=2, a chave é a do MEIO (posição 2 a
    # partir da direita) — a que o primeiro proxy confiável anotou — não a
    # última (que seria o IP interno do 2º proxy, não do cliente).
    req = _req({"x-forwarded-for": "forjado-atacante, 198.51.100.42, 203.0.113.1"})
    assert _chave_por_ip(req, hops=2) == "198.51.100.42"
    # hops=1 no MESMO header pegaria a última entrada (o proxy, não o cliente) —
    # prova que a posição realmente muda com `hops`.
    assert _chave_por_ip(req, hops=1) == "203.0.113.1"


def test_hops2_atacante_nao_consegue_forjar_a_chave_rotacionando_o_prefixo() -> None:
    # Rotacionar a parte que o atacante controla (a mais à esquerda) não muda a
    # chave derivada na posição fixa a partir da direita.
    a = _chave_por_ip(_req({"x-forwarded-for": "evil-1, 198.51.100.42, 203.0.113.1"}), hops=2)
    b = _chave_por_ip(_req({"x-forwarded-for": "evil-2-outro, 198.51.100.42, 203.0.113.1"}), hops=2)
    assert a == b == "198.51.100.42"


# ---------------------------------------------------------------------------
# FAIL-CLOSED — XFF mais curto que `hops` (ou ausente) NUNCA é confiado
# ---------------------------------------------------------------------------
def test_hops2_xff_mais_curto_que_hops_cai_para_remote_address() -> None:
    # Só 1 entrada no XFF, mas hops=2 exige 2 -> não confia, cai pro socket.
    req = _req({"x-forwarded-for": "203.0.113.1"}, client_ip="10.0.0.9")
    assert _chave_por_ip(req, hops=2) == "10.0.0.9"


def test_hops2_sem_xff_cai_para_remote_address() -> None:
    req = _req({}, client_ip="10.0.0.9")
    assert _chave_por_ip(req, hops=2) == "10.0.0.9"


def test_hops0_ou_negativo_nunca_indexa_e_cai_para_remote_address() -> None:
    # Defesa extra: um `hops` inválido (0/negativo) não pode virar um índice
    # degenerado (`partes[-0]` seria o PRIMEIRO elemento — o mais controlável
    # pelo atacante). Sempre cai para o IP do socket.
    req = _req({"x-forwarded-for": "evil, 198.51.100.42, 203.0.113.1"}, client_ip="10.0.0.9")
    assert _chave_por_ip(req, hops=0) == "10.0.0.9"


# ---------------------------------------------------------------------------
# Config — campo novo, default 1 (produção inalterada sem tocar o .env)
# ---------------------------------------------------------------------------
def test_config_rate_limit_trusted_proxy_hops_default_1() -> None:
    assert Settings().rate_limit_trusted_proxy_hops == 1


def test_config_rate_limit_trusted_proxy_hops_sobrepujavel() -> None:
    assert Settings(rate_limit_trusted_proxy_hops=2).rate_limit_trusted_proxy_hops == 2


# ---------------------------------------------------------------------------
# Integração — criar_limiter usa o hops configurado (ponta a ponta)
# ---------------------------------------------------------------------------
def test_criar_limiter_usa_o_hops_configurado_end_to_end() -> None:
    settings = SimpleNamespace(
        redis_url=None,
        rate_limit_global="120/minute",
        rate_limit_trusted_proxy_hops=2,
    )
    limiter = criar_limiter(settings)
    req = _req({"x-forwarded-for": "evil, 198.51.100.42, 203.0.113.1"}, client_ip="10.0.0.9")
    assert limiter._key_func(req) == "198.51.100.42"


def test_criar_limiter_sem_o_campo_no_settings_usa_hops_1_por_default() -> None:
    # Settings de teste "avulso" (SimpleNamespace) sem o campo novo -> getattr
    # com default 1 tolera, sem AttributeError e sem mudar o comportamento
    # anterior (regressão de compatibilidade com testes existentes).
    settings = SimpleNamespace(redis_url=None, rate_limit_global="120/minute")
    limiter = criar_limiter(settings)
    req = _req({"x-forwarded-for": "forjado, 8.8.8.8"}, client_ip="10.0.0.9")
    assert limiter._key_func(req) == "8.8.8.8"
