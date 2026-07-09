"use client";

// Fronteira de erro global: mensagem amigável sem detalhes internos
// (stack/URLs ficam no console do servidor, não na tela do usuário).
export default function ErroGlobal({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-start gap-4 px-4 py-24 sm:px-6">
      <h1 className="font-display text-2xl font-semibold tracking-tight text-tinta">
        Algo deu errado
      </h1>
      <p className="text-sm leading-relaxed text-tinta-2">
        Ocorreu um erro inesperado ao montar esta página. Nenhum dado foi
        perdido — tente de novo.
      </p>
      <button
        type="button"
        onClick={reset}
        className="rounded-lg bg-selo px-5 py-2.5 text-sm font-semibold text-sobre-selo hover:bg-selo-forte"
      >
        Tentar novamente
      </button>
    </main>
  );
}
