# DESIGN-TOKENS.md — BRASA EDITORIAL

> Referência de consumo para todas as ondas de telas. Fonte da verdade dos
> **valores** é `scratchpad/specs/DESIGN-BRIEF.md`; fonte da verdade da
> **implementação** é `src/app/globals.css`. Se este arquivo divergir do CSS,
> o CSS vence — mas isso não deveria acontecer: qualquer PR que mude um
> token tem que atualizar as duas coisas juntas.
>
> Regra de ouro: **componente consome utilitário Tailwind (semântico), nunca
> hex/valor arbitrário**. `bg-[#a03a06]`, `text-blue-600`, `p-[13px]` = defeito.

---

## 1. Cores — utilitário → papel → hex

Todo par abaixo já foi verificado WCAG AA (script `verify_globals_contrast.py`,
40 pares, luminância relativa real): **texto ≥ 4.5:1 · UI/foco ≥ 3:1**, nos
dois temas. Os valores trocam sozinhos com `prefers-color-scheme`: nenhuma
classe muda entre claro/escuro, só o CSS var por trás dela.

| Utilitário Tailwind | Papel semântico | Hex claro | Hex escuro | Uso |
|---|---|---|---|---|
| `bg-page` | Fundo da página | `#f6f6f3` | `#101216` | body, fundo de seções |
| `bg-card` | Superfície "folha" (card/tese) | `#fdfdfb` | `#16181d` | cards, painéis de conteúdo |
| `bg-elevated` | Superfície elevada (modal/tooltip/dropdown) | `#ffffff` | `#1d2027` | elevação — sombra só no claro (`.sombra-elevada`), borda no escuro |
| `text-ink` | Tinta primária (corpo, títulos) | `#16181d` | `#ebe9e4` | 16.40:1 / 15.45:1 na página |
| `text-ink-2` | Tinta secundária (subtítulos, descrições) | `#4a4f58` | `#b5b3ac` | 7.60:1 / 8.94:1 |
| `text-ink-3` | Tinta terciária (metadados, timestamps) | `#4c4f56` | `#a5a49e` | 7.58:1 / 7.50:1 na página — **≥4.67:1 / ≥4.62:1 até no pico composto da luz COM o termo REAL do shader** (aurora ∪ shader 0.051/0.059 medido por gl.readPixels ∪ penumbra ∪ bloom ∪ núcleo sobre `bg-page`; 2ª passada da calibração, Onda 3 2026-07-12 — os `#51545b`/`#9e9d97` da 1ª passada analítica caíam a 4.32:1/4.25:1 com o shader somado; ver emenda Onda 3 abaixo). Não usar abaixo de 14px |
| `border-line` | Hairline decorativa | `#e6e5df` | `#23262d` | réguas, zebra — **isenta de AA** (decorativa, não comunica estado) |
| `border-line-strong` | Régua de cabeçalho de seção | `#c7c6bf` | `#383c45` | também decorativa |
| `border-field` | Borda de campo/input interativo | `#6a6963` | `#7e8691` | ≥3:1 — **é a que precisa de AA**, nunca trocar por `line`/`line-strong` num controle. **≥3.13:1 / ≥3.14:1 até no pico composto COM o termo real do shader** (2ª passada, Onda 3 2026-07-12; os `#6f6e67`/`#78808c` da 1ª passada caíam a 2.91:1/2.90:1 com o shader somado — ver emenda Onda 3 abaixo) |
| `bg-brasa` / `text-brasa` | Brasa — ação primária | `#a03a06` | `#e97b3c` | botão primário, toggle ativo — 6.25:1 / 6.57:1 como UI |
| `bg-brasa-forte` | Brasa hover/pressed | `#7f2e04` | `#f28a50` | |
| `text-sobre-brasa` | Texto sobre fundo de brasa | `#ffffff` | `#1c0e05` | **no dark é tinta escura, NUNCA branco** (branco daria ~2.5:1, reprova) |
| `text-brasa-texto` | Links, números-fonte, tab ativa | `#9e3c00` | `#f4996a` | 6.26:1 / 8.58:1 — é também a cor do anel de foco (`:focus-visible`) |
| `bg-aviso-fundo` | Fundo de aviso / lacuna declarada | `#fbf0d9` | `#2a2214` | "dado não encontrado", "em breve", dado defasado |
| `border-aviso-borda` | Borda de aviso (UI) | `#a3781a` | `#957634` | 3.53:1 / 3.68:1 |
| `text-aviso-texto` | Texto de aviso | `#7a5200` | `#e6c172` | 6.12:1 / 9.15:1 |
| `bg-erro-fundo` | Fundo de erro técnico | `#fbeae8` | `#2a1614` | **só falha de fonte/serviço** — nunca para lacuna declarada |
| `border-erro-borda` | Borda de erro (UI) | `#c1554b` | `#ad5f54` | 3.86:1 / 3.71:1 |
| `text-erro-texto` | Texto de erro | `#a3251c` | `#f2938a` | 6.35:1 / 7.62:1 |
| `bg-realce` | Realce de citação ("salmão FT" guardado) | `#f9ece2` | `#251a12` | **exclusivo de citação/evidência** — nunca fundo decorativo de seção |

**Guard-rails cromáticos (não negociáveis):**
- Brasa em **<5% da superfície**, sempre com significado (ação ou evidência) — nunca "só para chamar atenção".
- Verde: **proibido** em qualquer papel (identidade anterior aposentada).
- Um único acento. Proibido segundo acento, gradiente multicolor, glassmorphism, blobs.
- Dark: nunca `#000` chapado, nunca branco puro de corpo, **nunca `text-white` sobre `bg-brasa`**.

### Emenda 2026-07-11 (missão cinematográfica) — luz ambiente fria (carve-out)

> **Luz ambiente fria (carve-out).** É permitida UMA luz monocromática azul-tinta (matiz ~222°, croma baixo) como profundidade/atmosfera, em duas intensidades: aurora ambiente ≤6% e foco interativo ≤10% claro / ≤12% escuro. A luz não é acento: nunca senta em controle, nunca comunica ação/estado/dado, nunca é quente. A brasa segue o único acento. Seguem PROIBIDOS: gradiente multicolor, glassmorphism, blobs, segundo acento, verde. A luz jamais banha número factual, citação, chip bg-realce ou região brasa/salmão (trava M3 — Bazley). Registro frio ≠ rebrand: nenhum hex de conteúdo/tinta/brasa muda; só entram as camadas de luz e o grão.

**O que NÃO muda:** paleta de conteúdo inteira (tinta, superfícies, brasa, aviso, erro, bg-realce, gráficos 1–6), tipografia, escala, contraste AA, dark por prefers-color-scheme. A luz é aditiva.

Fonte: `.maestro/direcao-de-arte-cinema.md` §1 (M1, LEI da missão) · lastro científico completo, estudo por estudo, com força de evidência declarada: `Design - Brief de Cor (Ciência).md` no Vault (`08 - Produto/`).

**Decisão arquitetural (emenda 2026-07-11) — Via A.** CSS puro evoluído + micro-hooks CSSOM para o follow do ponteiro e o drift da aurora. Libs de animação runtime (Framer Motion, GSAP etc.) **rejeitadas** para esta camada — motivo: bundle (zero dep npm nova), CSP (nonce, zero `style=` inline de terceiro) e estética (a casa já resolve reveal/motion em CSS-first; ver §3). A luz é sempre um sprite radial pré-pintado, movido só por `transform`.

#### Tokens novos — luz ambiente e grão

| Token CSS | Papel | Claro | Escuro | Teto |
|---|---|---|---|---|
| `--luz-tinta` | cor da luz (RGB space-separated p/ `rgb(var(...)/alfa)`) | `42 54 84` (`#2A3654`) | `132 148 178` (`#8494B2`) | matiz ~222° fixo, croma baixo — não muda |
| `--luz-aurora-alfa` | opacidade do leito ambiente (sempre presente, difuso, estático/scroll) | `0.05` (0.04 reprovou perceptibilidade no wow-gate) | `0.055` | **≤0.06** nos dois temas |
| `--luz-foco-alfa` | opacidade da luminária que segue o ponteiro | `0.09` (0.07 reprovou perceptibilidade no wow-gate) | `0.10` | **≤0.10 claro / ≤0.12 escuro** |
| `--mx`, `--my` | posição do sprite de foco (px), default neutro | `0px` | `0px` | setado só via CSSOM, nunca em CSS estático |
| `--grao-alfa` | opacidade da textura de grão (opcional, só `bg-page`) | `0.025` | `0.04` | **≤0.03 claro / ≤0.04 escuro** |
| `--ease-cena` | easing do glide de luz (follow do foco + drift da aurora) | `cubic-bezier(0.4, 0, 0.2, 1)` | idem | escopo estrito: só a luz — nunca reusar `ease-ink`/`ease-rule`/`ease-settle` nela, nem usar `--ease-cena` fora da luz |

Sprite do foco (referência de implementação): `radial-gradient(circle at center, rgb(var(--luz-tinta)/var(--luz-foco-alfa)) 0%, transparent 60%)` em camada ~120vmax, movida SÓ por `transform: translate3d(var(--mx),var(--my),0)`.

> **Superseded parcial (2026-07-12, emenda MATÉRIA VIVA abaixo):** os tetos
> de `--luz-aurora-alfa` (≤0.06) e `--luz-foco-alfa` (≤0.10/0.12) desta
> tabela foram SUBSTITUÍDOS por novos tetos autorizados (aurora 0.07/0.08;
> luminária dupla núcleo+bloom+penumbra com pico combinado ≈0.14/0.16), com
> cláusula de recuo. `--luz-foco-alfa` vira LEGADO até a Onda 1A trocar o
> sprite único pela dupla; `--luz-foco-card-alfa` e `--grao-alfa` seguem
> intocados com os tetos originais.

**Regra de consumo — CSSOM carve-out (não negociável):**
- **PERMITIDO:** `el.style.setProperty('--mx', …)` / `el.style.setProperty('--my', …)`, client-side, **pós-mount**, dentro de `pointermove` coalescido por `requestAnimationFrame`, listener `passive`, só sob `@media (hover:hover) and (pointer:fine)`.
- **PROIBIDO:** `el.setAttribute('style', …)`, prop `style={}` em JSX (SSR ou client), tag `<style>` solta, `styled-jsx`, qualquer `style=` inline literal. `.style.setProperty` é a porta permitida — governada por `script-src` sob nonce, não por `style-src` (CSP permanece intacta). **Ampliação formal 2026-07-12 (emenda MATÉRIA VIVA, abaixo):** o carve-out passa de "apenas `el.style.setProperty`" para "**escritas CSSOM do motor GSAP em folhas decorativas**" (o GSAP escreve via `element.style` — a mesma porta CSSOM); todas as proibições desta lista seguem integrais.

**TRAVA C2 (containing-block da Régua de Leitura) — inegociável:** PROIBIDO `transform`/`filter`/`will-change`/`contain` em `body`, `main` ou **qualquer ancestral** de `.regua-leitura`. As camadas de luz (aurora + foco) são SEMPRE pseudo-elementos ou `<div>` **irmãs** — nunca wrappers. O drift/follow anima o `transform` da própria camada de luz (o irmão), nunca de um ancestral. Motivo: `position: fixed` da régua depende do containing block do viewport; um ancestral com `transform` quebra isso silenciosamente (precedente: globals.css ~601–628/705–711). QA prova zero regressão visual da régua antes de qualquer merge.

### Emenda 2026-07-12 — correção de gate: `--ink-tertiary`/`--border-field` no PICO da luz

