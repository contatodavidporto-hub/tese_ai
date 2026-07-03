"""Testes offline do cliente HTTP central (sem rede real: httpx.MockTransport)."""

from __future__ import annotations

import httpx

from app.services import http_client


def test_get_keyless_injeta_user_agent_do_projeto() -> None:
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["ua"] = request.headers.get("user-agent", "")
        return httpx.Response(200, text="ok")

    resp = http_client.get_keyless(
        "https://exemplo.gov/dados", transport=httpx.MockTransport(handler)
    )
    assert resp.status_code == 200
    assert capturado["ua"].startswith("tese-ai/")


def test_get_keyless_ua_inclui_email_de_contato_para_sec() -> None:
    # Achado B1: a SEC exige e-mail de contato no UA (senão 403).
    assert "@" in http_client.UA


def test_get_keyless_headers_extra_nao_removem_o_ua() -> None:
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["ua"] = request.headers.get("user-agent", "")
        capturado["accept"] = request.headers.get("accept", "")
        return httpx.Response(200, text="ok")

    http_client.get_keyless(
        "https://exemplo.gov/x",
        headers={"Accept": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    assert capturado["ua"].startswith("tese-ai/")
    assert capturado["accept"] == "application/json"


def test_download_zip_devolve_bytes_e_levanta_em_erro() -> None:
    conteudo = b"PK\x03\x04conteudo-zip-fake"

    def handler_ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=conteudo)

    assert (
        http_client.download_zip("https://cvm.gov/a.zip", transport=httpx.MockTransport(handler_ok))
        == conteudo
    )

    def handler_404(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nao existe")

    try:
        http_client.download_zip(
            "https://cvm.gov/b.zip", transport=httpx.MockTransport(handler_404)
        )
        raise AssertionError("deveria ter levantado HTTPStatusError")
    except httpx.HTTPStatusError:
        pass
