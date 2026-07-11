"""Cliente HTTP central keyless — User-Agent padrão, timeout, retries.

Ponto único de saída de rede para os conectores públicos (CVM, BCB, SEC EDGAR,
World Bank, Treasury). Injeta um User-Agent com contato (a SEC exige e-mail no UA,
sob risco de 403 — achado B1 do red-team) e faz retry/backoff em erros de rede.
NUNCA lê segredo: todas as fontes são públicas/keyless. Conectores que exigem
chave leem de `.env` (behind-config) nos seus próprios serviços.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from urllib.parse import urlsplit

import httpx

# User-Agent no formato DOCUMENTADO da SEC ("Nome contato@email") + Accept-Encoding.
# Verificado ao vivo (2026-07-02): o formato "nome/versao (+url; email)" leva 403 no
# WAF da SEC (www e data) e também derrubou o BCB SGS; o formato abaixo passa nos dois.
# O contato é o operacional do projeto (público), não um segredo.
_CONTATO = "contato.davidporto@gmail.com"
UA = f"tese-ai/0.1 {_CONTATO}"
_HEADERS = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}

_BACKOFF_BASE = 0.5  # segundos; só dorme entre tentativas que falharam por rede

# --- Anti-SSRF: allowlist deny-by-default -----------------------------------
# Só estes hosts (e subdomínios) podem ser buscados. Defesa em profundidade: hoje
# as URLs dos conectores são constantes e o input do usuário não as compõe, mas a
# allowlist garante que NENHUMA URL futura/injetada saia para um host não previsto
# (ex.: metadata 169.254.169.254, rede interna). Verificado contra os conectores
# reais em 2026-07-02 (CVM/BCB/SEC/World Bank/FRED/Treasury); hosts da Fase 2
# multiativo (STN/Olinda) adicionados em 2026-07-08 — sem curinga *.gov.br.
_HOSTS_PERMITIDOS = frozenset(
    {
        "dados.cvm.gov.br",
        "www.sec.gov",
        "data.sec.gov",
        "api.bcb.gov.br",
        "api.worldbank.org",
        "fred.stlouisfed.org",
        "home.treasury.gov",
        "api.stlouisfed.org",  # FRED oficial (behind-config)
        "api.eia.gov",  # EIA (behind-config)
        "www.tesourotransparente.gov.br",  # Tesouro Direto/STN (CSV de preços e taxas)
        "olinda.bcb.gov.br",  # BCB Olinda — OData Focus/expectativas de mercado
        # Fase "Tese Profunda" (F0, 2026-07-10) — adicionados deliberadamente, sem
        # curinga (plano §2.12): COTAHIST, IF.data, ANEEL SIGET e ANBIMA ETTJ.
        "bvmf.bmfbovespa.com.br",  # B3 — COTAHIST (preços diários históricos)
        "sistemaswebb3-listados.b3.com.br",  # B3 — proventos (cashDividends)
        "www3.bcb.gov.br",  # BCB — IF.data (indicadores prudenciais de banco)
        "dadosabertos.aneel.gov.br",  # ANEEL — CKAN/SIGET (RAP homologada)
        "www.anbima.com.br",  # ANBIMA — ETTJ snapshot do dia (CZ-down.asp, POST)
    }
)


class HostNaoPermitido(httpx.RequestError):
    """URL fora da allowlist de saída (anti-SSRF). Subclasse de RequestError."""

    def __init__(self, host: str) -> None:
        super().__init__(f"host não permitido (anti-SSRF): {host!r}")


def _host_permitido(host: str) -> bool:
    host = (host or "").lower().split(":")[0]
    if host in _HOSTS_PERMITIDOS:
        return True
    # Aceita subdomínios de um host permitido (ex.: files.sec.gov), nunca o inverso.
    return any(host.endswith("." + h) for h in _HOSTS_PERMITIDOS)


def _resolve_publico(host: str) -> None:
    """Bloqueia hosts que resolvem para IP privado/loopback/link-local (SSRF).

    Complementa a allowlist: mesmo um host permitido não pode apontar para rede
    interna (defesa contra DNS rebinding/registros envenenados). Falha de resolução
    não bloqueia aqui (o request seguirá e falhará por rede, tratado no retry).
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise HostNaoPermitido(f"{host} -> IP interno {ip}")


def _validar_url(url: str) -> None:
    partes = urlsplit(url)
    if partes.scheme not in ("https", "http"):
        raise HostNaoPermitido(f"esquema não permitido: {partes.scheme!r}")
    host = partes.hostname or ""
    if not _host_permitido(host):
        raise HostNaoPermitido(host)
    _resolve_publico(host)


