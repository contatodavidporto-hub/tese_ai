"""Gate v3 (F4) — regras NOVAS do plano "Tese Profunda" §2.10 + correções de
red-team A1/A2/A3/A5/A6/A7 (`.maestro/plano-correcoes-redteam.md`, que VENCE
sobre o §2.10 em qualquer conflito).

Padrão fixtures-verbatim + red-team do repositório (`test_avaliacao.py`):
cada regra ganha casos que DEVEM bloquear (vermelho) e casos que DEVEM passar
(verde), com templates REAIS de `tecnica.py`/`valuation.py` onde a correção
exige ("importe e rode os templates de verdade").

Cobertura:
- A5: `texto_varredura` inclui `envelope['texto_livre_novo']`.
- A1/R12: carve-out de consenso (preço-alvo/price target/rating) escopado a
  seção + atribuição + número casado com item validado.
- A2/A3: relaxamento por CITAÇÃO (Basileia/inflação implícita/P-VP-FII/DY a
  mercado) — nunca por rótulo textual solto; DY a mercado é regra NOVA e
  independente da isenção do informe.
- A7/R10: técnica-como-conselho.
- A6/R11: valuation-como-preço-alvo, sem os gatilhos genéricos.
- Hotfix 2 (2026-07-11, bug TAEE11 provado ao vivo na 2ª tentativa): DUAS
  superfícies de varredura — `termos_vetados_com_numero`/A2/A3/R12/
  faithfulness SÓ em markdown+resumo (autoria do modelo, proveniência por
  citação); R1/R10/R11 seguem em markdown+resumo+texto_livre_novo (postura,
  qualquer autor). `texto_livre_novo` nunca tem citação correspondente
  (é escrito pelo backend DEPOIS da síntese) — antes do fix, número
  legítimo com proveniência estrutural (fonte_id) bloqueava sempre.
"""

from __future__ import annotations

import datetime as dt
import math
from types import SimpleNamespace

import pytest

from app.services import tecnica as tecnica_svc
from app.services import valuation as valuation_svc
from app.services.avaliacao import (
    _consenso_numeros_sem_atribuicao,
    _violacoes_recomendacao,
    _violacoes_tecnica_como_conselho,
    _violacoes_valuation_como_alvo,
    avaliar_tese,
    termos_vetados_com_numero,
)

# ---------------------------------------------------------------------------
# Helpers (espelham o padrão de test_avaliacao.py)
# ---------------------------------------------------------------------------

_FONTE_GENERICA = {
    "id": "11111111-1111-1111-1111-111111111111",
    "url": "https://dados.cvm.gov.br/x.zip",
    "descricao": "CVM DFP 2025 — PETR4",
    "dt_referencia": "2025-12-31",
}


def _completar_secoes(markdown: str) -> str:
    h2s = " | ".join(ln.lower() for ln in markdown.splitlines() if ln.startswith("## "))
    if "geopol" not in h2s:
        markdown += (
            "\n\n## Camada geopolítica (interpretação)\n"
            "Sem eventos afirmados; qualquer leitura é hipótese condicional."
        )
    if "lacun" not in h2s:
        markdown += "\n\n## Lacunas\n- dado não encontrado: exemplo de abstenção."
    return markdown


def _fonte(descricao: str, url: str = "https://exemplo.gov.br/y", **extra) -> dict:
    return {
        "id": descricao,
        "url": url,
        "descricao": descricao,
        "dt_referencia": "2026-07-10",
        **extra,
    }


def _citacao(texto_citado: str, fonte: dict, document_index: int = 0) -> dict:
    return {
        "texto_citado": texto_citado,
        "document_index": document_index,
        "titulo_documento": "doc",
        "fonte": fonte,
    }


def _consenso_env(itens: list[dict]) -> dict:
    return {
        "aviso": "Opiniões de terceiros reportadas com atribuição.",
        "itens": itens,
        "lacunas": [],
    }