> A emenda de 2026-07-11 introduziu a luz sem revalidar os pares AA contra o
> PIOR CASO de composição (aurora ambiente ∪ foco de ponteiro, sempre que o
> token está direto sobre `--bg-page`, sem card opaco por baixo — ex.: hero
> da home, `.tem-foco`). Auditoria por alpha-composite real (sRGB gama, não
> linear) provou reprovação em dois pares: `text-ink-3` claro caía a 3.78:1
> e `border-field` claro a 2.39:1 no pico (0.05 ∪ 0.09 = alfa 0.1355 sobre
> `#f6f6f3`); no escuro, `border-field` caía a 2.69:1 no pico (0.055 ∪ 0.10 =
> alfa 0.1495 sobre `#101216`). Bisecção provou que nenhum alfa de luz
> perceptível (0.04–0.06) resolve sem tocar os primitivos — a luz ficou como
> está; só os 3 tokens abaixo foram recalibrados (lightness apenas — matiz e
> saturação intocados, `border-field` claro segue greige, `border-field`
> escuro segue o mesmo azul-acinzentado de antes):
>
> | Token | Antes | Depois | Pico antes | Pico depois |
> |---|---|---|---|---|
> | `--ink-tertiary` (claro) | `#686d76` | `#5b5f67` | 3.78:1 (FALHA) | 4.66:1 |
> | `--border-field` (claro) | `#8f8e86` | `#7b7a72` | 2.39:1 (FALHA) | 3.14:1 |
> | `--border-field` (escuro) | `#616772` | `#6b727e` | 2.69:1 (FALHA) | 3.15:1 |
> | `--ink-tertiary` (escuro, folga opcional) | `#8f8d87` | `#908e88` | 4.60:1 (margem fina) | 4.67:1 |
>
> Script de auditoria: `scratchpad/contraste-tokens/calibra_tokens.py`
> (worktree `wt-cinema`). Também validado contra `--bg-card` puro, contra o
> composite local do masthead da tese (`.aurora-masthead`, só aurora, sem
> foco) e contra o foco local dos cards de galeria (`.tem-foco::after` do
> `CartaoTese`, `--luz-foco-card-alfa`) — todos os pares ficam ≥4.5:1
> (texto) / ≥3:1 (UI) nesses cenários também, com folga confortável.

### Emenda 2026-07-12 — missão imersiva "MATÉRIA VIVA" (Onda 0: fundação)

> LEI da missão: `.maestro/plano-imersivo.md` (worktree `wt-imersivo`),
> inclusive a seção 12 (emendas pós-red-team, que PREVALECEM). Esta emenda
> registra os tokens novos com lastro, os novos tetos de luz autorizados +
> cláusula de recuo, a recalibração AA da Onda 0, o carve-out CSSOM ampliado
> (GSAP), a licença do GSAP, a doutrina worker-src e as regras de
> arquitetura vinculantes para TODAS as ondas.

#### Tokens novos (lastro honesto, estudo a estudo)

| Token CSS | Claro | Escuro | Papel | Lastro |
|---|---|---|---|---|
| `--accent-confianca` (utilitários `*-confianca`) | `#2d4a7a` | `#9db4dd` | Confiança em elementos **salientes** (scrollspy ativo, keyline do selo de metodologia, trilha de auditoria, fio duplo dos chips); **nunca CTA/wash** — brasa segue única cor de ação | Cyr et al. 2010; Alberts & van der Geest 2011 (financeiro: azul mais confiável; all-black pontua pior); Labrecque & Milne 2012. Anti-folclore: croma saliente em micro-área, não wash; Mehta & Zhu 2009 EXCLUÍDO (falhou replicação — Gnambs 2020) |
| `--accent-valor` (utilitários `*-valor`) | `#8a6415` | `#d9b354` | Base do ouro-metálico em micro-área (<5% da tela): badge "Tese Profunda", marcos premium | Meert et al. 2014 (preferência por gloss); Skulmowski et al. 2016 (croma alto só em micro-área); família de `--grafico-3` |
| `--valor-brilho` (utilitários `*-valor-brilho`) | `#f0dfae` | `#f7ecc9` | Stop de highlight do gradiente especular (sheen por background-position; keyline ≤4px; varredura única na palavra "fonte" do hero) | Meert et al. 2014 (dourado só lê "metal" com highlight deslocado); Palmer & Schloss 2010 (gradiente tonal nunca cruza 60–90°) |
| `--moldura-ameixa` (utilitários `*-moldura-ameixa`) | `#5a3153` | `#b391ac` | Keyline 1px de molduras editoriais (pull-quotes, aberturas de capítulo, borda do masthead) — decorativo, **nunca texto/estado**; hue ~318° (fora de 70–200°) | Labrecque & Milne 2012 (roxo = sofisticação); Valdez & Mehrabian 1994 · **APOSENTADO 2026-07-16** → `--moldura-tinta` `#2d3f66`/`#8ea3c7` (~221°) — ver emenda OURIVESARIA abaixo |
| `--sombra-fria` | `rgb(42 54 84 / 0.16)` | n/a (elevação = borda) | Única sombra do `.sombra-elevada` — quita o ink hardcoded `rgb(22 24 29/.16)` apontado no recon | Valdez & Mehrabian 1994 (PAD: frio escuro = dominância sem arousal) |
| `--luz-nucleo-alfa` | `0.043` | `0.054` | Pico do núcleo rápido da luminária dupla (36vmax, lag ~180ms) — **é o 1º dial a reduzir se o AA do pico não fechar** | Orçamento composto AA calibrado por script; Skulmowski 2016 |
| `--luz-bloom-alfa` | `0.10`\* | `0.11`\* | Pico do bloom (90vmax, stop 45%, lag 700ms) — pico combinado da luminária ≈0.14/0.16 (novos tetos autorizados) | Autorização do humano + cadeia calibra_tokens.py→AA |
| `--luz-penumbra` + `--luz-penumbra-alfa` | `70 44 78` · α `0.03` | `176 146 186` · α `0.04` | Anel externo ameixa do foco (triplet RGB, mesmo padrão de `--luz-tinta`) — profundidade de joia na luz fria, nunca acionável | Valdez & Mehrabian 1994; Palmer & Schloss 2010 (222°→310° não cruza 60–90° nem 70–200°) · **TRIPLET APOSENTADO 2026-07-16** → safira `26 38 66`/`104 122 156` (~221°), alfas INTOCADOS — ver emenda OURIVESARIA abaixo |
| `--brasa-ember` | `160 58 6` | `233 123 60` | Cor das brasas do shader do hero (triplet; lida via `getComputedStyle`, nunca hardcoded no frag); **nunca sobre número/dado** (uMask + chips opacos) | Bazley et al. 2021 (âmbar, nunca vermelho sobre dado financeiro) |

\* provisórios — valores FINAIS saem do `calibra_tokens.py` da Onda 3 com o
termo REAL do shader (gl.readPixels); nunca no chute.

#### Novos tetos de luz autorizados + cláusula de recuo

Os tetos da emenda 2026-07-11 (aurora ≤0.06; foco ≤0.10/0.12) foram
**substituídos POR AUTORIZAÇÃO EXPLÍCITA do humano** (não-veto registrado no
plano §1), condicionada à cadeia completa: `calibra_tokens.py` →
recalibração `ink-3`/`border-field` → prova AA por screenshot no pico
composto. Novos valores: `--luz-aurora-alfa` **0.07/0.08** (modulada por
`body[data-secao]` entre 0.05–0.08 + decaimento por profundidade);
luminária dupla com pico combinado **≈0.14 claro / ≈0.16 escuro**
(bloom 0.10/0.11 ∪ núcleo 0.043/0.054) + penumbra 0.03/0.04.

**Cláusula de recuo (binária, sem iteração infinita):** se o AA não fechar
com tinta viável — reduzindo `--luz-nucleo-alfa` PRIMEIRO — o pico combinado
da luminária recua para **0.12/0.14** e a aurora para **0.06/0.06**. Sem a
cadeia completa, reverte tudo.

#### Recalibração AA — 1ª passada ANALÍTICA da Onda 0 (sem shader)

Pico composto analítico: aurora ∪ penumbra ∪ bloom ∪ núcleo sobre
`--bg-page` (compositing sequencial src-over em sRGB gama; incluir a
penumbra no centro é deliberadamente conservador). Script:
`.maestro/ferramentas/calibra_tokens.py` (parametrizado para receber o termo
do shader por CLI na Onda 3: `--shader-alfa-claro/--shader-alfa-escuro`).
Validação R12d em TODOS os contextos reais (bg-page, bg-card opaco,
bg-page+aurora, bg-page+pico, bg-card+foco-de-card 0.05) — 20/20 PASS para
os quatro tokens recalibrados. Só a lightness mudou (H/S preservados);
hierarquia de 3 níveis de tinta preservada nos dois temas.

| Token | Antes | Depois | Pico antes | Pico depois |
|---|---|---|---|---|
| `--ink-tertiary` (claro) | `#5b5f67` | `#51545b` | 3.95:1 (FALHA) | 4.67:1 |
| `--border-field` (claro) | `#7b7a72` | `#6f6e67` | 2.66:1 (FALHA) | 3.15:1 |
| `--ink-tertiary` (escuro) | `#908e88` | `#9e9d97` | 3.84:1 (FALHA) | 4.62:1 |
| `--border-field` (escuro) | `#6b727e` | `#78808c` | 2.59:1 (FALHA) | 3.15:1 |

> **Superseded (2026-07-12, Onda 3):** os quatro hexes desta 1ª passada foram
> substituídos pela 2ª passada com o termo REAL do shader — tabela abaixo.

> **ALERTA para a Onda 3 (gate AA):** `--accent-text` CLARO (`#9e3c00`,
> INTOCÁVEL — essência BRASA) cai a **4.17:1** no centro analítico do novo
> pico, e o dial NÃO resolve (núcleo=0 → 4.46:1; recuo binário → 4.39:1,
> ambos <4.5). No escuro passa com folga (5.75:1). Consequência de LAYOUT,
> não de token: nenhum link/número em `--accent-text` nu sobre `bg-page`
> pode habitar a zona de pico da luminária no hero — chip `bg-realce` opaco
> por cima (trava M3) ou distância espacial; a prova por screenshot da Onda
> 3 deve incluir esse par no pior enquadramento real.
> **Resolução (Onda 3, abaixo): medido por pixel real, o par PASSA — 4.95:1
> no pior enquadramento verdadeiro; nenhuma restrição de layout aplicada.**

#### Recalibração AA — 2ª passada com o termo REAL do shader (Onda 3, calibração, 2026-07-12)

**Termo do shader medido** (build de produção, Chromium/ANGLE D3D11 em GPU
real, hook de `gl.readPixels` pós-`drawArrays`, buffer premultiplicado,
viewport 1440×900): sob a coluna de texto o **cap do uMask segura exatamente
o teto** — alfa efetivo máximo **0.051 claro / 0.0588 escuro** (13/255 e
15/255; quantização de 8 bits do cap 0.05/0.06), idêntico na fase de
abertura e no assentado com a luminária no pico. Cross-check por diff de
screenshot (mesma cena com o canvas impedido de montar): p99,9 na zona
mascarada 0.048/0.064 — consistente. Na zona LIVRE do canvas (direita, sem
texto) o campo chega a 0.37 de alfa em fagulhas pontuais de brasa (por
design; nunca sob texto). Termo passado ao `calibra_tokens.py`:
`--shader-alfa-claro 0.051 --shader-alfa-escuro 0.059` (arredondado p/ cima),
cor padrão `--luz-tinta` + cenário de sensibilidade com `--brasa-ember` no
escuro (camada mais clara = pior caso lá) — mesmos candidatos nos dois
cenários. Validação R12d 20/20 contextos reais, hierarquia de 3 tintas
preservada nos dois temas (checagem do script).

