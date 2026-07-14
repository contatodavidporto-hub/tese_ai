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

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

// ---------------------------------------------------------------------------
// HORIZONTE (2026-07-14, Onda 3 · raia 3B) — "O MOSTRUÁRIO".
// Direção §9: masthead sobre faixa de VELUDO full-bleed (`.vitrine-veludo` +
// `.veludo-escopo`, folha da raia 1B — REUSO; jamais redeclarar os tokens) e
// a grade de cartões sobre PEDESTAIS (`.vitrine-pedestal`: elipse de sombra
// no chão + keyline ouro no aro).
// ELEMENTO NOVO (principal): PALCO 3D S1 na grade — `.grade-teses` (emenda de
// rito S3 em cinema/palco.css): o cartão sob o cursor sobe (zoom + tilt
// <=2.5deg seguindo o ponteiro, reversível) e os irmãos recuam/esmaecem.
// Zero JS novo: consome `--mx`/`--my` que o GradeFoco (usePonteiro) JÁ
// escrevia — e, acima do previsto na direção, sem baixar gsap nenhum.
// ELEMENTO NOVO (reserva, E27 — sem glow): o foco por CONTRASTE (recuo + dim
// dos irmãos), que sobrevive a qualquer recuo binário de AA.
// SEM DERIVA (a vitrine viva é exceção 2.2.2 exclusiva da landing — D36).
// Layout: `.bancada` — prosa na medida (<=68ch); grade e faixa final no
// `.b-palco` (até 96rem: MAIS largo que o antigo max-w-6xl — mini-gate E30).
// Copy: `.maestro/ondas/copy-horizonte-spec.md` §4, verbatim. Contagens
// SEMPRE derivadas de exemplosProntos() — nunca literais.
// INTOCADOS: CartaoTese, GradeFoco, morph (useViradaCartao / .vt-tese-N).
// ---------------------------------------------------------------------------
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
  // conjunto real quando um exemplo entra/sai (Fase 2 multiativo).
  const acoes = exemplos.filter((p) => (p.classe ?? "acao") === "acao").length;
  const fiis = exemplos.filter((p) => p.classe === "fii").length;
  const rendaFixa = exemplos.filter((p) => p.classe === "renda_fixa").length;
  const dataCarteira = formatDataIso(DATA_CARTEIRA_IBOV);

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Masthead sobre veludo full-bleed (D19/D20): o escopo-veludo da raia
            1B re-declara os semânticos em PARES COMPLETOS (E5/E6) — nada de
            token é redeclarado aqui. */}
        <section aria-labelledby="teses-titulo" className="bancada">
          <div className="b-sangria vitrine-veludo veludo-escopo">
            <div className="bancada w-full">
              <div className="b-medida-esq flex flex-col gap-5">
                <Reveal>
                  <p className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
                    Galeria de teses prontas
                  </p>
                </Reveal>
                <Reveal className="i-1">
                  <h1
                    id="teses-titulo"
                    className="font-display text-h1 font-semibold tracking-tight text-ink"
                  >
                    {exemplos.length} teses de exemplo — ações, FII e Tesouro Direto
                  </h1>
                </Reveal>
                <Reveal className="i-2">
                  <p className="font-sans text-lede leading-relaxed text-ink-2">
                    Nenhuma delas espera geração: estão prontas e abrem no clique. São
                    os {acoes} maiores pesos da{" "}
                    <TermoTooltip {...tooltipDe("carteira-teorica")}>
                      carteira teórica do Ibovespa
                    </TermoTooltip>{" "}
                    (B3, {dataCarteira}), mais {fiis} FII e {rendaFixa} título do
                    Tesouro Direto — prova viva de que o motor cobre as três classes.
                  </p>
                </Reveal>
                <Reveal className="i-3">
                  <p className="font-sans text-ui leading-relaxed text-ink-2">
                    Use qualquer uma como amostra do produto inteiro: a régua de
                    auditoria é a mesma da tese que você gerar depois. Escolha um
                    número, clique na citação, chegue ao documento público que a
                    sustenta.
                  </p>
                </Reveal>
                <Reveal className="i-4">
                  <p className="font-mono text-meta text-ink-3">
                    {exemplos.length}{" "}
                    <TermoTooltip {...tooltipDe("warm-cache")}>
                      teses prontas
                    </TermoTooltip>{" "}
                    · renovadas a cada ciclo diário · fonte dos pesos: B3 ·{" "}
                    {dataCarteira}
                  </p>
                </Reveal>
              </div>
            </div>
          </div>
        </section>

        {/* A grade sobre pedestais, no palco largo (E30: `.b-palco` chega a
            96rem — mais largo que o `max-w-6xl`/72rem que existia aqui). */}
        <section aria-labelledby="grade-titulo" className="bancada gap-y-8 py-14">
          <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden>
            {null}
          </Reveal>
          <h2 id="grade-titulo" className="sr-only">
            Grade de teses prontas
          </h2>
          {/* GradeFoco INTOCADO (1 listener passivo, delegado, escrevendo
              `--mx`/`--my` por CSSOM no cartão sob o cursor — o palco S1
              CONSOME essas vars). Continua GRADE DENSA (lei A1 do red-team:
              as teses lado a lado, nunca um carrossel) e SEM deriva (D36). */}
          <GradeFoco
            seletorAlvo=".cartao-ticker"
            className="grade-teses b-palco stagger grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5"
          >
            {exemplos.map((papel, indice) => (
              <li key={papel.ticker} className="vitrine-pedestal">
                <Reveal
                  variant="reveal-ticker"
                  className={`i-${Math.min(indice + 1, 12)} block h-full`}
                >
                  <CartaoTese papel={papel} dataCarteira={DATA_CARTEIRA_IBOV} />
                </Reveal>
              </li>
            ))}
          </GradeFoco>
        </section>

        {/* Bloco "gerar nova tese" */}
        <section aria-labelledby="gerar-titulo" className="bancada gap-y-8 py-14">
          <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden>
            {null}
          </Reveal>
          <div className="b-palco flex flex-col gap-4 border border-line bg-card px-6 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-8">
            <div className="flex flex-col gap-1.5">
              <h2
                id="gerar-titulo"
                className="font-display text-h3 font-semibold text-ink"
              >
                Não achou o ticker que procura?
              </h2>
              <p className="max-w-[68ch] font-sans text-ui leading-relaxed text-ink-2">
                O motor gera a tese completa de qualquer companhia aberta, FII ou
                título do Tesouro Direto sob demanda — basta o código do ativo. As
                regras são idênticas às da galeria: citação, fonte e data em toda
                afirmação factual, lacuna declarada quando o dado não existe. A única
                diferença é o tempo de geração.
              </p>
            </div>
            <Link
              href="/tese"
              className="w-fit shrink-0 bg-brasa px-6 py-3 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
            >
              Gerar nova tese
            </Link>
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
