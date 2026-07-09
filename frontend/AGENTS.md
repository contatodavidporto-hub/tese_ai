<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Rails deste frontend (detalhe no README.md)

- Tarja de não-recomendação sempre visível (layout raiz) — postura CVM.
- CSP estrita com nonce (`src/proxy.ts`): sem `style=`/`<style>` inline, sem
  `dangerouslySetInnerHTML` (markdown do LLM → nós React em `src/app/tese/Markdown.tsx`),
  links de conteúdo só viram `<a>` se http(s).
- Navegador fala só com a mesma origem; backend via route handlers com `API_URL`
  server-only (`src/lib/backend.ts`).
- Sem lib de UI (decisão registrada no README). Tokens de design em `globals.css`.
- Dado factual na UI exige fonte + data (ex.: `src/lib/tickers.ts` documenta carteira B3 e data).