def _item_consenso(
    valor: float, *, casa: str = "XP Investimentos", veiculo: str = "InfoMoney"
) -> dict:
    return {
        "casa": casa,
        "metrica": "preco_alvo",
        "valor": valor,
        "moeda": "BRL",
        "veiculo": veiculo,
        "url": "https://infomoney.com.br/materia",
        "titulo": "Casas de análise projetam alta para o papel",
        "data_materia": "2026-07-08",
        "data_busca": "2026-07-10",
    }


def _envelope(
    markdown: str,
    *,
    com_citacao: bool = True,
    citacoes: list | None = None,
    fontes: list | None = None,
    consenso: dict | None = None,
    texto_livre_novo: str = "",
    completo: bool = True,
) -> dict:
    fontes = fontes if fontes is not None else [_FONTE_GENERICA]
    if citacoes is None:
        citacoes = [_citacao("Lucro R$ 110.605.000.000,00", _FONTE_GENERICA)] if com_citacao else []
    md = _completar_secoes(markdown) if completo else markdown
    env: dict = {
        "markdown": md,
        "citacoes": citacoes,
        "fontes": fontes,
        "lacunas": [],
        "texto_livre_novo": texto_livre_novo,
    }
    if consenso is not None:
        env["consenso"] = consenso
    return env


# ===========================================================================
# A5 — texto_varredura passa a incluir envelope['texto_livre_novo']
# ===========================================================================


def test_a5_texto_livre_novo_bloqueia_linguagem_de_recomendacao():
    """Vermelho: número/linguagem de recomendação SÓ no texto_livre_novo (não
    no markdown) — antes de A5 isso NÃO seria varrido; agora precisa bloquear."""
    md = "## 1. Fundamentos\nReceita citada normalmente."
    env = _envelope(md, texto_livre_novo="Recomendamos comprar a ação agora mesmo.")
    laudo = avaliar_tese(env)
    assert laudo["bloqueante"] is True
    assert laudo["violacoes_recomendacao"]


def test_a5_texto_livre_novo_real_da_f3_passa():
    """Verde: `texto_livre_novo` construído com os templates REAIS da F3
    (`tese._texto_livre_novo`, reimplementado aqui só na formatação canônica
    documentada — a função em si é testada em test_pipeline_tese_profunda.py)
    combinando leituras técnicas reais + descrição real de valuation FII +
    consenso canônico — não pode bloquear."""
    tecnica_env = _tecnica_env_real()
    fii_valuation = _valuation_fii_real()
    partes = [ind["leitura"] for ind in tecnica_env["indicadores"]]
    partes.append(fii_valuation.modelos[0].descricao)
    partes.extend(fii_valuation.modelos[0].observacoes)
    partes.append("Segundo InfoMoney (2026-07-08), XP Investimentos tem preço-alvo de R$ 63,00.")
    texto_livre_novo = "\n".join(partes)
    md = "## 1. Fundamentos\nReceita citada normalmente."
    env = _envelope(
        md, texto_livre_novo=texto_livre_novo, consenso=_consenso_env([_item_consenso(63.0)])
    )
    laudo = avaliar_tese(env)
    assert laudo["violacoes_recomendacao"] == []
    assert laudo["violacoes_tecnica_como_conselho"] == []
    assert laudo["violacoes_valuation_como_alvo"] == []


# ===========================================================================
# A1/R12 — carve-out de consenso (preço-alvo/price target/rating)
# ===========================================================================

_H2_CONSENSO = "## Consenso de analistas (terceiros, atribuído)\n"


def _md_consenso(corpo: str) -> str:
    return "# Tese — XPTO4\n" + _H2_CONSENSO + corpo


# --- Vermelho -----------------------------------------------------------


