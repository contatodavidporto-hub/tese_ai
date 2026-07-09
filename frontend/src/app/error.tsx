"use client";

// Fronteira de erro global: microcopy sóbria e tipográfica (nenhuma
// ilustração), par --erro-* (falha técnica — nunca o par de aviso, reservado
// à lacuna declarada). Mensagem amigável sem detalhes internos (stack/URLs
// ficam no console do servidor, não na tela do usuário).
export default function ErroGlobal({ reset }: { error: Error; reset: () => void }) {
  return (
    <main
      id="conteudo"
      className="mx-auto flex w-full max-w-xl flex-1 flex-col items-start gap-5 px-4 py-24 sm:px-6"
    >
      <span className="border border-erro-borda bg-erro-fundo px-2 py-1 font-sans text-label font-semibold uppercase tracking-[0.16em] text-erro-texto">
        Falha técnica
      </span>
      <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
        Esta edição não fechou.
      </h1>
      <p className="max-w-md text-body leading-relaxed text-ink-2">
        Um erro inesperado interrompeu o carregamento desta página. Nenhum
        dado foi perdido — as teses já geradas continuam disponíveis no
        Histórico deste navegador.
      </p>
      <button
        type="button"
        onClick={reset}
        className="bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
      >
        Tentar novamente
      </button>
    </main>
  );
}
