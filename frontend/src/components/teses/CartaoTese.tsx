import Link from "next/link";

import { slotVirada, type ClasseAtivo, type PapelB3 } from "@/lib/tickers";

// Régua D1..D5: rótulos mono FACTUAIS (D5, CORRECOES-RODADA-1.md) — a fonte
// oficial de cada dimensão é fato verificado em ARQUITETURA.md /
// orquestracao.py (por classe: app/services/ativos/{acao,fii,renda_fixa}.py),
// não uma métrica de "cobertura" (o produto não expõe, nem finge expor, um
// percentual de preenchimento por dimensão — fabricar esse dado seria
// alucinação). D1 fundamentos (CVM) · D2 pares globais (SEC EDGAR) · D3 macro
// Brasil (BCB) · D4 macro global (World Bank) · D5 elos causais
// (interpretação, fonte nas duas pontas — sem sigla de fonte única).
//
// A régua VARIA por classe de ativo (Fase 2 multiativo) — cada classe declara
// EXATAMENTE as dimensões que o motor monta para ela, nem a mais, nem a menos
// (D2/D4 não existem para FII/renda fixa: sem pares globais SEC nem macro
// global World Bank dedicados nesses perfis, ver docstrings de
// renda_fixa.py/fii.py). Ação segue com as 5 dimensões, como sempre.
// - FII (_SYSTEM_FII): D1 fundamentos do fundo (informe mensal CVM) · D3
//   contexto macro e juros (BCB/Focus) · D5 elos/camada geopolítica.
// - Renda fixa (_SYSTEM_RF): D1 fundamentos do TÍTULO — características,
//   taxas/PUs com Data Base e derivadas de marcação/carrego, fonte
//   STN/Tesouro Transparente · D3 cenário de juros e inflação (BCB/Focus) ·
//   D5 elos/camada geopolítica.
const REGUA_POR_CLASSE: Record<ClasseAtivo, { regua: string; sublabel?: string }> = {
  acao: { regua: "D1 CVM · D2 SEC · D3 BCB · D4 WB · D5 ELOS" },
  fii: { regua: "D1 CVM · D3 BCB · D5 ELOS", sublabel: "Informe mensal CVM" },
  renda_fixa: {
    regua: "D1 STN · D3 BCB · D5 ELOS",
    sublabel: "Tesouro Transparente + Focus",
  },
};

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

type CartaoTeseProps = {
  papel: PapelB3;
  dataCarteira: string;
};

// Card-manchete da galeria /teses (Fila do Ticker). A régua D1..D5 no rodapé
// rotula as dimensões do motor para a classe do ativo (ver REGUA_POR_CLASSE);
// dentro de uma mesma classe, as marcas continuam idênticas entre si — o
// produto não expõe (nem finge expor) uma métrica de "cobertura por
// dimensão" — fabricar esse dado seria alucinação.
export function CartaoTese({ papel, dataCarteira }: CartaoTeseProps) {
  // Virada de Edição (motion): shared element via classe CSS pré-declarada
  // (`.vt-tese-N`, globals.css) — só para os 13 tickers do conjunto finito
  // EXEMPLOS_PRONTOS; cobre a navegação cross-document real (fallback sem
  // JS/hard nav). O véu em /tese cobre o caso comum (navegação SPA).
  const slot = slotVirada(papel.ticker);
  // Ausente == "acao" (mesma convenção de PapelB3.classe, lib/tickers.ts).
  const { regua, sublabel } = REGUA_POR_CLASSE[papel.classe ?? "acao"];
  return (
    <Link
      href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
      // `tem-foco` (spike cinema, §4): foco frio de ponteiro escopado ao
      // card (`.cartao-ticker.tem-foco::after`, globals.css) — pico ~5%,
      // só com pointer:fine+hover; `--mx`/`--my` chegam por delegação do
      // grid (ver GradeFoco.tsx). Hairline `::before` existente intacta.
      className="cartao-ticker tem-foco group flex h-full flex-col gap-3 border border-line bg-card p-5 transition-colors duration-[var(--dur-tick)] hover:border-field"
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
          medidor. Para ação o texto é constante em TODO card desta classe (já
          explicado em /como-funciona) e segue `aria-hidden` (repeti-lo por
          leitor de tela seria ruído sem informação nova). Para FII/renda fixa
          o conjunto de dimensões É a informação nova (o motor não monta pares
          globais SEC nem macro global World Bank para essas classes) — por
          isso este card específico NÃO fica `aria-hidden`. */}
      <p
        aria-hidden={papel.classe === "fii" || papel.classe === "renda_fixa" ? undefined : true}
        className="mt-auto flex flex-col gap-0.5 border-t border-line pt-3 font-mono text-meta tracking-wide text-ink-3"
      >
        <span>{regua}</span>
        {sublabel && <span>{sublabel}</span>}
      </p>
      <span className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto opacity-0 transition-opacity duration-[var(--dur-tick)] group-hover:opacity-100 group-focus-visible:opacity-100">
        Abrir tese →
      </span>
    </Link>
  );
}