| Token | Antes (1ª passada) | Depois (2ª passada) | Pico c/ shader antes | Pico c/ shader depois |
|---|---|---|---|---|
| `--ink-tertiary` (claro) | `#51545b` | `#4c4f56` | 4.32:1 (FALHA) | 4.67:1 |
| `--border-field` (claro) | `#6f6e67` | `#6a6963` | 2.91:1 (FALHA) | 3.13:1 |
| `--ink-tertiary` (escuro) | `#9e9d97` | `#a5a49e` | 4.25:1 (FALHA) | 4.62:1 (brasa: 4.65) |
| `--border-field` (escuro) | `#78808c` | `#7e8691` | 2.90:1 (FALHA) | 3.14:1 (brasa: 3.15) |

**Prova AA por pixel REAL** (screenshots com a luminária parada em cima de
cada alvo, pior pixel de fundo incluindo grão; evidências em
`.maestro/evidencias/calibracao/` do worktree): `ink-3` metadados do hero
5.51/5.23 e 5.51/5.10; `border-field` ao redor do CTA "Ver exemplo"
3.51/3.40; `accent-text` no sup `[1]` do H1 (o pior enquadramento do ALERTA)
**4.95 claro / 6.42 escuro — PASSA sem restrição de layout**: o pico
analítico co-localizado (3.86:1 com shader) é teto INALCANÇÁVEL na prática —
a penumbra é anel (contribuição ~0 no próprio centro), a aurora decai na
altura do H1 e a clareira do shader reduz o campo a 35% sob o cursor.
A doutrina de layout permanece de pé para elementos futuros: accent-text nu
sobre `bg-page` na zona de pico só com prova por pixel.

**Gates colaterais provados na mesma medição:** (a) hue do campo — 100% das
amostras readPixels (abertura + pico, 2 temas) são explicadas pela mistura
convexa `--luz-tinta`↔`--brasa-ember` com resíduo ≤0.86 unidade de 8 bits
(quantização), e a trajetória de hue desse segmento nunca entra em 70–200°
(safira 219–222° → magenta ~300° → brasa ~20°; ZERO pixel verde); (b) trava
M3 — chips `bg-realce` (hero sob o pico da luminária e prova viva): 100% dos
pixels de fundo do chip idênticos ao token puro (desvio máx 0 canal),
opacidade computada 1.

#### Carve-out CSSOM ampliado — motor GSAP (delta de CSP: ZERO)

- GSAP escreve estilo via CSSOM (`element.style`) — governado por
  `script-src` sob nonce; sem `unsafe-inline`, sem eval (grep provado no
  dist), sem `<style>` injetada. O carve-out formal passa a cobrir
  "**escritas CSSOM do motor GSAP em folhas decorativas**" (transform/
  opacity e custom properties escritas NA FOLHA consumidora).
- Seguem PROIBIDOS: `style={}` em JSX, `setAttribute('style')`, `<style>`
  injetada, styled-jsx, **plugin Flip** (usa `setAttribute('style')`) e
  `markers:true` em produção.
- Véus de rota e modo pinado = apenas `classList`. `src/proxy.ts` com
  **diff ZERO** é gate de merge.
- Loader único: `src/lib/gsapSetup.ts` (`carregarGsap()`, memoizado,
  `import()` dinâmico pós-idle/scroll-intent — R5). gsap JAMAIS em
  layout.tsx/Header/TeseClient (R2: delta zero em /tese).

#### Licença GSAP (registrada 2026-07-12)

`gsap@3.15.0` (pin exato): licença **Webflow "Standard no-charge"** —
gratuita inclusive para uso comercial, porém **não-MIT** (termos próprios;
sem redistribuir o GSAP como ferramenta concorrente). `@gsap/react@2.1.2`:
MIT. Citar no PR e manter no AGENTS.md.

#### Doutrina worker-src (único delta futuro admissível de CSP)

Sem worker nesta rodada. Se um dia houver OffscreenCanvas: worker **bundlado**
via `new Worker(new URL(...))` + 1 linha `worker-src 'self'` no proxy —
**nunca** `blob:` via `child-src`. Qualquer outro delta de CSP é defeito.

#### Regras de arquitetura vinculantes (todas as ondas)

1. **Um escritor por propriedade:** cada propriedade animável de um elemento
   tem UM dono (GSAP *ou* transition *ou* animation CSS). Elemento migrado ao
   CenaScrub PERDE `.reveal`/`.citacao-pin` na landing (diff explícito +
   grep de auditoria na Onda 3); aurora: transform é do drift do globals.css,
   opacity é do decaimento da `cinema/luz.css`.
2. **R1 (pin × transform):** NENHUM tween de transform em ancestral de
   elemento pinado; a seção do filmstrip fica FORA do CenaScrub; o pin nunca
   é ancestral da Tarja z-50 nem da `.regua-leitura` z-55 (trava C2).
3. **Folhas cinema (`src/styles/cinema/*.css`):** importadas no TOPO do
   `globals.css` (spec CSS: `@import` antes de qualquer regra) → em
   especificidade igual, o corpo do `globals.css` VENCE. Para sobrescrever
   regra existente use especificidade maior (`html body::before`,
   `.tem-foco .foco-luz`), nunca `!important` fora do bloco reduce. Cada
   folha tem UM dono (cabeçalho de cada arquivo); ninguém toca `globals.css`
   após a Onda 0.
4. **Reduced-motion nominal:** todo efeito novo entra POR NOME no bloco
   `@media (prefers-reduced-motion: reduce)` da SUA folha, classificado
   "progress" (isento, precedente régua/aurora) ou "decorativo"
   (`animation: none`/`display: none`) — o guard genérico NÃO zera
   `animation-delay` nem neutraliza scroll-timeline.
5. **Custom property dinâmica** escrita SEMPRE na folha consumidora
   (CSSOM); `@property inherits:false` segue PROIBIDO.
6. **Verde/jade banido** (hue 70–200°) em token, gradiente E interpolação de
   shader (mix por luminância/dessaturação; QA reprova hue amostrado via
   readPixels).

### Emenda APOTEOSE 2026-07-13 (Onda 0: fundação)

> LEI da missão: `.maestro/plano-apoteose.md` (worktree `wt-apoteose`), que
> PREVALECE sobre qualquer resumo abaixo — este bloco registra só o que
> toca TOKENS/CSS/contratos publicados pela Onda 0 (Fundação). As LEIs da
> missão Imersiva (R1–R12, trava C2, um-escritor-por-propriedade) seguem
> vinculantes, salvo as supersessões S1–S3.

#### S1–S3 — supersessões formais (autorizadas pelo humano)

- **S1:** cartões da Banca ganham zoom/tilt/mola no hover/foco (cai o veto
  11.5 SÓ ali). Scale sempre UNIFORME (nunca deforma eixo/valor isolado —
  "a geometria relativa dos dados não mente"); ativo ≤1.045, irmãos ≥0.96,
  tilt ≤2.5°, reversível. Mola registrada como **2ª exceção formal de
  spring** (ver §3 abaixo — a 1ª segue `.magnetico`).
- **S2:** brilho/glow autorizado APENAS em 4 set-pieces: box CVM da
  landing, specular do palco/tickers, contorno da constelação, joia da
  marca. **No dark, elevação-base continua = borda**: o brilho dark entra
  por keyline luminosa + specular contido — nunca glow puro — calibrado
  pela cadeia AA com **cláusula de recuo binária** (falhou AA → keyline sem
  glow, nunca itera).
- **S3:** o guard-rail `banca.css:25-27` ("tilt/levitação/scale proibidos")
  é emendado pela própria onda BANCA (dona de `banca.css`) — fora do
  escopo desta folha/Onda.

#### D1–D7 relevantes a tokens (resumo — detalhe completo no plano)

D1 marca CSS-first (zero JS no Header, entrada zero) · D3 palco (scale+dim+
specular claro; keyline+specular escuro; mola `quickTo`) · D4 morph (nome
`cartao-tese` via CSSOM só no clique, limpeza no `finally`) · D5 box CVM
(claro = halo baixíssimo; escuro = keyline ouro + specular contido; opacity
do texto travada em 1) · D6 hairline do rail (fallback JS gateado por
`@supports not`) · D7 tooltips (termo sem definição → fallback silencioso,
zero definição inventada).

#### Tokens novos (`globals.css` :root / dark) — teto + recuo por token

| Token | Claro | Escuro | Papel | Teto / cláusula de recuo |
|---|---|---|---|---|
| `--palco-scale-ativo` | `1.04` | idem | scale do cartão ativo no palco da Banca (S1/D3) | teto S1 ≤1.045. Recuo (perf/AA C12): reduzir a amplitude do tween (→1.02) DEPOIS de zerar `--palco-tilt` |
| `--palco-scale-irmaos` | `0.97` | idem | scale dos cartões irmãos (dim simultâneo) | piso S1 ≥0.96 |
| `--palco-dim` | `0.72` | idem | opacity dos irmãos no hover/focus-within do rail | checado: ink-primary sobre bg-card, ambos diluídos a 0.72 contra bg-page, 7.08:1 claro / 8.03:1 escuro — sem risco de ilegibilidade |
| `--palco-tilt` | `2.5deg` | idem | inclinação do cartão ativo | teto S1 ≤2.5°, reversível. **1º dial a recuar** (→0) se o composto de perf/AA não fechar |
| `--ticker-luz-alfa` | `0.08` | `0.10` | alfa do specular `.ticker-luz` (`--valor-brilho`) sobre cards/masthead/combobox/histórico | teto ≤0.10 nos dois temas (provisório — final na calibração de QA). Recuo: falhou AA → 0.05 (piso de `--luz-foco-card-alfa`) |
| `--cvm-halo-alfa` | `0.08` | *(n/a — dark usa keyline)* | halo `--accent-valor` do Box CVM sobre `--warn-bg` | teto ≤0.08 (S2/D5). Recuo BINÁRIO: falhou AA → keyline sem glow, nunca itera |
| `--cvm-keyline-dark` | *(n/a — claro usa halo)* | `var(--accent-valor)` | keyline 1px do Box CVM no escuro (elevação = borda, S2) | alias de componente; troca de tema já vem de `--accent-valor` |
| `--constelacao-traco-largura` | `1.5px` | idem | espessura do traçado SVG — **sobrevive à demolição da folha `constelacao.css` (D25, missão HORIZONTE)**: `cinema/salao.css` (fio lapidário do Salão) consome o MESMO nome/papel; a folha original morreu, o token não | fixo (geometria, não AA) |
| ~~`--constelacao-contorno-alfa`~~ | ~~`0.10`~~ | ~~*(n/a)*~~ | **REMOVIDO 2026-07-14 (LIMPEZA Onda D/HORIZONTE)** — glow do contorno do painel ativo da constelação (S2); único consumidor era `constelacao.css`, demolida na Onda 2 (D25); grep em `src/` confirmou zero uso residual antes da remoção | dead code — não recriar sem consumidor real |

Cores dos stops da constelação (safira/ink/ouro) e das partes da marca NÃO
ganham token de componente novo — consomem os semânticos existentes direto
(`--accent-confianca`, `--ink-primary`, `--accent-valor`, `--valor-brilho`):
arquitetura de 3 camadas já satisfeita sem camada extra (decisão registrada,
não omissão).

**Convenção `--marca-*` (contrato publicado pela Onda 0):** reservada para
a ilha de inércia CSSOM da Fase 2/opcional da marca (`--marca-lx`/
`--marca-ly`, mesmo padrão neutro-default de `--mx`/`--my`) — **não
declarada em `globals.css` nesta rodada** (é a primeira coisa a cortar se a
missão apertar, per `veredito-marca.md` §3/§5; declarar tokens não
consumidos seria dead code). Se a CHROME adotar a Fase 2, declara os dois
tokens ali, seguindo o mesmo contrato de `--mx`/`--my` (CSSOM, gate
`hover:hover) and (pointer:fine)`, clamp ±1px).

#### Calibração AA — emissores novos (analítica, src-over sRGB gama)

