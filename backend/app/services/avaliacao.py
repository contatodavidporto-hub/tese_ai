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

Fase 2 multiativo (D6): `avaliar_tese(envelope, classe="acao")` é retro-
compatível e ADITIVO por classe ('acao'/'banco'/'seguradora'/'fii'/'renda_fixa'):

4. Seções BLOQUEANTES universais: H2 contendo 'geopol' (sem ele a guarda
   geopolítica silenciosamente não roda — o buraco da fase 1) e H2 de Lacunas
   (abstenções declaradas). Tokens temáticos POR CLASSE são não-bloqueantes:
   ausência derruba `aprovado` (nota), nunca bloqueia.
5. Imperativos por classe ancorados em diretiva-ao-leitor (2ª pessoa/modal):
   'trave a taxa', 'adquira/subscreva cotas', 'deve/sugiro/recomendo +
   resgatar/travar/alocar/...'. Sujeito factual ('o fundo/o mandato invista
   em CRI') e subjuntivo condicional ('caso o investidor resgate...') passam.
6. Termos VETADOS-COM-NÚMERO (determinístico, bloqueante): 'curva DI' sem o
   rótulo 'proxy', 'inflação implícita', 'índice de Basileia' e — só p/ FII —
   'P/VP' e 'dividend yield' a mercado/anualizado. Fecha o convite à
   alucinação nas lacunas de cada classe.
7. Fidelidade numérica: para classes != 'acao' o piso derruba `aprovado`
   (nota), sem bloquear; comportamento de 'acao' inalterado (só reportada).
