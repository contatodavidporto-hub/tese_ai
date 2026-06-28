"""Gate de confiança — avaliação automática de uma tese gerada (Estágio 1B, S12).

Checagem **determinística** que complementa um faithfulness/NLI mais pesado
(RAGAS) e a revisão manual. Roda offline sobre o envelope da tese e é ACOPLADA
ao caminho de produção (`gerar_tese` chama este gate antes de servir):

1. Zero recomendação de compra/venda (postura CVM) — cobre verbos direcionais
   de research/sell-side em PT-BR, não só "comprar/vender".
2. Cobertura de citações: há citações, elas resolvem para fontes com URL, e a
   fração de fontes citadas atinge um limiar mínimo.
3. Integridade da abstenção + guarda geopolítica: a seção geopolítica não pode
   afirmar eventos específicos (guerra/OPEP/sanção…) sem hedge — como o slice
   não ingere eventos, qualquer afirmação dura ali é ungrounded.

`avaliar_tese` devolve `aprovado` (gate estrito) e `bloqueante` (subconjunto
inegociável que NUNCA pode ser servido: recomendação, evento sem fonte, fonte
sem URL). Heurística por desenho; a garantia forte é o system prompt + revisão.
"""

from __future__ import annotations

import re

# --- Recomendação direcional (positiva). Ancorada para evitar falsos positivos:
#     "venda" cru (conta "Receita de Venda"), "recomendação" (disclaimer),
#     "valor justo"/"acumulados" (termos contábeis). ---
_PADROES_RECOMENDACAO = [
    r"\brecomendo\b",
    r"\brecomendamos\b",
    r"\brecomenda-se\b",
    r"\brecomend[áa]vel\b",
    r"\bvale a pena\b",
    r"\bpre[çc]o[\s-]?alvo\b",
    r"\bvalor[\s-]?alvo\b",
    r"\bpre[çc]o[\s-]?justo\b",
    r"\bcompre\b",
    r"\b(comprar|vender)\s+(a|as|essa|essas|sua|suas)\s+a[çc][õoãa][eo]s?\b",
    r"\b(deve|deveria|sugiro|sugerimos)\s+(comprar|vender)\b",
    r"\bboa\s+(compra|oportunidade de compra)\b",
    # Jargão de research / sell-side (ancorado em posição/exposição p/ evitar
    # "manutenção de equipamentos", "lucros acumulados" etc.)
    r"\bmantenh[ao]\b",
    r"\bmanter\s+(a\s+)?(posi[çc][ãa]o|exposi[çc][ãa]o|o ativo|o papel)\b",
    r"\bacumul(e|ar|em)\b",
    r"\breduz(a|ir)\s+(a\s+)?(posi[çc][ãa]o|exposi[çc][ãa]o)\b",
    r"\baument(e|ar)\s+(a\s+)?(posi[çc][ãa]o|exposi[çc][ãa]o)\b",
    r"\brealiz(e|ar)\s+(o\s+)?lucro\b",
    r"\bstop[\s-]?loss\b",
    r"\bponto de (entrada|sa[íi]da)\b",
    r"\b(out|under)perform\b",
    r"\b(sobre|sub)ponderar\b",
    r"\b(over|under)weight\b",
    r"\b(up|down)side de\b",
    r"\bsegur(e|ar)\s+(a\s+)?(a[çc][ãa]o|posi[çc][ãa]o)\b",
    r"\brating[:\s]+(compra|venda|manter|neutro)\b",
]
_RECOMENDACAO_RE = re.compile("|".join(_PADROES_RECOMENDACAO), re.IGNORECASE)

# Remove só o TRECHO do disclaimer (a cláusula, NÃO o resto da frase) antes de
# varrer — assim "Não é recomendação, mas recomendo comprar" não escapa pela linha.
# Limitado a "de investimento" para não engolir texto direcional subsequente.
_DISCLAIMER_RE = re.compile(
    r"n[ãa]o (é|e|constitui|configura) recomenda[çc][ãa]o(\s+de\s+investimento)?",
    re.IGNORECASE,
)

# Guarda geopolítica: eventos específicos afirmados sem hedge na seção 3.
_EVENTO_RE = re.compile(
    r"\b(guerra|conflito armado|san[çc](ão|ões|oes|ões)|embargo|opep|opec|"
    r"invas(ão|ões|ao)|golpe|atentado|cessar[\s-]?fogo|bloqueio naval)\b",
    re.IGNORECASE,
)
_HEDGE_RE = re.compile(
    r"(cen[áa]rio|\bse\b|\bcaso\b|poderia|\bpode\b|eventual|hip[óo]tes|"
    r"interpreta[çc][ãa]o|poss[íi]vel|condicional|tens[õo]es geopol)",
    re.IGNORECASE,
)
# NEGAÇÃO da OCORRÊNCIA/AFIRMAÇÃO do evento: o disclaimer do próprio motor cita os
# termos de evento (guerra/OPEP/sanção…) só para NEGÁ-los ("não há … embargos/OPEP",
# "não afirmo nenhum evento", "Nenhuma guerra … é afirmada como ocorrida"). Isso não
# é afirmação dura — não pode disparar o alerta. O guard é DELIBERADAMENTE estreito
# para não criar falso-negativo (achado do auditor): exige que a negação trave a
# ocorrência/afirmação do evento, não um "não"/"nenhum" qualquer. Assim seguem
# BLOQUEANDO: "A guerra não acabou.", "Não resta nenhuma dúvida de que a OPEP cortou
# a produção." (nega a dúvida, afirma o evento) e "Nenhuma guerra foi declarada, mas
# houve um atentado." (nega um evento, afirma outro).
# LIMITAÇÃO conhecida (heurística — a garantia forte é o system prompt + revisão,
# ver docstring): a exenção vale para a FRASE inteira (split só em `.;`/quebra). Uma
# frase que negue um evento E afirme OUTRO na mesma oração ligada por vírgula/
# adversativa ("… não há registro, mas a OPEP cortou …") pode escapar. NÃO dividimos
# em vírgula/adversativa de propósito: quebraria a lista do disclaimer ("Nenhuma
# guerra, sanção, …") em fragmentos soltos e/ou isolaria o hedge da sua oração
# condicional ("Cenário: caso …, mas … embargos") → reintroduziria o falso-positivo
# que este fix corrige. Probabilidade baixa: o motor teria de emitir disclaimer
# correto E afirmação dura na mesma frase, o que o system prompt veda.
_NEGACAO_RE = re.compile(
    r"n[ãa]o\s+h[áa]\b"
    r"|n[ãa]o\s+afirm"
    r"|n[ãa]o\s+(é|e|foi|s[ãa]o)\s+afirmad"
    r"|\bsem\s+(evento|registro)\b"
    r"|\binexist"
    r"|\bnenhum[ao]?\b[^.;]*?\b(afirmad|afirma|ocorrid|ocorre|registrad|registro|mencionad|confirmad)",
    re.IGNORECASE,
)