`.maestro/ferramentas/calibra_tokens.py --help` só cobre a recalibração de
`ink-tertiary`/`border-field` contra o pico da luz ambiente (shader do
hero) — **não modela os 2 emissores novos desta missão** (confirmado por
`--help`, sem flags para eles). Script ad-hoc equivalente (mesmo método:
`alpha_composite` src-over em sRGB gama + luminância relativa WCAG),
`scratchpad/calibra_apoteose.py` (anexo ao PR):

```
CENÁRIO 1 — .ticker-luz (--valor-brilho @ --ticker-luz-alfa) sobre bg-card/bg-elevated
  CLARO  bg-card     -> ink-3 7.89:1 · ink-2 7.92:1 · border-field 5.30:1 · ink-1 17.09:1
  CLARO  bg-elevated -> ink-3 8.03:1 · ink-2 8.06:1 · border-field 5.39:1 · ink-1 17.38:1
  ESCURO bg-card     -> ink-3 5.50:1 · ink-2 6.55:1 · border-field 3.74:1 · ink-1 11.33:1
  ESCURO bg-elevated -> ink-3 4.96:1 · ink-2 5.91:1 · border-field 3.37:1 · ink-1 10.22:1  (PIOR CASO)
  Mínimos: texto ≥4.5:1, UI (border-field) ≥3.0:1 — 16/16 PASS.
  Bisecção de margem (escuro/bg-elevated, pior caso): 0.10 passa (4.96) — a reprovação
  real só começa entre 0.12 (ink-3 4.67, border-field 2.98 FALHA) e 0.14 — folga
  confortável dentro do teto ≤0.10.

CENÁRIO 2 — halo do Box CVM (--accent-valor @ --cvm-halo-alfa) sobre --warn-bg (claro)
  CLARO warn-bg -> warn-text 5.54:1 (min 4.5) · warn-border 3.20:1 (min 3.0) — PASS.

CENÁRIO 3 — contorno da constelação (--accent-confianca @ --constelacao-contorno-alfa) sobre bg-card (claro)
  0.08 -> ink-3 7.09:1 · border-field 4.76:1 · ink-2 7.12:1
  0.10 -> ink-3 6.86:1 · border-field 4.61:1 · ink-2 6.89:1  (valor escolhido)
  0.15 -> ink-3 6.31:1 · border-field 4.24:1 · ink-2 6.33:1  (ainda PASS — folga grande)

--cvm-keyline-dark (--accent-valor escuro #d9b354, UI ≥3:1):
  sobre bg-card #16181d -> 8.90:1 · bg-elevated #1d2027 -> 8.17:1 · bg-page #101216 -> 9.40:1
```

Todos os pares novos PASSAM com folga nos valores escolhidos (teto ≤0.10/
≤0.08/≤0.12 respectivamente); nenhuma recalibração de `ink-tertiary`/
`border-field` foi necessária além da já registrada na emenda MATÉRIA VIVA.
**Provisório declarado:** `--ticker-luz-alfa` e o glow da constelação/CVM
são calibração ANALÍTICA (sem screenshot de pico real) — a calibração final
por pixel real (QA) fica dentro dos tetos acima; se algum contexto real
(fonte custom, densidade de conteúdo) reprovar, aplicar a cláusula de recuo
do token correspondente (tabela acima), nunca iterar às cegas.

#### Ordem de `@import` (contrato de cascata, `globals.css`)

Depois das 8 folhas herdadas da missão Imersiva, entram (nesta ordem):
`marca.css`, `palco.css`, `virada.css`, `constelacao.css`, `ticker-luz.css`,
`tooltip.css`, `glossario.css`, `tese-apoteose.css` — **esta última por
ÚLTIMO, depois de `rotas.css` e de todas as outras**, porque a regra de
supressão do véu de chegada do morph
(`html body .virada-edicao.morph-chegada::after { animation:none; content:none; }`,
a escrever pela TESE) precisa vencer a cascata contra a regra irmã do
CORPO do `globals.css` — a especificidade maior já garante isso sozinha,
mas a ordem é reforço deliberado do plano, não uma dependência única.

#### Contratos publicados pela Onda 0 (consumidos pelas ondas de tela)

- Flag `tese-ai:morph-chegada` (sessionStorage, escrita pela BANCA) + classe
  `.morph-chegada` (aplicada pela TESE) + classe `.vt-morph-destino` + nome
  `view-transition-name: cartao-tese` (origem SÓ via CSSOM no clique, com
  limpeza no `finally` — não sombrear `.vt-tese-1..13` cross-document).
- Primitiva `.ticker-luz`/`.ticker-luz::after` (`cinema/ticker-luz.css`,
  conteúdo completo, dona única Onda 0) — BANCA/TESE/CHROME só aplicam a
  classe e garantem `--mx`/`--my` no alvo (delegação já estabelecida por
  `usePonteiro.ts`/`GradeFoco.tsx`); ninguém redefine a primitiva.
- `TermoTooltip.tsx` (`src/components/ui/TermoTooltip.tsx`) + folha
  `cinema/tooltip.css` — componente funcional completo (props `termo`,
  `children`, `definicao?`, `slug?`; WCAG 1.4.13 dismissible/hoverable/
  persistent). COPY é dona só de `lib/glossario.ts`/conteúdo — nunca da
  lógica/CSS do componente.
- Interface pública de `usePonteiro.ts` **CONGELADA** nesta rodada (Onda 0
  não a tocou) — qualquer modo novo (ex.: por-palavra da HERO) deve ser
  ADITIVO/retrocompatível.
- Href/label `/glossario` (COPY cria a rota; CHROME linka no nav).

### Emenda HORIZONTE 2026-07-14 (Onda 0: fundação)

> LEI da missão: `.maestro/plano-horizonte.md` (worktree `wt-horizonte`) —
> §0 vetos, §1 supersessões, §3 spec por critério, §4 ondas, **§5 emendas do
> red-team E1–E30 (PREVALECEM sobre a direção e sobre este resumo)**, §6
> não-regredir — e `.maestro/direcao-horizonte.md` (D1–D40, a direção de
> arte, §12 tabela de tokens). Este bloco registra o que a Onda 0 (Fundação)
> publica: as 4 emendas de governança decretadas ANTES da 1ª linha de
> código (D2), o sistema full-bleed **A Bancada** (D3), os tokens novos e o
> clamp/colisão de tooltip (D34/E13).

#### Emendas de governança decretadas (D2 — obrigatórias antes da 1ª onda)

- **S4 — set-pieces de glow, de 4 para 8** (estende S2/Apoteose): somam-se
  (5) `.gema-chip` da Prova Viva, (6) bolhas-bancada do Salão, (7) fio
  lapidário + faísca, (8) pedestais da vitrine. Cada um com teto próprio
  (tabela de tokens abaixo) e **recuo BINÁRIO**: reprovou AA por pixel →
  keyline sem specular, nunca itera às cegas. Doutrina dark intacta:
  elevação-base continua = borda/keyline (nunca glow puro no escuro).
- **S5 — a superfície opaca de palco** *(era HORIZONTE — "veludo" ameixa ~285°; re-materializada como família `--camara-*` tinta-de-safira ~221° e renomeada na OURIVESARIA, raia 1B)*: a ameixa (~285°, fora do hue
  banido 70–200°) deixa de ser keyline decorativa e vira **superfície
  OPACA** (`--veludo-fundo`), exclusiva de DUAS faixas da landing (vitrine
  + salão) e do aside de método do `/sobre`. NÃO é acento: nenhum
  controle/estado/dado usa veludo como cor de significado; a brasa segue o
  único acento; `bg-realce` segue exclusivo de citação. **Recuo binário
  registrado**: se o dono rejeitar o veludo no wow-gate, salão e vitrine
  re-skinam sobre `--bg-page` com vinheta fria — a mecânica (grid/deriva/
  pin/fio) sobrevive inteira; nenhuma onda pode acoplar lógica ao valor de
  `--veludo-fundo`.
- **M3-b — re-escopo da trava M3 para superfícies com bisel**: a exigência
  "100% dos pixels do chip idênticos ao token puro" (trava M3, Bazley)
  passa a valer só para o **campo interno de texto** (onde número/citação/
  fonte moram) das superfícies com bisel (`.gema-chip`, placas gravadas);
  as arestas de 1px do bisel (`--gema-aresta` luz / `--gema-quilha`
  sombra) ficam FORA da área aferida e são provadas separadamente como
  decorativas. A trava plena (token puro em 100%) segue valendo onde não
  há bisel.
- **Contrato de altura — DUAS constantes** (`--altura-tarja` E
  `--altura-header`; **E1 do red-team substitui o `.dobra-capa` único de
  D9**): cada var documenta a altura que o componente JÁ TEM, sem alterar
  nenhuma propriedade computada da Tarja/Header (nada de "fixar"
  padding/line-height para caber no número escolhido). **Por que duas e
  não uma**: um wrapper único envolvendo Header+hero (a ideia original D9)
  puxaria o `<header>` para dentro do `<main>` — e `<header>` descendente
  de `<main>` perde o role `banner` implícito (regressão de landmark) — ou
  tiraria o `#hero` de dentro do `<main>`, quebrando o skip-link. A
  correção (E1) é: **zero wrapper novo**; Header e `<main>` ficam
  exatamente onde já estão; a capa vira uma regra de altura no PRÓPRIO
  `#hero` (`min-block-size: calc(100svh - var(--altura-tarja) -
  var(--altura-header))`, escrita por `cinema/hero.css`, dona: Onda 1D).
  **Gate (E4, estende o §1 original "5 breakpoints" da emenda APOTEOSE)**:
  **varredura contínua 320→1920px (passo ≤16px) + zoom de texto 200% +
  text-spacing**, comparando `offsetHeight` real × var, para os DOIS
  componentes; se divergir, um escritor CSSOM único (fora do caminho
  crítico: `resize` + `fonts.ready`, rAF-coalescido) corrige a var — o
  valor estático permanece como default de first-paint (**CLS zero**);
  todo consumidor usa `min-*`, nunca altura exata. Essa varredura completa
  é execução de uma onda de QA/integração posterior — a Onda 0 só publica
  o contrato e os valores de partida (tabela abaixo), ancorados nos
  breakpoints reais de wrap de cada componente: Tarja (conteúdo textual
  quebra a ~640/1024px, valores do §12 da direção) e Header (nav
  mobile↔desktop no `md`=768px — **estimativa de Onda 0**, lida em
  `Header.tsx`/`Tarja.tsx`, sujeita à correção fina da varredura E4 numa
  onda posterior).

#### Sistema full-bleed oficial — "A Bancada" (D3, mata a linha imaginária)

Folha nova `src/styles/cinema/bancada.css` (dona única desta missão: a
Onda 0 cria o grid/fios/capa; nenhuma outra onda edita esta folha).
Content-grid de colunas nomeadas em que a **medida (≤68ch) é o DEFAULT** e
o **palco é opt-in** (o grid de 12 colunas alternativo foi rejeitado pelo
conselho — D3): `.bancada > * { grid-column: medida }` torna impossível
esticar prosa por acidente; `.b-palco`/`.b-sangria`/`.b-vazante-esq`/
`.b-vazante-dir`/`.b-medida-esq`/`.b-medida-dir` são os opt-ins de
largura. Variantes `.bancada--display` (`--medida: 88rem`, títulos/cenas)
e `.bancada--densa` (`--medida: 76ch`, fichas) — prosa NUNCA sai de ≤68ch
por fora dessas variantes deliberadas. Aninhável (um `.bancada` dentro de
um `.b-sangria` recria as colunas dentro de um palco de veludo), RTL-safe,
CLS-safe (first-paint puro, zero medição JS).

**`--sangria`/`--medida`/`--palco-max` vivem em `globals.css` (:root), não
redeclarados dentro de `.bancada`** — decisão desta Onda 0 (a direção
mostra esses três como declaração local no bloco ilustrativo do §2, mas
`cinema/tooltip.css`/D34 também consome `var(--sangria)` fora de qualquer
`.bancada` ancestral garantido; centralizar como token global evita
depender de herança por posição no DOM). `bancada.css` só CONSOME os três.