@pytest.mark.parametrize(
    "corpo",
    [
        # 1) Alvo INVENTADO dentro da seção — número não casa com item validado.
        "Segundo a InfoMoney (08/07/2026), a XP Investimentos tem preço-alvo de R$ 99,00.",
        # 2) Atribuição AUSENTE — número casa, mas sem marcador.
        "O preço-alvo é de R$ 63,00 para os próximos 12 meses.",
        # 3) "consenso de analistas: R$ 63" SEM veículo — nem termo preço-alvo,
        #    nem atribuição; ainda assim é número solto na seção (R12).
        "Consenso de analistas apurado: R$ 63,00 (sem citar a fonte).",
        # 4) marcador FORA da lista reconhecida ("com base em" não é atribuição).
        "Com base na XP, o preço-alvo soma R$ 63,00.",
        # 5) atribuição correta, mas número ERRADO (paráfrase gen3 malformada).
        "Conforme a XP, o preço-alvo é de R$ 70,00.",
        # 6) Inglês — atribuição em inglês não é reconhecida (marcador é PT).
        "According to XP, the target price is R$ 63,00.",
        # 7) rating direcional sem atribuição.
        "Rating: compra para o papel, com potencial de valorização.",
    ],
    ids=[
        "alvo_inventado",
        "atribuicao_ausente",
        "consenso_sem_veiculo",
        "marcador_nao_reconhecido",
        "numero_nao_casado_parafrase",
        "ingles_sem_atribuicao_pt",
        "rating_sem_atribuicao",
    ],
)
def test_a1_consenso_dentro_da_secao_sem_condicoes_bloqueia(corpo: str):
    md = _md_consenso(corpo)
    env = _envelope(md, consenso=_consenso_env([_item_consenso(63.0)]))
    laudo = avaliar_tese(env)
    assert laudo["bloqueante"] is True, corpo
    assert laudo["violacoes_recomendacao"] or laudo["consenso_sem_atribuicao"], corpo


def test_a1_preco_alvo_fora_da_secao_bloqueia_sem_excecao():
    """preço-alvo ATRIBUÍDO e com número CASADO, mas em outra seção — A1: fora
    da seção de consenso, bloqueante SEM EXCEÇÃO."""
    md = (
        "# Tese — XPTO4\n"
        "## Síntese\n"
        "Segundo a InfoMoney (08/07/2026), a XP Investimentos tem preço-alvo de R$ 63,00.\n"
        + _H2_CONSENSO
        + "Nenhum dado adicional nesta seção.\n"
    )
    env = _envelope(md, consenso=_consenso_env([_item_consenso(63.0)]))
    laudo = avaliar_tese(env)
    assert laudo["bloqueante"] is True
    assert laudo["violacoes_recomendacao"]


def test_a1_sem_bloco_consenso_no_envelope_carveout_nunca_dispara():
    """Sem `envelope['consenso']` (classe/estágio sem consenso), o carve-out
    não tem itens para casar — qualquer 'preço-alvo' na seção continua
    bloqueando (fail-closed por ausência de dado)."""
    md = _md_consenso(
        "Segundo a InfoMoney (08/07/2026), a XP Investimentos tem preço-alvo de R$ 63,00."
    )
    env = _envelope(md)  # sem consenso=...
    laudo = avaliar_tese(env)
    assert laudo["bloqueante"] is True


# --- Verde ----------------------------------------------------------------


@pytest.mark.parametrize(
    "corpo",
    [
        # Template canônico exato (tese._documento_consenso / _texto_livre_novo).
        "Segundo InfoMoney (08/07/2026), XP Investimentos tem preço-alvo de "
        "R$ 63,00 (Casas de análise projetam alta para o papel, "
        "https://infomoney.com.br/materia).",
        # Paráfrase gen2 — marcador reconhecido diferente ("conforme").
        "Conforme a InfoMoney (08/07/2026), a XP tem preço-alvo de R$ 63,00.",
        # Paráfrase gen3 — "na visão d[a]" + rating combinado.
        "Na visão da XP, segundo a InfoMoney (08/07/2026), o preço-alvo é de "
        "R$ 63,00 e o rating: compra.",
        # "para o" como marcador de atribuição.
        "Para a XP, segundo a InfoMoney (08/07/2026), o preço-alvo soma R$ 63,00.",
    ],
    ids=["canonico", "parafrase_conforme", "parafrase_visao_rating", "marcador_para_o"],
)
def test_a1_consenso_atribuido_e_casado_passa(corpo: str):
    md = _md_consenso(corpo)
    env = _envelope(md, consenso=_consenso_env([_item_consenso(63.0)]))
    laudo = avaliar_tese(env)
    assert laudo["violacoes_recomendacao"] == [], corpo
    assert laudo["consenso_sem_atribuicao"] == [], corpo
    assert laudo["bloqueante"] is False, corpo


