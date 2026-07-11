"""Testes offline do cliente HTTP central (sem rede real: httpx.MockTransport)."""

from __future__ import annotations

import httpx
import pytest

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


# ---------------------------------------------------------------------------
# Allowlist SSRF — hosts novos da Fase "Tese Profunda" (F0, §2.12)
# ---------------------------------------------------------------------------
def test_allowlist_inclui_os_cinco_hosts_novos_da_tese_profunda() -> None:
    novos = {
        "bvmf.bmfbovespa.com.br",
        "sistemaswebb3-listados.b3.com.br",
        "www3.bcb.gov.br",
        "dadosabertos.aneel.gov.br",
        "www.anbima.com.br",
    }
    assert novos <= http_client._HOSTS_PERMITIDOS


def test_post_keyless_bloqueia_url_fora_da_allowlist_sem_transport() -> None:
    # Sem transport (fluxo real) => a validação anti-SSRF roda e barra antes de conectar
    # — mesmo comportamento de get_keyless (test_seguranca.py).
    with pytest.raises(http_client.HostNaoPermitido):
        http_client.post_keyless("https://attacker.example/x", data={"a": "1"})


def test_post_keyless_mocktransport_pula_allowlist_para_testes() -> None:
    # Com MockTransport (testes), a allowlist é ignorada — mesmo comportamento de
    # get_keyless (permite URL fictícia sem sair à rede).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    resp = http_client.post_keyless(
        "https://qualquer.host/x", data={"a": "1"}, transport=httpx.MockTransport(handler)
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# post_keyless (correção A4) — form-encoded, mesma revalidação de redirect do GET
# ---------------------------------------------------------------------------
def test_post_keyless_envia_form_encoded_com_user_agent() -> None:
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["ua"] = request.headers.get("user-agent", "")
        capturado["content_type"] = request.headers.get("content-type", "")
        capturado["body"] = request.content.decode("utf-8")
        return httpx.Response(200, text="ok")

    resp = http_client.post_keyless(
        "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp",
        data={"Idioma": "PT", "Dt_Ref": "10072026"},
        transport=httpx.MockTransport(handler),
    )
    assert resp.status_code == 200
    assert capturado["ua"].startswith("tese-ai/")
    assert "application/x-www-form-urlencoded" in capturado["content_type"]
    assert "Idioma=PT" in capturado["body"] and "Dt_Ref=10072026" in capturado["body"]


def test_post_keyless_instala_o_mesmo_hook_de_revalidacao_de_redirect_do_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Correção A4: sem transport (fluxo real), post_keyless monta `event_hooks`
    exatamente como get_keyless — uma função "request" que chama `_validar_url`
    a cada request enviado pelo `httpx.Client`, inclusive o alvo de um redirect
    (um 302 para host interno não escaparia à checagem inicial). Como não há
    rede real disponível no teste, substituímos `httpx.Client` por um dublê que
    captura o `event_hooks` recebido, e então exercitamos o hook capturado
    diretamente — provando que ele é o MESMO mecanismo de `_validar_url`.
    """
    capturado: dict = {}

    class _RespostaFake:
        status_code = 200

    class _ClienteFake:
        def __init__(self, *, timeout, follow_redirects, transport, event_hooks):
            capturado["event_hooks"] = event_hooks

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, data=None, headers=None):
            return _RespostaFake()

    monkeypatch.setattr(http_client.httpx, "Client", _ClienteFake)

    resp = http_client.post_keyless("https://www.anbima.com.br/CZ-down.asp", data={"a": "1"})
    assert resp.status_code == 200

    hooks_request = capturado["event_hooks"]["request"]
    assert len(hooks_request) == 1

    class _RequisicaoFake:
        def __init__(self, url: str) -> None:
            self.url = url

    hooks_request[0](_RequisicaoFake("https://www.anbima.com.br/redirecionado"))  # não levanta
    with pytest.raises(http_client.HostNaoPermitido):
        hooks_request[0](_RequisicaoFake("https://interno.malicioso.example/steal"))


def test_post_keyless_retenta_em_erro_de_rede() -> None:
    tentativas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas["n"] += 1
        if tentativas["n"] < 2:
            raise httpx.ConnectError("falha simulada", request=request)
        return httpx.Response(200, text="ok")

    resp = http_client.post_keyless(
        "https://www.anbima.com.br/x",
        data={"a": "1"},
        transport=httpx.MockTransport(handler),
        retries=2,
    )
    assert resp.status_code == 200
    assert tentativas["n"] == 2
