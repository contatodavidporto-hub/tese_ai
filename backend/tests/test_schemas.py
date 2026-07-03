"""Testes offline dos contratos Pydantic da API de tese (app.schemas.tese).

Valida coerção de tipos (uuid/data a partir de strings), o disclaimer
regulatório padrão e a ausência de qualquer linguagem de compra/venda.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.schemas.tese import CitacaoOut, FonteOut, TeseOut

# Palavras direcionais proibidas (postura CVM): nunca recomendar.
_PALAVRAS_PROIBIDAS = ("compre", "venda", "comprar", "vender", "preço-alvo")


# ---------------------------------------------------------------------------
# TeseOut — validação mínima e disclaimer
# ---------------------------------------------------------------------------


def test_tese_out_valida_com_campos_minimos() -> None:
    tese = TeseOut(id=uuid.uuid4(), ticker="PETR4", status="ready")
    assert tese.ticker == "PETR4"
    assert tese.status == "ready"


def test_tese_out_aviso_padrao_nao_vazio() -> None:
    tese = TeseOut(id=uuid.uuid4(), ticker="PETR4", status="ready")
    assert tese.aviso.strip() != ""


def test_tese_out_aviso_nao_contem_linguagem_de_compra_venda() -> None:
    tese = TeseOut(id=uuid.uuid4(), ticker="PETR4", status="ready")
    aviso = tese.aviso.lower()
    for palavra in _PALAVRAS_PROIBIDAS:
        assert palavra not in aviso


def test_tese_out_aviso_afirma_que_nao_e_recomendacao() -> None:
    tese = TeseOut(id=uuid.uuid4(), ticker="PETR4", status="ready")
    assert "não é recomendação" in tese.aviso.lower()


def test_tese_out_coage_id_de_string() -> None:
    tese = TeseOut(id="123e4567-e89b-12d3-a456-426614174000", ticker="VALE3", status="ready")
    assert isinstance(tese.id, uuid.UUID)
    assert str(tese.id) == "123e4567-e89b-12d3-a456-426614174000"


def test_tese_out_listas_default_sao_vazias() -> None:
    tese = TeseOut(id=uuid.uuid4(), ticker="ITUB4", status="processing")
    assert tese.citacoes == []
    assert tese.fontes == []
    assert tese.lacunas == []


def test_tese_out_aceita_citacoes_e_fontes_como_dicts() -> None:
    payload = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "ticker": "PETR4",
        "status": "ready",
        "criado_em": "2026-06-22T12:00:00",
        "fontes": [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "url": "https://dados.cvm.gov.br/x.zip",
                "descricao": "CVM DFP 2024",
                "dt_referencia": "2024-12-31",
            }
        ],
        "citacoes": [
            {
                "texto_citado": "Lucro líquido R$ 110.605.000.000,00",
                "document_index": 0,
                "titulo_documento": "CVM DFP 2024",
                "fonte": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "descricao": "CVM DFP 2024",
                    "dt_referencia": "2024-12-31",
                },
            }
        ],
    }
    tese = TeseOut(**payload)
    assert isinstance(tese.criado_em, dt.datetime)
    assert isinstance(tese.fontes[0], FonteOut)
    assert isinstance(tese.fontes[0].id, uuid.UUID)
    assert tese.fontes[0].dt_referencia == dt.date(2024, 12, 31)
    assert isinstance(tese.citacoes[0], CitacaoOut)
    assert tese.citacoes[0].document_index == 0
    assert tese.citacoes[0].fonte is not None
    assert tese.citacoes[0].fonte.dt_referencia == dt.date(2024, 12, 31)


# ---------------------------------------------------------------------------
# FonteOut — coerção de uuid/data e opcionais
# ---------------------------------------------------------------------------


def test_fonte_out_coage_uuid_string_e_iso_date() -> None:
    fonte = FonteOut(
        id="00000000-0000-0000-0000-000000000009",
        url="https://exemplo/doc",
        descricao="Fonte X",
        dt_referencia="2025-12-31",
    )
    assert isinstance(fonte.id, uuid.UUID)
    assert fonte.dt_referencia == dt.date(2025, 12, 31)


def test_fonte_out_campos_opcionais_default_none() -> None:
    fonte = FonteOut(descricao="só descrição")
    assert fonte.id is None
    assert fonte.url is None
    assert fonte.dt_referencia is None


# ---------------------------------------------------------------------------
# CitacaoOut — opcionais e default
# ---------------------------------------------------------------------------


def test_citacao_out_minima_sem_fonte() -> None:
    cit = CitacaoOut(texto_citado="trecho citado")
    assert cit.texto_citado == "trecho citado"
    assert cit.document_index is None
    assert cit.fonte is None


def test_citacao_out_coage_fonte_aninhada_de_dict() -> None:
    cit = CitacaoOut(
        texto_citado="trecho",
        document_index=2,
        fonte={"descricao": "Fonte aninhada", "dt_referencia": "2024-01-01"},
    )
    assert isinstance(cit.fonte, FonteOut)
    assert cit.fonte.dt_referencia == dt.date(2024, 1, 1)