def test_a1_multiplos_itens_de_consenso_cada_um_casa_o_seu():
    md = _md_consenso(
        "Segundo InfoMoney (08/07/2026), XP Investimentos tem preço-alvo de R$ 63,00. "
        "Já segundo Suno (09/07/2026), o BTG Pactual tem preço-alvo de R$ 58,50."
    )
    env = _envelope(
        md,
        consenso=_consenso_env(
            [
                _item_consenso(63.0, casa="XP Investimentos", veiculo="InfoMoney"),
                _item_consenso(58.50, casa="BTG Pactual", veiculo="Suno"),
            ]
        ),
    )
    laudo = avaliar_tese(env)
    assert laudo["bloqueante"] is False
    assert laudo["violacoes_recomendacao"] == []


# --- R12 direto (função pura) ----------------------------------------------


def test_r12_numero_sem_atribuicao_pure_function():
    md = _md_consenso("O mercado precifica o ativo perto de R$ 63,00, sem detalhar a fonte.")
    assert _consenso_numeros_sem_atribuicao(md, [63.0]) != []
    md_ok = _md_consenso("Segundo a InfoMoney (08/07/2026), o preço-alvo é de R$ 63,00.")
    assert _consenso_numeros_sem_atribuicao(md_ok, [63.0]) == []


# ===========================================================================
# A2/A3 — relaxamentos por CITAÇÃO (Basileia / inflação implícita / P-VP-FII
# / DY a mercado — regra nova A3)
# ===========================================================================


def test_a2_basileia_sem_citacao_correspondente_bloqueia():
    texto = "## Solidez\nÍndice de Basileia: 16,8%."
    assert termos_vetados_com_numero(texto, "banco") != []
    # Com citações presentes mas de OUTRA origem — segue bloqueante (não é o
    # rótulo textual que isenta, é a CITAÇÃO da origem certa).
    citacoes = [_citacao("Basileia de 16,8% no trimestre", _fonte("CVM DFP — outra fonte"))]
    assert termos_vetados_com_numero(texto, "banco", citacoes=citacoes) != []


def test_a2_basileia_com_citacao_ifdata_relaxa():
    texto = "## Solidez\nÍndice de Basileia: 16,8%."
    citacoes = [
        _citacao(
            "índice de Basileia (PR/RWA) de 16,8% na data-base",
            _fonte("BCB IF.data, data-base 202603 — indicadores prudenciais de bancos"),
        )
    ]
    assert termos_vetados_com_numero(texto, "banco", citacoes=citacoes) == []
    laudo = avaliar_tese(
        _envelope(texto, citacoes=citacoes + [_citacao("x", _FONTE_GENERICA)]),
        classe="banco",
    )
    assert laudo["termos_vetados"] == []
    assert laudo["bloqueante"] is False


def test_a2_inflacao_implicita_sem_citacao_bloqueia():
    texto = "## Inflação\nInflação implícita: 6,20% ao ano."
    assert termos_vetados_com_numero(texto, "renda_fixa") != []


def test_a2_inflacao_implicita_com_citacao_anbima_relaxa():
    texto = "## Inflação\nInflação implícita: 6,20% ao ano."
    citacoes = [
        _citacao(
            "inflação implícita do vértice de 6,20% no snapshot",
            _fonte("ANBIMA — ETTJ (estrutura a termo), reprodução com atribuição"),
        )
    ]
    assert termos_vetados_com_numero(texto, "renda_fixa", citacoes=citacoes) == []


def test_a2_pvp_fii_sem_citacao_bloqueia():
    texto = "## Valuation\nP/VP a mercado: 0,92."
    assert termos_vetados_com_numero(texto, "fii") != []


