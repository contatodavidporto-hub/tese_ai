import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { GradeFoco } from "@/components/motion/GradeFoco";
import { Reveal } from "@/components/motion/Reveal";
import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { CartaoTese } from "@/components/teses/CartaoTese";
import { TermoTooltip } from "@/components/ui/TermoTooltip";
import { tooltipDe } from "@/lib/glossario";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";

// Renderização dinâmica: necessária para o CSP com nonce por requisição (src/proxy.ts)
// ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

// Copy reescrita na missão APOTEOSE (crit. 11): o jargão "warm-cache" saiu
// da UI (vira "teses prontas da galeria"; o termo técnico vive no
// /glossario#warm-cache, linkado pelo tooltip). Contagens seguem derivadas
// de exemplosProntos() — nunca literais.
export const metadata: Metadata = {
  title: "Teses",
  description:
    "Teses prontas da galeria do Tese AI: os maiores pesos da carteira teórica do Ibovespa, mais um FII e um título do Tesouro Direto — prova viva do motor multiativo, cada número com fonte e data.",
  openGraph: {
    title: "Teses — Tese AI",
    description:
      "A galeria de teses prontas: ações do Ibovespa, FII e Tesouro Direto — abrem na hora, cada número com fonte e data.",
  },
};

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

export default function TesesPage() {
  const exemplos = exemplosProntos();
  // Contagem derivada do catálogo (nunca hardcoded): evita a copy divergir do
  // conjunto real quando um novo exemplo entra/sai (Fase 2 multiativo).
  const acoes = exemplos.filter((p) => (p.classe ?? "acao") === "acao").length;
  const fiis = exemplos.filter((p) => p.classe === "fii").length;
  const rendaFixa = exemplos.filter((p) => p.classe === "renda_fixa").length;

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Masthead da galeria */}
        <section aria-labelledby="teses-titulo" className="border-b border-line">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-14 sm:px-6">
            {/* D4 (brasa gratuita no eyebrow): a brasa é acento de ação/evidência,
                não decoração de rótulo — padrão dos demais eyebrows do site
                (text-ink-3). Crit. 11: o jargão "warm-cache" saiu da UI. */}
            <Reveal>
              <p className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
                Galeria de teses prontas
              </p>
            </Reveal>
            <Reveal className="i-1">
              <h1
                id="teses-titulo"
                className="max-w-3xl font-display text-h1 font-semibold tracking-tight text-ink"
              >
                {exemplos.length} teses de exemplo — ações, FII e Tesouro Direto
              </h1>
            </Reveal>
            <Reveal className="i-2">
              <p className="max-w-2xl font-sans text-ui leading-relaxed text-ink-2">
                Pré-geradas pelo motor e mantidas prontas: os {acoes} maiores pesos da{" "}
                <TermoTooltip {...tooltipDe("carteira-teorica")}>
                  carteira teórica do Ibovespa
                </TermoTooltip>{" "}
                (B3, {formatDataIso(DATA_CARTEIRA_IBOV)}), mais {fiis} FII e {rendaFixa}{" "}
                título do Tesouro Direto — prova viva do motor multiativo, com a mesma
                trilha de citações de uma tese sob demanda. Abrem na hora; se o cache
                tiver expirado, a tese é regenerada automaticamente.
              </p>
            </Reveal>
            <Reveal className="i-3">
              <p className="font-mono text-meta text-ink-3">
                {exemplos.length}{" "}
                <TermoTooltip {...tooltipDe("warm-cache")}>teses prontas</TermoTooltip> ·
                renovadas a cada ciclo diário · {acoes} ações do Ibovespa + {fiis} FII +{" "}
                {rendaFixa} Tesouro Direto
              </p>
            </Reveal>
          </div>
        </section>

        {/* Grade densa 2×5 (desktop) de cards-manchete */}
        <section aria-labelledby="grade-titulo">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-14 sm:px-6">
            <h2 id="grade-titulo" className="sr-only">
              Grade de teses pré-geradas
            </h2>
            {/* GradeFoco (spike cinema, §4): mesma luz fria por delegação da
                galeria teaser da home (page.tsx) — 1 listener de pointermove
                para a grade inteira liga --mx/--my no `.cartao-ticker` sob o
                cursor. Continua GRADE DENSA (lei A1 do red-team: comparação
                de 13 teses lado a lado, nunca um carrossel). */}
            <GradeFoco
              seletorAlvo=".cartao-ticker"
              className="stagger grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
            >
              {exemplos.map((papel, indice) => (
                <li key={papel.ticker}>
                  <Reveal
                    variant="reveal-ticker"
                    className={`i-${Math.min(indice + 1, 12)}`}
                  >
                    <CartaoTese papel={papel} dataCarteira={DATA_CARTEIRA_IBOV} />
                  </Reveal>
                </li>
              ))}
            </GradeFoco>
          </div>
        </section>

        {/* Bloco "gerar nova tese" */}
        <section aria-labelledby="gerar-titulo" className="border-t border-line">
          <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6">
            <div className="flex flex-col gap-4 border border-line bg-card px-6 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-8">
              <div className="flex flex-col gap-1.5">
                <h2
                  id="gerar-titulo"
                  className="font-display text-h3 font-semibold text-ink"
                >
                  Não achou o ticker que procura?
                </h2>
                <p className="max-w-xl font-sans text-ui text-ink-2">
                  O motor gera a tese completa de qualquer companhia aberta, FII ou
                  título do Tesouro Direto sob demanda — basta o{" "}
                  <TermoTooltip {...tooltipDe("ticker")}>ticker</TermoTooltip>. As
                  mesmas dimensões e citações da classe; a única diferença é o tempo de
                  geração.
                </p>
              </div>
              <Link
                href="/tese"
                className="w-fit bg-brasa px-6 py-3 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
              >
                Gerar nova tese
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer
        saudeSlot={
          <Suspense fallback={<ChipSaude />}>
            <ChipSaudeAoVivo />
          </Suspense>
        }
      />
    </>
  );
}
