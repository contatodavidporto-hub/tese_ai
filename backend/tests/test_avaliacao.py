"""Testes offline do gate de avaliação (anti-recomendação / citação / abstenção)."""

import pytest

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


@pytest.mark.parametrize(
    "frase",
    [
        # Inglês direcional (research/sell-side) — a tese é PT-BR; vazamento.
        "## Síntese\nOur rating for this stock is a Strong Buy.",
        "## Síntese\nWe set a target price of R$ 45.",
        "## Síntese\nInvestors, you should buy PETR4 now.",
        "## Síntese\nWe recommend a buy rating on the shares.",
        "## Síntese\nAccumulate the position at current levels.",
        "## Síntese\nPrice target: R$ 50. Rating: Buy.",
        # PT que faltava.
        "## Síntese\nNossa recomendação de compra permanece.",
        "## Síntese\nSugiro adquirir as ações agora.",
        "## Síntese\nAloque capital neste ativo.",
    ],
)
def test_recomendacao_multi_idioma_reprova(frase: str):
    laudo = avaliar_tese(_envelope(frase))
    assert laudo["bloqueante"] is True
    assert laudo["violacoes_recomendacao"]  # não vazio


@pytest.mark.parametrize(
    "frase",
    [
        # Não podem ser falso-positivo (termos contábeis/factuais legítimos).
        "## Fundamentos\nA holding controla 60% das ações ordinárias.",
        "## Pares\nComparável: Household International (relatório anual).",
        "## Macro\nO IPCA acumulado no ano foi de 4,2% (BCB).",
        "## Fundamentos\nReceita de Venda de Bens e/ou Serviços: R$ 497,5 bi.",
    ],
)
def test_termos_legitimos_nao_sao_falso_positivo(frase: str):
    laudo = avaliar_tese(_envelope(frase))
    assert laudo["violacoes_recomendacao"] == []


def test_sem_citacao_reprova():
    laudo = avaliar_tese(_envelope("## Fundamentos\nDados.", com_citacao=False))
    assert laudo["aprovado"] is False
    assert "nenhuma citação ancorada à fonte" in laudo["motivos"]


def test_fonte_sem_url_reprova():
    fonte = {**_FONTE, "url": None}
    laudo = avaliar_tese(_envelope("## X\ntexto.", fontes=[fonte]))
    assert laudo["aprovado"] is False
    assert laudo["bloqueante"] is True
    assert laudo["fontes_sem_url"]


# --- Padrões de research/sell-side que o gate precisa pegar (achado HIGH do audit) ---


def test_verbos_direcionais_de_research_reprovam():
    for frase in [
        "## Síntese\nMantenha a posição no papel.",
        "## Síntese\nSugerimos acumular gradualmente.",
        "## Síntese\nO ideal é reduzir a exposição agora.",
        "## Síntese\nRealize lucro e coloque um stop-loss.",
        "## Síntese\nClassificação: outperform.",
        "## Síntese\nrating: compra.",
    ]:
        laudo = avaliar_tese(_envelope(frase))
        assert laudo["bloqueante"] is True, frase
        assert laudo["violacoes_recomendacao"], frase


def test_termos_contabeis_nao_sao_falso_positivo():
    # "lucros acumulados", "manutenção", "Receita de Venda" são contábeis/neutros.
    md = (
        "## Fundamentos\nLucros acumulados de R$ 10 bi; manutenção de equipamentos; "
        "Receita de Venda de Bens e/ou Serviços."
    )
    laudo = avaliar_tese(_envelope(md))
    assert laudo["violacoes_recomendacao"] == []


def test_recomendacao_na_mesma_linha_do_disclaimer_nao_escapa():
    md = "Não é recomendação, mas recomendo comprar as ações."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["bloqueante"] is True
    assert laudo["violacoes_recomendacao"]


def test_cobertura_baixa_reprova_aprovacao():
    # 4 fontes, só 1 citada (cobertura 0.25 < 0.5) -> não aprovado (mas não bloqueante).
    fontes = [{**_FONTE, "id": f"id-{i}", "url": f"https://x/{i}"} for i in range(4)]
    laudo = avaliar_tese(_envelope("## Fundamentos\ntexto.", fontes=fontes))
    assert laudo["cobertura_fontes"] == 0.25
    assert laudo["aprovado"] is False
    assert laudo["bloqueante"] is False  # cobertura é qualidade, não inegociável


def test_evento_geopolitico_sem_hedge_bloqueia():
    md = "## 3. Camada geopolítica\nA guerra na região derrubou a produção de petróleo."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"]
    assert laudo["bloqueante"] is True


def test_evento_geopolitico_com_hedge_passa():
    md = (
        "## 3. Camada geopolítica\n"
        "Cenário: caso haja tensões geopolíticas, o petróleo poderia subir (interpretação)."
    )
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"] == []


def test_disclaimer_geopolitico_de_negacao_nao_e_falso_positivo():
    # O motor sempre emite um disclaimer na seção 3 que cita os termos de evento
    # (guerra/sanção/OPEP/embargo) só para NEGÁ-los; não pode ser flagrado.
    md = (
        "## 3. Camada geopolítica (interpretação)\n"
        "⚠️ Nenhuma guerra, sanção, decisão da OPEP ou embargo é afirmada como "
        "ocorrida; o petróleo é tratado apenas como cenário condicional.\n"
    )
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"] == []
    assert laudo["bloqueante"] is False


def test_disclaimer_geopolitico_nao_ha_dado_nao_e_falso_positivo():
    # Forma real emitida pelo motor (tese PETR4): "não há nos documentos ... OPEP".
    md = (
        "## 3. Camada geopolítica\n"
        "Importante: não há nos documentos qualquer dado sobre embargos, "
        "decisões da OPEP ou sanções; seria especulação."
    )
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"] == []
    assert laudo["bloqueante"] is False


def test_evento_geopolitico_duro_sem_negacao_ainda_bloqueia():
    # Afirmação dura de evento (sem hedge e sem negação) AINDA deve bloquear.
    md = "## 3. Camada geopolítica\nA OPEP cortou a produção em 2026."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"]
    assert laudo["bloqueante"] is True


def test_negacao_de_duvida_com_evento_duro_ainda_bloqueia():
    # "nenhuma" negando a DÚVIDA (não o evento) não pode eximir a afirmação dura.
    md = "## 3. Camada geopolítica\nNão resta nenhuma dúvida de que a OPEP cortou a produção."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"]
    assert laudo["bloqueante"] is True


def test_negacao_de_um_evento_nao_exime_afirmacao_de_outro():
    # Negar um evento e afirmar outro na mesma frase AINDA deve bloquear.
    md = "## 3. Camada geopolítica\nNenhuma guerra foi declarada, mas houve um atentado em 2026."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["alertas_geopolitica"]
    assert laudo["bloqueante"] is True
