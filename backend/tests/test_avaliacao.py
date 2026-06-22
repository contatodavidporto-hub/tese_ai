"""Testes offline do gate de avaliação (anti-recomendação / citação / abstenção)."""

from app.services.avaliacao import avaliar_tese

_FONTE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "url": "https://dados.cvm.gov.br/x.zip",
    "descricao": "CVM DFP 2025 — PETR4",
    "dt_referencia": "2025-12-31",
}


def _envelope(markdown: str, *, com_citacao: bool = True, fontes=None) -> dict:
    fontes = fontes if fontes is not None else [_FONTE]
    citacoes = (
        [{"texto_citado": "Lucro R$ 110.605.000.000,00", "document_index": 0, "fonte": _FONTE}]
        if com_citacao
        else []
    )
    return {"markdown": markdown, "citacoes": citacoes, "fontes": fontes, "lacunas": []}


def test_tese_limpa_aprova():
    md = (
        "# Tese — PETR4\n"
        "> Não é recomendação de investimento.\n"
        "## 1. Fundamentos\n"
        "Receita de Venda de Bens e/ou Serviços: R$ 497,5 bi (CVM DFP 2025).\n"
    )
    laudo = avaliar_tese(_envelope(md))
    assert laudo["aprovado"] is True
    assert laudo["violacoes_recomendacao"] == []
    assert laudo["citacoes_total"] == 1
    assert laudo["cobertura_fontes"] == 1.0


def test_conta_receita_de_venda_nao_e_falso_positivo():
    # "Receita de Venda de Bens" NÃO pode ser lida como recomendação de venda.
    md = "## Fundamentos\nReceita de Venda de Bens e/ou Serviços: R$ 497,5 bi."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["violacoes_recomendacao"] == []


def test_disclaimer_nao_e_violacao():
    md = "> Não é recomendação de investimento. Esta análise não constitui recomendação."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["violacoes_recomendacao"] == []


def test_recomendacao_explicita_reprova():
    md = "## Síntese\nRecomendamos comprar as ações; vale a pena no preço-alvo atual."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["aprovado"] is False
    assert laudo["violacoes_recomendacao"]  # não vazio


def test_sem_citacao_reprova():
    laudo = avaliar_tese(_envelope("## Fundamentos\nDados.", com_citacao=False))
    assert laudo["aprovado"] is False
    assert "nenhuma citação ancorada à fonte" in laudo["motivos"]


def test_fonte_sem_url_reprova():
    fonte = {**_FONTE, "url": None}
    laudo = avaliar_tese(_envelope("## X\ntexto.", fontes=[fonte]))
    assert laudo["aprovado"] is False
    assert laudo["fontes_sem_url"]
