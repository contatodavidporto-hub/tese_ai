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
export default async function NaoEncontrada() {
  await headers();
  return (
    <>
      <Header />
      <main
        id="conteudo"
        className="tem-foco mx-auto flex w-full max-w-xl flex-1 flex-col items-start gap-5 px-4 py-24 sm:px-6"
      >
        <FocoLuz />
        {/* D7 (baixa): `atraso-regua` presume uma régua irmã logo antes —
            aqui não há nenhuma. Stagger simples (.i-N). */}
        <Reveal className="i-1">
          <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
            Erro 404
          </p>
        </Reveal>
        <Reveal className="i-2">
          <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
            Esta página não consta nesta edição.
          </h1>
        </Reveal>
        <Reveal className="i-3">
          <p className="max-w-md text-body leading-relaxed text-ink-2">
            O endereço não existe ou mudou. Nada foi perdido — as teses
            geradas neste navegador continuam no Histórico.
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
