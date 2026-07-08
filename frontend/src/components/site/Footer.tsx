import { backendSaudavel } from "@/lib/saude";
import { DATA_CARTEIRA_IBOV } from "@/lib/tickers";

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

export function ChipSaude({ estado }: { estado?: boolean }) {
  return (
    <span className="flex items-center gap-2 font-mono">
      <span
        aria-hidden
        className={`inline-block h-2 w-2 rounded-full ${
          estado === undefined
            ? "bg-linha-forte"
            : estado
              ? "bg-selo-texto"
              : "bg-erro-texto"
        }`}
      />
      backend:{" "}
      {estado === undefined ? "verificando…" : estado ? "operacional" : "indisponível"}
    </span>
  );
}

// Async: quem usa envolve em <Suspense fallback={<ChipSaude />}> — o rodapé
// chega no stream sem segurar o primeiro paint da página.
export async function ChipSaudeAoVivo() {
  const ok = await backendSaudavel();
  return <ChipSaude estado={ok} />;
}

// Rodapé do site. `saudeSlot` é opcional: só a home informa o estado do backend
// (via ChipSaudeAoVivo em Suspense) — as demais páginas não pagam essa latência.
export function Footer({ saudeSlot }: { saudeSlot?: React.ReactNode }) {
  return (
    <footer className="mt-auto border-t border-linha bg-papel">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-4 py-8 text-xs text-tinta-3 sm:px-6">
        <p>
          <strong className="font-semibold text-tinta-2">
            Não é recomendação de investimento.
          </strong>{" "}
          O Tese AI estrutura o raciocínio a partir de dados públicos, com fonte e
          data em cada afirmação factual; a decisão é sempre do leitor.
        </p>
        <p>
          Dados públicos: CVM, Banco Central do Brasil, FRED, SEC e Banco Mundial.
          Lista de papéis: carteira teórica do Ibovespa (B3) em{" "}
          {formatDataIso(DATA_CARTEIRA_IBOV)}.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-linha pt-3">
          <span className="font-mono">Tese AI · protótipo</span>
          {saudeSlot}
        </div>
      </div>
    </footer>
  );
}
