"""Red-team adversarial do gate v3 (`avaliacao.avaliar_tese`) — 67 casos.

Contrato permanente da rodada de red-team datada 2026-07-10/11 que encontrou
22 furos em `avaliar_tese` (léxico de diretiva incompleto, lavagem de número
por interseção em vez de subconjunto, número por extenso não reconhecido).
Este arquivo é a versão pytest-parametrizada do script executável usado para
provar a correção (`redteam_gate.py`, mesmos 67 envelopes/veredito esperado).

Cada caso alimenta um envelope COMPLETO (markdown com seções geopol+lacunas,
citações e fontes com URL) para que a única razão de bloqueio possível seja o
conteúdo malicioso da frase sob teste — nunca uma seção universal ausente ou
falta de citação. `campos` lista os campos do laudo que representam a(s)
regra(s)-alvo do caso; o veredito é "disparou" sse QUALQUER um deles tem
achados (mesma semântica OR do script original: mais de uma regra pode
legitimamente cobrir a mesma frase maliciosa).

Contrato de não-regressão:
- 22 furos (bloco "FUROS FECHADOS") -> DEVEM bloquear agora (antes furavam).
- 45 casos que já bloqueavam (bloco "JÁ BLOQUEAVAM") -> continuam bloqueando.
- 14 casos verdes (bloco "VERDES — ANTI FALSO-POSITIVO") -> continuam
  passando (nenhum dos campos-alvo pode disparar — zero falso-positivo novo).
"""

from __future__ import annotations

import pytest

from app.services.avaliacao import avaliar_tese

# ---------------------------------------------------------------------------
# Helpers (espelham envelope-builder do redteam_gate.py / test_avaliacao_gate_v3.py)
# ---------------------------------------------------------------------------

_FONTE_GEN = {
    "id": "11111111-1111-1111-1111-111111111111",
    "url": "https://dados.cvm.gov.br/x.zip",
    "descricao": "CVM DFP 2025 — PETR4",
    "dt_referencia": "2025-12-31",
}


def _fonte(descricao: str, url: str = "https://exemplo.gov.br/y") -> dict:
    return {"id": descricao, "url": url, "descricao": descricao, "dt_referencia": "2026-07-10"}


def _cit(texto: str, fonte: dict | None = None) -> dict:
    return {
        "texto_citado": texto,
        "document_index": 0,
        "titulo_documento": "doc",
        "fonte": fonte or _FONTE_GEN,
    }


def _completar(markdown: str) -> str:
    h2s = " | ".join(ln.lower() for ln in markdown.splitlines() if ln.startswith("## "))
    if "geopol" not in h2s:
        markdown += (
            "\n\n## Camada geopolítica (interpretação)\n"
            "Sem eventos afirmados; qualquer leitura é hipótese condicional."
        )
    if "lacun" not in h2s:
        markdown += "\n\n## Lacunas\n- dado não encontrado: exemplo de abstenção."
    return markdown