**E3 (red-team) — `vw` PROIBIDO em largura de palco**: `100vw` inclui a
barra de rolagem clássica do Windows (~15px) no Chrome/Firefox — overflow-x
global permanente (viola §0.10 do plano) e largura errada de pin-spacer.
Toda largura de palco/sangria usa **`inline-size`/colunas do grid**, nunca
`vw`. Regra vale para TODA a missão, não só para o Salão (onde o PoC do
pin full-viewport valida com
`document.scrollingElement.scrollWidth === clientWidth`).

**Chrome FORA da migração** (D4): Header/Footer/Tarja mantêm `max-w-6xl`
interno intacto — a lei do container morre só nas SEÇÕES das páginas,
nunca no chrome global.

**Assinatura de seção — `.fio-travessa`** (D6): hairline
`border-line-strong` de sangria a sangria abrindo cada seção, combinado
com a classe `.reveal-regua` já existente (`globals.css`, scaleX 0→1) —
nenhum mecanismo de animação novo, só a geometria full-bleed. Ritmo de
capítulos da landing (D6): papel-claro (capa) → papel (prova) → papel
(nascimento) → **veludo** (vitrine) → **veludo escurecendo** (salão) →
papel (contrato).

**Vocabulário da CAPA** (D10, em `bancada.css`): `.capa-orelha` (mono,
texto verbatim CVM à esquerda / edição+fontes à direita, ancoradas via
`.b-vazante-esq`/`.b-vazante-dir`), `.capa-cartola` (Archivo caps
condensada), `.capa-linha-fina` (2 colunas ≤34ch cada com fio de goteira
central; 1 coluna no mobile), `.capa-vinco` (rótulo mono do limite da
dobra), `.fio-de-prumo` (hairline 1px que se desenha com o scroll,
`animation-timeline: scroll(root block)`, `animation-range: 0 120svh` —
mesmo PADRÃO de `marca-fio-recolhe` de `cinema/marca.css`, mas com
keyframe PRÓPRIO desta folha; reusa o token `--fio-lapidario`, mesmo
motivo estético do fio do Salão). **E1: não existe `.dobra-capa`** — a
altura da capa vive numa regra do próprio `#hero` (`hero.css`, dona: Onda
1D); esta folha só declara o vocabulário estático. Reduced-motion:
`.fio-de-prumo` é "**progress**" (isento, mesma doutrina de
`.regua-leitura`/`aurora-drift`); nenhum outro efeito novo desta folha é
decorativo-animado (a régua usa `.reveal-regua` global, já coberta pelo
bloco de redução existente).

#### Tokens novos (`globals.css` :root / dark) — teto + recuo por token

| Token | Claro | Escuro | Papel | Teto / recuo |
|---|---|---|---|---|
| `--text-capa` (em `@theme inline`, gera `text-capa`) | `min(clamp(3rem, 9.5vw, 8rem), 13svh)` | idem | manchete de capa (E11: teto svh evita estouro em 1366×768) | recuo LCP: 8rem→7rem só se o gate de fold (E2E 1366×768/1280×720) reprovar |
| `--altura-tarja` | `2.75rem` (≥1024px) / `4rem` (640–1023px) / `5.25rem` (<640px) | idem | contrato de altura da Tarja | declarada sem tocar computado; gate E4 (sweep 320–1920+zoom+text-spacing) |
| `--altura-header` | `4.5rem` (≥768px) / `5.5rem` (<768px) | idem | contrato de altura do Header (E1) — **estimativa Onda 0** | mesmo gate E4 |
| `--sangria` | `1rem` (≥640px: `1.5rem`) | idem | respiro mínimo de borda da Bancada | fixo (geometria) |
| `--medida` / `--palco-max` | `68ch` / `96rem` | idem | colunas da Bancada | ≤68ch é lei (D3) |
| `--veludo-fundo` *(era HORIZONTE — família renomeada `--camara-*` e re-materializada na OURIVESARIA; ver emenda abaixo)* | `#241e2b` | `#16121c` | superfície do salão/vitrine (S5, hue ~285°) | superfície opaca, nunca wash; recuo S5: re-skin `--bg-page` |
| `--veludo-tinta` | `#efe9e4` | `#e9e5df` | tinta primária sobre veludo | ≥12:1 (verificado ~13,5:1) |
| `--veludo-tinta-2` | `#beb3c6` | `#b3a9bc` | metadados/legendas/controles sobre veludo | ≥4.5:1 texto / ≥3:1 UI no pico real; recuo: clarear lightness |
| `--veludo-anel` | `var(--valor-brilho)` | idem | `:focus-visible` DENTRO do escopo veludo (E15) — `--accent-text` global dá ~2,39:1 ali | ≥3:1 (estimado ~11:1) |
| `--veludo-vinheta-alfa` | `0.35` | `0.45` | vinheta radial das faixas (anel, centro limpo) | decorativa; nunca sob texto |
| `--gema-aresta` | `var(--valor-brilho)` | idem | aresta de luz do bisel (1px topo/esquerda) | alias; fora do campo de texto (M3-b) |
| `--gema-quilha` | `rgb(90 49 83 / 0.28)` | `rgb(0 0 0 / 0.45)` | aresta de sombra do bisel (1px baixo/direita) | ≤0.30/0.50; recuo: keyline simples |
| `--gema-elevacao` | `0 2px 6px rgb(42 54 84/.16), 0 14px 32px rgb(42 54 84/.10)` | `none` (keyline) | sombra de peso de chip/placa no claro | S2/S4: dark = borda; recuo binário |
| `--fio-lapidario` | `var(--accent-valor)` | idem | traço do fio (salão + fio de prumo da capa) | alias; decorativo |
| `--fio-faisca` | `var(--valor-brilho)` | idem | faísca na frente de corte (dasharray 0.02 1) | decorativa; `display:none` sob reduce |
| `--bolha-specular-alfa` | `0.10` | `0.10` | calota specular da bolha-bancada (S4) | teto de partida 0.10 (0.12 só com pixel-prova); recuo binário → keyline |
| `--deriva-vel` | `12` (px/s; mobile <640px: `8`) | idem | cruzeiro da vitrine (lido 1× por `getComputedStyle`) | ≤16; recuo perf: update 30fps; reduce = nem monta |

Mecanismo **escopo-câmara** (D20/E5/E6 — não é token, é contrato; nome da
era HORIZONTE: *escopo-veludo*): `.vitrine-camara`/`.salao-fundo` re-declaram
localmente **PARES COMPLETOS** de semânticos (superfície+tinta+on-accent:
`--bg-card`/`--bg-elevated`, `--ink-primary/-2/-3`, `--text-sobre-brasa`,
`--border-line/-strong`, anel) — nunca meio-par (E5: um `bg-card` claro
herdando `ink-primary` do tema errado é quase-branco sobre branco). O ramo
de elevação (sombra fria claro / keyline dark) é forçado por **CLASSE**
(`.camara-escopo`), nunca por `@media (prefers-color-scheme)` (E6). Todos
os pares entram na re-enumeração AA por pixel (Onda 4). Zero hex de
conteúdo/tinta/brasa existente muda; zero hue novo em 70–200°.

#### Tooltip — clamp de largura (D34) + colisão horizontal (E13)

`cinema/tooltip.css` ganha a regra ÚNICA de clamp (D34, vale para TODOS os
palcos novos): `.tt-popup { max-inline-size: min(20rem, calc(100vw - 2 *
var(--sangria))) }` — como `max-inline-size` mapeia para a mesma
propriedade física de `max-width` (CSS Logical Properties, cascade por
propriedade correspondente), esta regra da folha cinema (importada depois
de `@import "tailwindcss"`) prevalece sobre o `max-w-[...]` arbitrário
aplicado hoje via className em `TermoTooltip.tsx`, sem precisar de
`!important` — mesma doutrina de cascade já registrada acima ("folhas
cinema... em especificidade igual, quem vem depois no arquivo vence").

**E13 — o clamp limita LARGURA, não POSIÇÃO**: a bolha do Salão que "espia
pela borda" (design deliberado) pode abrir um popup que ainda estoura o
viewport horizontalmente mesmo com a largura clampada, e o wrapper
`.salao-pinado { overflow-x: clip }` cortaria a sobra. `TermoTooltip.tsx`
ganha colisão horizontal ADITIVA (contrato D7 continua intacto: definição
só de `lib/glossario.ts`/`o_que_mede`): ao abrir, mede
`getBoundingClientRect()` do popup e escreve `--tt-dx` (px de correção)
via `popup.style.setProperty` — **zero `style=` inline, zero
`setAttribute('style')`** (mesmo carve-out CSSOM já documentado acima).
`tooltip.css` passa a consumir `left: calc(50% + var(--tt-dx, 0px))` no
lugar de `left: 50%` fixo — o `transform: translate(-50%, …)` das
keyframes de entrada segue intocado (só o ANCORAMENTO horizontal muda, não
a centralização relativa a ele). QA da Onda 4 prova por pixels que 100% do
popup fica visível nos dois lados (pior caso: bolha da borda do salão).

### Registro de fechamento — missão HORIZONTE (Onda D, 2026-07-14)

> Consolidação final (a próxima missão lê isto ANTES de tocar em Bancada,
> veludo, salão ou capa). Fonte primária dos números: gates rodados na Onda
> 4 (`.maestro/defeitos-onda4.md`, `.maestro/evidencias/aa/aa_tabela_horizonte.md`,
> `.maestro/evidencias/perf/css_bytes.json`).

**A Bancada — sistema de layout oficial, com a armadilha que custou caro.**
`grid-column: medida` (forma curta de um único nome) **NÃO** resolve para o
par de linhas `[medida-inicio] … [medida-fim]`: o atalho de um nome só vira
range quando as linhas terminam literalmente em `-start`/`-end` (regra do
próprio spec de CSS Grid, que gera esses nomes a partir de uma
`grid-area`). Como os nomes de linha da casa são em português
(`-inicio`/`-fim`, não `-start`/`-end`), a forma curta cai em
**auto-placement** e o item é espremido numa faixa estreita na borda — o
full-bleed inteiro (a correção-mãe da missão) ficou **inerte** até isso ser
achado. **Regra permanente: sempre `X-inicio / X-fim` por extenso**, nunca o
atalho de um nome, em qualquer novo opt-in de coluna que a Bancada ganhar.
Ver o comentário-prova em `cinema/bancada.css` (linhas 64–72).

**A segunda armadilha — `gap-N` do Tailwind num nó `.bancada`.** Um
`className="bancada gap-4"` (ou qualquer `gap-N` sem sufixo de eixo) aplica
`column-gap`, que **soma-se** às larguras já calculadas das trilhas
nomeadas do grid (`sangria`/`palco`/`medida`) — a soma das trilhas deixa de
bater com `100%` e o documento ganha **overflow-x real** (achado como
bloqueante B3 em `not-found.tsx`/`error.tsx`: `column-gap: 20px` num
`main#conteudo.bancada`). **Regra permanente: `gap-y-N`, nunca `gap-N` puro,
em qualquer nó que tenha a classe `.bancada`** — o espaçamento entre linhas
de conteúdo empilhado não precisa (e não pode) de gap horizontal, porque as
colunas já são geometria do grid, não espaçamento de flex/gap.

**Os contratos de altura (`--altura-tarja`/`--altura-header`).** Os degraus
vivem em `globals.css` (`@media (min-width: 400/768/880/944px)`) —
ancorados nos **platôs REAIS de wrap** de cada componente, medidos por
varredura contínua (gate E4: a 1ª estimativa em breakpoints do Tailwind
reprovou 202/202 medições; a Tarja quebra de linha em ~400px e de novo em
~880px, o Header tem um platô anômalo de ~137px entre 768–943px — nenhum
desses pontos é um breakpoint padrão do Tailwind). A ilha `MedidaCromo.tsx`
(`src/components/motion/MedidaCromo.tsx`) é o **backstop CSSOM**: mede
`getBoundingClientRect().height` da Tarja/Header real via `ResizeObserver` +
`fonts.ready` (a fonte com `display:swap` muda a altura DEPOIS do 1º paint)
e só reescreve a var quando o valor diverge ≥0,5px — sob zoom de texto 200%
(1.4.4) e text-spacing (1.4.12), onde os platôs mudam de forma não-linear
(divergência medida de até +180px na 1ª estimativa). **O default estático é
quem é dono do first-paint**: no caso comum (zoom 100%, espaçamento padrão)
a ilha reescreve o MESMO valor que já estava lá — nenhum shift, **CLS
zero** (pós-fix: 303/303 medições com delta 0,0px). `MedidaCromo` NUNCA
altera uma propriedade computada da Tarja/Header — só mede e publica.

**A exceção 2.2.2 da vitrine** — a única animação contínua do site (D21,
`useVitrineDeriva.ts` + `GaleriaBanca.tsx`): deriva por scroll real
(`rail.scrollLeft`), pêndulo com rampas, pausa por interação, gates de
`IntersectionObserver`+`visibilitychange`+`prefers-reduced-motion`. O
controle on-page mora em `GaleriaBanca.tsx`: botão ≥44px com **rótulo FIXO
"Movimento da vitrine"** (nunca troca — só `aria-pressed` porta o estado; um
rótulo que trocasse JUNTO com `aria-pressed` faria o leitor de tela anunciar
algo como "Girar vitrine, pressionado", um anti-padrão) + `role="status"`
sr-only que anuncia **só** mudança iniciada pelo usuário (clique/tecla,
nunca por scroll/gesto) + persistência em
`localStorage("tese-ai:vitrine-pausada")`, lida de forma síncrona (E16,
antes do 1º rAF da deriva) em `useLayoutEffect` — nunca durante o 1º render
(bloqueante B1 corrigido: ler `localStorage` no render diverge o HTML do
servidor do cliente e quebra a hidratação; a leitura correta acontece
depois do render inicial, sempre servidor-primeiro).

**O escopo-câmara (`.camara-escopo`; nome da era HORIZONTE:
`.veludo-escopo`)** — re-declaração de **pares
completos** (superfície+tinta+on-accent: `--bg-card`/`--bg-elevated`,
`--ink-primary/-2/-3`, `--text-sobre-brasa`, `--border-line/-strong`, anel),
nunca meio-par. Por quê: re-declarar só a tinta (sem a superfície-par) deixa
a cascata descer até sub-superfícies opacas internas com o tema ERRADO —
ex.: um `bg-card` claro herdando `--ink-primary` do tema escuro vira
quase-branco sobre branco (texto invisível). O ramo de elevação (sombra fria
no claro / keyline ouro no escuro) é forçado **por CLASSE**
(`.camara-escopo`), nunca por `@media (prefers-color-scheme)`: a media query
pergunta "qual é o tema do SISTEMA operacional", não "este elemento está
sobre veludo" — no tema CLARO sobre um veludo (superfície opaca ~285°,
sempre escura) o ramo por media query aplicaria o tratamento de elevação do
claro (sombra fria) num fundo que precisa do tratamento do escuro (keyline),
errando o lado exatamente na combinação onde o defeito é mais visível
(bloqueante B2 confirmado: o dot da Banca ficava a 1,03:1 dentro do veludo
porque usava `--bg-card` — cor de SUPERFÍCIE — como preenchimento; corrigido
para `--veludo-tinta-2`/`--veludo-tinta`/`--accent-valor`, ≥3:1 provado por
pixel).

