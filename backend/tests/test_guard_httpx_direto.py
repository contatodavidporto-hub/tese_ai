"""Guard A4 — nenhum conector abre `httpx` direto (plano-correcoes-redteam.md).

Todo acesso de rede a fontes PÚBLICAS/KEYLESS deve passar por
`app/services/http_client.py` (allowlist anti-SSRF + retry + teto de bytes).
Este teste de lint varre `app/services/*.py` procurando chamadas diretas
`httpx.Client(`/`httpx.AsyncClient(`/`httpx.get(`/`httpx.post(`/etc. — a
FORMA de bypass real do http_client (o módulo pode seguir importando `httpx`
só para anotar tipo, ex.: `transport: httpx.BaseTransport | None`, que é o
padrão de injeção de transporte usado em TODOS os conectores para testar sem
rede real; o guard não proíbe isso, só a abertura de conexão).

Exceções documentadas (fora do escopo do guard, threat model diferente):
- `http_client.py`: é o próprio wrapper sancionado.
- `demo_user.py`: chama a Admin API do PRÓPRIO projeto Supabase
  (`settings.supabase_url`, autenticado com `service_role`) — não é um
  conector público keyless de terceiro; a URL vem de config confiável do
  operador, não de entrada externa. Pré-existente à Fase "Tese Profunda".
"""

from __future__ import annotations

import re
from pathlib import Path

_SERVICES_DIR = Path(__file__).resolve().parent.parent / "app" / "services"

_ISENTOS = {"http_client.py", "demo_user.py"}

# Chamada de rede direta via módulo `httpx` (não via `app.services.http_client`).
_PADRAO_HTTPX_DIRETO = re.compile(
    r"\bhttpx\.(Client|AsyncClient)\s*\(|\bhttpx\.(get|post|put|delete|patch|request|stream)\s*\("
)


def _arquivos_services() -> list[Path]:
    return sorted(p for p in _SERVICES_DIR.glob("*.py") if p.name not in _ISENTOS)


def test_nenhum_conector_abre_httpx_direto() -> None:
    """`app/services/*.py` (exceto as isenções documentadas) não chama
    `httpx.Client`/`httpx.get`/`httpx.post`/etc. diretamente — só via
    `http_client.get_keyless`/`post_keyless`/`download_zip`."""
    violacoes: dict[str, list[str]] = {}
    for arquivo in _arquivos_services():
        texto = arquivo.read_text(encoding="utf-8")
        achados = _PADRAO_HTTPX_DIRETO.findall(texto)
        if achados:
            violacoes[arquivo.name] = [m.group() for m in _PADRAO_HTTPX_DIRETO.finditer(texto)]
    assert not violacoes, (
        "conector(es) abrindo httpx direto (bypass do anti-SSRF do http_client): "
        f"{violacoes} — use http_client.get_keyless/post_keyless/download_zip"
    )


def test_import_httpx_so_para_anotacao_de_tipo_no_transport() -> None:
    """Onde `httpx` é importado fora de `http_client.py`/`demo_user.py`, o único
    uso aceito é a anotação `httpx.BaseTransport` (injeção de transporte nos
    testes) ou `httpx.HTTPError`/`httpx.HTTPStatusError`/etc. (tratamento de
    exceção) — nunca abertura de conexão (garantido pelo teste anterior)."""
    for arquivo in _arquivos_services():
        texto = arquivo.read_text(encoding="utf-8")
        if re.search(r"^import httpx\b", texto, re.MULTILINE) is None:
            continue
        # Reforço redundante e barato do guard principal — mesma regra.
        assert not _PADRAO_HTTPX_DIRETO.search(
            texto
        ), f"{arquivo.name}: importa httpx mas abre conexão direta — bypass do http_client"
