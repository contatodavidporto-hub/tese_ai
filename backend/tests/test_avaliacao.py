"""Testes offline do gate de avaliação (anti-recomendação / citação / abstenção).

Fase 2 multiativo: o gate passou a BLOQUEAR markdown sem H2 'geopol' (o buraco
da guarda muda) e sem seção de Lacunas — universal, toda classe. Os fixtures
antigos são FRAGMENTOS de tese; `_completar_secoes` anexa as seções universais
quando ausentes para preservar o alvo original de cada teste antigo. Os testes
de regressão do buraco usam `completo=False` para exercitar a ausência.
"""

import pytest

from app.services.avaliacao import avaliar_tese, termos_vetados_com_numero

_FONTE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "url": "https://dados.cvm.gov.br/x.zip",
    "descricao": "CVM DFP 2025 — PETR4",
    "dt_referencia": "2025-12-31",
}


def _completar_secoes(markdown: str) -> str:
    """Anexa as seções universais BLOQUEANTES (geopol/Lacunas) quando ausentes."""
    h2s = " | ".join(ln.lower() for ln in markdown.splitlines() if ln.startswith("## "))
    if "geopol" not in h2s:
        markdown += (
            "\n\n## Camada geopolítica (interpretação)\n"
            "Sem eventos afirmados; qualquer leitura é hipótese condicional."
        )
    if "lacun" not in h2s:
        markdown += "\n\n## Lacunas\n- dado não encontrado: exemplo de abstenção."
    return markdown


def _envelope(markdown: str, *, com_citacao: bool = True, fontes=None, completo: bool = True):
    fontes = fontes if fontes is not None else [_FONTE]
    citacoes = (
        [{"texto_citado": "Lucro R$ 110.605.000.000,00", "document_index": 0, "fonte": _FONTE}]
        if com_citacao
        else []
    )
    md = _completar_secoes(markdown) if completo else markdown
    return {"markdown": md, "citacoes": citacoes, "fontes": fontes, "lacunas": []}


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


def test_cobertura_deduplica_fontes_repetidas_por_url_descricao():
    # Achado B1 (red-team fase 2): no caso RF, cada Data Base do CSV da STN
    # cria uma `Fonte` própria com a MESMA url+descricao — 4 documentos da
    # mesma fonte lógica citada 1x davam cobertura 0,25. Dedup -> 1.0.
    fontes = [{**_FONTE, "id": f"id-{i}"} for i in range(4)]  # mesma url/descricao
    laudo = avaliar_tese(_envelope("## Fundamentos\nTexto citado.", fontes=fontes))
    assert laudo["fontes_total"] == 4
    assert laudo["fontes_unicas"] == 1
    assert laudo["cobertura_fontes"] == 1.0
    assert laudo["aprovado"] is True


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


# =============================================================================
# Fase 2 multiativo (etapa 13) — gate por classe: seções universais, imperativos
# por diretiva-ao-leitor, termos vetados-com-número e piso de fidelidade.
# =============================================================================


# --- Seções universais BLOQUEANTES (regressão do buraco: guarda geopol muda) --


def test_markdown_sem_h2_geopolitica_bloqueia():
    # Sem H2 'geopol', `_alertas_geopolitica` silenciosamente não roda (fase 1).
    md = "# Tese\n## 1. Fundamentos\nReceita: R$ 497,5 bi.\n## Lacunas\n- dado não encontrado."
    laudo = avaliar_tese(_envelope(md, completo=False))
    assert laudo["bloqueante"] is True
    assert any("geopol" in s for s in laudo["secoes_ausentes"])


def test_markdown_sem_secao_lacunas_bloqueia():
    md = "# Tese\n## 4. Camada geopolítica (interpretação)\nSem eventos afirmados."
    laudo = avaliar_tese(_envelope(md, completo=False))
    assert laudo["bloqueante"] is True
    assert any("lacun" in s for s in laudo["secoes_ausentes"])


def test_secoes_universais_presentes_nao_bloqueiam():
    md = (
        "# Tese\n## 1. Fundamentos\nReceita citada.\n"
        "## 4. Camada geopolítica (interpretação)\nSem eventos afirmados.\n"
        "## 8. Lacunas\n- dado não encontrado: exemplo."
    )
    laudo = avaliar_tese(_envelope(md, completo=False))
    assert laudo["secoes_ausentes"] == []
    assert laudo["bloqueante"] is False


