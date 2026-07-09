import Link from "next/link";

import { slotVirada, type PapelB3 } from "@/lib/tickers";

// Régua D1..D5: rótulos mono FACTUAIS (D5, CORRECOES-RODADA-1.md) — a fonte
// oficial de cada dimensão é fato verificado em ARQUITETURA.md /
// orquestracao.py, não uma métrica de "cobertura" (o produto não expõe, nem
// finge expor, um percentual de preenchimento por dimensão — fabricar esse
// dado seria alucinação). D1 fundamentos (CVM) · D2 pares globais (SEC
// EDGAR) · D3 macro Brasil (BCB) · D4 macro global (World Bank) · D5 elos
// causais (interpretação, fonte nas duas pontas — sem sigla de fonte única).
const REGUA_D1_D5 = "D1 CVM · D2 SEC · D3 BCB · D4 WB · D5 ELOS";

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
      {/* Régua D1..D5: linha mono factual (fonte oficial por dimensão) — não é
          medidor, `aria-hidden` porque o texto é constante em TODO card (já
          explicado em /como-funciona); repeti-lo por leitor de tela em cada
          card da grade seria ruído sem informação nova. */}
      <p
        aria-hidden
        className="mt-auto border-t border-line pt-3 font-mono text-meta tracking-wide text-ink-3"
      >
        {REGUA_D1_D5}
      </p>
      <span className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto opacity-0 transition-opacity duration-[var(--dur-tick)] group-hover:opacity-100 group-focus-visible:opacity-100">
        Abrir tese →
      </span>
    </Link>
  );
}