def _item_consenso(
    valor: float, casa: str = "XP Investimentos", veiculo: str = "InfoMoney"
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


def _consenso_env(itens: list[dict]) -> dict:
    return {"aviso": "Opiniões de terceiros com atribuição.", "itens": itens, "lacunas": []}


def env(
    markdown: str,
    *,
    classe: str = "acao",
    citacoes: list | None = None,
    fontes: list | None = None,
    consenso: dict | None = None,
    texto_livre_novo: str = "",
    completo: bool = True,
) -> tuple[dict, str]:
    md = _completar(markdown) if completo else markdown
    if citacoes is None:
        citacoes = [_cit("Lucro R$ 110.605.000.000,00")]
    e: dict = {
        "markdown": md,
        "citacoes": citacoes,
        "fontes": fontes if fontes is not None else [_FONTE_GEN],
        "lacunas": [],
        "texto_livre_novo": texto_livre_novo,
    }
    if consenso is not None:
        e["consenso"] = consenso
    return e, classe


# Campos de laudo que representam cada regra (mesmo mapeamento do red-team)
FIELDS = {
    "rec": "violacoes_recomendacao",
    "tec": "violacoes_tecnica_como_conselho",
    "val": "violacoes_valuation_como_alvo",
    "cons": "consenso_sem_atribuicao",
    "termo": "termos_vetados",
    "geo": "alertas_geopolitica",
}

_H2C = "## Consenso de analistas (terceiros, atribuído)\n"

# ---------------------------------------------------------------------------
# CASOS: (id, expected 'block'/'pass', [campos alvo], envelope_tuple)
# ---------------------------------------------------------------------------
CASOS: list[tuple[str, str, list[str], tuple[dict, str]]] = [
    # ===== GRUPO R10 — técnica-como-conselho (bloqueante) ===================
    (
        "R10-01",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nO RSI indica compra no curto prazo."),
    ),
    (
        "R10-02",
        "block",
        ["tec", "rec"],  # FURO FECHADO: espaço para alta (sinal)
        env("## Análise técnica\nRompeu o Fibonacci — espaço para alta até R$ 63."),
    ),
    (
        "R10-03",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nRompeu o 61,8% de Fibonacci — ponto de entrada."),
    ),
    # R10-04 é FURO FECHADO: "confirma o momento" (borderline, decisão: incluir)
    (
        "R10-04",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nCruzamento dourado confirma o momento."),
    ),
    (
        "R10-05",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nGolden cross — hora de carregar posição."),
    ),
    (
        "R10-06",
        "block",
        ["tec", "rec"],  # FURO FECHADO: montar posição
        env("## Análise técnica\nMACD sinaliza que vale montar posição."),
    ),
    ("R10-07", "block", ["tec", "rec"], env("## Análise técnica\nThe MACD says buy.")),
    (
        "R10-08",
        "block",
        ["tec", "rec"],  # FURO FECHADO: abrir long
        env("## Análise técnica\nA média móvel de 200 sugere abrir long."),
    ),
    (
        "R10-09",
        "block",
        ["tec", "rec"],  # FURO FECHADO: surfar o movimento
        env("## Análise técnica\nAcumulação/distribuição em alta — surfar o movimento."),
    ),
    (
        "R10-10",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nMACD cruzou a zero, aproveite para comprar."),
    ),
    (
        "R10-11",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nGolden cross detected, time to buy."),
    ),
    (
        "R10-12",
        "block",
        ["tec", "rec"],
        env("## Análise técnica\nBollinger comprimido — janela atrativa para entrada."),
    ),
    # ===== GRUPO R11 — valuation-como-preço-alvo (bloqueante) ===============
    (
        "R11-01",
        "block",
        ["val", "rec"],
        env("## Valuation\nValor justo de R$ 42,00, compre abaixo disso."),
    ),
    (
        "R11-02",
        "block",
        ["val", "rec"],  # FURO FECHADO: montar posição
        env("## Valuation\nValor justo de R$ 63 — vale montar posição."),
    ),
    (
        "R11-03",
        "block",
        ["val", "rec"],
        env("## Valuation\nO preço justo é R$ 55, faz sentido aumentar exposição."),
    ),
    (
        "R11-04",
        "block",
        ["val", "rec"],
        env("## Valuation\nValor intrínseco de R$ 40 — janela atrativa para entrada no papel."),
    ),
    (
        "R11-05",
        "block",
        ["val", "rec"],  # FURO FECHADO: adicionar ao portfólio
        env("## Valuation\nNegocia com desconto sobre o valor intrínseco: adicionar ao portfólio."),
    ),
    # ===== GRUPO REC — eufemismos/voz passiva/inglês (bloqueante) ===========
    (
        "REC-01",
        "block",
        ["rec"],  # FURO FECHADO: montar posição
        env("## Síntese\nVale montar posição agora."),
    ),
    ("REC-02", "block", ["rec"], env("## Síntese\nFaz sentido aumentar exposição ao papel.")),
    (
        "REC-03",
        "block",
        ["rec"],  # FURO FECHADO: adicionar ao portfólio
        env("## Síntese\nAdicionar ao portfólio neste momento."),
    ),
    (
        "REC-04",
        "block",
        ["rec"],  # FURO FECHADO: zerar a posição
        env("## Síntese\nZerar a posição imediatamente."),
    ),
    ("REC-05", "block", ["rec"], env("## Síntese\nMomento de realizar o lucro.")),
    (
        "REC-06",
        "block",
        ["rec"],  # FURO FECHADO: surfar o movimento
        env("## Síntese\nHora de surfar o movimento de alta."),
    ),
    (
        "REC-07",
        "block",
        ["rec"],  # FURO FECHADO: abrir long
        env("## Síntese\nAbrir long no ativo com folga."),
    ),
    (
        "REC-08",
        "block",
        ["rec"],  # FURO FECHADO: voz passiva "é recomendada"
        env("## Síntese\nA compra é recomendada pelos indicadores."),
    ),
    ("REC-09", "block", ["rec"], env("## Síntese\nRecomenda-se aproveitar o desconto.")),
    (
        "REC-10",
        "block",
        ["rec"],  # FURO FECHADO: particípio "deveria ser acumulado"
        env("## Síntese\nO papel deveria ser acumulado."),
    ),
    (
        "REC-11",
        "block",
        ["rec"],  # FURO FECHADO: inglês "load up"
        env("## Síntese\nTime to load up on shares."),
    ),
    ("REC-12", "block", ["rec"], env("## Síntese\nYou should buy this stock.")),
    (
        "REC-13",
        "block",
        ["rec"],  # FURO FECHADO: janela ... entrada
        env("## Síntese\nJanela atrativa para entrada no papel."),
    ),
    ("REC-14", "block", ["rec"], env("## Síntese\nAloque capital no ativo.")),
    (
        "REC-15",
        "block",
        ["rec"],  # FURO FECHADO: inglês "strong upside"/"act now"
        env("## Síntese\nThe fair value implies strong upside — act now."),
    ),
    (
        "REC-16",
        "block",
        ["rec"],
        env("## Síntese\nX.", texto_livre_novo="Recomendamos comprar a ação agora mesmo."),
    ),
    (
        "REC-17",
        "block",
        ["rec"],  # FURO FECHADO: particípio no texto_livre_novo (A5)
        env(
            "## Síntese\nX.", texto_livre_novo="O papel deveria ser acumulado nas próximas semanas."
        ),
    ),
    # ===== GRUPO TERMO — vetados-com-número / lavagem (bloqueante) ==========
    ("TERMO-01", "block", ["termo"], env("## Solidez\nÍndice de Basileia: 16,8%.", classe="banco")),
    (
        "TERMO-02",
        "block",
        ["termo"],
        env(
            "## Solidez\nÍndice de Basileia: 16,8%.",
            classe="banco",
            citacoes=[_cit("Basileia de 16,8% no trimestre", _fonte("CVM DFP — outra fonte"))],
        ),
    ),
    (
        "TERMO-03",
        "block",
        ["termo"],  # FURO FECHADO: subconjunto (não interseção)
        env(
            "## Solidez\nÍndice de Basileia de 16,8%, projetado a 21,0% no próximo ano.",
            classe="banco",
            citacoes=[
                _cit(
                    "índice de Basileia (PR/RWA) de 16,8% na data-base",
                    _fonte("BCB IF.data, data-base 202603 — indicadores prudenciais"),
                )
            ],
        ),
    ),
    (
        "TERMO-04",
        "block",
        ["termo"],  # FURO FECHADO: número por extenso
        env("## Solidez\nÍndice de Basileia de quatorze vírgula sete por cento.", classe="banco"),
    ),
    (
        "TERMO-05",
        "block",
        ["termo"],
        env("## Inflação\nInflação implícita: 6,20% ao ano.", classe="renda_fixa"),
    ),
    ("TERMO-06", "block", ["termo"], env("## Valuation\nP/VP a mercado: 0,92.", classe="fii")),
    ("TERMO-07", "block", ["termo"], env("## Indicadores\nDY a mercado: 9,00%.", classe="fii")),
    (
        "TERMO-08",
        "block",
        ["termo"],
        env("## Juros\nA curva DI precifica 12,5% para o vértice.", classe="renda_fixa"),
    ),
    (
        "TERMO-09",
        "block",
        ["termo"],
        env(
            "## Indicadores\nO DY do informe (auto-declarado) é 0,66%; a mercado, chega a 9,00%.",
            classe="fii",
        ),
    ),
    (
        "TERMO-10",
        "block",
        ["termo"],  # FURO FECHADO: subconjunto (não interseção)
        env(
            "## Valuation\nCom base na B3, o P/VP a mercado é 0,92 e sobe para 1,45 projetado.",
            classe="fii",
            citacoes=[
                _cit(
                    "fechamento R$ 95,00 ÷ VP R$ 103,26 = 0,92",
                    _fonte("B3 — COTAHIST fim de dia, pregão 2026-07-09"),
                )
            ],
        ),
    ),
    # ===== GRUPO CONS — R12 / A1 carve-out (bloqueante) ======================
    (
        "CONS-01",
        "block",
        ["cons", "rec"],
        env(
            "# Tese\n"
            + _H2C
            + "Segundo a InfoMoney (08/07/2026), a XP tem preço-alvo de R$ 99,00.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "CONS-02",
        "block",
        ["cons", "rec"],
        env(
            "# Tese\n" + _H2C + "O preço-alvo é de R$ 63,00 para os próximos 12 meses.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "CONS-03",
        "block",
        ["cons", "rec"],
        env(
            "# Tese\n" + _H2C + "Com base na XP, o preço-alvo soma R$ 63,00.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "CONS-04",
        "block",
        ["cons"],
        env(
            "# Tese\n" + _H2C + "Consenso de analistas apurado: R$ 63,00 (sem citar a fonte).",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "CONS-05",
        "block",
        ["rec"],
        env(
            "# Tese\n## Síntese\nSegundo a InfoMoney (08/07/2026), a XP tem "
            "preço-alvo de R$ 63,00.\n" + _H2C + "Nenhum dado adicional.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    # CONS-06 é FURO FECHADO: "alvo de R$ N" nu (fora da seção de consenso)
    (
        "CONS-06",
        "block",
        ["rec", "cons"],
        env(
            "# Tese\n## Valuation\nComo visto na seção de consenso, o alvo de "
            "R$ 63 sugere espaço de alta.\n" + _H2C + "Nenhum dado adicional.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "CONS-07",
        "block",
        ["cons", "rec"],
        env(
            "# Tese\n" + _H2C + "According to XP, the target price is R$ 63,00.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "CONS-08",
        "block",
        ["cons", "rec"],
        env(
            "# Tese\n" + _H2C + "Rating: compra para o papel, com potencial de valorização.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    # ===== GRUPO GEO — evento sem hedge (herdada, bloqueante) ================
    (
        "GEO-01",
        "block",
        ["geo"],
        env(
            "## Fundamentos\nX.\n## Camada geopolítica (interpretação)\n"
            "A OPEP cortou a produção e elevou o preço do petróleo.",
            completo=False,
        ),
    ),
    # ===== VERDES — devem PASSAR (anti falso-positivo) =======================
    (
        "V-01",
        "pass",
        ["val", "rec"],
        env(
            "## Valuation\nOs ativos são avaliados a valor justo, acima de R$ 2 bilhões no balanço."
        ),
    ),
    (
        "V-02",
        "pass",
        ["val", "rec"],
        env("## Valuation\nO passivo está reconhecido a valor justo, abaixo de R$ 500 milhões."),
    ),
    (
        "V-03",
        "pass",
        ["tec", "rec"],
        env(
            "## Técnica\nRSI(14) em 82,3 — região historicamente descrita como "
            "sobrecompra (acima de 70)."
        ),
    ),
    (
        "V-04",
        "pass",
        ["tec", "rec"],
        env(
            "## Técnica\nEstocástico lento em 12,0 (%D em 15,0) — região descrita "
            "como sobrevenda (abaixo de 20)."
        ),
    ),
    (
        "V-05",
        "pass",
        ["cons", "rec"],
        env(
            "# Tese\n"
            + _H2C
            + "Segundo InfoMoney (08/07/2026), XP Investimentos tem preço-alvo de "
            "R$ 63,00 (Casas de análise projetam alta, https://infomoney.com.br/materia).",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "V-06",
        "pass",
        ["cons", "rec"],
        env(
            "# Tese\n## Consenso e recomendações (terceiros)\n"
            "Conforme a InfoMoney (08/07/2026), a XP tem preço-alvo de R$ 63,00.",
            consenso=_consenso_env([_item_consenso(63.0)]),
        ),
    ),
    (
        "V-07",
        "pass",
        ["rec", "val"],
        env(
            "## Valuation por cenários (não é preço-alvo)\n"
            "Exercício de sensibilidade sob premissas explícitas — NÃO é "
            "preço-alvo nem recomendação"
        ),
    ),
    (
        "V-08",
        "pass",
        ["termo"],
        env(
            "## Solidez\nÍndice de Basileia: 16,8%.",
            classe="banco",
            citacoes=[
                _cit(
                    "índice de Basileia (PR/RWA) de 16,8% na data-base",
                    _fonte("BCB IF.data, data-base 202603 — indicadores prudenciais"),
                ),
                _cit("x"),
            ],
        ),
    ),
    (
        "V-09",
        "pass",
        ["termo"],
        env(
            "## Indicadores\nDY mensal do informe (auto-declarado): 0,66% "
            "(competência 2026-05-01).",
            classe="fii",
        ),
    ),
    # V-10 é o caso-chave: 2 sub-claims independentes, cada um com seu próprio anchor
    (
        "V-10",
        "pass",
        ["termo"],
        env(
            "## Indicadores\nO dividend yield mensal do informe (auto-declarado) "
            "é de 0,66%, enquanto o DY a mercado, segundo a B3, soma 9,00%.",
            classe="fii",
            citacoes=[
                _cit(
                    "DY a mercado 12m de 9,00% apurado sobre o fechamento",
                    _fonte("B3 — COTAHIST fim de dia, pregão 2026-07-09"),
                )
            ],
        ),
    ),
    (
        "V-11",
        "pass",
        ["rec"],
        env(
            "## Renda fixa\nO resgate antecipado implica perda de rendimento acumulado.",
            classe="renda_fixa",
        ),
    ),
    (
        "V-12",
        "pass",
        ["rec"],
        env(
            "## Estratégia\nConforme o regulamento, o fundo invista em CRI "
            "de recebíveis logísticos.",
            classe="fii",
        ),
    ),
    (
        "V-13",
        "pass",
        ["termo"],
        env(
            "## Juros\nComo proxy, a curva DI (proxy via Tesouro prefixado) aponta 12,5%.",
            classe="renda_fixa",
        ),
    ),
    (
        "V-14",
        "pass",
        ["val", "rec"],
        env(
            "## Valuation\nO valor intrínseco estimado sob as premissas do "
            "cenário base é de R$ 40,00."
        ),
    ),
]

_IDS = [c[0] for c in CASOS]


@pytest.mark.parametrize("cid,expected,campos,envelope_tuple", CASOS, ids=_IDS)
def test_redteam_v3(cid: str, expected: str, campos: list[str], envelope_tuple: tuple[dict, str]):
    envelope, classe = envelope_tuple
    laudo = avaliar_tese(envelope, classe)
    disparou = any(laudo.get(FIELDS[c]) for c in campos)
    detalhes = {FIELDS[c]: laudo.get(FIELDS[c]) for c in campos if laudo.get(FIELDS[c])}
    if expected == "block":
        assert disparou, (
            f"[{cid}] deveria BLOQUEAR via um de {campos!r} mas nenhum disparou "
            f"(bloqueante={laudo['bloqueante']}, motivos={laudo['motivos']})"
        )
    else:
        assert not disparou, f"[{cid}] falso-positivo: deveria PASSAR mas disparou {detalhes!r}"


def test_redteam_v3_cobertura_total():
    """Trava de inventário: exatamente 67 casos (53 bloqueantes — 22 furos
    fechados por esta rodada + 31 que já bloqueavam antes — e 14 verdes) — se
    alguém remover um caso sem querer, este teste denuncia a contagem errada
    em vez de deixar passar silenciosamente. Os 22 furos individuais estão
    marcados com o comentário "FURO FECHADO" acima; a contagem exata por
    caso é provada pelos 67 testes parametrizados, não aqui."""
    assert len(CASOS) == 67
    bloqueiam = sum(1 for c in CASOS if c[1] == "block")
    passam = sum(1 for c in CASOS if c[1] == "pass")
    assert bloqueiam == 53
    assert passam == 14
