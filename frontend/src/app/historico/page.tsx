import Link from "next/link";

import { Reveal } from "@/components/motion/Reveal";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { exemplosProntos } from "@/lib/tickers";
import { HistoricoClient } from "./HistoricoClient";

// Dinâmica pelo CSP com nonce por requisição (src/proxy.ts).
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Histórico",
  description:
    "Extrato de auditoria das teses geradas neste navegador — guardado só localmente, nunca sai do dispositivo.",
};

export default function HistoricoPage() {
  const exemplos = exemplosProntos();

  return (
    <>
      <Header />
      <main
        id="conteudo"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-12 px-4 py-14 sm:px-6"
      >
        <div className="flex flex-col gap-3">
          <Reveal>
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              Histórico
            </h1>
          </Reveal>
          <Reveal className="i-1">
            <p className="max-w-2xl font-sans text-ui leading-relaxed text-ink-2">
              Teses geradas neste navegador. Reabrir não gera nada de novo: a
              tese é lida do registro original, com as mesmas citações e
              fontes.
            </p>
          </Reveal>
        </div>

        <section aria-labelledby="extrato-titulo" className="flex flex-col gap-4">
          <h2 id="extrato-titulo" className="sr-only">
            Extrato de auditoria
          </h2>
          <HistoricoClient />
        </section>

        <section aria-labelledby="exemplos-titulo" className="flex flex-col gap-3 border-t border-line pt-8">
          <h2
            id="exemplos-titulo"
            className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3"
          >
            Teses de exemplo
          </h2>
          <p className="max-w-2xl font-sans text-ui text-ink-2">
            Pré-geradas para os maiores pesos do Ibovespa e para os exemplos
            multiativo — um FII e um título do Tesouro Direto. Abrem na hora.
          </p>
          {/* A3 (alvo ≥24px, WCAG 2.5.8): piso py-1.5 + inline-block. */}
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            {exemplos.map((papel) => (
              <li key={papel.ticker}>
                <Link
                  href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
                  className="sublinhado-brasa inline-block py-1.5 font-mono text-ui text-ink-2 hover:text-ink"
                >
                  {papel.ticker}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <Footer />
    </>
  );
}
