import { headers } from "next/headers";
import Link from "next/link";

import { Header } from "@/components/site/Header";

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
        className="mx-auto flex w-full max-w-xl flex-1 flex-col items-start gap-4 px-4 py-24 sm:px-6"
      >
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-tinta-3">
          Erro 404
        </p>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-tinta">
          Página não encontrada
        </h1>
        <p className="text-sm leading-relaxed text-tinta-2">
          O endereço não existe ou mudou. Nada foi perdido — as teses geradas
          neste navegador continuam no Histórico.
        </p>
        <div className="flex gap-3">
          <Link
            href="/"
            className="rounded-lg bg-selo px-5 py-2.5 text-sm font-semibold text-sobre-selo hover:bg-selo-forte"
          >
            Ir para o início
          </Link>
          <Link
            href="/historico"
            className="rounded-lg border border-borda-campo px-5 py-2.5 text-sm font-medium text-tinta hover:border-selo-texto"
          >
            Ver histórico
          </Link>
        </div>
      </main>
    </>
  );
}