def test_a2_pvp_fii_com_citacao_cotahist_relaxa():
    texto = "## Valuation\nP/VP a mercado: 0,92."
    citacoes = [
        _citacao(
            "fechamento de R$ 95,00 ÷ VP por cota de R$ 103,26 = 0,92",
            _fonte("B3 — COTAHIST (dados de fim de dia), pregão 2026-07-09"),
        )
    ]
    assert termos_vetados_com_numero(texto, "fii", citacoes=citacoes) == []


def test_a3_dy_a_mercado_sem_citacao_bloqueia():
    texto = "## Indicadores\nDY a mercado: 9,00%."
    achados = termos_vetados_com_numero(texto, "fii")
    assert achados != []
    assert any("mercado" in a.lower() for a in achados)


def test_a3_dy_a_mercado_com_citacao_cotahist_relaxa():
    texto = "## Indicadores\nDY a mercado: 9,00%."
    citacoes = [
        _citacao(
            "soma dos proventos 12m ÷ fechamento resulta em 9,00%",
            _fonte("B3 — COTAHIST (dados de fim de dia), pregão 2026-07-09"),
        )
    ]
    assert termos_vetados_com_numero(texto, "fii", citacoes=citacoes) == []


def test_a3_dy_do_informe_e_dy_a_mercado_coexistem_na_mesma_frase():
    """Fixture central da correção A3: os DOIS DYs (informe, isento por
    RÓTULO; mercado, isento por CITAÇÃO) na MESMA frase — nenhum bloqueia
    quando cada um tem sua própria justificativa."""
    texto = (
        "## Indicadores\n"
        "O dividend yield mensal do informe (auto-declarado) é de 0,66%, enquanto "
        "o DY a mercado, segundo a B3, soma 9,00%."
    )
    citacoes = [
        _citacao(
            "DY a mercado 12m de 9,00% apurado sobre o fechamento",
            _fonte("B3 — COTAHIST (dados de fim de dia), pregão 2026-07-09"),
        )
    ]
    assert termos_vetados_com_numero(texto, "fii", citacoes=citacoes) == []


def test_a3_dy_do_informe_isolado_continua_isento_como_antes():
    """A3: a isenção do DY do informe NÃO foi tocada — continua funcionando
    sem nenhuma citação (comportamento pré-F4, `_dy_isento_no_periodo`)."""
    texto = "DY mensal do informe (auto-declarado): 0,66% (competência 2026-05-01)."
    assert termos_vetados_com_numero(texto, "fii") == []


# ===========================================================================
# A7/R10 — técnica-como-conselho
# ===========================================================================


@pytest.mark.parametrize(
    "frase",
    [
        "O RSI indica compra no curto prazo.",
        "Cruzamento dourado — hora de comprar.",
        "A média móvel de 200 sinaliza momento de compra.",
        "Rompeu o Fibonacci — ponto de entrada.",
        "MACD cruzou a zero, momento de venda.",
        "Estocástico em zona de sobrevenda: sinal de compra.",
        "The RSI signals a buy here.",  # inglês
        "Golden cross detected, time to buy.",  # inglês
    ],
)
def test_r10_tecnica_como_conselho_bloqueia(frase: str):
    assert _violacoes_tecnica_como_conselho(frase) != [], frase
    laudo = avaliar_tese(_envelope("## Técnica\n" + frase))
    assert laudo["bloqueante"] is True, frase
    assert laudo["violacoes_tecnica_como_conselho"], frase


def _tecnica_env_real() -> dict:
    """Roda os templates REAIS de `tecnica.py` sobre uma série sintética
    (~260 pregões, o suficiente p/ SMA(200)/EMA/MACD/RSI/Estocástico/
    Bollinger/Williams/A-D/Fibonacci NÃO ficarem omitidos)."""
    hoje = dt.date(2026, 7, 10)
    dias: list[dt.date] = []
    cursor = hoje - dt.timedelta(days=400)
    while len(dias) < 260:
        if cursor.weekday() < 5:
            dias.append(cursor)
        cursor += dt.timedelta(days=1)
    barras = []
    for i, data in enumerate(dias):
        preco = 30.0 + 5.0 * math.sin(i / 9.0) + i * 0.01
        barras.append(
            SimpleNamespace(
                ticker="TESTE4",
                data_pregao=data,
                maxima=preco + 0.6,
                minima=preco - 0.6,
                fechamento=preco,
                volume=1_500_000.0,
            )
        )
    resultado = tecnica_svc.calcular(barras)
    return tecnica_svc.tecnica_para_envelope(resultado)


