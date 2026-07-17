import Link from "next/link";

import { GradeFoco } from "@/components/motion/GradeFoco";
import { Reveal } from "@/components/motion/Reveal";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { exemplosProntos } from "@/lib/tickers";
import { HistoricoClient } from "./HistoricoClient";

// Dinâmica pelo CSP com nonce por requisição (src/proxy.ts).
export const dynamic = "force-dynamic";

// Copy CONGELADA (missão OURIVESARIA, .maestro/copy-ourivesaria.md §3 —
// transcrição byte-fiel, §7-E5): o `title` é o do anexo; a description
// REUSA a linha-fina do masthead (zero redação nova — a string é a mesma
// do anexo, nenhuma palavra fora dele).
export const metadata = {
  title: "Seu registro de teses",
  description:
    "As teses que você gerou ou abriu neste navegador — ficam só aqui, no seu aparelho. Nada sobe para servidor.",
};

// MISSÃO OURIVESARIA — raia 2D (crit. 9 · §3-C9 · §7-E9/F6 · conceito B §8):
// a Hemeroteca vira "REGISTRO DE BANCADA" — página reconstruída do zero
// (as lombadas verticais da Horizonte morreram em HistoricoClient.tsx).
// Este arquivo é só o masthead + moldura da rota:
//   - masthead autoexplicativo em 5s: eyebrow mono "Registro de bancada" +
//     talha de ouro (mastheads padronizados da 1A) + H1 + linha-fina que
//     DIZ a função ("ficam só aqui, no seu aparelho");
//   - a lista inteira (fichas por dia, ações, vazio, limpeza em 2 tempos)
//     vive em HistoricoClient.tsx (client — localStorage);
//   - seção "Teses de exemplo": BYTE-IDÊNTICA à da 1A (fora do redesenho;
//     é o destino do link "Ver os exemplos prontos" do estado vazio, via
//     âncora #exemplos-titulo — [id]{scroll-margin-top} global cobre o
//     salto sob a Tarja).
// RITMO (escala congelada 0.5): py-14 = 3.5rem contra Header/Footer
// (--ritmo-capitulo), gap-y-12 = 3rem entre blocos (--ritmo-bloco),
// gap-6 = assento/pós-fio único 1.5rem no masthead. ZERO folha CSS nova
// nesta raia — Tailwind + primitivas existentes (talha-capitulo,
// gema-chip, ticker-luz, reveal-ticker, pedra-404).
export default function HistoricoPage() {
  const exemplos = exemplosProntos();

  return (
    <>
      <Header />
      <main id="conteudo" className="bancada flex-1 gap-y-12 py-14">
        <div className="flex flex-col gap-6">
          <Reveal>
            <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
              Registro de bancada
            </p>
          </Reveal>
          <Reveal variant="reveal-regua" className="talha-capitulo" aria-hidden>
            {null}
          </Reveal>
          <Reveal className="i-1">
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              Seu registro de teses
            </h1>
          </Reveal>
          <Reveal className="i-2">
            <p className="font-sans text-ui leading-relaxed text-ink-2">
              As teses que você gerou ou abriu neste navegador — ficam só
              aqui, no seu aparelho. Nada sobe para servidor.
            </p>
          </Reveal>
        </div>

        {/* E30 (correção-mãe): o registro é LISTA (fichas por dia), não
            prosa — `.b-palco` (as duas trilhas) mantém a paridade de
            largura com a produção (nunca mais estreito). O H1 acima já
            nomeia a região; os cabeçalhos de dia (h2 nas fichas) fazem a
            hierarquia — a seção não precisa de heading próprio. */}
        <section className="b-palco">
          <HistoricoClient />
        </section>

        {/* COSTURA 1A (intocada pela 2D): talha de ouro + respiro no lugar
            do border-t; gap-6 = pós-fio único 1.5rem. */}
        <section
          aria-labelledby="exemplos-titulo"
          className="b-palco flex flex-col gap-6"
        >
          <Reveal variant="reveal-regua" className="talha-capitulo" aria-hidden>
            {null}
          </Reveal>
          <Reveal className="i-1">
            <h2
              id="exemplos-titulo"
              className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3"
            >
              Teses de exemplo
            </h2>
          </Reveal>
          <Reveal className="i-2">
            <p className="max-w-2xl font-sans text-ui text-ink-2">
              Pré-geradas para os maiores pesos do Ibovespa e para os exemplos
              multiativo — um FII e um título do Tesouro Direto. Abrem na
              hora, sem entrar no seu histórico.
            </p>
          </Reveal>
          {/* A3 (alvo ≥24px, WCAG 2.5.8): piso py-1.5 + inline-block.
              GradeFoco = ilha client fina que delega --mx/--my ao ticker
              sob o ponteiro (seletorAlvo .ticker-luz); a lista continua
              server-rendered. Destino /tese = bypass do LinkCinema de
              qualquer forma (véu especializado mora lá) — <Link> puro.
              `[overflow-x:clip]` (defeito 3, gate de geometria): o sprite de
              `.ticker-luz::after` (cinema/ticker-luz.css) é um círculo
              46vmax centrado no próprio link — sem ancestral que clipe, a
              caixa do <a> herda o overflow do pseudo-elemento e o
              `scrollWidth` do documento estoura em mobile (a régua/Tarja não
              são ancestrais desta lista — mesmo padrão de `.salao-pinado`,
              clip nunca hidden). */}
          <GradeFoco
            seletorAlvo=".ticker-luz"
            className="flex flex-wrap gap-x-6 gap-y-2 [overflow-x:clip]"
          >
            {exemplos.map((papel) => (
              <li key={papel.ticker}>
                <Link
                  href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
                  className="ticker-luz sublinhado-brasa inline-block py-1.5 font-mono text-ui text-ink-2 hover:text-ink"
                >
                  {papel.ticker}
                </Link>
              </li>
            ))}
          </GradeFoco>
        </section>
      </main>
      <Footer />
    </>
  );
}