_COBERTURA_MINIMA = 0.5


def _strip_disclaimer(texto: str) -> str:
    return _DISCLAIMER_RE.sub("", texto)


def _violacoes_recomendacao(texto: str) -> list[str]:
    achados: list[str] = []
    for ln in texto.splitlines():
        limpo = _strip_disclaimer(ln)
        for m in _RECOMENDACAO_RE.finditer(limpo):
            achados.append(m.group(0).strip())
    return achados


def _secao_geopolitica(markdown: str) -> str:
    """Extrai o texto da seção '## 3. Camada geopolítica' (até o próximo H2)."""
    linhas = markdown.splitlines()
    dentro = False
    buf: list[str] = []
    for ln in linhas:
        if re.match(r"^##\s", ln):
            dentro = "geopol" in ln.lower()
            continue
        if dentro:
            buf.append(ln)
    return "\n".join(buf)


def _alertas_geopolitica(markdown: str) -> list[str]:
    """Frases na seção geopolítica que afirmam um evento específico sem hedge."""
    secao = _secao_geopolitica(markdown)
    alertas: list[str] = []
    for frase in re.split(r"(?<=[.;])\s+|\n", secao):
        if (
            _EVENTO_RE.search(frase)
            and not _HEDGE_RE.search(frase)
            and not _NEGACAO_RE.search(frase)
        ):
            alertas.append(frase.strip()[:160])
    return alertas


def avaliar_tese(envelope: dict) -> dict:
    """Avalia o envelope de uma tese e devolve o laudo + `aprovado`/`bloqueante`."""
    markdown = envelope.get("markdown") or ""
    citacoes = envelope.get("citacoes") or []
    fontes = envelope.get("fontes") or []
    lacunas = envelope.get("lacunas") or []
    # Inclui texto gerado por LLM exposto ao usuário (resumo do Haiku) na varredura.
    resumo = ((envelope.get("metadata") or {}).get("resumo")) or ""
    texto_varredura = markdown + "\n" + resumo

    violacoes = _violacoes_recomendacao(texto_varredura)
    alertas_geo = _alertas_geopolitica(markdown)
    fontes_sem_url = [
        (f.get("descricao") or f.get("id") or "?") for f in fontes if not f.get("url")
    ]

    fontes_citadas: set[str] = set()
    for c in citacoes:
        fonte = c.get("fonte") or {}
        fid = fonte.get("id") or fonte.get("url")
        if fid:
            fontes_citadas.add(str(fid))
    cobertura = (len(fontes_citadas) / len(fontes)) if fontes else 0.0

    lacunas_no_texto = sum(1 for ln in markdown.splitlines() if "dado não encontrado" in ln.lower())

    # Subconjunto INEGOCIÁVEL — nunca pode ser servido como tese pronta.
    bloqueante = bool(violacoes) or bool(alertas_geo) or bool(fontes_sem_url)

    motivos: list[str] = []
    if violacoes:
        motivos.append(f"linguagem de recomendação detectada: {sorted(set(violacoes))}")
    if alertas_geo:
        motivos.append(f"afirmação de evento geopolítico sem fonte/hedge: {alertas_geo}")
    if not citacoes:
        motivos.append("nenhuma citação ancorada à fonte")
    if fontes_sem_url:
        motivos.append(f"{len(fontes_sem_url)} fonte(s) sem URL")
    if fontes and cobertura < _COBERTURA_MINIMA:
        motivos.append(
            f"cobertura de citações insuficiente ({cobertura:.0%} < {_COBERTURA_MINIMA:.0%})"
        )

    aprovado = (
        not bloqueante and len(citacoes) > 0 and (not fontes or cobertura >= _COBERTURA_MINIMA)
    )

    return {
        "aprovado": aprovado,
        "bloqueante": bloqueante,
        "violacoes_recomendacao": sorted(set(violacoes)),
        "alertas_geopolitica": alertas_geo,
        "citacoes_total": len(citacoes),
        "fontes_total": len(fontes),
        "fontes_citadas": len(fontes_citadas),
        "cobertura_fontes": round(cobertura, 3),
        "cobertura_minima": _COBERTURA_MINIMA,
        "fontes_sem_url": fontes_sem_url,
        "lacunas_total": len(lacunas),
        "lacunas_no_texto": lacunas_no_texto,
        "motivos": motivos,
    }
