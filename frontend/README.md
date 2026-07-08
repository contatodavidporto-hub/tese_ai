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

"Relatório institucional": papel/tinta/verde-cédula, serif Fraunces para títulos,
Geist para texto, mono para números e tickers. Tokens semânticos em
`src/app/globals.css` (`--papel`, `--tinta`, `--selo`, `--aviso-*`…), dark mode por
`prefers-color-scheme`, contrastes WCAG AA nos dois temas.

**Decisão (Fase 5 do build de UX): não adotar shadcn/ui por ora.** Zero dependência
de UI mantém a superfície de supply-chain e o CSP simples; a identidade própria já
cobre os ~12 componentes do produto. Revisitar se o produto ganhar formulários/
tabelas complexas ou um time maior.

## Testes de fumaça

E2E com Playwright (dev-only, fora do bundle): ver histórico do build — o script
sobe `next start` e verifica galeria instantânea, autocomplete, histórico, CSP
(console sem erro), dark mode e mobile.
