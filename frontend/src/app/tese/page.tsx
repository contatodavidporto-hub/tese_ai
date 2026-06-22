import Link from "next/link";
import { TeseClient } from "./TeseClient";

// Renderização dinâmica: o CSP com nonce por requisição (src/proxy.ts) precisa que
// cada resposta HTML seja gerada por requisição para o nonce ser injetado.
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Gerar tese — Tese AI",
};

export default function TesePage() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-8 bg-neutral-50 px-4 py-12 dark:bg-neutral-950">
      <div className="flex w-full max-w-2xl flex-col gap-2">
        <Link
          href="/"
          className="text-sm text-neutral-500 underline-offset-2 hover:underline dark:text-neutral-400"
        >
          ← Início
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
          Gerar tese
        </h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Informe o ticker de uma empresa da B3. A tese é estruturada com cada
          afirmação ligada à sua fonte — sem recomendação de compra ou venda.
        </p>
      </div>

      <TeseClient />
    </main>
  );
}
