"""Gate de confiança — avaliação automática de uma tese gerada (Estágio 1B, S12).

Checagem **determinística** que complementa um faithfulness/NLI mais pesado
(RAGAS) e a revisão manual. Roda offline sobre o envelope da tese:

1. Zero recomendação de compra/venda (postura CVM).
2. Cobertura de citações: há citações e elas resolvem para fontes com URL.
3. Integridade da abstenção: lacunas declaradas batem com "dado não encontrado".

Heurística por desenho (a garantia forte é o system prompt + revisão humana);
os padrões abaixo evitam falsos positivos comuns (a conta contábil "Receita de
Venda…" e o disclaimer "não é recomendação", que usa o substantivo).
"""

from __future__ import annotations

import re

# Padrões de RECOMENDAÇÃO direcional (positivos). Evitam:
# - "venda" cru (colide com a conta "Receita de Venda de Bens");
# - "recomendação" (substantivo do disclaimer / negações "não é recomendação").
_PADROES_RECOMENDACAO = [
    r"\brecomendo\b",
    r"\brecomendamos\b",
    r"\brecomenda-se\b",
    r"\brecomend[áa]vel\b",
    r"\bvale a pena\b",
    r"\bpre[çc]o[- ]alvo\b",
    r"\bcompre\b",
    r"\b(comprar|vender)\s+(a|as|essa|essas|sua|suas)\s+a[çc][õoãa][eo]s?\b",
    r"\b(deve|deveria|sugiro|sugerimos)\s+(comprar|vender)\b",
    r"\bboa\s+(compra|oportunidade de compra)\b",
]
_RECOMENDACAO_RE = re.compile("|".join(_PADROES_RECOMENDACAO), re.IGNORECASE)


def _violacoes_recomendacao(markdown: str) -> list[str]:
    # Ignora linhas de disclaimer (que negam recomendação) antes de varrer.
    linhas = [
        ln
        for ln in markdown.splitlines()
        if "não é recomendação" not in ln.lower() and "nao e recomendacao" not in ln.lower()
    ]
    achados: list[str] = []
    for ln in linhas:
        for m in _RECOMENDACAO_RE.finditer(ln):
            achados.append(m.group(0).strip())
    return achados


def avaliar_tese(envelope: dict) -> dict:
    """Avalia o envelope de uma tese e devolve o laudo + `aprovado` (bool)."""
    markdown = envelope.get("markdown") or ""
    citacoes = envelope.get("citacoes") or []
    fontes = envelope.get("fontes") or []
    lacunas = envelope.get("lacunas") or []

    violacoes = _violacoes_recomendacao(markdown)

    fontes_sem_url = [
        (f.get("descricao") or f.get("id") or "?") for f in fontes if not f.get("url")
    ]

    # Cobertura: fontes referenciadas por ao menos uma citação.
    fontes_citadas: set[str] = set()
    for c in citacoes:
        fonte = c.get("fonte") or {}
        fid = fonte.get("id") or fonte.get("url")
        if fid:
            fontes_citadas.add(str(fid))
    cobertura = (len(fontes_citadas) / len(fontes)) if fontes else 0.0

    lacunas_no_texto = sum(1 for ln in markdown.splitlines() if "dado não encontrado" in ln.lower())

    motivos: list[str] = []
    if violacoes:
        motivos.append(f"linguagem de recomendação detectada: {sorted(set(violacoes))}")
    if not citacoes:
        motivos.append("nenhuma citação ancorada à fonte")
    if fontes_sem_url:
        motivos.append(f"{len(fontes_sem_url)} fonte(s) sem URL")

    aprovado = not violacoes and len(citacoes) > 0 and not fontes_sem_url

    return {
        "aprovado": aprovado,
        "violacoes_recomendacao": sorted(set(violacoes)),
        "citacoes_total": len(citacoes),
        "fontes_total": len(fontes),
        "fontes_citadas": len(fontes_citadas),
        "cobertura_fontes": round(cobertura, 3),
        "fontes_sem_url": fontes_sem_url,
        "lacunas_total": len(lacunas),
        "lacunas_no_texto": lacunas_no_texto,
        "motivos": motivos,
    }
