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

Gate v3 (F4, plano "Tese Profunda" §2.10 + correções de red-team A1/A2/A3/A5/
A6/A7 — as correções VENCEM sobre o §2.10 onde conflitam):

8. A5 — varredura ampliada: as regras de linguagem/diretiva passam a
   varrer também `envelope['texto_livre_novo']` (leituras técnicas +
   descrições de valuation + implicações de métricas + exibição canônica
   de consenso), além de markdown + resumo. Cobre todo texto livre
   user-visible. Hotfix 2 (item 14, abaixo) restringe QUAIS regras usam
   essa superfície ampliada — release original.
9. A1/R12 — carve-out de consenso: `preço-alvo`/`price target`/`rating`
   direcional só são PERMITIDOS quando (a) a frase está dentro da seção H2
   cujo título contém 'consenso', (b) há marcador de atribuição, e (c) o
   número casa com o `valor` de algum item de `envelope['consenso']`. Fora
   da seção, ou faltando (b)/(c), continua bloqueante. Todo número 'de
   claim' na seção de consenso sem atribuição+casamento também bloqueia
   (R12), mesmo sem a palavra 'preço-alvo'.
10. A2 — relaxamentos por CITAÇÃO (não por rótulo emitido pelo modelo):
    'índice de Basileia', 'P/VP'(FII)/'DY a mercado' e 'inflação implícita'
    só deixam de bloquear quando o número consta do `texto_citado` de uma
    citação cuja fonte casa com a origem esperada (IF.data/BCB; COTAHIST/B3;
    ANBIMA/ETTJ). Sem citação correspondente, continua bloqueante — nunca
    rebaixado por rótulo textual solto.
11. A3 — 'DY a mercado' é regra NOVA e independente (`_VETADO_DY_MERCADO`),
    sem tocar a isenção do DY do informe (`_dy_isento_no_periodo`).
12. A7/R10 — técnica-como-conselho (bloqueante): palavra-de-sinal de
    indicador técnico + diretiva ao leitor na MESMA frase. Leitura
    descritiva pura (sem diretiva) passa.
13. A6/R11 — valuation-como-preço-alvo (bloqueante): termo de valuation
    ('valor justo'/'preço justo'/'valor intrínseco') + diretiva REAL ao
    leitor na MESMA frase — SEM os gatilhos genéricos 'acima de'/'abaixo
    de' (uso contábil/IFRS legítimo não pode bloquear).

Hotfix 2 (2026-07-11, bug TAEE11 provado ao vivo na 2ª tentativa — após o
hotfix do `_documentos_metricas` por origem já ter corrigido a 1ª): a
varredura ampliada do item 8 (A5) tinha um efeito colateral não previsto —
ela também expunha `texto_livre_novo` às regras NUMÉRICAS ancoradas em
CITAÇÃO (`termos_vetados_com_numero` com os relaxamentos A2/A3, R12/
carve-out de consenso e `_faithfulness_numerica`). Essas regras foram
desenhadas para números de AUTORIA DO MODELO (a síntese do LLM), cuja única
prova de proveniência é uma citação Anthropic apontando para a fonte
correta — sem citação, o número é tratado como possível alucinação. Mas
`texto_livre_novo` é preenchido pelo BACKEND, DEPOIS da síntese (`tese.
_texto_livre_novo`), com métricas/leituras técnicas/valuation calculadas
deterministicamente a partir de dado real — cada número ali carrega
proveniência ESTRUTURAL (o `fonte_id` NOT NULL da métrica/insumo, nunca
escrito pelo LLM), não proveniência por citação. Um trecho assim NUNCA vai
ter uma citação Anthropic correspondente (o LLM não vê nem escreve
`texto_livre_novo`), então a isenção por citação das regras acima é
estruturalmente inalcançável para esse texto — todo termo vetado-com-
número presente ali bloqueia SEMPRE, mesmo sendo 100% legítimo e groundado
(prova ao vivo: 'Dividend yield 12m a mercado: 8,23% (Σ proventos por ação
com data-com nos últimos 12 meses / último preço de fechamento)' do
template determinístico de métricas).

14. Correção — DUAS superfícies de varredura, não uma:
    - `texto_varredura_amplo` (markdown + resumo + texto_livre_novo):
      regras de RECOMENDAÇÃO/diretiva (R1 `_violacoes_recomendacao`, R10
      técnica-como-conselho, R11 valuation-como-preço-alvo) — diretiva ao
      leitor é uma violação de POSTURA (CVM), não uma alegação numérica;
      não importa QUEM autorou a frase, uma diretiva de compra/venda
      nunca pode ser servida. A guarda geopolítica (`_alertas_geopolitica`)
      segue essa mesma lógica de defesa em profundidade — continua restrita
      ao markdown (nunca teve motivo estrutural para aparecer em
      `texto_livre_novo`, que não tem seção H2 'geopolítica').
    - `texto_varredura_modelo` (markdown + resumo, SEM texto_livre_novo):
      regras NUMÉRICAS ancoradas em citação (`termos_vetados_com_numero`
      com A2/A3, R12/carve-out de consenso, `_faithfulness_numerica`) —
      essas regras EXISTEM para pegar número de autoria do modelo sem
      proveniência; aplicá-las a texto de autoria do backend com
      proveniência estrutural é o bug em si (falso-positivo por desenho).
    Blocos determinísticos NUNCA precisam de citação para se justificar —
    a garantia vem do pipeline (`metricas_setor._fonte_obrigatoria`/
    `valuation.Insumo.fonte`, sempre com `Fonte` real), não do texto.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

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
    # "preço justo" SAIU daqui (A6, correção red-team): passa a ser regido
    # SÓ pelo R11 (`_R11_TERMO_RE`/`_R11_DIRETIVA_RE`, abaixo) junto com
    # "valor justo"/"valor intrínseco" — os três só bloqueiam combinados com
    # diretiva REAL ao leitor; uso contábil/IFRS legítimo passa a não bloquear.
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
    r"\bload\s+up\b",
    r"\btime\s+to\s+(buy|sell|load)\b",
    r"\bact\s+now\b",
    r"\bstrong\s+upside\b",
    # --- Red-team v3 (gate v3, 22 furos) — léxico de diretiva ampliado. Estes
    #     padrões vivem no léxico GERAL (não em `_R10_DIRETIVA_RE`/`_R11_
    #     DIRETIVA_RE`) porque são diretiva ao leitor por si só, em QUALQUER
    #     seção — não dependem de coexistir com um sinal técnico/termo de
    #     valuation na mesma frase (ao contrário de "espaço para alta"/
    #     "confirma o momento", abaixo, que só viram diretiva quando
    #     ANCORADOS num sinal técnico — ver `_R10_DIRETIVA_RE`). ---
    r"\bmont(?:e|em|ar)\s+(?:a\s+)?posi[çc][ãa]o\b",
    r"\b(?:adicion|inclu[ai]|incorpor)\w*\s+(?:ao|à|na|no|a)\s+"
    r"(?:sua\s+|essa\s+)?(?:carteira|portf[óo]lio|posi[çc][ãa]o)\b",
    r"\bzer(?:e|em|ar)\s+(?:a\s+)?posi[çc][ãa]o\b",
    r"\bsurf(?:e|em|ar)\s+(?:o\s+)?movimento\b",
    r"\babrir\s+(?:posi[çc][ãa]o\s+)?(?:long|short|comprad[oa]|vendid[oa])\b",
    r"\bjanela\b[^.;\n]{0,40}\bentrada\b",
    # Voz passiva / particípio — o verbo direcional muda de sujeito, não de
    # sentido: "a compra é recomendada" / "deveria ser acumulado" continuam
    # sendo diretiva de compra/venda, só que sem imperativo/1ª pessoa.
    r"\b(?:compra|venda)\s+(?:é|foi|est[áa]|s[ãa]o)\s+recomendad[ao]s?\b",
    r"\bdeve(?:ria)?m?\s+ser\s+" r"(?:acumulad|comprad|vendid|adquirid|carregad|reduzid)[oa]s?\b",
    # "alvo" NU (sem "preço-"/"valor-" na frente — esses já são cobertos por
    # `\bpre[çc]o[\s-]?alvo\b`/`\bvalor[\s-]?alvo\b` acima) seguido de valor:
    # fecha o contrabando de preço-alvo para FORA da seção de consenso sob um
    # rótulo mais curto ("o alvo de R$ 63 sugere...", CONS-06).
    r"\balvo\s*(?:de|em|:)\s*R\$",
]
_RECOMENDACAO_RE = re.compile("|".join(_PADROES_RECOMENDACAO), re.IGNORECASE)