# --- Imperativos ancorados em diretiva-ao-leitor (bloqueiam, toda classe) -----


@pytest.mark.parametrize(
    ("frase", "classe"),
    [
        ("## Síntese\nTrave a taxa antes da próxima reunião do Copom.", "renda_fixa"),
        ("## Síntese\nAdquira cotas do fundo neste patamar.", "fii"),
        ("## Síntese\nVocê deve alocar em prefixados agora.", "renda_fixa"),
        ("## Síntese\nSugiro carregar o título até o vencimento.", "renda_fixa"),
        ("## Síntese\nSubscreva cotas na próxima emissão.", "fii"),
        ("## Síntese\nRecomendo resgatar o título hoje.", "renda_fixa"),
        ("## Síntese\nAconselho travar a taxa nominal.", "renda_fixa"),
    ],
)
def test_imperativos_por_classe_bloqueiam(frase: str, classe: str):
    laudo = avaliar_tese(_envelope(frase), classe=classe)
    assert laudo["violacoes_recomendacao"], frase
    assert laudo["bloqueante"] is True, frase


# --- Linguagem factual multiativo NÃO bloqueia (aceite da etapa 13) -----------


@pytest.mark.parametrize(
    ("frase", "classe"),
    [
        (
            "## Renda fixa\nTaxa Venda Manhã: 13,25% (Tesouro Transparente, Data Base 07/07/2026).",
            "renda_fixa",
        ),
        (
            "## Renda fixa\nCaso o investidor resgate o título antes do vencimento, "
            "há marcação a mercado.",
            "renda_fixa",
        ),
        ("## Mandato\nO mandato permite que o fundo invista em CRI.", "fii"),
        ("## Renda fixa\nO resgate antecipado implica marcação a mercado.", "renda_fixa"),
        ("## Imóveis\nVacância ponderada por área: 3,2% (informe trimestral CVM).", "fii"),
        ("## Indicadores\nDY mensal do informe (auto-declarado): 0,66%.", "fii"),
        ("## Juros\nProxy da curva soberana via Tesouro prefixado: 13,1% (2029).", "renda_fixa"),
        ("## Regras\nPor regra CVM, o fundo deve investir ao menos 67% em imóveis.", "fii"),
    ],
)
def test_linguagem_factual_multiativo_nao_bloqueia(frase: str, classe: str):
    laudo = avaliar_tese(_envelope(frase), classe=classe)
    assert laudo["violacoes_recomendacao"] == [], frase
    assert laudo["termos_vetados"] == [], frase
    assert laudo["bloqueante"] is False, frase


# --- Termos vetados-com-número (bloqueante determinístico, D6c) ---------------


@pytest.mark.parametrize(
    ("frase", "classe"),
    [
        ("## Juros\nCurva DI: 12,5% para 2027.", "renda_fixa"),
        ("## Juros\nA curva DI precifica 12,5% no vencimento 2027.", "acao"),  # universal
        ("## Inflação\nInflação implícita: 6,2% ao ano.", "renda_fixa"),
        ("## Solidez\nÍndice de Basileia: 14,8%.", "acao"),
        ("## Solidez\nO índice de Basileia do banco é 14,8%.", "banco"),
        ("## Valuation\nP/VP: 0,92 — desconto sobre o valor patrimonial.", "fii"),
        ("## Indicadores\nDividend yield anualizado: 8,1%.", "fii"),
        ("## Indicadores\nDY a mercado: 9,0%.", "fii"),
        # anualizar o DY do informe é vetado MESMO rotulado ("NUNCA anualizar").
        ("## Indicadores\nDY do informe anualizado: 8,0%.", "fii"),
    ],
)
def test_termos_vetados_com_numero_bloqueiam(frase: str, classe: str):
    laudo = avaliar_tese(_envelope(frase), classe=classe)
    assert laudo["termos_vetados"], frase
    assert laudo["bloqueante"] is True, frase


def test_pvp_com_numero_fora_de_fii_nao_bloqueia():
    # Escopo por classe: o veto de P/VP vale para FII (lacuna de preço B3).
    md = "## Valuation\nP/VP: 0,92 segundo o relatório da administradora."
    laudo = avaliar_tese(_envelope(md))  # classe default 'acao'
    assert laudo["termos_vetados"] == []
    assert laudo["bloqueante"] is False


def test_curva_di_sem_numero_como_lacuna_nao_bloqueia():
    md = "## Juros\nCurva DI completa: dado não encontrado (fonte licenciada)."
    laudo = avaliar_tese(_envelope(md), classe="renda_fixa")
    assert laudo["termos_vetados"] == []


