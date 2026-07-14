import { headers } from "next/headers";

import { Header } from "@/components/site/Header";
// PESO ACEITO (arbitragem do gate perf, 2026-07-13): este import embarca
// FocoLuz+usePonteiro (~5,6KB gzip) no first-load de TODAS as rotas — o
// not-found raiz compartilha o segmento de rota de cada página e o Next 16
// mantém o grafo dele eager (async:false) por design, para o 404 renderizar
// sem round-trip; next/dynamic NÃO muda essa classificação (tentado e
// revertido — só deduplicava 375B). Alternativas rejeitadas: remover a
// gramática de luz do 404 (regrediria o crit. 10, verificado pelo QA) e
// global-not-found (experimental — vetado). TBT não afetado (Δ+8ms landing);
// o orçamento ≤3KB da LEI é da ilha C7 de /tese, que fecha em 2601B.
import { FocoLuz } from "@/components/motion/FocoLuz";
import { LinkCinema } from "@/components/motion/LinkCinema";
import { Reveal } from "@/components/motion/Reveal";

// 404 amigável DENTRO do layout raiz (tarja regulatória segue visível).
// `await headers()` força renderização dinâmica: o CSP com nonce por requisição
// (src/proxy.ts) exige HTML gerado por request — um 404 estático serviria
// scripts sem nonce e poluiria o console com violações de CSP.
//
// Missão APOTEOSE (crit.10 — onda CHROME):
// - <Link> → <LinkCinema>: a saída do 404 ganha a mesma virada de página do
//   resto da nav (matriz de bypass/R10 intactas — LinkCinema intocado).
// - Gramática de luz da casa: `.tem-foco` + <FocoLuz /> (a MESMA luminária
//   dupla fria do hero — núcleo rápido, corpo com atraso), opt-in por
//   superfície como manda o item 13 do globals.css. Os sprites são filhos
//   DIRETOS do container `.tem-foco` (contrato do FocoLuz); o <main> nunca
//   envolve a Tarja (z-50) nem a régua de leitura — o stacking context de
//   `.tem-foco` não aprisiona nada do chrome. Reduce/touch: a luminária é
//   inerte por construção (usePonteiro + bloco de redução do globals.css).
//
// Missão HORIZONTE (2026-07-14 — "A Pedra Bruta", direcao-horizonte.md §9):
// - Migração D3/D5: `mx-auto max-w-xl` -> `.bancada` (prosa em `medida`,
//   ≤68ch — este bloco já era só texto+CTAs, a lei tipográfica não regride
//   nada aqui; E30 preservado).
// - ELEMENTO NOVO: a pedra bruta — o MESMO polígono cinza-fosco de
//   `CenaNascimento.tsx` (plano 2, "extração" — a pedra ANTES da
//   lapidação), como SVG inline PEQUENO, com o `d` literalmente
//   DUPLICADO neste arquivo (pegadinha 3, D18-boundary: o segmento deste
//   `not-found` é EAGER no Next 16 e compartilha o grafo de TODA rota —
//   um `import` de `CenaNascimento.tsx`/`lapidacao.css` aqui vazaria peso
//   para /tese e todas as demais. Zero import novo: a classe
//   `.nascimento-pedra-bruta` já é global via `globals.css` @import
//   `cinema/lapidacao.css` — CSS já pago em toda rota, JS zero). Reserva
//   independente de glow: a própria pedra é CINZA-FOSCA por design (sem
//   specular) — nada aqui depende do recuo binário do S4.
export default async function NaoEncontrada() {
  await headers();
  return (
    <>
      <Header />
      {/* `gap-y-5`, NUNCA `gap-5`: `<main>` É a `.bancada` (display:grid) — a
          forma curta do Tailwind vira `column-gap` na grade de 5 trilhas e
          soma px que estouram a viewport (gate de geometria, defeito 4). */}
      <main
        id="conteudo"
        className="tem-foco bancada flex-1 items-start gap-y-5 py-24"
      >
        <FocoLuz />
        {/* D7 (baixa): `atraso-regua` presume uma régua irmã logo antes —
            aqui não há nenhuma. Stagger simples (.i-N). */}
        <Reveal className="i-1">
          <svg
            viewBox="405 135 110 85"
            className="h-16 w-auto"
            aria-hidden="true"
            focusable="false"
          >
            <path
              d="M 420 150 L 470 143 L 508 168 L 497 208 L 438 212 L 413 183 Z"
              className="nascimento-pedra-bruta"
            />
          </svg>
        </Reveal>
        <Reveal className="i-2">
          <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
            Erro 404
          </p>
        </Reveal>
        <Reveal className="i-3">
          <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
            Esta página não foi lapidada.
          </h1>
        </Reveal>
        <Reveal className="i-4">
          <p className="text-body leading-relaxed text-ink-2">
            O endereço não existe ou mudou. Nada foi perdido: as teses
            geradas neste navegador continuam no Histórico, e as teses
            prontas continuam abrindo na hora.
          </p>
        </Reveal>
        <div className="flex flex-wrap gap-3">
          <LinkCinema
            href="/"
            className="bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
          >
            Ir para o início
          </LinkCinema>
          <LinkCinema
            href="/historico"
            className="border border-field px-5 py-2.5 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto"
          >
            Ver histórico
          </LinkCinema>
        </div>
      </main>
    </>
  );
}