# Remove só o TRECHO do disclaimer (a cláusula, NÃO o resto da frase) antes de
# varrer — assim "Não é recomendação, mas recomendo comprar" não escapa pela linha.
# Limitado a "de investimento" para não engolir texto direcional subsequente.
_DISCLAIMER_RE = re.compile(
    r"n[ãa]o (é|e|constitui|configura) recomenda[çc][ãa]o(\s+de\s+investimento)?",
    re.IGNORECASE,
)
# Disclaimer do bloco de VALUATION (F3, `valuation.AVISO_VALUATION` — "NÃO é
# preço-alvo nem recomendação"): sem este strip, o próprio aviso anti-
# recomendação do motor colidiria com o veto de 'preço-alvo' (achado desta
# integração — decisão fora do plano original, ver resposta final). Mesma
# lógica do `_DISCLAIMER_RE`: remove só a cláusula de NEGAÇÃO.
_DISCLAIMER_VALUATION_RE = re.compile(
    r"n[ãa]o (é|e|constitui|configura) pre[çc]o[\s-]?alvo"
    r"(\s+(nem|e|ou)\s+recomenda[çc][ãa]o(\s+de\s+investimento)?)?",
    re.IGNORECASE,
)

# --- A1 (correção red-team) — carve-out de consenso ------------------------
# Marcador de ATRIBUIÇÃO exigido p/ permitir 'preço-alvo'/'price target'/
# 'rating' direcional DENTRO da seção de consenso (condição b).
_ATRIBUICAO_RE = re.compile(
    r"\bsegundo\b|\bde acordo com\b|\bconforme\b|\bpara [oa]\b|\bna vis[ãa]o d[aeo]",
    re.IGNORECASE,
)
# Subconjunto de `_PADROES_RECOMENDACAO` elegível ao carve-out (A1): SÓ estes
# três — os demais padrões (compre, mantenha, stop-loss...) seguem
# bloqueantes incondicionalmente, mesmo dentro da seção de consenso.
_CARVEOUT_CONSENSO_RE = re.compile(
    r"\bpre[çc]o[\s-]?alvo\b|\bprice\s+target\b|\btarget\s+price\b|"
    r"\brating[:\s]+(compra|venda|manter|neutro)\b|"
    r"\brating[:\s]+(buy|sell|hold|neutral|overweight|underweight)\b",
    re.IGNORECASE,
)

# --- A7/R10 — técnica-como-conselho -----------------------------------------
# Palavra-de-sinal de indicador técnico computado (tecnica.py). Âncoras com
# \b: 'sobrecompra'/'sobrevenda' (leituras REAIS e neutras do motor) não têm
# fronteira de palavra antes de 'compr'/'vend' (são uma palavra só) — não
# colidem com a diretiva abaixo.
_R10_SINAL_RE = re.compile(
    r"\b(rsi|ifr|estoc[áa]stico|macd|bollinger|williams|"
    r"m[eé]dias?\s+m[óo]ve(?:l|is)|mm|sma|ema|fibonacci|"
    r"acumula[çc][ãa]o/?distribui[çc][ãa]o|a/d|"
    r"golden\s+cross|death\s+cross|cruzamento\s+(?:dourado|de\s+morte))\b",
    re.IGNORECASE,
)
# Diretiva ao leitor (verbo comprar/vender por radical, entrada/saída,
# posicionamento, "hora de", "momento de compra/venda", "sinal de
# compra/venda"). `\w*` após o radical casa a flexão inteira (compre/
# comprar/comprando/vendam...) com fronteira de palavra no fim. `buy|sell`
# (decisão fora do plano, ver resposta final): a tese é PT-BR, então
# sinal+diretiva em INGLÊS ("The RSI signals a buy") só aparece como
# vazamento — mesma lógica do bloco INGLÊS já existente em
# `_PADROES_RECOMENDACAO`.
# Red-team v3 (gate v3): "espaço para alta/queda" e "confirma o momento/
# movimento" são desfechos direcionais que só configuram diretiva quando
# ANCORADOS a um sinal técnico (`_R10_SINAL_RE`) na MESMA frase — por isso
# vivem aqui, e não no léxico geral (`_PADROES_RECOMENDACAO`): fora de um
# contexto técnico, "espaço para alta" pode ser uma leitura de cenário
# legítima (ex.: valuation) sem virar recomendação. "confirma o momento" é
# borderline (R10-04) — decisão: incluir, pois SÓ dispara combinado com
# sinal técnico explícito, o que já restringe a superfície a leituras
# técnicas (nenhum verde do red-team usa a frase fora desse contexto).
_R10_DIRETIVA_RE = re.compile(
    r"\b(compr\w*|vend\w*|entrada|sa[íi]da|buy|sell|"
    r"posicion(?:e|ar)(?:-se)?\s+(?:comprad[oa]|vendid[oa])|"
    r"hora\s+de|momento\s+de\s+(?:compra|venda|comprar|vender)|"
    r"sinal\s+de\s+(?:compra|venda)|"
    r"espa[çc]o\s+para\s+(?:alta|queda)|"
    r"alvo\s+(?:de|em)|"
    r"confirma\s+o\s+(?:momento|movimento))\b",
    re.IGNORECASE,
)