def test_curva_di_com_proxy_no_mesmo_periodo_nao_bloqueia():
    md = "## Juros\nProxy da curva DI via Tesouro prefixado: 13,1% (2029)."
    laudo = avaliar_tese(_envelope(md), classe="renda_fixa")
    assert laudo["termos_vetados"] == []
    assert laudo["bloqueante"] is False


def test_termos_vetados_funcao_pura_positivos_e_negativos():
    # POSITIVOS — termo + número no mesmo período => achado.
    assert termos_vetados_com_numero("A curva DI precifica 12,5% em 2027.", "acao")
    assert termos_vetados_com_numero("Inflação implícita: 6,2%.", "renda_fixa")
    assert termos_vetados_com_numero("O índice de Basileia é de 14,8%.", "banco")
    assert termos_vetados_com_numero("P/VP: 0,92.", "fii")
    assert termos_vetados_com_numero("Dividend yield a mercado: 9,0%.", "fii")
    # NEGATIVOS — proxy nomeado, escopo de classe, rótulo do informe, sem número.
    assert termos_vetados_com_numero("Proxy da curva DI: prefixado a 13,1%.", "renda_fixa") == []
    assert termos_vetados_com_numero("P/VP: 0,92.", "acao") == []
    assert termos_vetados_com_numero("DY mensal do informe (auto-declarado): 0,66%.", "fii") == []
    assert termos_vetados_com_numero("A inflação implícita não é observável aqui.", "rf") == []
    assert termos_vetados_com_numero("Curva DI: dado não encontrado.", "renda_fixa") == []


# --- Red-team fase 2 (M4): falso positivo de ano/data e bypasses do veto ------


def test_ano_de_referencia_nao_bloqueia_lacuna_legitima_m4a():
    # M4a: '2025' é metadado de data (mesmo critério de número-de-claim de
    # _numeros_significativos), não número — a lacuna legítima de FII passa.
    md = "## Lacunas\n- P/VP a preço de mercado: dado não encontrado (dados do informe de 2025)"
    laudo = avaliar_tese(_envelope(md), classe="fii")
    assert laudo["termos_vetados"] == []
    assert laudo["bloqueante"] is False


def test_data_dd_mm_aaaa_nao_conta_como_numero_de_claim_m4a():
    lacuna_datada = "P/VP: dado não encontrado (informe de 31/12/2025)."
    assert termos_vetados_com_numero(lacuna_datada, "fii") == []
    assert termos_vetados_com_numero("Curva DI: dado não encontrado em 2025.", "rf") == []
    # Percentual explícito segue sendo claim mesmo sem separador decimal.
    assert termos_vetados_com_numero("Curva DI em 13% no curto prazo.", "renda_fixa")


def test_numero_antes_do_termo_na_mesma_frase_bloqueia_m4b():
    # M4b: número ANTES do termo não pode escapar — a frase INTEIRA é varrida.
    assert termos_vetados_com_numero("Aos 12,5%, a curva DI segue pressionada.", "renda_fixa")
    laudo = avaliar_tese(
        _envelope("## Juros\nAos 12,5%, a curva DI segue pressionada no curto prazo."),
        classe="renda_fixa",
    )
    assert laudo["termos_vetados"]
    assert laudo["bloqueante"] is True


# --- Achado da 1ª síntese FII ao vivo (HGLG11, 09/07/2026): ressalva negada ---


def test_dy_do_informe_com_ressalva_negada_nao_bloqueia():
    # Regressão do falso positivo ao vivo: o rótulo mandatório do informe
    # (fii._ROTULOS_INDICADOR) contém ';' — o split de frase separa 'do
    # informe (auto-declarado' do número — e a ressalva protetora "NÃO é DY a
    # preço de mercado e não deve ser anualizado" acionava o veto. Negação
    # na mesma cláusula é cautela, não claim.
    md = (
        "## 1. Fundamentos do fundo\n"
        "- **Dividend yield mensal do informe (auto-declarado; NÃO é DY a preço "
        "de mercado e não deve ser anualizado):** 0,66% (competência 2026-05-01; "
        "metodologia: auto-declarado pelo administrador; informe mensal CVM)."
    )
    assert termos_vetados_com_numero(md, "fii") == []
    laudo = avaliar_tese(_envelope(md), classe="fii")
    assert laudo["termos_vetados"] == []
    assert laudo["bloqueante"] is False


