"""Cliente HTTP central keyless — User-Agent padrão, timeout, retries.

Ponto único de saída de rede para os conectores públicos (CVM, BCB, SEC EDGAR,
World Bank, Treasury). Injeta um User-Agent com contato (a SEC exige e-mail no UA,
sob risco de 403 — achado B1 do red-team) e faz retry/backoff em erros de rede.
NUNCA lê segredo: todas as fontes são públicas/keyless. Conectores que exigem
chave leem de `.env` (behind-config) nos seus próprios serviços.
"""

from __future__ import annotations

import time

import httpx

# User-Agent com contato (política de acesso justo da SEC pede e-mail). O contato
# é o operacional do projeto (público), não um segredo.
_CONTATO = "contato.davidporto@gmail.com"
UA = f"tese-ai/0.1 (+https://github.com/contatodavidporto-hub/tese_ai; {_CONTATO})"
_HEADERS = {"User-Agent": UA}

_BACKOFF_BASE = 0.5  # segundos; só dorme entre tentativas que falharam por rede


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
    hdrs = {**_HEADERS, **(headers or {})}
    ultimo_erro: httpx.RequestError | None = None
    for tentativa in range(retries + 1):
        try:
            with httpx.Client(
                timeout=timeout, follow_redirects=follow_redirects, transport=transport
            ) as client:
                return client.get(url, headers=hdrs)
        except httpx.RequestError as exc:  # conexão/timeout — reentar
            ultimo_erro = exc
            if tentativa < retries:
                time.sleep(_BACKOFF_BASE * (2**tentativa))
    assert ultimo_erro is not None  # só chega aqui após esgotar as tentativas
    raise ultimo_erro


def download_zip(
    url: str,
    *,
    timeout: float = 180.0,
    transport: httpx.BaseTransport | None = None,
) -> bytes:
    """Baixa um recurso binário (ex.: ZIP da CVM) e devolve os bytes.

    Levanta `httpx.HTTPStatusError` (subclasse de `HTTPError`) em status != 2xx,
    compatível com os `except httpx.HTTPError` dos conectores.
    """
    resp = get_keyless(url, timeout=timeout, transport=transport)
    resp.raise_for_status()
    return resp.content
