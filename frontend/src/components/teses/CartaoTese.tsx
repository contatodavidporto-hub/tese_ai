import Link from "next/link";

import { slotVirada, type PapelB3 } from "@/lib/tickers";

// Rótulos das 5 dimensões canônicas do motor (ARQUITETURA.md / orquestracao.py):
// D1 fundamentos (CVM) · D2 pares globais (SEC EDGAR) · D3 macro Brasil (BCB,
// Brent) · D4 macro global (World Bank + Treasury) · D5 elos causais.
const DIMENSOES = ["D1", "D2", "D3", "D4", "D5"] as const;

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

type CartaoTeseProps = {
  papel: PapelB3;
  dataCarteira: string;
};

// Card-manchete da galeria /teses (Fila do Ticker). A régua D1..D5 no rodapé
// é SOMENTE decorativa/rotuladora: cinco marcas idênticas nomeando as
// dimensões do motor. O produto não expõe (nem finge expor) uma métrica de
// "cobertura por dimensão" — fabricar esse dado seria alucinação — então
// nenhuma marca recebe altura, cor ou preenchimento diferente das outras.
export function CartaoTese({ papel, dataCarteira }: CartaoTeseProps) {
  // Virada de Edição (motion): shared element via classe CSS pré-declarada
  // (`.vt-tese-N`, globals.css) — só para os 10 tickers do conjunto finito
  // EXEMPLOS_PRONTOS; cobre a navegação cross-document real (fallback sem
  // JS/hard nav). O véu em /tese cobre o caso comum (navegação SPA).
  const slot = slotVirada(papel.ticker);
  return (
    <Link
      href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
      className="cartao-ticker group flex h-full flex-col gap-3 border border-line bg-card p-5 transition-colors duration-[var(--dur-tick)] hover:border-field"
    >
      <span
        className={`font-mono text-h2 font-semibold tracking-tight text-ink${slot ? ` vt-tese-${slot}` : ""}`}
      >
        {papel.ticker}
      </span>
      <span className="truncate font-display text-lede leading-snug text-ink">
        {papel.nome}
      </span>
      {papel.participacaoPct > 0 && (
        <span className="font-mono text-meta text-ink-3">
          {papel.participacaoPct.toLocaleString("pt-BR", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
          })}
          % do IBOV · fonte B3, {formatDataIso(dataCarteira)}
        </span>
      )}
      {/* Régua D1..D5: decorativa/rotuladora, aria-hidden — não é medidor. */}
      <div aria-hidden className="mt-auto flex gap-1.5 pt-3">
        {DIMENSOES.map((d) => (
          <span key={d} className="flex flex-1 flex-col items-center gap-1">
            <span className="h-2.5 w-full border border-line-strong bg-line" />
            <span className="font-mono text-[0.625rem] text-ink-3">{d}</span>
          </span>
        ))}
      </div>
      <span className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto opacity-0 transition-opacity duration-[var(--dur-tick)] group-hover:opacity-100 group-focus-visible:opacity-100">
        Abrir tese →
      </span>
    </Link>
  );
}
