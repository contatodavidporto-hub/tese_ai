// Tarja regulatória fixa (postura CVM): a ferramenta ESTRUTURA a tese; a decisão
// é do leitor. Fica no layout raiz para nunca sair de vista — requisito de
// conformidade do produto (AGENTS.md: "nunca dar recomendação de compra/venda").
export function Tarja() {
  return (
    <div
      role="note"
      aria-label="Aviso regulatório"
      className="sticky top-0 z-50 border-b border-aviso-borda bg-aviso-fundo px-4 py-1.5 text-center text-xs text-aviso-texto"
    >
      <strong className="font-semibold">Não é recomendação de investimento.</strong>{" "}
      Tese estruturada a partir de dados públicos — a decisão é do leitor.
    </div>
  );
}