# --- A6/R11 — valuation-como-preço-alvo -------------------------------------
# Termo de valuation. "valor intrínseco"/"valor justo" têm uso contábil/IFRS
# legítimo (ex.: 'ativos avaliados a valor justo') — só bloqueia combinado
# com diretiva REAL (abaixo); "acima de"/"abaixo de" NÃO são gatilho (A6).
_R11_TERMO_RE = re.compile(
    r"\b(valor\s+justo|pre[çc]o\s+justo|valor\s+intr[íi]nseco)\b", re.IGNORECASE
)
_R11_DIRETIVA_RE = re.compile(
    r"\b(compr\w*|vend\w*|aproveite\w*|entrada|"
    r"oportunidade\s+de\s+(?:compra|venda)|"
    r"desconto\s+de\s+\d+%\s*(?:—|→|=|,)?\s*(?:compr\w*|oportunidad\w*))\b",
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
# (bullet "- "/*/+ — o traço de bullet exige espaço: linha começando em número
# NEGATIVO '-12,5%' é CONTINUAÇÃO, não bullet (red-team v2.1: reabria o buraco
# M4c) —, heading #, citação >, item numerado "1. ") ou é linha em branco/fim
# do texto (parágrafo novo). SÓ o check de termos vetados usa esta
# normalização; os demais checks preservam o split legado por linha.
_QUEBRA_CONTINUACAO_RE = re.compile(r"\n(?![ \t]*(?:-\s|[*+#>]|\d+[.)]\s|\n|$))")
_PROXY_RE = re.compile(r"\bproxy\b", re.IGNORECASE)
_DY_ROTULO_INFORME_RE = re.compile(
    r"\bdo\s+informe|\bauto[\s-]?declarad|\binforme\s+mensal", re.IGNORECASE
)
# Quebra-isenção: anualização (qualquer flexão — anualizado/anualizar/
# anualização/anualiza; red-team v2.2/B2: o radical 'anualiz' cobre também a
# abreviação 'anualiz.' e acento espúrio PÓS-radical, 'anualizádo' — acento
# DENTRO do radical, 'anuálizado', segue fora: exigiria normalizar o texto e
# os spans protetores juntos) e 'a/ao/aos preço(s)/valor de mercado' (red-team
# v2.1: 'ao preço', plural, 'a valor de mercado' e ç sem cedilha escapavam).
_DY_ANUALIZADO_OU_MERCADO_RE = re.compile(
    r"anualiz|\ba[os]{0,2}\s+(?:pre[çc]os?\s+de\s+|valor\s+de\s+)?mercado\b",
    re.IGNORECASE,
)
# Ressalvas PROTETORAS mandatórias do rótulo do informe (fii._ROTULOS_INDICADOR:
# "NÃO é DY a preço de mercado e NUNCA deve ser anualizado") — cautela, não
# claim. Reconhecidas QUASE-VERBATIM e protegem por SPAN apenas o termo-quebra
# que está DENTRO delas (red-team do fix v1: deleção por janela de negação
# engolia o próprio claim — "Não é exagero dizer que o DY anualizado chega a
# 12%" passava; agora nada é deletado e só a ressalva literal protege).
# Forma: negação + cadeia VERBO-PRIMEIRO de conectores + termo-quebra
# ('não/nem é|representa|deve|pode ser [lido como] DY/yield/valor a preço de
# mercado', 'nem deve ser anualizado') OU negação/'sem' + particípio direto
# ('nunca anualizado', 'sem anualizar'). Verbo-primeiro impede 'nem o DY
# anualizado de 12%' de se proteger; 'não raro supera...' e 'não por acaso...'
# seguem desprotegidos. Falso positivo de PRODUÇÃO (HGLG11, 2026-07-10)
# ampliou o reconhecimento com 3 formas reais da ressalva, cada uma justificada
# por frase verbatim do banco: gerúndios 'sendo'/'devendo' no ramo verbo-
# primeiro ('não sendo DY a preço de mercado', 'não devendo ser anualizado' —
# o conector 'ser' já existente completa o segundo) e a preposição 'sem' no
# ramo do particípio direto ('sem anualizar', 'sem ser anualizado'). O span
# protegido continua cobrindo SÓ a ressalva: 'Sem anualizar seria conservador
# demais; o DY anualizado atinge 9,5%' segue vetado (o claim fica fora).
# Red-team v2.2 (PR #24):
# (B1) '\b' antes das DUAS listas de negação — 'fossem/pudessem/quisessem'
#   terminam em 'sem' e a alternativa sem borda casava o FIM do verbo no
#   subjuntivo, criando span protetor espúrio que mascarava anualização real
#   ('Se os 0,66% do informe fossem anualizados...').
# (FP2) o ramo direto cobre também a ELIPSE de mercado da ressalva ('nem a
#   preço de mercado', 'sem ser a preço de mercado'). A alternação casa UM
#   termo-quebra por span: 'sem anualizar' NÃO cobre um 'a preço de mercado'
#   posterior (C5 segue vetando) e 'vendessem a mercado' segue quebra (B1).
# (FP1) 'CDI/Selic/IPCA/taxa DI anualizado' é anualização de OUTRO indicador,
#   não do DY — protege por span SÓ o par indicador+anualizad*; um
#   'anualizado' do próprio DY fora desse par segue derrubando a isenção.
# (B2) radical 'anualiz\w*' casa a abreviação 'anualiz.' e acento espúrio
#   pós-radical — pareado com o MESMO radical na quebra-isenção acima.
_DY_CAVEAT_PROTEGIDO_RE = re.compile(
    r"\b(?:n[ãa]o|nunca|jamais|nem)\s+"
    r"(?:[ée]|ser[áã]?|sendo|sido|deve(?:ria|m|r[áã]|ndo)?|pode(?:m|r[áã])?|representa(?:m)?"
    r"|constitui|equivale|corresponde|reflete(?:m)?|foi|seja|est[áa])\s+"
    r"(?:(?:ser|sido|lid[oa]|como|o|a|um|uma|dy|dividend|yield|rendimento|valor|de)\s+){0,4}"
    r"(?:anualiz\w*|a[os]{0,2}\s+(?:pre[çc]os?\s+de\s+|valor\s+de\s+)?mercado\b)"
    r"|\b(?:n[ãa]o|nunca|jamais|nem|sem)\s+(?:ser\s+|sido\s+)?"
    r"(?:anualiz\w*|a[os]{0,2}\s+(?:pre[çc]os?\s+de\s+|valor\s+de\s+)?mercado\b)"
    r"|\b(?:cdi|selic|ipca|taxa\s+di)\s+anualiz\w*",
    re.IGNORECASE,
)
# 'VP/DY' (e as formas do motor: 'valor patrimonial/dividend yield' do
# destino_label do elo em fii.py e a notação de par 'DY×Selic' do co-movimento)
# é vocabulário do PRÓPRIO motor — direção do elo/par, não claim de dividend
# yield ('Elo Selic → VP/DY do FII (força 0,50...', 2º falso positivo ao vivo).
# Descontado SÓ quando o período tem vocabulário de elo (red-team: 'O VP/DY
# implica yield de 8,5%' sem contexto de elo segue vetado).
_VP_SLASH_PREFIXO_RE = re.compile(r"(?:vp|valor\s+patrimonial)\s*/\s*$", re.IGNORECASE)
_PAR_SUFIXO_RE = re.compile(r"^\s*[×x]\s*\w")
_ELO_CONTEXTO_RE = re.compile(r"\belos?\b|\bfor[çc]a\b|co-?movimento|interpretativ", re.IGNORECASE)

_VETADO_CURVA_DI = "curva DI com número sem rótulo 'proxy'"
_VETADO_INFLACAO_IMPLICITA = "inflação implícita com número"
_VETADO_BASILEIA = "índice de Basileia com número (não está na DFP — lacuna)"
_VETADO_PVP_FII = "P/VP com número (preço B3 licenciado — lacuna)"
_DY_BARE_RE = re.compile(r"\b(dividend\s+yield|dy)\b", re.IGNORECASE)
_VETADO_DY = "dividend yield/DY com número sem rótulo 'do informe'/'auto-declarado'"
# A3 (correção red-team): regra NOVA e independente p/ 'DY a mercado' — NÃO
# reusa/toca `_dy_isento_no_periodo`/`_DY_ANUALIZADO_OU_MERCADO_RE` (isenção
# do informe, semântica preservada). Única saída: relaxamento por CITAÇÃO
# COTAHIST/B3 (A2, `_RELAXAMENTO_POR_CITACAO` abaixo). Aplica a TODA classe —
# a métrica "DY a mercado 12m" também existe p/ ação/energia (§2.6).
_VETADO_DY_MERCADO = "DY/dividend yield a mercado com número (permite citação COTAHIST/B3)"
_MERCADO_FRAG = r"a[os]{0,2}\s+(?:pre[çc]os?\s+de\s+|valor\s+de\s+)?mercado"
_MERCADO_TERMO_RE = re.compile(rf"\b{_MERCADO_FRAG}\b", re.IGNORECASE)

# (rótulo, regex do termo, classes onde vale — None = todas as classes)
_REGRAS_VETADAS: tuple[tuple[str, re.Pattern[str], frozenset[str] | None], ...] = (
    (_VETADO_CURVA_DI, re.compile(r"\bcurva\s+DI\b", re.IGNORECASE), None),
    (
        _VETADO_INFLACAO_IMPLICITA,
        re.compile(r"\binfla[çc][ãa]o\s+impl[íi]cita\b", re.IGNORECASE),
        None,
    ),
    (
        _VETADO_BASILEIA,
        re.compile(r"\b[íi]ndice\s+de\s+basil[eé]ia\b", re.IGNORECASE),
        None,
    ),
    (
        _VETADO_PVP_FII,
        re.compile(r"\bP\s*/\s*VP\b", re.IGNORECASE),
        frozenset({"fii"}),
    ),
    (_VETADO_DY, _DY_BARE_RE, frozenset({"fii"})),
    # termo_re não é consultado p/ esta rotulo — detecção real é
    # `_dy_mercado_termo_presente` (respeita a MESMA ressalva protetora de
    # `_DY_CAVEAT_PROTEGIDO_RE`, senão a negação "NÃO é DY a preço de
    # mercado" do próprio rótulo do informe dispararia a regra nova).
    (_VETADO_DY_MERCADO, _DY_BARE_RE, None),
)

# --- A2 (correção red-team) — relaxamentos por CITAÇÃO, não por rótulo -----
# Origem esperada (url/descrição da `Fonte` citada) por termo relaxável.
# Termo+número SEM citação correspondente permanece BLOQUEANTE (não rebaixa).
_ORIGEM_BASILEIA_RE = re.compile(r"if\.?\s?data|\bbcb\b", re.IGNORECASE)
_ORIGEM_ANBIMA_RE = re.compile(r"\banbima\b|\bettj\b", re.IGNORECASE)
_ORIGEM_COTAHIST_RE = re.compile(r"\bcotahist\b|\bb3\b", re.IGNORECASE)

_RELAXAMENTO_POR_CITACAO: dict[str, re.Pattern[str]] = {
    _VETADO_BASILEIA: _ORIGEM_BASILEIA_RE,
    _VETADO_INFLACAO_IMPLICITA: _ORIGEM_ANBIMA_RE,
    _VETADO_PVP_FII: _ORIGEM_COTAHIST_RE,
    _VETADO_DY: _ORIGEM_COTAHIST_RE,
    _VETADO_DY_MERCADO: _ORIGEM_COTAHIST_RE,
}


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


# --- Red-team v3 (TERMO-04) — número por extenso PT-BR ----------------------
# Numeral por extenso (dicionário fechado um..dez/vinte/trinta.../cem/mil —
# não tenta cobrir toda a gramática de composição numérica, só o vocabulário
# suficiente p/ frases como "quatorze vírgula sete por cento") + marcador
# ('vírgula'/'por cento') NA MESMA FRASE. Chamada só DEPOIS que o termo
# vetado já casou (`_tem_numero_de_claim(frase) or _tem_numero_extenso(frase)`
# em `termos_vetados_com_numero`) — a coocorrência com o termo vetado É a
# condição da regra, então "por cento" sozinho em texto legítimo alhures
# nunca chega a este check (não contamina `_tem_numero_de_claim`, que segue
# só dígitos — usado também por `_consenso_numeros_sem_atribuicao`/R12).
_NUMERAL_EXTENSO_PT = (
    "zero",
    "um",
    "uma",
    "dois",
    "duas",
    "tr[êe]s",
    "quatro",
    "cinco",
    "seis",
    "sete",
    "oito",
    "nove",
    "dez",
    "onze",
    "doze",
    "treze",
    "quatorze",
    "catorze",
    "quinze",
    "dezesseis",
    "dezesseis",
    "dezessete",
    "dezoito",
    "dezenove",
    "vinte",
    "trinta",
    "quarenta",
    "cinq(?:u|ü)enta",
    "sessenta",
    "setenta",
    "oitenta",
    "noventa",
    "cem",
    "cento",
    "duzentos",
    "trezentos",
    "quatrocentos",
    "quinhentos",
    "seiscentos",
    "setecentos",
    "oitocentos",
    "novecentos",
    "mil",
)
_NUMERAL_EXTENSO_RE = re.compile(r"\b(?:" + "|".join(_NUMERAL_EXTENSO_PT) + r")\b", re.IGNORECASE)
_EXTENSO_MARCADOR_RE = re.compile(r"\bv[íi]rgula\b|\bpor\s+cento\b", re.IGNORECASE)


def _tem_numero_extenso(frase: str) -> bool:
    """Número por extenso como número-de-claim: exige a COOCORRÊNCIA de um
    numeral por extenso com 'vírgula'/'por cento' na MESMA frase — ver nota
    acima sobre por que isso não é falso-positivo."""
    return bool(_NUMERAL_EXTENSO_RE.search(frase) and _EXTENSO_MARCADOR_RE.search(frase))


def _tokens_numericos_de_claim(frase: str) -> set[str]:
    """Dígitos normalizados (sem separador) de todo número "de claim" da
    frase — MESMO critério de significância de `_tem_numero_de_claim`
    (separador OU >=5 dígitos OU percentual explícito), mas devolvendo os
    tokens em vez de um bool. Usado pelo relaxamento por citação (A2): a
    detecção (`_tem_numero_de_claim`) e a checagem de casamento numérico
    precisam do MESMO critério de significância, senão um percentual inteiro
    ('Basileia: 15%') seria detectado mas nunca conseguiria casar com a
    citação (perdia a checagem de separador de `_numeros_significativos`).
    """
    achados: set[str] = set()
    for m in _NUMERO_RE.finditer(frase):
        tok = m.group(0).rstrip(".")
        digitos = tok.replace(".", "").replace(",", "")
        if "," in tok or "." in tok or len(digitos) >= 5:
            achados.add(digitos)
        elif frase[m.end() : m.end() + 1] == "%":
            achados.add(digitos)
    return achados


def _numeros_citados_de_origem(citacoes: list | None, origem_re: re.Pattern[str]) -> set[str]:
    """Números "significativos" (dígitos normalizados) do `texto_citado` de
    citações cuja fonte (url + descrição) casa com `origem_re` (A2:
    relaxamento por CITAÇÃO — nunca por rótulo emitido pelo próprio modelo).
    """
    textos: list[str] = []
    for c in citacoes or []:
        if not isinstance(c, dict):
            continue
        fonte = c.get("fonte") or {}
        alvo = f"{fonte.get('url') or ''} {fonte.get('descricao') or ''}"
        if origem_re.search(alvo):
            textos.append(c.get("texto_citado") or "")
    return _numeros_significativos(" ".join(textos))


def _isento_por_citacao(frase: str, origem_re: re.Pattern[str], citacoes: list | None) -> bool:
    """O termo vetado nesta frase tem TODOS os seus números ancorados numa
    citação da origem esperada (A2 + correção red-team v3, TERMO-03/TERMO-10)?

    SUBCONJUNTO, não interseção: antes, `nums_frase & citados` bastava UM
    número bater para isentar a FRASE inteira — um número real citado
    "lavava" um número fabricado na mesma frase ('Basileia de 16,8% [citado],
    projetado a 21,0% [inventado]' passava por inteiro). Agora TODOS os
    números-de-claim da frase (`nums_frase`) precisam estar em `citados`;
    sobrando qualquer um, a frase inteira segue bloqueante. Sem `citacoes`
    (chamada direta da função pura, compatibilidade retroativa) ou sem
    citação correspondente -> nunca isento (fail-closed).
    """
    nums_frase = _tokens_numericos_de_claim(frase)
    if not nums_frase:
        return False
    return nums_frase.issubset(_numeros_citados_de_origem(citacoes, origem_re))


# --- Red-team v3 — subconjunto vs. sub-claims independentes na MESMA frase --
# O subconjunto acima é correto para "mesma métrica, valor real + valor
# fabricado" (TERMO-03/10), mas um período pode legitimamente conter DOIS
# sub-claims DISTINTOS e cada um com seu PRÓPRIO mecanismo de isenção válido
# — 'DY do informe: 0,66%' (isento pelo RÓTULO, não por citação) 'enquanto o
# DY a mercado ... soma 9,00%' (isento por CITAÇÃO COTAHIST) — ver V-10. Sem
# tratamento, o subconjunto exigiria que o número do informe TAMBÉM tivesse
# citação (que não existe por natureza: é auto-declarado), quebrando V-10.
# As funções abaixo isolam o SUB-TRECHO local (';'/', enquanto') em torno de
# uma posição, para que o subconjunto de CADA sub-claim seja avaliado com
# SEUS PRÓPRIOS números — não com os do vizinho.
_SUBCLAUSULA_DY_RE = re.compile(r";|,\s*enquanto\b|,\s*ao\s+passo\s+que\b", re.IGNORECASE)


def _subclausula_em(texto: str, pos: int) -> str:
    """Sub-trecho de `texto` delimitado por ';'/', enquanto'/', ao passo que'
    que contém a posição `pos`. Sem fronteira nenhuma, devolve `texto`
    inteiro (comportamento idêntico ao escopo de frase inteira já usado
    pelas demais regras — mudança é ADITIVA, só entra em jogo quando há de
    fato uma sub-cláusula contrastante)."""
    limites = [0] + [m.start() for m in _SUBCLAUSULA_DY_RE.finditer(texto)] + [len(texto)]
    limites = sorted(set(limites))
    for ini, fim in zip(limites, limites[1:], strict=False):
        if ini <= pos < fim:
            return texto[ini:fim]
    return texto


def _subclausula_dy_mercado(frase: str) -> str:
    """Escopo do relaxamento por citação de `_VETADO_DY_MERCADO`: a
    sub-cláusula em torno da menção 'a mercado', não a frase inteira — evita
    que o número de um sub-claim VIZINHO (o DY do informe, isento por rótulo
    e por natureza sem citação) force o subconjunto do sub-claim de mercado a
    falhar (V-10). Sem menção 'a mercado' na frase, devolve a frase inteira
    (não deveria ser chamada nesse caso, mas é fail-safe)."""
    m = _MERCADO_TERMO_RE.search(frase)
    if m is None:
        return frase
    return _subclausula_em(frase, m.start())


def _dy_periodo_quebras_ancoradas(periodo: str, citacoes: list | None) -> bool:
    """Toda quebra 'a mercado'/anualização do período (fora de ressalva
    protetora) tem, na SUA PRÓPRIA sub-cláusula, todos os números ancorados
    por citação COTAHIST/B3? Usado só para RESTAURAR a isenção do DY do
    informe quando `_dy_isento_no_periodo` (period-wide, A3 — INTACTO, não
    tocado) a nega por causa de um sub-claim de mercado que É legitimamente
    citado (V-10: 'DY do informe 0,66%, enquanto o DY a mercado ... 9,00%
    [citado COTAHIST]'). Um sub-claim de mercado FABRICADO (sem citação
    correspondente, TERMO-09) mantém a poison period-wide original — devolve
    False e a isenção do informe continua negada."""
    protegidos = [m.span() for m in _DY_CAVEAT_PROTEGIDO_RE.finditer(periodo)]
    for quebra in _DY_ANUALIZADO_OU_MERCADO_RE.finditer(periodo):
        if any(ini <= quebra.start() and quebra.end() <= fim for ini, fim in protegidos):
            continue  # dentro de ressalva protetora — não é quebra real
        sub = _subclausula_em(periodo, quebra.start())
        if not _isento_por_citacao(sub, _ORIGEM_COTAHIST_RE, citacoes):
            return False
    return True


def _dy_isento_no_periodo_com_citacao(periodo: str, fim_frase: int, citacoes: list | None) -> bool:
    """Isenção do DY do informe (A3, `_dy_isento_no_periodo`, PRESERVADA sem
    alteração) + fallback por citação (red-team v3, correção V-10): se o
    rótulo do informe está presente mas a isenção period-wide falha só por
    causa de uma quebra 'a mercado' que tem, ela própria, citação válida na
    sua sub-cláusula (`_dy_periodo_quebras_ancoradas`), a isenção do informe
    é restaurada — o sub-claim vizinho é genuíno e citado, não lavagem."""
    if _DY_ROTULO_INFORME_RE.search(periodo[:fim_frase]) is None:
        return False
    if _dy_isento_no_periodo(periodo, fim_frase):
        return True
    return _dy_periodo_quebras_ancoradas(periodo, citacoes)


def _parse_numero_brl(token: str) -> float | None:
    """Converte um token numérico pt-BR ('63,00'/'1.234,50'/'63') para float
    (ponto = separador de milhar, vírgula = decimal — convenção de `_NUMERO_RE`
    usada em todo o módulo). `None` se não for um número válido."""
    limpo = token.strip().rstrip(".")
    if not limpo:
        return None
    if "," in limpo:
        parte_inteira, _, parte_decimal = limpo.replace(".", "").partition(",")
        texto = f"{parte_inteira}.{parte_decimal}"
    else:
        texto = limpo.replace(".", "")
    try:
        return float(texto)
    except ValueError:
        return None


def _numero_bate_algum_item(frase: str, valores: Sequence[float]) -> bool:
    """Algum número pt-BR da frase é (numericamente, com pequena tolerância
    de arredondamento) igual a algum `valor` de item VALIDADO de
    `envelope['consenso']` (A1 condição c — "isso é o R12 real")."""
    if not valores:
        return False
    for m in _NUMERO_RE.finditer(frase):
        v = _parse_numero_brl(m.group(0))
        if v is not None and any(abs(v - alvo) < 0.005 for alvo in valores):
            return True
    return False


def _dy_mercado_termo_presente(frase: str) -> bool:
    """Há 'DY a mercado' de CLAIM na frase (A3, `_VETADO_DY_MERCADO`)?

    Exige 'DY'/'dividend yield' + um trecho 'a mercado' (`_MERCADO_FRAG`) NÃO
    protegido por uma ressalva quase-verbatim (`_DY_CAVEAT_PROTEGIDO_RE`) —
    reusa a MESMA proteção de `_dy_isento_no_periodo` (sem tocá-la, A3) para
    que a negação mandatória do rótulo do informe ("NÃO é DY a preço de
    mercado") não dispare esta regra NOVA sozinha (ela nega A OCORRÊNCIA,
    não afirma um DY a mercado).
    """
    if not _DY_BARE_RE.search(frase):
        return False
    protegidos = [m.span() for m in _DY_CAVEAT_PROTEGIDO_RE.finditer(frase)]
    for m in _MERCADO_TERMO_RE.finditer(frase):
        if not any(ini <= m.start() and m.end() <= fim for ini, fim in protegidos):
            return True
    return False


def _dy_termo_presente(termo_re: re.Pattern[str], frase: str, periodo: str) -> bool:
    """Há 'dividend yield'/'DY' de CLAIM na frase?

    Os compostos do MOTOR — 'VP/DY' e 'valor patrimonial/dividend yield' (elo
    interpretativo, fii.py) e a notação de par 'DY×Selic' (co-movimento) — só
    são descontados quando o período carrega vocabulário de elo; fora dele,
    'O VP/DY implica yield de 8,5%' segue contando (red-team do fix v1).
    """
    matches = list(termo_re.finditer(frase))
    if matches and _ELO_CONTEXTO_RE.search(periodo):
        matches = [
            m
            for m in matches
            if not _VP_SLASH_PREFIXO_RE.search(frase[: m.start()])
            and not _PAR_SUFIXO_RE.search(frase[m.end() :])
        ]
    return bool(matches)


def _dy_isento_no_periodo(periodo: str, fim_frase_claim: int) -> bool:
    """Isenção do DY: rótulo ANTES do fim da frase do claim + quebras no período.

    O rótulo mandatório do informe contém ';' — o split de frase separa
    'do informe (auto-declarado' do número (1º falso positivo ao vivo) — então
    o rótulo é buscado no período ATÉ O FIM DA FRASE DO CLAIM (red-team v2.1:
    rótulo em frase POSTERIOR não pode isentar 'O DY é 14%, muito atrativo.
    Segundo o informe mensal...'). Termos-quebra são julgados no período
    INTEIRO (direção estrita): nenhum 'anualiza*'/'a (preço de) mercado' fora
    do span de uma ressalva protetora quase-verbatim ("NÃO é DY a preço de
    mercado", "nem/não/nunca deve ser anualizado"). Nada é deletado: um
    quebra-isenção fora de ressalva ("DY do informe anualizado: 8%") derruba
    a isenção e o veto fica.
    """
    if _DY_ROTULO_INFORME_RE.search(periodo[:fim_frase_claim]) is None:
        return False
    protegidos = [m.span() for m in _DY_CAVEAT_PROTEGIDO_RE.finditer(periodo)]
    for quebra in _DY_ANUALIZADO_OU_MERCADO_RE.finditer(periodo):
        if not any(ini <= quebra.start() and quebra.end() <= fim for ini, fim in protegidos):
            return False
    return True


def _frases_com_fim(periodo: str):
    """Frases do período com a posição de FIM de cada uma (p/ rótulo-antes)."""
    inicio = 0
    for corte in _FRASE_SPLIT_RE.finditer(periodo):
        yield periodo[inicio : corte.start()], corte.start()
        inicio = corte.end()
    yield periodo[inicio:], len(periodo)


def termos_vetados_com_numero(
    texto: str, classe: str = "acao", citacoes: list | None = None
) -> list[str]:
    """Termos VETADOS com número no mesmo período (bloqueante, D6c).

    `citacoes` (A2, correção red-team; opcional — `None` preserva o
    comportamento ORIGINAL/retrocompatível desta função pura): Basileia,
    inflação implícita, P/VP (FII) e o NOVO 'DY a mercado' (A3, abaixo) só
    deixam de bloquear quando o número casa com o `texto_citado` de alguma
    citação cuja fonte corresponde à origem esperada (IF.data/BCB; ANBIMA/
    ETTJ; COTAHIST/B3) — relaxamento por CITAÇÃO, nunca por rótulo textual
    solto emitido pelo próprio modelo (`_RELAXAMENTO_POR_CITACAO`). Sem
    `citacoes` ou sem citação correspondente, o termo permanece bloqueante.

    RISCO RESIDUAL ACEITO (red-team v2.2, PR #24): anualização por SINÔNIMO —
    'equivale a X% no ano', 'em base anual', '12x o mensal' — NÃO é quebra-
    isenção (colide com Selic/CDI legítimos em '% a.a.' no mesmo período);
    mitigação a jusante: faithfulness + Citations + system prompt + revisão.

    Função PURA e determinística. Fecha o convite à alucinação nas lacunas de
    cada classe: 'curva DI' (sem fonte keyless — só o PROXY nomeado via Tesouro
    prefixado é citável), 'inflação implícita' (vencimentos não coincidem),
    'índice de Basileia' (não está na DFP) e — só para FII — 'P/VP' e
    'dividend yield' (preço B3 licenciado). O DY MENSAL do informe CVM é
    permitido quando o PERÍODO (linha do bullet) traz o rótulo ('do informe'/
    'auto-declarado') ANTES do fim da frase do claim e nenhum 'anualiza*'/'a
    (preço de) mercado' fora das ressalvas protetoras quase-verbatim — ver
    `_dy_isento_no_periodo` (1º/2º falsos positivos ao vivo, HGLG11 09/07) e
    `_dy_termo_presente` (VP/DY, valor patrimonial/DY, par DY×Selic).

    Red-team fase 2 (M4): o número conta em qualquer posição da frase (M4b),
    ano/data não conta como número (M4a) e quebra de linha simples de bullet
    quebrado é o MESMO período (M4c; linha iniciando em número NEGATIVO é
    continuação) — ver `_tem_numero_de_claim` e `_QUEBRA_CONTINUACAO_RE`.
    Red-team do fix v1: detecção NUNCA roda sobre texto deletado — só a
    isenção considera as ressalvas, por span. LIMITAÇÕES CONHECIDAS
    (documentadas no follow-up de hardening; mitigação a jusante = Citations +
    faithfulness + system prompt + revisão): sinônimos semânticos de
    anualização ('ao ano', 'a.a.', 'em base anual') não são quebra-isenção —
    colidem com a Selic/CDI legitimamente citados '% a.a.' no mesmo período —
    e 'yield'/'rendimento' isolados estão fora do escopo do termo.
    """
    classe = _normalizar_classe(classe)
    achados: list[str] = []
    texto_continuo = _QUEBRA_CONTINUACAO_RE.sub(" ", texto or "")
    for periodo in texto_continuo.split("\n"):
        for frase, fim_frase in _frases_com_fim(periodo):
            if not frase.strip():
                continue
            for rotulo, termo_re, classes in _REGRAS_VETADAS:
                if classes is not None and classe not in classes:
                    continue
                if rotulo is _VETADO_DY:
                    if not _dy_termo_presente(termo_re, frase, periodo):
                        continue
                elif rotulo is _VETADO_DY_MERCADO:
                    if not _dy_mercado_termo_presente(frase):
                        continue
                elif termo_re.search(frase) is None:
                    continue
                # Red-team v3 (TERMO-04): número por extenso PT-BR também conta
                # como número-de-claim — só é consultado aqui, DEPOIS do termo
                # vetado já ter casado na frase (a coocorrência com o termo é a
                # condição da regra; ver `_tem_numero_extenso`), então não
                # contamina `_tem_numero_de_claim`/`_consenso_numeros_sem_
                # atribuicao` (que seguem só dígitos, comportamento intacto).
                if not _tem_numero_de_claim(frase) and not _tem_numero_extenso(frase):
                    continue
                if rotulo is _VETADO_CURVA_DI and _PROXY_RE.search(frase):
                    continue  # proxy NOMEADO no mesmo período é o uso citável permitido
                if rotulo is _VETADO_DY and _dy_isento_no_periodo_com_citacao(
                    periodo, fim_frase, citacoes
                ):
                    continue  # DY do informe (A3, intacto) + fallback por citação (V-10)
                # A2 (correção red-team): relaxamento por CITAÇÃO — não toca
                # `_dy_isento_no_periodo` (A3); é uma saída ADICIONAL (OR),
                # então um DY do informe (rótulo) e um DY a mercado (citação)
                # na MESMA frase podem cada um se justificar por seu próprio
                # caminho. Sem citação/origem correspondente -> segue vetado.
                # `_VETADO_DY_MERCADO` usa a SUB-CLÁUSULA em torno de "a
                # mercado" (não a frase inteira) — senão o subconjunto (abaixo)
                # exigiria citação também para o número do sub-claim vizinho
                # (o DY do informe, auto-declarado, isento por rótulo — nunca
                # por citação), quebrando V-10 (correção red-team v3).
                origem_re = _RELAXAMENTO_POR_CITACAO.get(rotulo)
                if origem_re is not None:
                    texto_escopo = (
                        _subclausula_dy_mercado(frase) if rotulo is _VETADO_DY_MERCADO else frase
                    )
                    if _isento_por_citacao(texto_escopo, origem_re, citacoes):
                        continue
                # 240 chars: o corte em 120 truncava a frase ANTES do trecho
                # que causou o veto (diagnóstico do FP de produção 10/07 exigiu
                # reconstruir o texto no banco) — laudo precisa mostrar o gatilho.
                achados.append(f"{rotulo}: '{frase.strip()[:240]}'")
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
    # Remove SÓ as cláusulas de negação (recomendação e, agora, o disclaimer
    # de valuation "NÃO é preço-alvo nem recomendação" — decisão fora do
    # plano original, ver resposta final: sem isto, o próprio aviso anti-
    # recomendação do bloco de valuation da F3 colidiria com o veto de
    # 'preço-alvo'). O resto da frase segue exposto à varredura.
    texto = _DISCLAIMER_RE.sub("", texto)
    return _DISCLAIMER_VALUATION_RE.sub("", texto)


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


def _secao_por_titulo(markdown: str, chave: str) -> str:
    """Extrai o texto de TODA seção H2 cujo título contém `chave` (minúsculo,
    sem acento), até o próximo H2 — generalização do mecanismo de escopo
    original da seção geopolítica, reusado pelo carve-out de consenso (A1)."""
    linhas = (markdown or "").splitlines()
    dentro = False
    buf: list[str] = []
    for ln in linhas:
        if re.match(r"^##\s", ln):
            dentro = chave in _sem_acentos(ln.lower())
            continue
        if dentro:
            buf.append(ln)
    return "\n".join(buf)


def _linhas_com_escopo(markdown: str, chave: str) -> list[tuple[str, bool]]:
    """(linha, dentro) p/ cada linha do markdown — `dentro=True` sse a linha
    está sob um H2 cujo título contém `chave` (mesmo mecanismo de
    `_secao_por_titulo`, mas preservando a linha-a-linha p/ `_violacoes_
    recomendacao` decidir a condição (a) do carve-out de consenso, A1)."""
    dentro = False
    saida: list[tuple[str, bool]] = []
    for ln in (markdown or "").splitlines():
        if re.match(r"^##\s", ln):
            dentro = chave in _sem_acentos(ln.lower())
            saida.append((ln, False))  # o cabeçalho em si não é "corpo" da seção
            continue
        saida.append((ln, dentro))
    return saida


def _violacoes_recomendacao(
    markdown: str, extra_texto: str, consenso_valores: Sequence[float]
) -> list[str]:
    """Linguagem de recomendação/direcional (bloqueante).

    A1 (correção red-team) — carve-out de consenso: `_CARVEOUT_CONSENSO_RE`
    ('preço-alvo'/'price target'/'rating' direcional) só é EXEMPTO quando (a)
    a linha está dentro de uma seção H2 cujo título contém 'consenso', (b) há
    marcador de atribuição na linha (`_ATRIBUICAO_RE`) e (c) algum número da
    linha casa com o `valor` de algum item VALIDADO de `envelope['consenso']`
    (`consenso_valores`). Fora da seção — ou faltando (b)/(c) — permanece
    bloqueante sem exceção; todo o resto de `_PADROES_RECOMENDACAO` (compre,
    mantenha, stop-loss...) segue bloqueante incondicionalmente, mesmo
    DENTRO da seção de consenso — só os 3 termos do carve-out são elegíveis.

    `extra_texto` (resumo do Haiku + `texto_livre_novo`, A5) não tem
    estrutura H2 — é 100% determinístico (`texto_livre_novo`) ou um resumo
    neutro; a ÚNICA fonte possível de 'preço-alvo' ali é o renderizador
    canônico do consenso já validado, então a condição (a) é satisfeita por
    construção quando (b)+(c) valem (nenhuma superfície de ataque do LLM
    livre nesta zona para este carve-out específico).
    """
    achados: list[str] = []

    def _varrer(linha: str, *, dentro_consenso: bool) -> None:
        limpo = _strip_disclaimer(linha)
        for m in _RECOMENDACAO_RE.finditer(limpo):
            trecho = m.group(0).strip()
            if (
                dentro_consenso
                and _CARVEOUT_CONSENSO_RE.search(trecho)
                and _ATRIBUICAO_RE.search(limpo)
                and _numero_bate_algum_item(limpo, consenso_valores)
            ):
                continue  # A1: carve-out válido — atribuído e com número casado
            achados.append(trecho)

    for ln, dentro in _linhas_com_escopo(markdown, "consenso"):
        _varrer(ln, dentro_consenso=dentro)
    for ln in (extra_texto or "").splitlines():
        _varrer(ln, dentro_consenso=True)
    return achados


def _consenso_numeros_sem_atribuicao(markdown: str, valores: Sequence[float]) -> list[str]:
    """R12 (realizado via A1): todo número "de claim" dentro da seção H2 de
    consenso do markdown precisa de marcador de atribuição + casar com um
    item VALIDADO de `envelope['consenso']` — senão é tratado como número
    inventado/laundering (bloqueante), MESMO sem a palavra 'preço-alvo'
    (cobre 'consenso de analistas: R$ 63' sem veículo, alvo agregado
    inventado pelo próprio LLM etc.). Espelha `_faithfulness_numerica`, mas
    escopado à seção e aos itens VALIDADOS do envelope (não ao texto_citado
    bruto — correção A1 condição c).
    """
    secao = _secao_por_titulo(markdown, "consenso")
    achados: list[str] = []
    for frase in re.split(r"(?<=[.;!?])\s+|\n", secao):
        limpo = _strip_disclaimer(frase)
        if not limpo.strip() or not _tem_numero_de_claim(limpo):
            continue
        if _ATRIBUICAO_RE.search(limpo) and _numero_bate_algum_item(limpo, valores):
            continue
        achados.append(limpo.strip()[:200])
    return achados


def _violacoes_tecnica_como_conselho(texto: str) -> list[str]:
    """R10 (A7, bloqueante): palavra-de-sinal de indicador técnico computado
    (RSI/MACD/Bollinger/Estocástico/Williams/médias móveis/Fibonacci/A-D/
    cruzamento dourado-de-morte) + diretiva ao leitor na MESMA frase. Leitura
    puramente descritiva (sem diretiva) passa — provado pelos templates REAIS
    de `tecnica.py` no teste dedicado."""
    achados: list[str] = []
    for frase in re.split(r"(?<=[.;!?])\s+|\n", texto or ""):
        limpo = _strip_disclaimer(frase)
        if _R10_SINAL_RE.search(limpo) and _R10_DIRETIVA_RE.search(limpo):
            achados.append(limpo.strip()[:200])
    return achados


def _violacoes_valuation_como_alvo(texto: str) -> list[str]:
    """R11 (A6, bloqueante): termo de valuation ('valor justo'/'preço justo'/
    'valor intrínseco') + diretiva REAL ao leitor na MESMA frase — SEM os
    gatilhos genéricos 'acima de'/'abaixo de' (uso contábil/IFRS legítimo,
    ex.: 'ativos avaliados a valor justo, acima de R$ 2 bilhões', não pode
    bloquear)."""
    achados: list[str] = []
    for frase in re.split(r"(?<=[.;!?])\s+|\n", texto or ""):
        limpo = _strip_disclaimer(frase)
        if _R11_TERMO_RE.search(limpo) and _R11_DIRETIVA_RE.search(limpo):
            achados.append(limpo.strip()[:200])
    return achados


def _alertas_geopolitica(markdown: str) -> list[str]:
    """Frases na seção geopolítica que afirmam um evento específico sem hedge."""
    secao = _secao_por_titulo(markdown, "geopol")
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

    Gate v3 (F4) + Hotfix 2 (2026-07-11, item 14 da docstring do módulo):
    DUAS superfícies de varredura. `texto_varredura_amplo` (markdown +
    resumo + `envelope['texto_livre_novo']`, A5) alimenta as regras de
    RECOMENDAÇÃO/diretiva — R1 (`_violacoes_recomendacao`), R10 (técnica-
    como-conselho, A7) e R11 (valuation-como-preço-alvo, A6): diretiva ao
    leitor bloqueia não importa quem autorou a frase. `texto_varredura_
    modelo` (markdown + resumo, SEM texto_livre_novo) alimenta as regras
    NUMÉRICAS ancoradas em citação — `termos_vetados_com_numero` (A2/A3),
    o carve-out de consenso (A1/R12) e `_faithfulness_numerica`: essas
    regras existem para número de AUTORIA DO MODELO sem proveniência;
    `texto_livre_novo` é escrito pelo BACKEND com proveniência ESTRUTURAL
    (`fonte_id` por métrica/insumo) e NUNCA vai ter uma citação Anthropic
    correspondente (o LLM não vê nem escreve esse campo) — aplicar a regra
    de citação a ele bloqueia conteúdo 100% legítimo (bug TAEE11 provado
    ao vivo, 2ª tentativa).
    """
    classe = _normalizar_classe(classe)
    markdown = envelope.get("markdown") or ""
    citacoes = envelope.get("citacoes") or []
    fontes = envelope.get("fontes") or []
    lacunas = envelope.get("lacunas") or []
    # Inclui texto gerado por LLM exposto ao usuário (resumo do Haiku) na
    # varredura, e — A5 (correção red-team) — o texto livre 100%
    # determinístico dos blocos novos (leituras técnicas + descrições de
    # valuation + implicações de métricas + exibição canônica de consenso).
    # Quebra DUPLA entre partes: parágrafo novo — nenhuma parte pode se
    # fundir à última linha da anterior sob a normalização de continuação do
    # check de termos vetados.
    resumo = ((envelope.get("metadata") or {}).get("resumo")) or ""
    texto_livre_novo = envelope.get("texto_livre_novo") or ""
    extra_texto = resumo + "\n\n" + texto_livre_novo
    # Hotfix 2 (2026-07-11): DUAS superfícies — ver docstring da função/item
    # 14 do módulo. `_amplo` inclui texto_livre_novo (defesa de POSTURA,
    # aplica a QUALQUER autor); `_modelo` NÃO inclui (defesa de PROVENIÊNCIA
    # numérica, só faz sentido para texto de autoria do modelo — o único que
    # pode ter/faltar uma citação Anthropic).
    texto_varredura_amplo = markdown + "\n\n" + extra_texto
    texto_varredura_modelo = markdown + "\n\n" + resumo

    # A1 condição (c): valores dos itens VALIDADOS de consenso (para o
    # carve-out de 'preço-alvo'/'rating' e para o R12 de números soltos).
    consenso_env = envelope.get("consenso") or {}
    consenso_valores = [
        float(it["valor"])
        for it in (consenso_env.get("itens") or [])
        if isinstance(it, dict) and it.get("valor") is not None
    ]

    violacoes = _violacoes_recomendacao(markdown, extra_texto, consenso_valores)
    alertas_geo = _alertas_geopolitica(markdown)
    # Termos vetados-com-número (D6c): SÓ na superfície MODELO (markdown +
    # resumo) — Hotfix 2. `texto_livre_novo` NÃO entra aqui: é bloco
    # determinístico com proveniência estrutural (fonte_id), nunca citado
    # pelo LLM, então a isenção por citação (A2/A3) é inalcançável para ele
    # por desenho — incluí-lo bloquearia número legítimo sem alternativa
    # (bug TAEE11, 2ª tentativa). A2/A3: relaxamento por citação (Basileia/
    # inflação implícita/P-VP-FII/DY a mercado) recebe as citações reais do
    # envelope — seguem valendo para número de autoria do MODELO.
    termos_vetados = termos_vetados_com_numero(texto_varredura_modelo, classe, citacoes=citacoes)
    # R10/R11 (A6/A7, bloqueantes): seguem na superfície AMPLA (inclui
    # texto_livre_novo) — são regra de POSTURA/diretiva, não de proveniência
    # numérica: uma leitura técnica ou de valuation virada conselho bloqueia
    # não importa se veio do LLM ou do template determinístico (defesa em
    # profundidade contra template corrompido).
    violacoes_tecnica = _violacoes_tecnica_como_conselho(texto_varredura_amplo)
    violacoes_valuation = _violacoes_valuation_como_alvo(texto_varredura_amplo)
    # R12 (A1): números soltos na seção de consenso sem atribuição/casamento
    # — escopado ao MARKDOWN (a única zona com texto livre do LLM sujeito a
    # laundering; texto_livre_novo é determinístico, ver `_violacoes_
    # recomendacao`).
    consenso_sem_atribuicao = _consenso_numeros_sem_atribuicao(markdown, consenso_valores)
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
        or bool(violacoes_tecnica)
        or bool(violacoes_valuation)
        or bool(consenso_sem_atribuicao)
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
    if violacoes_tecnica:
        motivos.append(f"leitura técnica transformada em conselho (R10): {violacoes_tecnica}")
    if violacoes_valuation:
        motivos.append(f"valuation apresentado como preço-alvo (R11): {violacoes_valuation}")
    if consenso_sem_atribuicao:
        motivos.append(
            f"número na seção de consenso sem atribuição/citação válida (R12): "
            f"{consenso_sem_atribuicao}"
        )
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
        "violacoes_tecnica_como_conselho": violacoes_tecnica,
        "violacoes_valuation_como_alvo": violacoes_valuation,
        "consenso_sem_atribuicao": consenso_sem_atribuicao,
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