def test_r10_leituras_reais_de_tecnica_py_nao_bloqueiam():
    """Verde: TODAS as leituras REAIS (RSI/MACD/Bollinger/Estocástico/
    Williams/médias móveis/A-D/Fibonacci) calculadas por `tecnica.calcular`
    passam — descritivo puro, sem diretiva."""
    tecnica_env = _tecnica_env_real()
    indicadores = tecnica_env["indicadores"]
    assert len(indicadores) >= 8, "esperava a bateria completa de indicadores"
    for ind in indicadores:
        achados = _violacoes_tecnica_como_conselho(ind["leitura"])
        assert achados == [], f"{ind['nome']}: {ind['leitura']!r} -> {achados}"
        achados_mede = _violacoes_tecnica_como_conselho(ind["o_que_mede"])
        assert achados_mede == [], f"{ind['nome']} (o_que_mede): {achados_mede}"


def test_r10_descritivo_puro_com_sobrecompra_sobrevenda_nao_bloqueia():
    """'sobrecompra'/'sobrevenda' são leituras REAIS e neutras — não têm
    fronteira de palavra antes de 'compr'/'vend' (uma palavra só) e não
    podem colidir com a diretiva."""
    frases = [
        "RSI(14) em 82,3 — região historicamente descrita como sobrecompra (acima de 70).",
        "Estocástico lento em 12,0 (%D em 15,0) — região historicamente descrita "
        "como sobrevenda (abaixo de 20).",
        "Williams %R(14) em -5,0 — região historicamente descrita como sobrecompra "
        "(acima de −20).",
    ]
    for frase in frases:
        assert _violacoes_tecnica_como_conselho(frase) == [], frase


# ===========================================================================
# A6/R11 — valuation-como-preço-alvo (sem gatilhos genéricos)
# ===========================================================================


@pytest.mark.parametrize(
    "frase",
    [
        "Valor justo de R$ 42,00, compre abaixo disso.",
        "Preço justo de R$ 55,00 — aproveite a oportunidade.",
        "O valor intrínseco supera o preço atual — oportunidade de compra clara.",
        "Com desconto de 20% sobre o valor justo, momento de entrada no papel.",
    ],
)
def test_r11_valuation_como_alvo_bloqueia(frase: str):
    assert _violacoes_valuation_como_alvo(frase) != [], frase
    laudo = avaliar_tese(_envelope("## Valuation\n" + frase))
    assert laudo["bloqueante"] is True, frase
    assert laudo["violacoes_valuation_como_alvo"], frase


@pytest.mark.parametrize(
    "frase",
    [
        # A6: gatilho genérico REMOVIDO — uso contábil/IFRS legítimo.
        "Os ativos são avaliados a valor justo, acima de R$ 2 bilhões no balanço.",
        "O passivo está reconhecido a valor justo, abaixo de R$ 500 milhões.",
        # paráfrases sem diretiva real.
        "O valor intrínseco estimado sob as premissas do cenário base é de R$ 40,00.",
        "O preço justo contábil dos instrumentos financeiros consta da nota explicativa.",
    ],
)
def test_r11_uso_contabil_sem_diretiva_nao_bloqueia(frase: str):
    assert _violacoes_valuation_como_alvo(frase) == [], frase


def _valuation_fii_real() -> valuation_svc.Valuation:
    """Roda o modelo REAL de leitura de mercado do FII (`valuation._modelo_fii`,
    via `valuation.avaliar`) — P/VP a mercado + DY a mercado + spread vs CDI."""
    insumos = valuation_svc.InsumosValuation(
        preco_atual=valuation_svc.Insumo(valor=95.0, fonte="B3 COTAHIST"),
        vp_cota=valuation_svc.Insumo(valor=103.26, fonte="Informe mensal CVM"),
        proventos_12m_por_cota=valuation_svc.Insumo(valor=8.55, fonte="B3 proventos"),
        cdi=valuation_svc.Insumo(valor=0.1415, fonte="BCB SGS 4391"),
    )
    resultado = valuation_svc.avaliar("fii", None, None, insumos)
    assert resultado is not None
    return resultado


