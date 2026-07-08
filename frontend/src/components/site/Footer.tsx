import { DATA_CARTEIRA_IBOV } from "@/lib/tickers";

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Rodapé do site. `saudeBackend` é opcional: só a home (server component com
// fetch próprio) informa o estado do backend — as demais páginas não pagam essa
// latência a cada request.
export function Footer({ saudeBackend }: { saudeBackend?: boolean }) {
  return (
    <footer className="mt-auto border-t border-linha bg-papel">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-4 py-8 text-xs text-tinta-3 sm:px-6">
        <p>
          <strong className="font-semibold text-tinta-2">
            Não é recomendação de investimento.
          </strong>{" "}
          O Tese AI estrutura o raciocínio a partir de dados públicos, com fonte e
          data em cada afirmação; a decisão é sempre do leitor.
        </p>
        <p>
          Dados públicos: CVM, Banco Central do Brasil, FRED, SEC e Banco Mundial.
          Lista de papéis: carteira teórica do Ibovespa (B3) em{" "}
          {formatDataIso(DATA_CARTEIRA_IBOV)}.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-linha pt-3">
          <span className="font-mono">Tese AI · protótipo</span>
          {saudeBackend !== undefined && (
            <span className="flex items-center gap-2 font-mono">
              <span
                aria-hidden
                className={`inline-block h-2 w-2 rounded-full ${
                  saudeBackend ? "bg-selo-texto" : "bg-erro-texto"
                }`}
              />
              backend: {saudeBackend ? "operacional" : "indisponível"}
            </span>
          )}
        </div>
      </div>
    </footer>
  );
}
