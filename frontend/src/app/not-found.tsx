import { headers } from "next/headers";
import Link from "next/link";

import { Header } from "@/components/site/Header";
import { Reveal } from "@/components/motion/Reveal";

// 404 amigável DENTRO do layout raiz (tarja regulatória segue visível).
// `await headers()` força renderização dinâmica: o CSP com nonce por requisição
// (src/proxy.ts) exige HTML gerado por request — um 404 estático serviria
// scripts sem nonce e poluiria o console com violações de CSP.
export default async function NaoEncontrada() {
  await headers();
  return (
    <>
      <Header />
      <main
        id="conteudo"
        className="mx-auto flex w-full max-w-xl flex-1 flex-col items-start gap-5 px-4 py-24 sm:px-6"
      >
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
          <Link
            href="/"
            className="bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
          >
            Ir para o início
          </Link>
          <Link
            href="/historico"
            className="border border-field px-5 py-2.5 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto"
          >
            Ver histórico
          </Link>
        </div>
      </main>
    </>
  );
}
