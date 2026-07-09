import Link from "next/link";

import { backendSaudavel } from "@/lib/saude";
import { DATA_CARTEIRA_IBOV } from "@/lib/tickers";

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Contrato preservado (consumido em page.tsx via <Suspense fallback={<ChipSaude />}>):
// `estado` undefined = verificando, true = operacional, false = indisponível.
export function ChipSaude({ estado }: { estado?: boolean }) {
  return (
    <span className="flex items-center gap-2 font-mono text-meta text-ink-3">
      <span
        aria-hidden
        className={`inline-block h-2 w-2 rounded-full ${
          estado === undefined
            ? "bg-line-strong"
            : estado
              ? "bg-brasa-texto"
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

const NAV_FOOTER = [
  { href: "/como-funciona", label: "Como funciona" },
  { href: "/teses", label: "Teses" },
  { href: "/cobertura", label: "Cobertura" },
  { href: "/sobre", label: "Sobre" },
  { href: "/historico", label: "Histórico" },
  { href: "/tese", label: "Gerar tese" },
] as const;

// Fontes públicas usadas pelo motor (dimensões D1…D5 — orquestracao.py do
// backend): CVM (D1), SEC EDGAR (D2), BCB (D3), World Bank + Tesouro (D4).
const FONTES_PUBLICAS = [
  "CVM",
  "SEC EDGAR",
  "Banco Central do Brasil (BCB)",
  "World Bank",
  "Tesouro Nacional",
] as const;

// Rodapé do site. `saudeSlot` é opcional: só a home informa o estado do
// backend (via ChipSaudeAoVivo em Suspense) — as demais páginas não pagam
// essa latência.
export function Footer({ saudeSlot }: { saudeSlot?: React.ReactNode }) {
  return (
    <footer className="mt-auto border-t border-line-strong bg-page">
      <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="flex flex-col gap-3">
          <span className="font-display text-h3 font-semibold text-ink">Tese AI</span>
          <p className="max-w-xs font-sans text-ui leading-relaxed text-ink-2">
            <strong className="font-semibold text-ink">
              Não é recomendação de investimento.
            </strong>{" "}
            Estruturamos o raciocínio a partir de dados públicos, com fonte e
            data em cada afirmação factual; a decisão é sempre do leitor.
          </p>
        </div>

        <nav aria-label="Rodapé" className="flex flex-col gap-2">
          <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
            Navegação
          </span>
          {NAV_FOOTER.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="w-fit font-sans text-ui text-ink-2 underline-offset-4 hover:text-ink hover:underline"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex flex-col gap-2">
          <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
            Fontes públicas
          </span>
          <ul className="flex flex-col gap-1 font-mono text-meta text-ink-2">
            {FONTES_PUBLICAS.map((fonte) => (
              <li key={fonte}>{fonte}</li>
            ))}
          </ul>
          <p className="mt-1 font-sans text-ui text-ink-3">
            Papéis: carteira teórica do Ibovespa (B3) em{" "}
            {formatDataIso(DATA_CARTEIRA_IBOV)}.
          </p>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4 font-mono text-meta text-ink-3 sm:px-6">
          <span>Tese AI · protótipo</span>
          {saudeSlot}
        </div>
      </div>
    </footer>
  );
}