"""

from __future__ import annotations

import re
import unicodedata

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
    # --- PT que faltava (gap de idioma do gate — achado ALTO do auditor) ---
    # "recomendação de compra/venda" NÃO colide com o disclaimer, que é
    # "recomendação de investimento" (removido antes da varredura).
    r"\brecomenda[çc][ãa]o\s+(de\s+)?(compra|venda|comprar|vender)\b",
    r"\b(sugiro|sugerimos|recomendo|recomendamos)\s+(adquirir|alienar|alocar)\b",
    r"\baloqu?e(m|mos)?\s+(capital|recursos)\b",
    # --- Fase 2 multiativo (FII/RF/banco): diretivas ao leitor, ancoradas em
    #     2ª pessoa/modal (D6b). Lookbehinds excluem o SUJEITO factual: "o
    #     fundo/o mandato invista em CRI" descreve mandato FII (regra CVM),
    #     "o investidor" introduz subjuntivo condicional ("caso o investidor
    #     resgate..."). "resgate/venda" nus NÃO entram (campo STN "Taxa Venda
    #     Manhã", "o resgate antecipado implica..." são factuais). ---
    r"\btrav(e|em)\s+(a\s+|sua\s+|essa\s+)?taxa\b",
    r"(?<!fundo\s)(?<!mandato\s)\b(adquira|adquiram|subscreva|subscrevam)\s+(as\s+)?cotas\b",
    r"(?<!fundo\s)(?<!mandato\s)\b(deve(ria)?m?|sugiro|sugerimos|recomendo|recomendamos|"
    r"aconselho|aconselhamos)\s+(resgatar|travar|alocar|adquirir|carregar|comprar|vender)\b",
    r"(?<!fundo\s)(?<!mandato\s)(?<!investidor\s)\b(invista|invistam|aplique|apliquem)\s+em\b",
    # --- INGLÊS direcional (research/sell-side em EN) — a tese é PT-BR, então
    #     estes termos no output só aparecem como recomendação vazada. ---
    r"\bstrong\s+buy\b",
    r"\btarget\s+price\b",
    r"\byou\s+should\s+(buy|sell)\b",
    r"\b(buy|sell|hold|accumulate|overweight|underweight)\s+(rating|recommendation)\b",
    r"\b(buy|sell|hold|accumulate)\s+(the\s+)?(stock|shares|position)\b",
    r"\bprice\s+target\b",
    r"\brating[:\s]+(buy|sell|hold|neutral|overweight|underweight)\b",
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
# Piso de fidelidade numérica (D6d): reusa o limiar informativo já existente.
# Para classes != 'acao' derruba `aprovado` (nota) sem bloquear — o proxy é
# fuzzy (substring de números) e não pode vetar sozinho uma tese legítima.
_FAITHFULNESS_PISO = _COBERTURA_MINIMA

# Número "significativo" no texto: pelo menos 2 dígitos, com separadores de milhar/
# decimal BR (497.549.000.000,00 · 14,25 · 71,59). Ignora anos soltos e números de
# 1 dígito (ruído). Usado no proxy de fidelidade numérica.
_NUMERO_RE = re.compile(r"\d[\d.]*(?:,\d+)?")


# ---------------------------------------------------------------------------
# Fase 2 multiativo — classe, seções universais, tokens por classe e termos
# vetados-com-número (D6). Tudo determinístico e offline.
# ---------------------------------------------------------------------------

_CLASSE_ALIASES = {"rf": "renda_fixa", "renda-fixa": "renda_fixa", "renda fixa": "renda_fixa"}

# Tokens temáticos NÃO-bloqueantes por classe (D6a): ausência derruba `aprovado`
# (nota), nunca bloqueia. Buscados no corpo INTEIRO (minúsculo, sem acento) —
# não só em H2 — para que um reword de título não reprove a classe inteira.
_TOKENS_CLASSE: dict[str, tuple[str, ...]] = {
    "acao": (),
    "banco": ("pdd", "credito"),
    "seguradora": (),
    "fii": ("vac", "patrim"),
    "renda_fixa": ("marca", "juros"),
}

_FRASE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n")
# M4c (red-team fase 2): quebra de linha SIMPLES que só CONTINUA o mesmo
# bullet/parágrafo ("- A curva DI precifica\n  12,5%...") não pode encerrar o
# período do check de termos vetados — o número na linha seguinte escapava.
# A quebra vira espaço, EXCETO quando a próxima linha inicia novo bloco
# (bullet -/*/+, heading #, citação >, item numerado "1. ") ou é linha em
# branco/fim do texto (parágrafo novo). SÓ o check de termos vetados usa esta
# normalização; os demais checks preservam o split legado por linha.
_QUEBRA_CONTINUACAO_RE = re.compile(r"\n(?![ \t]*(?:[-*+#>]|\d+[.)]\s|\n|$))")
_PROXY_RE = re.compile(r"\bproxy\b", re.IGNORECASE)
_DY_ROTULO_INFORME_RE = re.compile(
    r"do\s+informe|auto[\s-]?declarad|informe\s+mensal", re.IGNORECASE
)
_DY_ANUALIZADO_OU_MERCADO_RE = re.compile(r"anualizad|\ba\s+mercado\b", re.IGNORECASE)

_VETADO_CURVA_DI = "curva DI com número sem rótulo 'proxy'"
_VETADO_DY = "dividend yield/DY com número sem rótulo 'do informe'/'auto-declarado'"

# (rótulo, regex do termo, classes onde vale — None = todas as classes)
_REGRAS_VETADAS: tuple[tuple[str, re.Pattern[str], frozenset[str] | None], ...] = (
    (_VETADO_CURVA_DI, re.compile(r"\bcurva\s+DI\b", re.IGNORECASE), None),
    (
        "inflação implícita com número",
        re.compile(r"\binfla[çc][ãa]o\s+impl[íi]cita\b", re.IGNORECASE),
        None,
    ),
    (
        "índice de Basileia com número (não está na DFP — lacuna)",
        re.compile(r"\b[íi]ndice\s+de\s+basil[eé]ia\b", re.IGNORECASE),
        None,
    ),
    (
        "P/VP com número (preço B3 licenciado — lacuna)",
        re.compile(r"\bP\s*/\s*VP\b", re.IGNORECASE),
        frozenset({"fii"}),
    ),
    (_VETADO_DY, re.compile(r"\b(dividend\s+yield|dy)\b", re.IGNORECASE), frozenset({"fii"})),
)


def _sem_acentos(texto: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", texto) if not unicodedata.combining(ch)
    )


def _normalizar_classe(classe: str | None) -> str:
    c = _sem_acentos((classe or "acao").strip().lower())
    return _CLASSE_ALIASES.get(c, c)


def _secoes_obrigatorias_ausentes(markdown: str) -> list[str]:
    """Seções BLOQUEANTES universais (toda classe): geopolítica e Lacunas.

    Sem um H2 contendo 'geopol', `_alertas_geopolitica` silenciosamente não
    roda (o buraco da fase 1 — guarda desligada sem erro); sem um H2 de
    Lacunas, as abstenções não foram declaradas. Ausência => bloqueia.
    """
    h2s = [
        _sem_acentos(ln.lower()) for ln in (markdown or "").splitlines() if re.match(r"^##\s", ln)
    ]
    ausentes: list[str] = []
    if not any("geopol" in h for h in h2s):
        ausentes.append("camada geopolítica (nenhum H2 contém 'geopol' — guarda não roda)")
    if not any("lacun" in h for h in h2s):
        ausentes.append("lacunas (nenhum H2 contém 'lacun' — abstenções não declaradas)")
    return ausentes


def _tokens_classe_ausentes(markdown: str, classe: str) -> list[str]:
    """Tokens temáticos da classe ausentes do corpo (NÃO-bloqueante, D6a)."""
    texto = _sem_acentos((markdown or "").lower())
    return [t for t in _TOKENS_CLASSE.get(classe, ()) if t not in texto]


def _tem_numero_de_claim(frase: str) -> bool:
    """Há número "de claim" em QUALQUER posição da frase (M4a/M4b do red-team)?

    M4a (falso positivo): usa o MESMO critério de número-de-claim de
    `_numeros_significativos` — separador de milhar/decimal OU >=5 dígitos.
    Ano solto (2025) e componentes de data dd/mm/aaaa são metadado de
    referência, não claim: a linha de lacuna legítima 'P/VP: dado não
    encontrado (dados do informe de 2025)' não pode bloquear a tese.
    Percentual explícito ('13%') conta mesmo sem separador (é claim).
    Trade-off documentado: inteiro curto sem '%' nem separador ('em 123')
    deixa de contar — o mesmo recorte já aceito na fidelidade numérica.

    M4b (bypass): número ANTES do termo na mesma frase ('Aos 12,5%, a curva
    DI segue...') também conta — varre a frase INTEIRA, não só o sufixo.
    """
    for m in _NUMERO_RE.finditer(frase):
        tok = m.group(0).rstrip(".")  # ponto final de frase não é separador
        digitos = tok.replace(".", "").replace(",", "")
        if "," in tok or "." in tok or len(digitos) >= 5:
            return True
        if frase[m.end() : m.end() + 1] == "%":
            return True
    return False


def termos_vetados_com_numero(texto: str, classe: str = "acao") -> list[str]:
    """Termos VETADOS com número no mesmo período (bloqueante, D6c).

    Função PURA e determinística. Fecha o convite à alucinação nas lacunas de
    cada classe: 'curva DI' (sem fonte keyless — só o PROXY nomeado via Tesouro
    prefixado é citável), 'inflação implícita' (vencimentos não coincidem),
    'índice de Basileia' (não está na DFP) e — só para FII — 'P/VP' e
    'dividend yield' (preço B3 licenciado). O DY MENSAL do informe CVM é
    permitido quando rotulado ('do informe'/'auto-declarado') no mesmo período
    e sem 'anualizado'/'a mercado' (NUNCA anualizar o DY do informe).

    Red-team fase 2 (M4): o número conta em qualquer posição da frase (M4b),
    ano/data não conta como número (M4a) e quebra de linha simples de bullet
    quebrado é o MESMO período (M4c) — ver `_tem_numero_de_claim` e
    `_QUEBRA_CONTINUACAO_RE`.
    """
    classe = _normalizar_classe(classe)
    achados: list[str] = []
    texto_continuo = _QUEBRA_CONTINUACAO_RE.sub(" ", texto or "")
    for frase in _FRASE_SPLIT_RE.split(texto_continuo):
        if not frase.strip():
            continue
        for rotulo, termo_re, classes in _REGRAS_VETADAS:
            if classes is not None and classe not in classes:
                continue
            if termo_re.search(frase) is None or not _tem_numero_de_claim(frase):
                continue
            if rotulo is _VETADO_CURVA_DI and _PROXY_RE.search(frase):
                continue  # proxy NOMEADO no mesmo período é o uso citável permitido
            if (
                rotulo is _VETADO_DY
                and _DY_ROTULO_INFORME_RE.search(frase)
                and not _DY_ANUALIZADO_OU_MERCADO_RE.search(frase)
            ):
                continue  # DY mensal do informe, auto-declarado e rotulado
            achados.append(f"{rotulo}: '{frase.strip()[:120]}'")
    return achados


def _chave_fonte(fonte: dict) -> tuple | None:
    """Identidade LÓGICA de uma fonte no cálculo de cobertura (achado B1).

    Documentos distintos podem repetir a mesma fonte lógica: no caso RF, cada
    Data Base do CSV da STN cria uma `Fonte` própria com a MESMA URL+descrição
    — 1 fonte ancorando 4 docs deprimia o denominador (cobertura máx. 0,25).
    Dedup por (url, descricao); fonte sem ambos cai para o id (fontes anônimas
    distintas não colapsam). Sem identificador algum -> None (não conta).
    """
    url = (fonte.get("url") or "").strip()
    descricao = (fonte.get("descricao") or "").strip()
    if url or descricao:
        return (url, descricao)
    fid = fonte.get("id")
    return ("id", str(fid)) if fid else None


def _strip_disclaimer(texto: str) -> str:
    return _DISCLAIMER_RE.sub("", texto)


def _numeros_significativos(texto: str) -> set[str]:
    """Tokens numéricos "de claim" (normalizados sem separadores) do texto.

    Qualifica quem tem separador de milhar/decimal (valor financeiro/taxa: 14,25 ·
    497.549.000.000,00) OU >=5 dígitos. Exclui ano solto (2025) e inteiros curtos —
    metadados de data/referência, não afirmações a ancorar.
    """
    achados: set[str] = set()
    for m in _NUMERO_RE.findall(texto or ""):
        tem_separador = "." in m or "," in m
        digitos = m.replace(".", "").replace(",", "")
        if tem_separador or len(digitos) >= 5:
            achados.add(digitos)
    return achados


def _faithfulness_numerica(markdown: str, citacoes: list) -> float | None:
    """Fração dos números do markdown que aparecem em ALGUM texto citado.

    Proxy determinístico e sem-modelo de fidelidade (RAGAS/NLI-lite): a Anthropic
    Citations garante que `texto_citado` veio da fonte, então um número do corpo
    que também está num trecho citado está ancorado na fonte. `None` se não há
    número no corpo (métrica não se aplica — abstenção não é infidelidade).
    """
    nums_texto = _numeros_significativos(markdown)
    if not nums_texto:
        return None
    citado = " ".join((c.get("texto_citado") or "") for c in citacoes if isinstance(c, dict))
    nums_citados = _numeros_significativos(citado)
    ancorados = sum(1 for n in nums_texto if n in nums_citados)
    return round(ancorados / len(nums_texto), 3)


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


def avaliar_tese(envelope: dict, classe: str = "acao") -> dict:
    """Avalia o envelope de uma tese e devolve o laudo + `aprovado`/`bloqueante`.

    `classe` (default 'acao' — retrocompatível com as chamadas existentes;
    'banco'/'seguradora'/'fii'/'renda_fixa' são passadas por kwarg pelo motor)
    só ADICIONA checagens: tokens temáticos não-bloqueantes, termos vetados
    escopados e o piso de fidelidade numérica como nota (nunca bloqueio).
    """
    classe = _normalizar_classe(classe)
    markdown = envelope.get("markdown") or ""
    citacoes = envelope.get("citacoes") or []
    fontes = envelope.get("fontes") or []
    lacunas = envelope.get("lacunas") or []
    # Inclui texto gerado por LLM exposto ao usuário (resumo do Haiku) na varredura.
    # Quebra DUPLA: parágrafo novo — o resumo não pode se fundir à última linha
    # do markdown sob a normalização de continuação do check de termos vetados.
    resumo = ((envelope.get("metadata") or {}).get("resumo")) or ""
    texto_varredura = markdown + "\n\n" + resumo

    violacoes = _violacoes_recomendacao(texto_varredura)
    alertas_geo = _alertas_geopolitica(markdown)
    # Termos vetados-com-número (D6c): varre também o resumo — número inventado
    # exposto ao usuário é exatamente o que o check fecha.
    termos_vetados = termos_vetados_com_numero(texto_varredura, classe)
    # Seções universais (D6a): vivem no markdown (o resumo não é seccionado).
    secoes_ausentes = _secoes_obrigatorias_ausentes(markdown)
    tokens_ausentes = _tokens_classe_ausentes(markdown, classe)
    fontes_sem_url = [
        (f.get("descricao") or f.get("id") or "?") for f in fontes if not f.get("url")
    ]
    # Elo de correlação (D5) só vale ancorado nas DUAS pontas (achado A4). Elo citado
    # sem fonte numa ponta é ungrounded => bloqueia (defesa em profundidade).
    elos = envelope.get("elos") or []
    elos_sem_fonte = [
        (e.get("dimensao") or "?")
        for e in elos
        if not e.get("origem_fonte_id") or not e.get("destino_fonte_id")
    ]

    # Cobertura DEDUPLICADA por fonte lógica (achado B1): o mesmo
    # (url, descricao) repetido em N documentos conta UMA vez no denominador,
    # e a citação a qualquer um deles conta a mesma UMA vez no numerador.
    chaves_fontes = {ch for f in fontes if (ch := _chave_fonte(f)) is not None}
    fontes_citadas: set[tuple] = set()
    for c in citacoes:
        chave = _chave_fonte(c.get("fonte") or {})
        if chave is not None:
            fontes_citadas.add(chave)
    cobertura = (len(fontes_citadas) / len(chaves_fontes)) if chaves_fontes else 0.0

    lacunas_no_texto = sum(1 for ln in markdown.splitlines() if "dado não encontrado" in ln.lower())

    faithfulness = _faithfulness_numerica(markdown, citacoes)
    # Piso de fidelidade (D6d): NOTA para classes novas; 'acao' fica inalterada
    # (métrica só reportada, como na fase 1).
    fidelidade_baixa = (
        classe != "acao" and faithfulness is not None and faithfulness < _FAITHFULNESS_PISO
    )

    # Subconjunto INEGOCIÁVEL — nunca pode ser servido como tese pronta.
    bloqueante = (
        bool(violacoes)
        or bool(alertas_geo)
        or bool(fontes_sem_url)
        or bool(elos_sem_fonte)
        or bool(secoes_ausentes)
        or bool(termos_vetados)
    )

    motivos: list[str] = []
    if violacoes:
        motivos.append(f"linguagem de recomendação detectada: {sorted(set(violacoes))}")
    if alertas_geo:
        motivos.append(f"afirmação de evento geopolítico sem fonte/hedge: {alertas_geo}")
    if secoes_ausentes:
        motivos.append(f"seção obrigatória ausente: {secoes_ausentes}")
    if termos_vetados:
        motivos.append(f"termo vetado com número: {termos_vetados}")
    if elos_sem_fonte:
        motivos.append(f"elo de correlação sem fonte numa das pontas: {elos_sem_fonte}")
    if not citacoes:
        motivos.append("nenhuma citação ancorada à fonte")
    if fontes_sem_url:
        motivos.append(f"{len(fontes_sem_url)} fonte(s) sem URL")
    if fontes and cobertura < _COBERTURA_MINIMA:
        motivos.append(
            f"cobertura de citações insuficiente ({cobertura:.0%} < {_COBERTURA_MINIMA:.0%})"
        )
    if tokens_ausentes:
        motivos.append(f"tema(s) da classe '{classe}' ausente(s) do corpo: {tokens_ausentes}")
    if fidelidade_baixa:
        motivos.append(
            f"fidelidade numérica abaixo do piso ({faithfulness} < {_FAITHFULNESS_PISO})"
        )

    aprovado = (
        not bloqueante
        and len(citacoes) > 0
        and (not fontes or cobertura >= _COBERTURA_MINIMA)
        and not tokens_ausentes
        and not fidelidade_baixa
    )

    return {
        "aprovado": aprovado,
        "bloqueante": bloqueante,
        "classe": classe,
        "faithfulness_numerica": faithfulness,
        "faithfulness_piso": _FAITHFULNESS_PISO,
        "violacoes_recomendacao": sorted(set(violacoes)),
        "alertas_geopolitica": alertas_geo,
        "secoes_ausentes": secoes_ausentes,
        "tokens_classe_ausentes": tokens_ausentes,
        "termos_vetados": termos_vetados,
        "citacoes_total": len(citacoes),
        "fontes_total": len(fontes),
        "fontes_unicas": len(chaves_fontes),  # dedup (url, descricao) — B1
        "fontes_citadas": len(fontes_citadas),
        "cobertura_fontes": round(cobertura, 3),
        "cobertura_minima": _COBERTURA_MINIMA,
        "fontes_sem_url": fontes_sem_url,
        "elos_sem_fonte": elos_sem_fonte,
        "elos_total": len(elos),
        "lacunas_total": len(lacunas),
        "lacunas_no_texto": lacunas_no_texto,
        "motivos": motivos,
    }