def get_keyless(
    url: str,
    *,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
    transport: httpx.BaseTransport | None = None,
    retries: int = 2,
) -> httpx.Response:
    """GET keyless com UA padrão e retry em erro de REDE (não em status HTTP).

    Devolve a `Response` (o chamador decide sobre `raise_for_status`). `transport`
    permite `httpx.MockTransport` nos testes (sem rede real).
    """
    # Anti-SSRF: valida o destino ANTES de qualquer conexão (allowlist + IP público).
    # `transport` (MockTransport nos testes) pula a checagem — sem rede real. Um
    # event hook revalida CADA request, incluindo os alvos de redirect (senão um
    # 302 para host interno escaparia a checagem inicial).
    hooks: dict = {}
    if transport is None:
        _validar_url(url)
        hooks = {"request": [lambda req: _validar_url(str(req.url))]}
    hdrs = {**_HEADERS, **(headers or {})}
    ultimo_erro: httpx.RequestError | None = None
    for tentativa in range(retries + 1):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=follow_redirects,
                transport=transport,
                event_hooks=hooks,
            ) as client:
                return client.get(url, headers=hdrs)
        except httpx.RequestError as exc:  # conexão/timeout — reentar
            ultimo_erro = exc
            if tentativa < retries:
                time.sleep(_BACKOFF_BASE * (2**tentativa))
    if ultimo_erro is None:  # inalcançável: o range garante ao menos uma tentativa
        raise RuntimeError("nenhuma tentativa registrou erro ao esgotar as retentativas")
    raise ultimo_erro


def post_keyless(
    url: str,
    *,
    data: dict[str, str] | None = None,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
    transport: httpx.BaseTransport | None = None,
    retries: int = 2,
) -> httpx.Response:
    """POST keyless form-encoded com UA padrão e retry em erro de REDE (correção A4).

    Mesma defesa anti-SSRF do `get_keyless`: allowlist + IP público validados
    ANTES da conexão, com o MESMO event hook revalidando cada request —
    incluindo alvos de redirect — para que um 302 não escape a checagem
    inicial. `data` vai form-encoded (`application/x-www-form-urlencoded`,
    comportamento padrão do `httpx` quando `data` é um dict). Usado pelo
    conector ANBIMA (`CZ-down.asp`, POST); nenhum conector deve abrir `httpx`
    diretamente — sempre via `get_keyless`/`post_keyless`. `transport` permite
    `httpx.MockTransport` nos testes (sem rede real).
    """
    hooks: dict = {}
    if transport is None:
        _validar_url(url)
        hooks = {"request": [lambda req: _validar_url(str(req.url))]}
    hdrs = {**_HEADERS, **(headers or {})}
    ultimo_erro: httpx.RequestError | None = None
    for tentativa in range(retries + 1):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=follow_redirects,
                transport=transport,
                event_hooks=hooks,
            ) as client:
                return client.post(url, data=data, headers=hdrs)
        except httpx.RequestError as exc:  # conexão/timeout — reentar
            ultimo_erro = exc
            if tentativa < retries:
                time.sleep(_BACKOFF_BASE * (2**tentativa))
    if ultimo_erro is None:  # inalcançável: o range garante ao menos uma tentativa
        raise RuntimeError("nenhuma tentativa registrou erro ao esgotar as retentativas")
    raise ultimo_erro


# Teto de bytes para downloads (defesa contra resposta ilimitada / zip-bomb no
# transporte). Os ZIPs da CVM (DFP/FCA) ficam na casa de dezenas de MB; 512 MB dá
# folga larga e ainda barra um payload malicioso gigante.
_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


class RespostaGrandeDemais(httpx.RequestError):
    """Download excedeu o teto de bytes — aborta (anti-DoS de memória)."""


def download_zip(
    url: str,
    *,
    timeout: float = 180.0,
    transport: httpx.BaseTransport | None = None,
    max_bytes: int = _MAX_DOWNLOAD_BYTES,
) -> bytes:
    """Baixa um recurso binário (ex.: ZIP da CVM) e devolve os bytes.

    STREAMA com teto de tamanho: aborta se o corpo passar de `max_bytes` (defesa
    contra resposta ilimitada — a resposta externa é não-confiável). Levanta
    `httpx.HTTPStatusError` em status != 2xx e `RespostaGrandeDemais` no estouro,
    ambos subclasses de `HTTPError`/`RequestError` (tratados pelos conectores).
    """
    if transport is None:
        _validar_url(url)  # anti-SSRF antes de abrir a conexão
    hooks = {"request": [lambda req: _validar_url(str(req.url))]} if transport is None else {}
    with httpx.Client(
        timeout=timeout, follow_redirects=True, transport=transport, event_hooks=hooks
    ) as client:
        with client.stream("GET", url, headers=_HEADERS) as resp:
            resp.raise_for_status()
            # Content-Length adiantado (quando presente) evita começar o download.
            declarado = resp.headers.get("content-length")
            if declarado is not None and declarado.isdigit() and int(declarado) > max_bytes:
                raise RespostaGrandeDemais(f"content-length {declarado} > teto {max_bytes}")
            buffer = bytearray()
            for chunk in resp.iter_bytes():
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    raise RespostaGrandeDemais(f"download excedeu {max_bytes} bytes")
            return bytes(buffer)
