# Tese AI — Frontend

Next.js 16 (App Router, Turbopack) + React 19 + Tailwind CSS v4, **sem biblioteca de
UI** (decisão registrada abaixo). Fala com o backend FastAPI **só pelo servidor**
(route handlers em `src/app/api/teses`), nunca direto do navegador.

## Rodar

```bash
npm install
npm run dev        # http://localhost:3000 (backend local em :8000 por padrão)
npm run build && npm start   # modo produção (CSP estrita — igual à Vercel)
npm run lint
```

Variáveis (server-only, nunca no bundle): `API_URL` — URL do backend FastAPI
(ex.: `https://teseai-production.up.railway.app`). Sem ela, em produção os proxies
respondem 502 com mensagem clara; em dev cai em `http://localhost:8000`.

## Telas

- `/` — landing: proposta de valor + galeria de exemplos pré-gerados (cache do
  backend; abrir não custa nada) + postura do produto.
- `/tese` — gerar tese: combobox de ticker (lista embutida — ver
  `src/lib/tickers.ts`), polling com skeleton, tese estruturada em seções com
  sumário, citações ancoradas por valor com preview da fonte, lacunas destacadas,
  registro de fontes. `?ticker=XXXX` pré-preenche; auto-inicia **só** para os
  exemplos da galeria. `?id=<uuid>` reabre por GET (nunca regenera).
- `/historico` — teses geradas neste navegador (localStorage; nada sai do
  dispositivo).

## Rails (não negociar)

- **Tarja de não-recomendação sempre visível** (layout raiz — postura CVM).
- **CSP estrita com nonce** (`src/proxy.ts`): nada de `style=`/`<style>` inline em
  componente, nada de `dangerouslySetInnerHTML` — o markdown do LLM é parseado em
  nós React (`src/app/tese/Markdown.tsx`); links só viram `<a>` se http(s).
- **Navegador só fala com a mesma origem** (`connect-src 'self'`); o backend é
  alcançado apenas pelos route handlers com `API_URL` server-only.
- Toda afirmação factual na UI tem fonte + data (ex.: a lista de tickers documenta
  a carteira IBOV/B3 e a data da consulta no próprio arquivo).

## Identidade visual

**BRASA EDITORIAL** — "relatório institucional com uma luminária": papel/tinta
sobre fundo frio, um único acento (brasa, cobre queimado — ação ou evidência,
nunca decoração; verde proibido). Newsreader (serif) para títulos e argumento,
Archivo (grotesca) para chrome de UI, IBM Plex Mono para todo número
factual/ticker/timestamp — se está em mono, tem fonte; sem fonte, não vai para
a tela. Tokens semânticos (3 camadas: primitivo → semântico → componente) em
`src/app/globals.css`, dark mode por `prefers-color-scheme`, contrastes WCAG AA
verificados nos dois temas.

**Emenda 2026-07-11 (missão cinematográfica) — luz ambiente fria.** Camada
aditiva sobre a identidade acima (nenhum hex de conteúdo/tinta/brasa muda):
uma luz monocromática azul-tinta (~222°, croma baixo), NUNCA acionável e
nunca um 2º acento — só profundidade. Dois registros com teto fixo: aurora
ambiente (leito sempre presente, ≤6%) e foco interativo (segue o ponteiro só
em `hover:hover`+`pointer:fine`, ≤10% claro/≤12% escuro), movidos exclusivamente
por `transform: translate3d(...)` via CSSOM (`el.style.setProperty`, nunca
`style=`/`setAttribute('style', …)` — CSP intacta). A luz jamais banha número
factual, citação ou `bg-realce` (trava M3), e nenhum ancestral de
`.regua-leitura` recebe `transform`/`filter`/`will-change`/`contain` (trava
C2 — quebraria o `position: fixed` da régua de leitura). Tabela completa de
tokens/regras de consumo: `DESIGN-TOKENS.md` §1 (emenda) — é a fonte de
verdade para qualquer novo uso desta camada, não este README.

**Decisão (Fase 5 do build de UX): não adotar shadcn/ui por ora.** Zero dependência
de UI mantém a superfície de supply-chain e o CSP simples; a identidade própria já
cobre os ~12 componentes do produto. Revisitar se o produto ganhar formulários/
tabelas complexas ou um time maior.

## Testes de fumaça

E2E com Playwright (dev-only, fora do bundle): ver histórico do build — o script
sobe `next start` e verifica galeria instantânea, autocomplete, histórico, CSP
(console sem erro), dark mode e mobile.
