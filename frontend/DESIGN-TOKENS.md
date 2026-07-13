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
| `--moldura-ameixa` (utilitários `*-moldura-ameixa`) | `#5a3153` | `#b391ac` | Keyline 1px de molduras editoriais (pull-quotes, aberturas de capítulo, borda do masthead) — decorativo, **nunca texto/estado**; hue ~318° (fora de 70–200°) | Labrecque & Milne 2012 (roxo = sofisticação); Valdez & Mehrabian 1994 |
| `--sombra-fria` | `rgb(42 54 84 / 0.16)` | n/a (elevação = borda) | Única sombra do `.sombra-elevada` — quita o ink hardcoded `rgb(22 24 29/.16)` apontado no recon | Valdez & Mehrabian 1994 (PAD: frio escuro = dominância sem arousal) |
| `--luz-nucleo-alfa` | `0.043` | `0.054` | Pico do núcleo rápido da luminária dupla (36vmax, lag ~180ms) — **é o 1º dial a reduzir se o AA do pico não fechar** | Orçamento composto AA calibrado por script; Skulmowski 2016 |
| `--luz-bloom-alfa` | `0.10`\* | `0.11`\* | Pico do bloom (90vmax, stop 45%, lag 700ms) — pico combinado da luminária ≈0.14/0.16 (novos tetos autorizados) | Autorização do humano + cadeia calibra_tokens.py→AA |
| `--luz-penumbra` + `--luz-penumbra-alfa` | `70 44 78` · α `0.03` | `176 146 186` · α `0.04` | Anel externo ameixa do foco (triplet RGB, mesmo padrão de `--luz-tinta`) — profundidade de joia na luz fria, nunca acionável | Valdez & Mehrabian 1994; Palmer & Schloss 2010 (222°→310° não cruza 60–90° nem 70–200°) |
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
| `--constelacao-traco-largura` | `1.5px` | idem | espessura do traçado SVG da constelação | fixo (geometria, não AA) |
| `--constelacao-contorno-alfa` | `0.10` | *(n/a — dark usa borda sólida)* | glow do contorno do painel ativo (S2) | teto ≤0.12. Recuo: falhou AA → contorno também vira borda sólida no claro |

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
