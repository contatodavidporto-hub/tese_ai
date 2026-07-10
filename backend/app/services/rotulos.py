"""Rótulos humanos EXPLÍCITOS das séries macro (achado A5 do red-team).

Substitui a derivação frágil do rótulo por `fonte.descricao.split(": ")` — que
quebraria com descrições de múltiplos ": " (World Bank/commodities) e reintroduziria
confusão de unidade. O código da série é a chave canônica do rótulo.
"""

from __future__ import annotations

ROTULOS_MACRO: dict[str, str] = {
    "SELIC_DIARIA": "Selic diária (% a.d.)",
    "SELIC_META_ANUAL": "Meta Selic - Copom (% a.a.)",
    "USD_VENDA": "Dólar venda (R$/US$)",
    "IPCA_MENSAL": "IPCA - variação mensal (% a.m.)",
    "IGP_M_MENSAL": "IGP-M - variação mensal (% a.m.)",
    "COMMODITY_BRENT": "Petróleo Brent (US$/barril)",
    "GLOBAL_PIB_BR": "PIB do Brasil (US$ correntes)",
    "GLOBAL_PIB_US": "PIB dos EUA (US$ correntes)",
    "GLOBAL_INFLACAO_US": "Inflação anual EUA (% CPI a.a.)",
    "GLOBAL_TREASURY_10Y": "Juro do Tesouro EUA 10 anos (% a.a.)",
    # Renda fixa / cenário de juros (Fase 2 multiativo). CDI é FATO (SGS);
    # séries Focus são EXPECTATIVA e o rótulo diz isso explicitamente — o motor
    # de tese nunca pode narrá-las como fato realizado.
    "CDI_DIARIO": "CDI diário (% a.d.) — BCB SGS 12",
    "CDI_ANUAL": "CDI anualizado (% a.a.) — BCB SGS 4389",
    "FOCUS_SELIC_COPOM": (
        "Expectativa de mercado (Focus/BCB) — mediana Selic próxima reunião Copom; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_SELIC_COPOM_2": (
        "Expectativa de mercado (Focus/BCB) — mediana Selic 2ª reunião Copom mais próxima; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_SELIC_COPOM_3": (
        "Expectativa de mercado (Focus/BCB) — mediana Selic 3ª reunião Copom mais próxima; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_SELIC_COPOM_4": (
        "Expectativa de mercado (Focus/BCB) — mediana Selic 4ª reunião Copom mais próxima; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_SELIC_FIM_ANO": (
        "Expectativa de mercado (Focus/BCB) — mediana Selic no fim do ano corrente; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_SELIC_FIM_ANO_SEGUINTE": (
        "Expectativa de mercado (Focus/BCB) — mediana Selic no fim do ano seguinte; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_IPCA_ANO": (
        "Expectativa de mercado (Focus/BCB) — mediana IPCA acumulado no ano corrente; "
        "expectativa, não fato realizado"
    ),
    "FOCUS_IPCA_ANO_SEGUINTE": (
        "Expectativa de mercado (Focus/BCB) — mediana IPCA acumulado no ano seguinte; "
        "expectativa, não fato realizado"
    ),
}


def rotulo_macro(codigo: str, fallback: str | None = None) -> str:
    """Rótulo canônico da série; cai no fallback (ou no próprio código) se desconhecida."""
    return ROTULOS_MACRO.get(codigo) or fallback or codigo
