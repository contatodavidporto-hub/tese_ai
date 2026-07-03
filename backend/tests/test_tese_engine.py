"""Testes offline dos helpers puros do motor de tese (app.services.tese).

Cobre formatação de reais, detecção de lacunas, estimativa de custo (com
stub de usage) e a montagem de documentos para o Anthropic Citations.
Nenhuma chamada ao Claude/DB/rede.
"""

from __future__ import annotations

import datetime as dt
import types
import uuid

from app.services.tese import (
    _build_documents,
    _detect_lacunas,
    _estimar_custo,
    _fmt_reais,
)


def _usage_stub(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> types.SimpleNamespace:
    """Stub mínimo do objeto `usage` da Anthropic (só os atributos lidos)."""
    return types.SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
    )


def _fonte_stub(
    *,
    fonte_id: uuid.UUID | None = None,
    url: str | None = "https://dados.cvm.gov.br/x.zip",
    descricao: str | None = "CVM DFP 2024 — Petrobras",
    dt_referencia: dt.date | None = dt.date(2024, 12, 31),
) -> types.SimpleNamespace:
    """Stub mínimo de `Fonte` (só os atributos lidos por _build_documents)."""
    return types.SimpleNamespace(
        id=fonte_id or uuid.uuid4(),
        url=url,
        descricao=descricao,
        dt_referencia=dt_referencia,
    )


# ---------------------------------------------------------------------------
# _fmt_reais — formatação brasileira
# ---------------------------------------------------------------------------


def test_fmt_reais_bilhoes() -> None:
    assert _fmt_reais(110605000000.0) == "R$ 110.605.000.000,00"


def test_fmt_reais_valor_pequeno() -> None:
    assert _fmt_reais(1234.5) == "R$ 1.234,50"


def test_fmt_reais_zero() -> None:
    assert _fmt_reais(0.0) == "R$ 0,00"


def test_fmt_reais_negativo() -> None:
    assert _fmt_reais(-1500.25) == "R$ -1.500,25"


# ---------------------------------------------------------------------------
# _detect_lacunas — linhas com "dado não encontrado"
# ---------------------------------------------------------------------------


def test_detect_lacunas_encontra_linha() -> None:
    md = "## Lacunas\n- Margem líquida: dado não encontrado\n- ok"
    lacunas = _detect_lacunas(md)
    assert lacunas == ["Margem líquida: dado não encontrado"]


def test_detect_lacunas_case_insensitive() -> None:
    md = "Receita: DADO NÃO ENCONTRADO"
    assert _detect_lacunas(md) == ["Receita: DADO NÃO ENCONTRADO"]


def test_detect_lacunas_multiplas_linhas() -> None:
    md = (
        "linha boa\n"
        "* Selic: dado não encontrado\n"
        "outra linha\n"
        "- Câmbio: dado não encontrado\n"
    )
    assert _detect_lacunas(md) == [
        "Selic: dado não encontrado",
        "Câmbio: dado não encontrado",
    ]


def test_detect_lacunas_sem_ocorrencia_retorna_vazio() -> None:
    assert _detect_lacunas("# Tese\nTudo com fonte.") == []


def test_detect_lacunas_remove_marcadores_e_espacos() -> None:
    # Strip de "-*" e espaços nas pontas.
    assert _detect_lacunas("  --* dado não encontrado *--  ") == ["dado não encontrado"]


# ---------------------------------------------------------------------------
# _estimar_custo — com stub de usage
# ---------------------------------------------------------------------------


def test_estimar_custo_modelo_desconhecido_retorna_none() -> None:
    assert _estimar_custo("modelo-que-nao-existe", _usage_stub(input_tokens=1000)) is None


def test_estimar_custo_usage_none_retorna_none() -> None:
    assert _estimar_custo("claude-opus-4-8", None) is None


def test_estimar_custo_opus_calcula_valor_conhecido() -> None:
    # Opus: (in=5.0, out=25.0) USD / 1M tokens.
    # 1M input + 1M output = 5.0 + 25.0 = 30.0 USD.
    custo = _estimar_custo(
        "claude-opus-4-8",
        _usage_stub(input_tokens=1_000_000, output_tokens=1_000_000),
    )
    assert custo == 30.0


def test_estimar_custo_inclui_cache_read_e_write() -> None:
    # cache_write * p_in * 1.25 + cache_read * p_in * 0.10, p_in=5.0.
    # write 1M -> 5.0*1.25 = 6.25 ; read 1M -> 5.0*0.10 = 0.5.
    custo = _estimar_custo(
        "claude-opus-4-8",
        _usage_stub(
            cache_creation_input_tokens=1_000_000,
            cache_read_input_tokens=1_000_000,
        ),
    )
    assert custo == 6.75


def test_estimar_custo_arredonda_para_seis_casas() -> None:
    custo = _estimar_custo("claude-opus-4-8", _usage_stub(input_tokens=1))
    assert custo == round(5.0 / 1_000_000, 6)


# ---------------------------------------------------------------------------
# _build_documents — blocos `document` para Citations
# ---------------------------------------------------------------------------


def test_build_documents_vazio_retorna_listas_vazias() -> None:
    documents, index_to_fonte = _build_documents([])
    assert documents == []
    assert index_to_fonte == []


def test_build_documents_marca_tipo_document_e_citations() -> None:
    f1 = _fonte_stub(descricao="Fonte A")
    f2 = _fonte_stub(descricao="Fonte B")
    documents, _ = _build_documents([(f1, "texto A"), (f2, "texto B")])
    assert len(documents) == 2
    for doc in documents:
        assert doc["type"] == "document"
        assert doc["citations"] == {"enabled": True}
        assert doc["source"]["type"] == "text"


def test_build_documents_carrega_texto_na_source() -> None:
    f1 = _fonte_stub()
    documents, _ = _build_documents([(f1, "fato citável")])
    assert documents[0]["source"]["data"] == "fato citável"


def test_build_documents_apenas_ultimo_tem_cache_control() -> None:
    f1 = _fonte_stub(descricao="A")
    f2 = _fonte_stub(descricao="B")
    f3 = _fonte_stub(descricao="C")
    documents, _ = _build_documents([(f1, "a"), (f2, "b"), (f3, "c")])
    assert "cache_control" not in documents[0]
    assert "cache_control" not in documents[1]
    assert documents[-1]["cache_control"] == {"type": "ephemeral"}


def test_build_documents_index_to_fonte_mapeia_posicoes() -> None:
    f1 = _fonte_stub(descricao="primeira")
    f2 = _fonte_stub(descricao="segunda")
    _documents, index_to_fonte = _build_documents([(f1, "a"), (f2, "b")])
    assert index_to_fonte == [f1, f2]
    assert index_to_fonte[0].descricao == "primeira"
    assert index_to_fonte[1].descricao == "segunda"


def test_build_documents_titulo_vem_da_descricao_truncada() -> None:
    descricao_longa = "x" * 300
    f1 = _fonte_stub(descricao=descricao_longa)
    documents, _ = _build_documents([(f1, "texto")])
    assert documents[0]["title"] == "x" * 200


def test_build_documents_context_inclui_url_e_dt_referencia() -> None:
    f1 = _fonte_stub(url="https://exemplo/x", dt_referencia=dt.date(2024, 12, 31))
    documents, _ = _build_documents([(f1, "texto")])
    assert "https://exemplo/x" in documents[0]["context"]
    assert "2024-12-31" in documents[0]["context"]
