import Link from "next/link";

import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { exemplosProntos } from "@/lib/tickers";
import { HistoricoClient } from "./HistoricoClient";

// Dinâmica pelo CSP com nonce por requisição (src/proxy.ts).
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Histórico",
};

export default function HistoricoPage() {
  const exemplos = exemplosProntos();

  return (
    <>
      <Header />
      <main
        id="conteudo"
        className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-4 py-10 sm:px-6"
      >
        <div className="flex max-w-2xl flex-col gap-2">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-tinta">
            Histórico
          </h1>
          <p className="text-sm leading-relaxed text-tinta-2">
            Teses geradas neste navegador. Reabrir não gera nada de novo: a tese
            é lida do registro original, com as mesmas citações e fontes.
          </p>
        </div>

        <HistoricoClient />

        <section aria-labelledby="exemplos-titulo" className="flex flex-col gap-3">
          <h2
            id="exemplos-titulo"
            className="font-display text-xl font-semibold tracking-tight text-tinta"
          >
            Teses de exemplo
          </h2>
          <p className="max-w-2xl text-sm text-tinta-2">
            Pré-geradas para os maiores pesos do Ibovespa — abrem na hora.
          </p>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {exemplos.map((papel) => (
              <li key={papel.ticker}>
                <Link
                  href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
                  className="flex flex-col gap-0.5 rounded-xl border border-linha bg-cartao px-4 py-3 transition-colors hover:border-selo-texto"
                >
                  <span className="font-mono text-sm font-semibold text-tinta">
                    {papel.ticker}
                  </span>
                  <span className="truncate text-xs text-tinta-3">{papel.nome}</span>
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
