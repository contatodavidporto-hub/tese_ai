"""Teste offline do núcleo do motor: extração determinística de citações.

Usa um cliente Anthropic FALSO (sem rede/chave) para provar que _synthesize
mapeia cada citação (document_index) de volta à Fonte correta e gera o
prompt_hash. Langfuse fica desligado (sem chaves) → caminho no-op.
"""

import uuid
from types import SimpleNamespace

from app.services import tese as tese_svc


def _fonte(url: str, descricao: str):
    return SimpleNamespace(id=uuid.uuid4(), url=url, descricao=descricao, dt_referencia=None)


class _FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessages:
    def __init__(self, message):
        self._message = message
        self.captured = None

    def stream(self, **kwargs):
        self.captured = kwargs
        return _FakeStream(self._message)


class _FakeClient:
    def __init__(self, message):
        self.messages = _FakeMessages(message)


def test_synthesize_mapeia_citacoes_para_fontes():
    fontes = [
        _fonte("https://dados.cvm.gov.br/x.zip", "CVM DFP 2025 — Lucro"),
        _fonte("https://api.bcb.gov.br/sgs/432", "BCB — Meta Selic"),
    ]
    itens = [(f, f"texto {i}") for i, f in enumerate(fontes)]
    documents, index_to_fonte = tese_svc._build_documents(itens)

    citation = SimpleNamespace(
        document_index=1, cited_text="Meta Selic 14,25% a.a.", document_title="BCB — Meta Selic"
    )
    block = SimpleNamespace(type="text", text="A Meta Selic é 14,25% a.a.", citations=[citation])
    usage = SimpleNamespace(
        input_tokens=120, output_tokens=80, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )
    message = SimpleNamespace(content=[block], usage=usage)
    client = _FakeClient(message)

    markdown, citacoes, ret_usage, prompt_hash = tese_svc._synthesize(
        client, "claude-opus-4-8", documents, index_to_fonte, "PETR4", "Petrobras"
    )

    assert "Meta Selic" in markdown
    assert len(citacoes) == 1
    # A citação document_index=1 deve resolver para a 2ª fonte (BCB).
    assert citacoes[0]["document_index"] == 1
    assert citacoes[0]["fonte"]["url"] == "https://api.bcb.gov.br/sgs/432"
    assert citacoes[0]["texto_citado"] == "Meta Selic 14,25% a.a."
    assert len(prompt_hash) == 64  # sha256 hex
    assert ret_usage is usage
    # O documento citável tem Citations habilitado e o último tem cache_control.
    assert documents[0]["citations"] == {"enabled": True}
    assert documents[-1]["cache_control"] == {"type": "ephemeral"}


class _FakeLangfuseGen:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeLangfuse:
    """Captura o que o motor manda pro Langfuse (traço de custo/tokens)."""

    def __init__(self):
        self.updates: list[dict] = []

    def start_as_current_observation(self, **kwargs):
        self.started = kwargs
        return _FakeLangfuseGen()

    def update_current_generation(self, **kwargs):
        self.updates.append(kwargs)


def test_synthesize_traca_custo_e_tokens_no_langfuse(monkeypatch):
    """Com LANGFUSE_* presente, cada geração traça tokens completos + custo USD."""
    lf = _FakeLangfuse()
    monkeypatch.setattr(tese_svc, "get_langfuse", lambda: lf)

    f = _fonte("https://x/y", "fonte")
    documents, index_to_fonte = tese_svc._build_documents([(f, "texto")])
    block = SimpleNamespace(type="text", text="Texto.", citations=[])
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        cache_read_input_tokens=200,
        cache_creation_input_tokens=100,
    )
    client = _FakeClient(SimpleNamespace(content=[block], usage=usage))

    tese_svc._synthesize(client, "claude-opus-4-8", documents, index_to_fonte, "PETR4", "Petrobras")

    assert lf.started["as_type"] == "generation"
    assert len(lf.updates) == 1
    upd = lf.updates[0]
    assert upd["model"] == "claude-opus-4-8"
    assert upd["usage_details"] == {
        "input": 1000,
        "output": 500,
        "cache_read_input_tokens": 200,
        "cache_creation_input_tokens": 100,
    }
    # Custo estimado em USD acompanha o traço (não depende do catálogo do Langfuse).
    assert upd["cost_details"]["total"] > 0


def test_synthesize_sem_citacoes_ainda_gera_markdown():
    f = _fonte("https://x/y", "fonte")
    documents, index_to_fonte = tese_svc._build_documents([(f, "texto")])
    block = SimpleNamespace(type="text", text="Texto sem citações.", citations=[])
    usage = SimpleNamespace(
        input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )
    client = _FakeClient(SimpleNamespace(content=[block], usage=usage))

    markdown, citacoes, _usage, prompt_hash = tese_svc._synthesize(
        client, "claude-opus-4-8", documents, index_to_fonte, "PETR4", "Petrobras"
    )
    assert markdown == "Texto sem citações."
    assert citacoes == []
    assert len(prompt_hash) == 64