**Tokens novos (veludo/gema/fio/bolha/deriva/capa)** — tabela completa com
teto e recuo binário por token na seção "Tokens novos (`globals.css` :root
/ dark)" logo acima desta nota. **Resultado do AA re-enumerado (Onda 4,
`aa_tabela_horizonte.md`): 110 PASSOU · 0 FALHOU** (mais 8 pares pendentes
de integração e 28 informativos — decorativos/specular, fora do gate por
construção) — nos dois temas, incluindo os pares herdados da Banca no
veludo, `--veludo-anel`, o campo interno das gemas, bolha, fio/faísca, a
capa sob o `uMask` re-medido e a pedra do 404.

**`--bolha-dy-1..5` precisa ser px puro** (contrato entre `salao.css` e
`SalaoDimensoes.tsx`): o valor computado de uma custom property é o TOKEN
em si, não um comprimento resolvido — `getComputedStyle(li).getPropertyValue
("--bolha-dy")` devolveria a STRING `"min(8vh, 80px)"` (não um número em px)
se o token usasse `min()`/`clamp()`/`vh`. O `translate` do `<li>` consome a
var e o JS lê a MESMA var para compor o centro do círculo publicado
(`cy = offsetTop + offsetHeight/2 + dy`, E2) — trocar por uma unidade
relativa quebraria essa leitura **em silêncio** (sem erro de build, sem
warning: o JS receberia uma string não-numérica, o cálculo do centro do
círculo ficaria `NaN` ou usaria um fallback errado, e a catenária do fio
cortaria por dentro da bolha — exatamente o defeito que a demolição do
filmstrip/constelação tentou resolver). Variações por viewport vêm SEMPRE de
`@media`, nunca de fórmulas dentro do próprio valor do token (ver
`cinema/salao.css`, linhas 25–36 e 126–130/470–474).

**Limpeza de CSS desta Onda (arbitragem A2 do maestro):** o CSS compilado
cresceu +5,18KB gzip contra o teto de +4KB do gate E23 — o teto era um
PROXY do medo de degradar o LCP de /tese; a medição real mostrou o
**LCP de /tese MELHORANDO** (a Onda 4 mediu 120→104ms) com CLS 0 nos dois
lados. **Decisão: o delta é ACEITO e documentado**, com duas limpezas de
risco zero: (a) remoção do token órfão `--constelacao-contorno-alfa` (ver
tabela de tokens da emenda APOTEOSE acima — a folha `constelacao.css` que o
consumia foi demolida; `--constelacao-traco-largura` sobrevive porque
`salao.css` o consome de verdade); (b) deduplicação de `cinema/palco.css`
entre `.banca-rail .cartao-ticker`/`.grade-teses .cartao-ticker` (seletores
combinados onde os valores eram byte-idênticos — `:focus-visible`,
recuo/dim dos irmãos, keyline do dark-mode, bloco `reduced-motion`; a
`transition` da regra base permanece deliberadamente separada porque a
grade soma uma transição de `transform` que a Banca não tem — somá-la à
Banca mudaria a física da mola JS do `usePalco`/`quickTo`). Novo delta
medido após a limpeza: ver `.maestro/evidencias/perf/css_bytes.json`
(re-executar `gate_css_bytes.py` reporta o número corrente). Follow-up NÃO
executado nesta limpeza (fica registrado para a próxima missão, se o
orçamento apertar de novo): escopar `salao.css`/`lapidacao.css` (~+2,3KB)
para fora das rotas que não os usam via CSS Modules/route-level import, em
vez do `@import` global único que hoje entra em toda rota via
`globals.css`.

---

### Emenda OURIVESARIA 2026-07-16 (Onda 0.5 — CONGELAMENTO de tokens)

> LEI da missão: `.maestro/plano-ourivesaria.md` (o §7 prevalece). Vereditos
> dos protótipos da Onda 0: **0.2 gráficos PASSOU_COM_RECUO · 0.3
> câmara/lábio PASSOU · 0.4 fio PASSOU · 0.6 geometria PASSOU**. Depois
> desta emenda **ninguém toca `globals.css`** (lei herdada; carve-outs
> §7-E3: nenhum além dos já aplicados aqui). Lista FECHADA de tokens novos
> = §7-E10 — token fora dela é ESCALAR ao maestro, nunca valor arbitrário.

#### Tokens congelados (`globals.css` :root / dark) — teto + recuo por token

| Token | Claro | Escuro | Papel | Teto / recuo |
|---|---|---|---|---|
| `--grafico-4` | `#8c1f27` (E-A1, ~356°) | `#d97687` (~349,7°) | granada — série quaternária (histograma negativo) | Claro: congelado (candidato E-A1). Escuro: **RECUO §7-C4 ACIONADO** pelo eixo L/S pré-aprovado (achado 24): `#f0949b` (ΔE76 9,0 vs `--error-text` `#f2938a`) e `#e78798` REPROVADOS na distância do erro-*; `#d97687` = ΔE76 16,2/19,8 vs erro-* e CVD ≥12,4 em todos os pares; regra "proibido 358–2° sem passar erro-*" respeitada; re-provado por pixel |
| `--grafico-5` | `#46628c` | `#a3b5cc` | aço-safira ~216° — faixa de Bollinger / 5ª série | Recuo 222° (`#5a7bab`/`#b9c6d9`) **NÃO acionado**; prova de franja contra a janela do verde ok (drift medido para baixo) |
| `--luz-penumbra` | `26 38 66` · α `0.03` | `104 122 156` · α `0.04` | anel externo da luminária COLAPSADO na safira ~221° (um só eixo de temperatura) | Alfas/geometria/tempos INTOCADOS; recuo pré-aprovado do passo 0.7 (escada −8 de L no triplet escuro) reservado à varredura verde `capa_escuro` |
| `--moldura-tinta` | `#2d3f66` | `#8ea3c7` | keyline 1px de molduras editoriais (pull-quotes, borda do masthead) — decorativo, nunca texto/estado; ~221° | Rename ATÔMICO feito nesta 0.5 (achado 39): `@theme` + `como-funciona/page.tsx` + `tese-apoteose.css` no mesmo passe; grep-zero pelo nome antigo em `src/` |
| família **câmara** — `--camara-fundo` / `--camara-tinta` / `--camara-tinta-2` / `--camara-anel` / `--camara-vinheta-alfa` (rename atômico **FEITO** pela raia 1B, 2026-07-17, §7-E1 fase serial; classes `.camara-escopo` / `.vitrine-camara`) | fundo `#1b2334` · tinta `#efe9e4` · tinta-2 `#aebacf` · anel `var(--valor-brilho)` · vinheta-α `0.35` | fundo `#131a26` · tinta `#e9e5df` · tinta-2 `#a9b6cb` · anel idem · vinheta-α `0.45` | superfície de palco tinta-de-safira (câmara = pedra: S≤33/L≤15,5; nunca confundir com `--accent-confianca` = voz) | VALORES congelados (protótipo 0.3: recuo "escurecer câmara" **NÃO acionado** — nenhum hex novo); recuo S5 herdado (re-skin `--bg-page`) segue registrado |
| `--gema-quilha` (claro) | `rgb(42 54 84 / 0.28)` | `rgb(0 0 0 / 0.45)` (intocado) | aresta de sombra do bisel — família sombra-fria | teto ≤0.30; recuo: keyline simples |
| `--labio-alfa` | `0.5` | `0.5` | dial do lábio de ouro — CONTRATO da fronteira REAL de material no dark (§7-C3) | **0.50 = primeiro degrau da escada pré-aprovada 0.35→0.50→0.60 que fecha ≥3:1 POR PIXEL nos dois lados, nas 2 bordas** ("fronteira dark lê com lábio 0.50"). Teto 0.60 (headroom medido 4,04/4,09 — disponível se a raia 1B quiser margem); recuo binário 1px sólido `var(--accent-valor)` medido 9,08/9,18 — registrado, **NÃO acionado**. Tema claro: lábio DECORATIVO (sem exigência 3:1) — fronteira assinada pelo par papel×câmara 15,27:1 (§7-C3a) |
| `--ritmo-assento` / `--ritmo-bloco` / `--ritmo-respiro` / `--ritmo-capitulo` / `--ritmo-pos-fio` | `1.5rem` / `3rem` / `6rem` / `3.5rem` / `1.5rem` | idem | escala única de ritmo (C2): título→conteúdo · blocos irmãos · seções de mesmo fundo (substitui hairline) · padding por lado da fronteira de material · vão único pós-fio | `gate_ritmo.py`: vão ∈ {0.75, 1.5, 3, 6}rem ±1px OU exceção da lista FECHADA (`ritmo-excecoes.json`) |
| `--text-body-lg` | `1.0625rem` (17px) | idem | degrau tipográfico novo — uso EXCLUSIVO bolha/letreiro (achado 41) | Deliberadamente FORA do `@theme`: não gera utilitário Tailwind — a exclusividade é estrutural (consumo só por `var()` nas folhas donas) |
| `--salao-repouso` | `2rem` | idem | pouso da bolha da vez (§7-A1 decompõe entrada≠repouso) | Snap na forma implementável (protótipo 0.6): `ponto_i = (offset_i − REPOUSO_PX)/distancia` com `REPOUSO_PX = 32` CONSTANTE no TSX — `getComputedStyle` devolve a string `'2rem'`, nunca px (pegadinha 5) |
| `--deriva-vel` | `14` (mobile <640px: `10`) | idem | cruzeiro da vitrine (C5; carve-out §7-E3 — 1E só consome) | teto ≤16 |
| *locais nas folhas donas (registro §7-E10)* | — | — | `--ease-assento`, `--nasc-lume` (default `1`), `--bolha-*` nas folhas donas; `--salao-recuo` em `salao.css` | `--salao-recuo: calc(100% − var(--bolha-largura) − var(--salao-gap))` CONGELADA pelo 0.6, mas o CONSUMO muda na 1D (ver nota geometria abaixo) |