def test_dy_anualizado_sem_negacao_segue_vetado():
    # A ressalva só protege quando NEGADA na MESMA cláusula: negação seguida
    # de ':' (outra cláusula, mesmo período do split) não blinda o termo.
    assert termos_vetados_com_numero("DY do informe anualizado: 8,0%.", "fii")
    assert termos_vetados_com_numero(
        "O DY do informe não é especulativo: anualizado atinge 8,1% (auto-declarado).",
        "fii",
    )


def test_dy_a_preco_de_mercado_sem_negacao_e_vetado():
    # Furo fechado junto: 'a PREÇO DE mercado' não casava com r'\ba\s+mercado\b'
    # — um DY rotulado 'do informe' mas afirmado A PREÇO DE MERCADO passava.
    assert termos_vetados_com_numero(
        "DY do informe (auto-declarado) a preço de mercado: 9,0%.", "fii"
    )


def test_numero_em_linha_seguinte_de_bullet_quebrado_bloqueia_m4c():
    # M4c: quebra de linha SIMPLES dentro do mesmo bullet é o MESMO período.
    md = "## Juros\n- A curva DI precifica\n  12,5% no vencimento 2027."
    laudo = avaliar_tese(_envelope(md), classe="renda_fixa")
    assert laudo["termos_vetados"]
    assert laudo["bloqueante"] is True


def test_bullets_distintos_nao_se_fundem_no_check_m4c():
    # Bullet novo ('- ') é fronteira de período: a lacuna da curva DI não herda
    # o número do bullet vizinho (e o DY rotulado do informe segue legítimo).
    md = (
        "## Lacunas\n"
        "- Curva DI completa por prazo: dado não encontrado (B3/ANBIMA licenciadas)\n"
        "- DY mensal do informe (auto-declarado): 0,66%"
    )
    laudo = avaliar_tese(_envelope(md), classe="fii")
    assert laudo["termos_vetados"] == []
    assert laudo["bloqueante"] is False


# --- Tokens temáticos por classe: NÃO-bloqueantes (derrubam só `aprovado`) ----


def test_tokens_de_classe_ausentes_derrubam_aprovado_sem_bloquear():
    md = "## 1. Visão\nFundo de galpões com contratos longos."  # sem 'vac'/'patrim'
    laudo = avaliar_tese(_envelope(md), classe="fii")
    assert laudo["tokens_classe_ausentes"] == ["vac", "patrim"]
    assert laudo["bloqueante"] is False
    assert laudo["aprovado"] is False


def test_tokens_de_classe_presentes_nao_derrubam():
    md = "## Imóveis\nVacância física: 3,2%; patrimônio líquido de R$ 7,06 bi."
    laudo = avaliar_tese(_envelope(md), classe="fii")
    assert laudo["tokens_classe_ausentes"] == []


def test_tokens_de_classe_nao_afetam_acao():
    md = "## Fundamentos\nReceita de Venda de Bens e/ou Serviços: R$ 497,5 bi."
    laudo = avaliar_tese(_envelope(md))  # default 'acao': sem tokens de classe
    assert laudo["tokens_classe_ausentes"] == []


# --- Piso de fidelidade numérica: nota p/ classes novas, 'acao' inalterada ----


def test_faithfulness_piso_derruba_aprovado_de_classe_nova_sem_bloquear():
    # Números do corpo NÃO citados => fidelidade 0 < piso; deve derrubar
    # `aprovado` (nota) sem bloquear (proxy fuzzy não veta sozinho).
    md = "## Imóveis\nVacância: 3,2%; patrimônio: R$ 7,06 bi."
    laudo = avaliar_tese(_envelope(md), classe="fii")
    assert laudo["faithfulness_numerica"] is not None
    assert laudo["faithfulness_numerica"] < laudo["faithfulness_piso"]
    assert laudo["aprovado"] is False
    assert laudo["bloqueante"] is False


def test_faithfulness_piso_nao_muda_comportamento_de_acao():
    # Mesmo cenário (número não citado) em 'acao': métrica só reportada (fase 1).
    md = "## Fundamentos\nReceita: R$ 497,5 bi (CVM)."
    laudo = avaliar_tese(_envelope(md))
    assert laudo["faithfulness_numerica"] is not None
    assert laudo["faithfulness_numerica"] < laudo["faithfulness_piso"]
    assert laudo["aprovado"] is True
    assert laudo["bloqueante"] is False
