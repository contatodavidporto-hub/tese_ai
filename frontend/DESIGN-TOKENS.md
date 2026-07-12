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
| `text-ink-3` | Tinta terciária (metadados, timestamps) | `#5b5f67` | `#908e88` | 5.92:1 / 5.72:1 na página — **≥4.66:1 / ≥4.67:1 até no PICO da luz** (aurora ∪ foco sobre `bg-page`, recalibrado 2026-07-12; hexes antigos `#686d76`/`#8f8d87` caíam a 3.78:1/4.60:1 no pico). Não usar abaixo de 14px |
| `border-line` | Hairline decorativa | `#e6e5df` | `#23262d` | réguas, zebra — **isenta de AA** (decorativa, não comunica estado) |
| `border-line-strong` | Régua de cabeçalho de seção | `#c7c6bf` | `#383c45` | também decorativa |
| `border-field` | Borda de campo/input interativo | `#7b7a72` | `#6b727e` | ≥3:1 — **é a que precisa de AA**, nunca trocar por `line`/`line-strong` num controle. **≥3.14:1 / ≥3.15:1 até no PICO da luz** (aurora ∪ foco sobre `bg-page`, recalibrado 2026-07-12; hexes antigos `#8f8e86`/`#616772` caíam a 2.39:1/2.69:1 no pico) |
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
| `--luz-aurora-alfa` | opacidade do leito ambiente (sempre presente, difuso, estático/scroll) | `0.04` | `0.055` | **≤0.06** nos dois temas |
| `--luz-foco-alfa` | opacidade da luminária que segue o ponteiro | `0.07` | `0.10` | **≤0.10 claro / ≤0.12 escuro** |
| `--mx`, `--my` | posição do sprite de foco (px), default neutro | `0px` | `0px` | setado só via CSSOM, nunca em CSS estático |
| `--grao-alfa` | opacidade da textura de grão (opcional, só `bg-page`) | `0.025` | `0.04` | **≤0.03 claro / ≤0.04 escuro** |
| `--ease-cena` | easing do glide de luz (follow do foco + drift da aurora) | `cubic-bezier(0.4, 0, 0.2, 1)` | idem | escopo estrito: só a luz — nunca reusar `ease-ink`/`ease-rule`/`ease-settle` nela, nem usar `--ease-cena` fora da luz |

Sprite do foco (referência de implementação): `radial-gradient(circle at center, rgb(var(--luz-tinta)/var(--luz-foco-alfa)) 0%, transparent 60%)` em camada ~120vmax, movida SÓ por `transform: translate3d(var(--mx),var(--my),0)`.

**Regra de consumo — CSSOM carve-out (não negociável):**
- **PERMITIDO:** `el.style.setProperty('--mx', …)` / `el.style.setProperty('--my', …)`, client-side, **pós-mount**, dentro de `pointermove` coalescido por `requestAnimationFrame`, listener `passive`, só sob `@media (hover:hover) and (pointer:fine)`.
- **PROIBIDO:** `el.setAttribute('style', …)`, prop `style={}` em JSX (SSR ou client), tag `<style>` solta, `styled-jsx`, qualquer `style=` inline literal. `.style.setProperty` é a ÚNICA porta permitida — governada por `script-src` sob nonce, não por `style-src` (CSP permanece intacta).

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