def test_r11_template_real_de_valuation_fii_nao_bloqueia():
    """Verde: `_DESC_FII` ("...sem modelo de valor intrínseco") + as
    observações REAIS de P/VP a mercado, DY a mercado e spread vs CDI não
    podem casar com R11 (nenhuma diretiva ao leitor)."""
    resultado = _valuation_fii_real()
    modelo = resultado.modelos[0]
    assert "valor intrínseco" in modelo.descricao.lower()
    assert _violacoes_valuation_como_alvo(modelo.descricao) == []
    for obs in modelo.observacoes:
        assert _violacoes_valuation_como_alvo(obs) == [], obs
    assert _violacoes_valuation_como_alvo(resultado.aviso) == []


def test_r11_template_real_de_valuation_acao_gordon_nao_bloqueia():
    """Verde: descrição real do modelo de Gordon (ação genérica) + o aviso
    padrão de valuation não podem casar com R11 nem com o veto genérico de
    'preço-alvo' (decisão fora do plano — ver resposta final)."""
    insumos = valuation_svc.InsumosValuation(
        dividendo_por_acao_12m=valuation_svc.Insumo(valor=1.5, fonte="B3 proventos"),
        selic=valuation_svc.Insumo(valor=0.1425, fonte="BCB SGS 432"),
    )
    resultado = valuation_svc.avaliar("acao", None, None, insumos)
    assert resultado is not None
    modelo = resultado.modelos[0]
    assert _violacoes_valuation_como_alvo(modelo.descricao) == []
    assert _violacoes_recomendacao("", resultado.aviso, []) == []


# ===========================================================================
# Compatibilidade — disclaimer do bloco de valuation (decisão fora do plano)
# ===========================================================================


def test_aviso_valuation_nao_colide_com_veto_de_preco_alvo():
    """`valuation.AVISO_VALUATION` ("NÃO é preço-alvo nem recomendação") é o
    disclaimer do próprio motor — não pode ser lido como violação de
    'preço-alvo' (achado desta integração, `_DISCLAIMER_VALUATION_RE`)."""
    aviso = valuation_svc.AVISO_VALUATION
    assert "preço-alvo" in aviso.lower()
    md = "## Valuation por cenários (não é preço-alvo)\n" + aviso + "\n"
    laudo = avaliar_tese(_envelope(md))
    assert laudo["violacoes_recomendacao"] == []
    assert laudo["bloqueante"] is False


# ===========================================================================
# Hotfix 2 (2026-07-11) — bug TAEE11 provado ao vivo na 2ª tentativa: A5
# ampliou a varredura de linguagem/diretiva para `texto_livre_novo`, mas
# `termos_vetados_com_numero` (numérico, ancorado em CITAÇÃO) foi arrastado
# junto sem querer. `texto_livre_novo` é bloco DETERMINÍSTICO do backend
# (métricas/leituras técnicas/valuation), escrito DEPOIS da síntese — nunca
# tem citação Anthropic correspondente (proveniência é o `fonte_id`
# estrutural de cada métrica/insumo, não uma citação). Aplicar a isenção
# por citação (A2/A3) a esse texto é estruturalmente impossível de
# satisfazer, então todo termo vetado-com-número ali bloqueava sempre,
# mesmo groundado. Correção: DUAS superfícies —
# `texto_varredura_amplo` (+texto_livre_novo) só para R1/R10/R11 (postura);
# `texto_varredura_modelo` (sem texto_livre_novo) para as regras numéricas.
# ===========================================================================

_FRASE_TAEE11_DY_MERCADO = (
    "**Proventos (retrato do passado):** Dividend yield 12m a mercado: 8,23% "
    "(Σ proventos por ação com data-com nos últimos 12 meses / último preço "
    "de fechamento);"
)


