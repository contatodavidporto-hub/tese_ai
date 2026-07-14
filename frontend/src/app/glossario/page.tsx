import type { Metadata } from "next";
import { Suspense } from "react";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { Reveal } from "@/components/motion/Reveal";
import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { gruposAlfabeticos, verbetePorSlug } from "@/lib/glossario";
import { IndiceLetras } from "./IndiceLetras";

// Rota NOVA · DONA: onda COPY (APOTEOSE, crit. 11). Renderização dinâmica:
// necessária para o CSP com nonce por requisição (src/proxy.ts) ser aplicado
// em cada resposta — regra de TODA página nova.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Glossário",
  description:
    "Os termos técnicos usados nas teses e no site, definidos em linguagem direta — com a fonte do conceito quando houver (ANBIMA, B3, BCB, ANEEL, CVM). Definição é conceito; número continua vivendo nas teses, com fonte e data.",
  openGraph: {
    title: "Glossário — Tese AI",
    description:
      "Cada termo técnico do site, definido em linguagem direta e com a fonte do conceito quando houver — de P/VP a marcação a mercado.",
  },
};

export default function GlossarioPage() {
  const grupos = gruposAlfabeticos();

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Masthead do glossário — migrado para a Bancada (D5/E30): a medida
            do texto (b-medida-esq) é IGUAL ou mais generosa que o max-w-2xl
            de antes; a largura MÁXIMA da rota (o corpo de verbetes abaixo,
            b-palco) fica bem mais larga que o max-w-6xl anterior. */}
        <section aria-labelledby="glossario-titulo" className="border-b border-line">
          <div className="bancada py-14 sm:py-20">
            <div className="b-medida-esq flex flex-col gap-4">
              <Reveal className="i-1">
                <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
                  Glossário
                </p>
              </Reveal>
              <Reveal className="i-2">
                <h1
                  id="glossario-titulo"
                  className="max-w-2xl font-display text-h1 font-semibold tracking-tight text-ink"
                >
                  Os termos do jargão, em linguagem direta.
                </h1>
              </Reveal>
              <Reveal className="i-3">
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  Todo termo técnico do site tem definição a um toque de distância — aqui,
                  ou no balão sobre a própria palavra. Definição aqui é conceito, não dado:
                  número, taxa e preço continuam vivendo nas teses, cada um com sua fonte e
                  data.
                </p>
              </Reveal>
              <Reveal className="i-4">
                <p className="text-ui text-ink-3">
                  Chegou aqui por um termo do texto? O voltar do navegador devolve ao ponto
                  exato da leitura — ou siga para{" "}
                  <LinkCinema href="/" className="sublinhado-brasa text-brasa-texto">
                    o início
                  </LinkCinema>{" "}
                  ·{" "}
                  <LinkCinema href="/como-funciona" className="sublinhado-brasa text-brasa-texto">
                    como funciona
                  </LinkCinema>{" "}
                  ·{" "}
                  <LinkCinema href="/teses" className="sublinhado-brasa text-brasa-texto">
                    teses prontas
                  </LinkCinema>
                  .
                </p>
              </Reveal>
            </div>
          </div>
        </section>

        <div className="bancada py-14">
          <div className="b-palco">
            {/* Índice A–Z: no mobile, lista completa dobrável (sem espaço para
                régua fixa); no desktop, a régua de talha (fixed, IndiceLetras
                variante="regua" default) — ver IndiceLetras.tsx. */}
            <div className="mb-10 lg:hidden">
              <details className="border border-line bg-card px-4">
                <summary className="flex min-h-11 cursor-pointer items-center font-sans text-ui font-medium text-ink">
                  Índice A–Z
                </summary>
                <div className="pb-3">
                  <IndiceLetras grupos={grupos} variante="lista" />
                </div>
              </details>
            </div>
            <IndiceLetras grupos={grupos} />

            {/* Verbetes agrupados por letra, em 2 colunas assimétricas ≤65ch
                (CSS multi-column nativo — `break-inside-avoid` impede que um
                grupo seja cortado ao meio; cada verbete já é ≤65ch por si,
                `max-w-[65ch]` abaixo). Reveals one-shot (padrão Reveal fora
                da landing); a varredura do motor Reveal cobre a chegada por
                âncora profunda (#slug) — nada fica preso invisível. */}
            <div className="flex min-w-0 flex-col lg:block lg:columns-2 lg:pl-20 lg:[column-gap:3.5rem]">
              {grupos.map((grupo) => (
                <section
                  key={grupo.letra}
                  id={`letra-${grupo.letra.toLowerCase()}`}
                  aria-label={`Termos com ${grupo.letra}`}
                  className="mb-14 flex flex-col gap-6 break-inside-avoid last:mb-0"
                >
                  <Reveal variant="reveal-regua" className="h-px w-full origin-left bg-line-strong" aria-hidden>
                    {null}
                  </Reveal>
                  <Reveal className="atraso-regua">
                    <p
                      aria-hidden
                      className="font-mono text-h2 font-semibold text-line-strong"
                    >
                      {grupo.letra}
                    </p>
                  </Reveal>
                  <div className="flex flex-col gap-8">
                    {grupo.verbetes.map((v) => (
                      <Reveal key={v.slug}>
                        <article
                          id={v.slug}
                          aria-labelledby={`${v.slug}-titulo`}
                          className="verbete-glossario flex flex-col gap-2 border-b border-line pb-8"
                        >
                          <h2
                            id={`${v.slug}-titulo`}
                            className="font-display text-h3 font-semibold tracking-tight text-ink"
                          >
                            {v.termo}
                          </h2>
                          <p className="max-w-[65ch] text-body leading-relaxed text-ink-2">
                            {v.definicao}
                          </p>
                          {v.detalhe && (
                            <p className="max-w-[65ch] text-ui leading-relaxed text-ink-2">
                              {v.detalhe}
                            </p>
                          )}
                          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-2">
                            {v.fonteDoConceito && (
                              <span className="inline-flex w-fit items-center gap-1.5 border border-line-strong bg-card px-2 py-1 font-mono text-meta uppercase tracking-wide text-ink-3">
                                Conceito · {v.fonteDoConceito}
                              </span>
                            )}
                            {v.verTambem?.map((slugRelacionado) => {
                              const relacionado = verbetePorSlug(slugRelacionado);
                              if (!relacionado) return null;
                              return (
                                <a
                                  key={slugRelacionado}
                                  href={`#${slugRelacionado}`}
                                  className="sublinhado-brasa font-sans text-label font-semibold text-brasa-texto"
                                >
                                  ver também: {relacionado.termo} →
                                </a>
                              );
                            })}
                          </div>
                        </article>
                      </Reveal>
                    ))}
                  </div>
                </section>
              ))}
            </div>

            {/* Fecho — postura, e o caminho de volta para o produto. */}
            <div className="mt-14 flex flex-wrap items-center gap-3 border border-line bg-card px-6 py-5 lg:pl-20">
              <p className="flex-1 text-ui text-ink-2">
                Faltou um termo? Ele provavelmente é uma métrica dinâmica — nas teses, cada
                indicador chega com a própria explicação e fonte, no lugar onde aparece.
              </p>
              <LinkCinema
                href="/teses"
                className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
              >
                Ver as teses prontas →
              </LinkCinema>
            </div>
          </div>
        </div>
      </main>
      <Footer
        saudeSlot={
          <Suspense fallback={<ChipSaude />}>
            <ChipSaudeAoVivo />
          </Suspense>
        }
      />
    </>
  );
}