#### Aposentadoria da família *ameixa* — racional (adendo científico C10)

O site colapsa em **um só eixo de temperatura** (pedra fria ~221° × luz de
ouro): a penumbra ~310° e a moldura ~318° eram os últimos violetas vivos do
sistema e morrem aqui (janela banida canônica **[250°, 345°]**; croma piso 8
na prova por token, 12 por pixel). Lastros admitidos: **Reber 2004**
(fluência de processamento — coerência de um eixo), **Labrecque & Milne
2012** (sofisticação comunicada via LUMINÂNCIA, não via matiz violeta),
**Bazley 2021** (vermelho só em série negativa — `--grafico-4` granada),
**Cyr 2010** (azul-confiança SÓ no papel do acento `--accent-confianca`,
nunca alegado para superfície). **PROIBIDO** citar Mehta & Zhu 2009
(excluído pelo brief por falha de replicação). Mapa do rename: 
`--moldura-ameixa` → `--moldura-tinta` (FEITO nesta 0.5, atômico);
`--veludo-*` → `--camara-*` e `.veludo-escopo` → `.camara-escopo` /
`.vitrine-veludo` → `.vitrine-camara` (**FEITO pela raia 1B, 2026-07-17**:
commit único + grep-zero funcional e nominal em `src/` e
`.maestro/ferramentas/` + harness sincronizado §7-C9 — gate1_virada,
fps_deriva, gate_ritmo, prova_tokens, medir_aa, prototipo_04).

#### Nota C6 — os 12 hexes do escopo dark são BYTE-IDÊNTICOS

Os 12 hexes copiados do bloco dark de `globals.css` para o escopo da câmara
(`vitrine.css`) ficam **byte-idênticos** — nenhum é roxo; a frase
"REVISADOS" do C8 do plano está SOBREPOSTA pelo §7-C6. Gate: diff mecânico
contra o bloco dark de `globals.css` = zero (pós-condição da raia 1B).

#### Nota E-C3 — `lapidacao.css` PERMANECE GLOBAL

Racional gravado: a pedra do 404/`error.tsx` (boundary EAGER no Next 16 —
Pegadinha 3 da Apoteose) depende de classes já pagas no CSS global; escopar
a folha quebraria o 404 sem round-trip. Toda regra NOVA do nascimento que
não seja compartilhada com /como-funciona/404 tenta folha escopada primeiro.
**`.pedra-404`** (classe + keyframe `pedra-404-desenho` 900ms one-shot +
registro reduce nominal) nasceu nesta 0.5 em `lapidacao.css` com **dona
nomeada** (achado 40): 2C e 2D são CONSUMIDORAS — a licença de substituição
de elemento da 2C NÃO cobre remover/renomear a classe compartilhada.

#### Redundância de marca dos gráficos (registro do protótipo 0.2)

Distinguibilidade **5×2 e 5×6 no escuro** e **4×1/4×`err-text`** assegurada
por REDUNDÂNCIA de tipo de marca, não só por cor: Bollinger = banda com
fill 15% + legenda TRACEJADA vs linha SÓLIDA das séries vs referência
tracejada 4-4 (`--grafico-6`); histograma negativo assinado pela LINHA DO
ZERO. Política de franja §7-C1 validada inteira: falha só cluster ≥2×2;
100% das violações residuais classificáveis como franja AA de cruzamento
laranja×índigo (~269–273°) e granada×índigo (~331–344°). O selo da prova
por pixel EXIGE a máscara de decorativos `aria-hidden` (pegadinha herdada
reconfirmada: sem ela o ◈ ouro vira falso pior-pixel `[123,91,23]`).

#### Registro do protótipo 0.3 — bônus B3

O par `--ink-primary`/`--ink-tertiary` sobre `bg-card` está APTO para o
esmaecimento por TROCA DE COR das legendas do nascimento (§7-B3): 7,11:1 no
pior tema (≥4,5:1) — mecanismo primário confirmado, opacity fica 1 sempre.

#### Registro do protótipo 0.4 — fio sobre a câmara

`--fio-lapidario` PERMANECE `var(--accent-valor)` e o `color-mix` de
`salao.css:92` permanece **78%** — congelados como estão. Recuos
pré-aprovados (clarear fio no escopo do salão / ajustar % do color-mix)
registrados e **NÃO usados**. Gate decidido pela leitura honesta (corte
75% + erosão + máscara de bolhas/HUD); método do baseline reportado junto
só para comparabilidade com o 3,35 herdado. Achado encaminhado à raia 1D
(fora do escopo de recuo do 0.4): traço da talha inativa ~3,0 —
pré-existente e melhorado pela câmara; sugestão de 1 linha: `opacity`
.5→.55 no `.salao-talha__traco` inativo.

#### Registro do protótipo 0.6 — geometria do Salão (VINCULANTE à raia 1D)

Fórmula do recuo CONGELADA (token §7-A1 mantido) mas o CONSUMO muda:
`.salao-pinado .salao-trilho { padding-inline-start: 0 }` e `.salao-pinado
.salao-trilho > li:nth-child(1) { margin-inline-start: var(--salao-recuo) }`.
Espaçador CONGELADO: `.salao-pinado .salao-espaco { inline-size: max(1px,
calc(100% − var(--bolha-largura) − var(--salao-gap) − var(--salao-repouso)))
}` — `block-size` 1px mantido (pegadinha 6). **RECUO ACIONADO sobre a
fórmula literal da emenda** (achado 1c/§7-A2 com base 100%): degenera por
construção — PROIBIDO espaçador em 100% com recuo no padding do trilho.
Alternativa 100vw+padding registrada como recuo binário (só com overlay
scrollbar garantida; fura §7-A3(iv) e p5 ≥0.995 com scrollbar clássica).
Achado 18/§7-RT2.2 é no-op neste worktree (`padding-inline: 0` do palco
pinado já existe em `salao.css:377`); mantida como GATE a asserção de
entrada `b2.gBCR.left ≥ documentElement.clientWidth` (clientWidth, não
innerWidth). Notas: **0 deixa de ser ponto de snap** (p1
viewport-dependente 0,153–0,363; re-prova E10 entrada/saída obrigatória);
comentários `salao.css:398-423` e `SalaoDimensoes.tsx:558-561` ficam FALSOS
— a 1D atualiza; fórmulas paramétricas: re-medir com 26rem/17rem na raia.

#### `calibra_tokens.py` emendado (§7-C7, achados 14/29) — resultado da 0.5

Emenda aplicada com rito S3 (cabeçalho com data/motivo): (1) penumbra =
triplets safira novos; (2) `ink_tertiary_atual`/`border_field_atual`
re-sincronizados com o `globals.css` VIGENTE (`#4c4f56`/`#6a6963` ·
`#a5a49e`/`#7e8691` — os hexes antigos do script eram os da 1ª passada,
defasados); (3) conferência automática: o script LÊ `globals.css`
(ink-3, border-field, bg-page/card, luz-tinta, penumbra) e **ABORTA** em
divergência. Nenhum resultado anterior à emenda é evidência válida.
**Rodado na 0.5 (analítico, shader=0)**: sincronia OK; pico composto novo
`#c8cbcf`/`#2d323d`; **`--ink-tertiary` e `--border-field` MANTIDOS** —
ink-3 5,031/5,116:1 e border-field 3,377/3,474:1 no pico (mínimos 4,5/3,0;
alvos 4,62/3,13), todos os 5 contextos R12d passam nos 2 temas → NENHUMA
recalibração aplicada; os pares dos Grupos A–F do R7 já nascem medidos
contra os finais. Informativo pré-existente (não é reprovação da emenda):
`accent-text` claro no pico ANALÍTICO sem shader dá 4,155:1 — com a
penumbra ameixa antiga já dava 4,171:1 (Δ−0,016); o dial é da cadeia AA da
Onda 3 (readPixels + pixel real), nunca deste script (token intocável).
Saída completa: `.maestro/evidencias/onda0/05-congelamento/calibra_tokens_emendado_saida.txt`.

---

## 2. Tipografia

### Famílias (`next/font/google`, self-host, zero request externo)

| Utilitário | Fonte | Pesos/eixos carregados | Papel |
|---|---|---|---|
| `font-display` | Newsreader (variável) | `wght` 200–800 inteiro + `opsz` 6–72, só estilo **normal** | H1–H3, corpo longo de research report, blockquotes |
| `font-display-italico` | Newsreader (2ª instância, `src/lib/fontes.ts`) | peso 500 itálico + `opsz` 6–72 | Voz exclusiva da D5 narrada — SÓ existe onde a página aplica `newsreaderItalico.variable` a um ancestral (hoje `/tese` e `/como-funciona`; ver §3 "P1" abaixo). Combine sempre com a utilidade `italic` do Tailwind (família + estilo); só um dos dois sintetiza um itálico falso |
| `font-sans` | Archivo (variável) | `wght` 100–900 inteiro + `wdth` 62–125 | UI (nav, botões, forms) em wdth ~100; labels de dado em wdth ~72 (`font-stretch: 72%`) + `font-semibold` + `uppercase` + tracking aberto |
| `font-mono` | IBM Plex Mono | 400/500/600 (não é variável) | **Todo número factual, timestamp, ID de auditoria, versão de modelo.** Sempre `tabular-nums` — já embutido na classe `.font-mono` (ver globals.css), não precisa adicionar manualmente |

**P1 (CORRECOES-RODADA-1.md):** o itálico do Newsreader (147 kB) deixou de
ser preloadado em toda rota — só `/tese` e `/como-funciona` (as únicas que
renderizam itálico de verdade: `Markdown.tsx` `<em>`/voz D5 e o parágrafo
narrado da cláusula 05) importam `newsreaderItalico` de `src/lib/fontes.ts`
e aplicam `.variable` a um elemento ancestral (o `<main>` da página). As
outras 5 rotas (`/`, `/teses`, `/cobertura`, `/sobre`, `/historico`) não
pagam esse peso.