def test_hotfix2_a_dy_mercado_no_texto_livre_novo_nao_bloqueia():
    """(a) Verde — a frase VIVA do bug TAEE11 (DY a mercado + número + Σ),
    EXATAMENTE como observada, dentro de `texto_livre_novo` e SEM nenhuma
    citação COTAHIST/B3 correspondente, com markdown limpo: aprovada,
    não-bloqueante. Proveniência é o `fonte_id` estrutural da métrica, não
    citação — este é o cenário que estava quebrado."""
    md = "## 1. Fundamentos\nReceita citada normalmente."
    env = _envelope(md, texto_livre_novo=_FRASE_TAEE11_DY_MERCADO)
    laudo = avaliar_tese(env, classe="acao")
    assert laudo["termos_vetados"] == [], laudo["termos_vetados"]
    assert laudo["bloqueante"] is False, laudo["motivos"]
    assert laudo["aprovado"] is True, laudo


def test_hotfix2_b_dy_mercado_no_markdown_sem_citacao_continua_bloqueando():
    """(b) Vermelho — SEM regressão: o MESMO tipo de claim ('DY a mercado de
    8,23%'), mas de autoria do MODELO (no markdown) e sem citação COTAHIST/B3,
    continua bloqueando. A superfície MODELO nunca perdeu a exigência de
    citação — só texto_livre_novo saiu da varredura numérica."""
    md = "## Indicadores\nDY a mercado de 8,23%, apurado no fechamento mais recente."
    env = _envelope(md)  # citação genérica default não é COTAHIST/B3
    laudo = avaliar_tese(env, classe="acao")
    assert laudo["bloqueante"] is True
    assert laudo["termos_vetados"] != []


def test_hotfix2_c_diretiva_no_texto_livre_novo_continua_bloqueando():
    """(c) Vermelho — SEM regressão: diretiva ao leitor ('recomendamos
    comprar') dentro de `texto_livre_novo` continua bloqueando — R1 roda na
    superfície AMPLA (que segue incluindo texto_livre_novo), pois é regra de
    POSTURA (CVM), não de proveniência numérica; não importa quem autorou."""
    md = "## 1. Fundamentos\nReceita citada normalmente."
    env = _envelope(md, texto_livre_novo="Recomendamos comprar a ação agora mesmo.")
    laudo = avaliar_tese(env, classe="acao")
    assert laudo["bloqueante"] is True
    assert laudo["violacoes_recomendacao"] != []


def test_hotfix2_d_basileia_no_texto_livre_novo_aprovado_no_markdown_bloqueia():
    """(d) Par verde/vermelho — Basileia (classe 'banco') com número: em
    `texto_livre_novo` (backend, proveniência estrutural) não bloqueia; o
    MESMO claim no markdown (autoria do modelo) sem citação IF.data/BCB
    continua bloqueando."""
    # Heading SEM numeração ("## Fundamentos", não "## 1. Fundamentos") —
    # evita o efeito colateral não relacionado de `_numeros_significativos`
    # tratar "1." do próprio número da seção como número "de claim" (ponto
    # após dígito conta como separador), o que derrubaria a fidelidade
    # numérica (D6d, nota — não bloqueia, mas reprovaria por outro motivo).
    md_verde = "## Fundamentos\nCarteira de crédito e PDD citadas normalmente."
    env_verde = _envelope(md_verde, texto_livre_novo="Índice de Basileia: 16,8% na data-base.")
    laudo_verde = avaliar_tese(env_verde, classe="banco")
    assert laudo_verde["termos_vetados"] == [], laudo_verde["termos_vetados"]
    assert laudo_verde["bloqueante"] is False, laudo_verde["motivos"]
    assert laudo_verde["aprovado"] is True, laudo_verde

    md_vermelho = "## Solidez\nÍndice de Basileia: 16,8% na data-base."
    env_vermelho = _envelope(md_vermelho)  # citação genérica default não é IF.data/BCB
    laudo_vermelho = avaliar_tese(env_vermelho, classe="banco")
    assert laudo_vermelho["bloqueante"] is True
    assert laudo_vermelho["termos_vetados"] != []
