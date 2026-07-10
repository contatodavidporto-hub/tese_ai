// Tarja regulatória (postura CVM): a ferramenta ESTRUTURA a tese; a decisão é
// do leitor. Redesenhada como "brasão/faixa própria" — manchete digna, não
// letra miúda de rodapé (guard-rail do design system: nunca escondida, nunca
// cinza 10px). Fica no layout raiz, sticky no topo, para nunca sair de vista
// — requisito de conformidade do produto (AGENTS.md: "nunca dar recomendação
// de compra/venda").
export function Tarja() {
  return (
    <div
      role="note"
      aria-label="Aviso regulatório"
      className="sticky top-0 z-50 border-b-2 border-aviso-borda bg-aviso-fundo"
    >
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-center gap-x-3 gap-y-1 px-4 py-2 text-center sm:px-6">
        <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-aviso-texto">
          Aviso CVM
        </span>
        <span aria-hidden className="hidden h-3 w-px bg-aviso-borda sm:inline-block" />
        <p className="font-sans text-ui text-aviso-texto">
          <strong className="font-semibold">Não é recomendação de investimento.</strong>{" "}
          Tese estruturada a partir de dados públicos — a decisão é sempre do leitor.
        </p>
      </div>
    </div>
  );
}