`opsz` (Newsreader) e `wdth` (Archivo) são eixos variáveis reais: o navegador
já ajusta `opsz` sozinho pelo tamanho de fonte usado (`font-optical-sizing:
auto` é o padrão) — H1 grande puxa opsz alto, corpo 16px fica em opsz ~16,
de graça, sem CSS extra. Para `wdth` em labels condensadas use a utilidade
arbitrária `[font-stretch:72%]` do Tailwind.

**Cláusula do design system:** número factual nunca aparece na sans — se
está em mono, tem fonte; se não tem fonte, não existe (gate anti-alucinação
do `AGENTS.md` como regra visual).

### Escala (utilitários `text-*` — nomes próprios, não confundir com a escala default do Tailwind)

| Utilitário | px | Papel |
|---|---|---|
| `text-label` | 12 | Labels caps (Archivo, `uppercase tracking-[0.16em]`) |
| `text-meta` | 13 | Metadados mono (fonte, data, id) |
| `text-ui` | 14 | Chrome de interface |
| `text-body` | 16 | Corpo de tese — combinar com `max-w-prose` (65ch) ou `max-w-[68ch]` |
| `text-lede` | 18 | Lede/abertura |
| `text-h3` | 22 | H3 |
| `text-h2` | 28 | H2 |
| `text-h1` | 40 | H1 |
| `text-hero` | `clamp(4rem,8vw,5.5rem)` | Hero da landing — line-height 0.98, letter-spacing -0.015em já embutidos no token |

Todos vêm com `line-height` pareado (Tailwind aplica junto automaticamente).
Corpo de tese: medida 65–70ch, `leading-` já é 1.6 via `text-body`.

---

## 3. Motion — tokens e classes de assinatura

### Tokens de tempo/easing

| Token CSS | Valor | Uso |
|---|---|---|
| `--dur-tick` | 120ms | micro: hover, focus, toggle |
| `--dur-set` | 240ms | estado: tabs, chips, accordion |
| `--dur-press` | 420ms | entradas de conteúdo, reveals |
| `--dur-edition` | 700ms | hero, página/tema (1x por view) |
| `ease-ink` (utilitário Tailwind) | `cubic-bezier(0.22,1,0.36,1)` | padrão da casa — sai rápido, assenta longo |
| `ease-rule` (utilitário Tailwind) | `cubic-bezier(0.65,0,0.35,1)` | simétrico — réguas/barras que se imprimem |
| `ease-settle` (utilitário Tailwind) | `linear(0,0.53 18%,0.92 38%,1.02 58%,0.99 78%,1)` | **único spring do sistema** — só o Pin de Citação |

`--dur-*` não vira utilitário Tailwind dedicado (Tailwind v4 não tem
namespace `--duration-*`); use via valor arbitrário: `duration-[var(--dur-
tick)]`. `--ease-*` SÃO utilitários Tailwind de verdade (`ease-ink`,
`ease-rule`, `ease-settle`) porque `--ease-*` é um namespace nativo do tema.

### Disparo — `Reveal` / `useReveal` (`src/components/motion/Reveal.tsx`)

```tsx
import { Reveal } from "@/components/motion/Reveal";

// Wrapper de conveniência (renderiza uma <div>): Assentamento de Tipo padrão.
<Reveal>
  <h2 className="font-display text-h2 text-ink">Fundamentos</h2>
</Reveal>

// Com uma assinatura específica:
<Reveal variant="reveal-ticker" className="i-3">
  <CardTese ... />
</Reveal>
```

```tsx
import { useReveal, classesReveal } from "@/components/motion/Reveal";

// Para aplicar a um elemento que já existe, sem <div> extra:
function ReguaDeSecao() {
  const { ref, armado, revelado } = useReveal<HTMLHRElement>();
  return <hr ref={ref} className={classesReveal("reveal-regua", armado, revelado)} />;
}
```

Contrato: SSR sempre visível (sem `.is-armed` nenhuma regra esconde nada);
JS arma a transição só depois de montar; `prefers-reduced-motion` aplica
`is-revealed` imediato, pulando a animação por completo (mais o `@media
(prefers-reduced-motion: reduce)` do CSS como rede de segurança). Roda 1x —
o observer se desconecta ao revelar.

### Classes de assinatura (`globals.css`)

| Classe | Assinatura | Efeito | Combine com |
|---|---|---|---|
| `.reveal` | Assentamento de Tipo | `translateY(0.35em)+opacity` → 0, `--dur-press`/`ease-ink` | padrão do `<Reveal>` sem `variant`. **Fix Q1** (CORRECOES-RODADA-1.md): não anima mais `clip-path` no nó observado pelo IntersectionObserver — isso zerava a geometria e travava o reveal com JS ligado (39/39 elementos presos). Só opacity+transform, como as demais variantes |
| `.entrada-hero` | Entrada do Hero (LCP-safe) | SÓ `transform: translateY(0.35em)→0` via `animation` (não `transition`+classe), incondicional no load — **sem opacity**, sem gate de IO | conteúdo acima da dobra (P2) — nasce com opacity:1 (não atrasa LCP); usa `.i-1`…`.i-12` para o stagger (mesmas classes, que também setam `animation-delay`) |
| `.reveal-regua` | Impressão de Régua | `scaleX(0→1)` origem esquerda, `--dur-press`/`ease-rule` | aplique numa `<hr>`/barra fina; o texto que segue leva `.atraso-regua` (delay 80ms) para assentar depois da régua — **só quando existe uma régua irmã antes** (D7); sem régua precedente, use `.i-N` puro |
| `.reveal-ticker` | Fila do Ticker | `translateY(12px)+opacity`, `--dur-set`/`ease-ink` | grade de cards — envolva o grid com `.stagger` e cada card com `.i-1`…`.i-12` |
| `.cartao-ticker` | hover do card da fila | hairline superior 1px→2px em brasa, `--dur-tick` | **não** é reveal (é hover/focus-within) — sem levitação, sem sombra |
| `.citacao-pin` | Pin de Citação (único spring) | `scale(0.92→1)+opacity`, `--ease-settle`; borda esquerda 2px `scaleY(0→1)` via `::before` | chip com `bg-realce font-mono` por cima |
| `.sublinhado-brasa` | Sublinhado de Brasa | `background-size` 0%→100% de 2px, `--dur-tick`/`ease-rule`, ativa em hover/focus-visible/`aria-current="page"`/`aria-current="location"` | links de nav, tabs — dark ganha `text-shadow` sutil junto. `location` cobre TOCs/sumários (D2: scrollspy do IndiceNav) |
| `.lacuna-declarada` | Lacuna Declarada | outline tracejado (`--warn-border`) expande 6px e dissolve, `--dur-press`/`ease-ink` | badge "dado não encontrado" — **mesma hierarquia visual de citação**, nunca a de erro |
| `.hachura-lacuna` | (estática, sem reveal) | `repeating-linear-gradient` 45°, CSS puro, sem imagem | célula de tabela com dado ausente |
| `.stagger` + `.i-1`…`.i-12` | stagger CSP-safe | `transition-delay` E `animation-delay`: `calc(var(--stagger-step) * N)`, passo 60ms | qualquer grade/lista que entra em ordem de leitura (via `transition`) ou o hero acima da dobra (via `animation`, `.entrada-hero`) |
| `.sombra-elevada` | elevação (camada componente) | sombra fria só no claro; `none` no escuro (elevação por borda) | `bg-elevated` + esta classe |

### Scrollspy compartilhado (`useSecaoAtiva`)

`src/components/motion/useSecaoAtiva.ts` (D2, CORRECOES-RODADA-1.md):
`useSecaoAtiva(ids: readonly string[]): string | null` — observa os elementos
com os `ids` informados e devolve o id da seção "atual" (mais próxima do
topo da faixa de leitura). Usado por `Sumario` (`app/tese/TeseView.tsx`) e
por `IndiceNav` (`app/como-funciona/IndiceNav.tsx`, client component pequeno
— a página em si continua Server Component, só passa `items` como prop).

**Fora de escopo desta fundação** (ficam para as ondas de tela, que têm o
DOM específico de cada página): **Virada de Edição** (View Transitions API,
galeria→tese), **Traço do Elo** (SVG causal do `/como-funciona`), **Régua de
Leitura** (barra de progresso de scroll da página da tese). Os tokens de
tempo/easing acima já cobrem essas três — só falta o CSS/HTML específico de
cada uma.

**Guard-rails de motion:** um único spring (`ease-settle`, só no Pin de
Citação); nada quica/flutua em cards ou botões; reveals rodam 1x; zero
`style=` inline (CSP com nonce); zero lib de animação runtime; zero parallax
decorativo, shimmer em loop, `filter: blur` animado em grade.

> **Emenda 2026-07-12 (MATÉRIA VIVA):** o "zero lib de animação runtime" foi
> flexibilizado por decisão de conselho EXCLUSIVAMENTE para `gsap@3.15.0` +
> `@gsap/react@2.1.2` (chunks da landing, `import()` dinâmico via
> `src/lib/gsapSetup.ts`, carve-out CSSOM — ver emenda na §1). Framer
> Motion, Lenis e afins seguem vetados. O retorno `elastic.out(1,0.45)` do
> `.magnetico` é exceção REGISTRADA à regra do spring único (física de
> cursor em CTA — nunca entrada de conteúdo, nunca card); reveals da landing
> migrados ao CenaScrub deixam de ser one-shot (scrub reversível é o novo
> contrato LÁ; motor Reveal segue one-shot nas demais rotas).

> **Emenda APOTEOSE 2026-07-13 — 2ª exceção formal de spring:** a mola do
> **palco 3D da Banca** (S1, `cinema/palco.css`, dona: onda BANCA) — cartão
> ativo escala/inclina via `gsap.quickTo` (mesmo motor `carregarGsap()`
> lazy da landing, R5) — é a SEGUNDA exceção registrada à regra do spring
> único CSS (`--ease-settle`, exclusivo do Pin de Citação). Escopo estrito:
> só o palco `.cartao-ticker` sob ancestral `.banca-rail`; nunca entrada de
> conteúdo; scale sempre UNIFORME (nunca eixo/valor isolado). Tokens de
> teto: `--palco-scale-ativo`/`--palco-scale-irmaos`/`--palco-dim`/
> `--palco-tilt` (globals.css :root, tetos e cláusula de recuo em §1
> "Emenda APOTEOSE").

**Emenda 2026-07-11 (missão cinematográfica):** `--ease-cena` é o único
easing do follow/drift da luz ambiente — nunca reusar `ease-ink`/`ease-rule`/
`ease-settle` nela, nem `--ease-cena` fora da luz. Camadas de luz nunca em
ancestral de `.regua-leitura` (TRAVA C2, detalhe completo em §1).

---

## 4. Componentes desta onda (contrato preservado)

- `Header` — sem props, nav fixa (`Como funciona · Teses · Cobertura · Sobre
  · Histórico` + CTA "Gerar tese"), masthead com data da edição (server-side,
  `new Date()`), menu mobile via `<details>/<summary>` nativo (sem lib), sem
  necessidade de `"use client"`.
- `Footer({ saudeSlot? })` — mesma assinatura de antes; `ChipSaude` e
  `ChipSaudeAoVivo` continuam exportados com o mesmo contrato (`estado?:
  boolean`, `ChipSaudeAoVivo` é async para uso em `<Suspense>`).
- `Tarja` — sem props, `role="note"`, sticky no topo (`z-50`), sempre
  visível — nunca remover/ocultar.
- `Reveal` / `useReveal` / `classesReveal` — ver seção 3.

## 5. Regras que não são só estilo

- Lacuna declarada usa o par `aviso-*` com a hierarquia de citação — nunca o
  par `erro-*` (erro é falha técnica; lacuna é evidência de primeira classe).
- Disclaimer CVM sempre como faixa/brasão própria (`Tarja`) — nunca rodapé
  cinza 10px.
- Toda mudança futura de token exige re-rodar `verify_globals_contrast.py`
  (ou equivalente) e documentar falhas/recalibrações aqui e no PR.
