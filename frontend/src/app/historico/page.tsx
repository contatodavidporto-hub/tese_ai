import Link from "next/link";

import { GradeFoco } from "@/components/motion/GradeFoco";
import { Reveal } from "@/components/motion/Reveal";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { exemplosProntos } from "@/lib/tickers";
import { HistoricoClient } from "./HistoricoClient";

// Dinâmica pelo CSP com nonce por requisição (src/proxy.ts).
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Histórico",
  description:
    "Seu extrato de auditoria: as teses geradas neste navegador, guardadas só localmente — nunca sobem para o servidor.",
};

// Migração HORIZONTE (D3/D5/E30 — "A Bancada", cinema/bancada.css): o
// container `mx-auto max-w-4xl` (recon historico:33, 896px) vira `.bancada`.
// Mini-gate de largura: masthead fica em `medida` (prosa, lei D3 — não
// regride: já era ~max-w-2xl/672px por dentro); a Hemeroteca e os exemplos
// usam `.b-medida-esq` (medida + 1 vão do palco, ~1000px+) — MAIS largo que
// os 896px anteriores, nunca mais estreito (prova: screenshot vs :3010).
//
// Copy HORIZONTE (copy-horizonte-spec.md §8, verbatim). ELEMENTO NOVO desta
// rota: as "lombadas" verticais dos cabeçalhos de dia (HistoricoClient.tsx)
// — a Hemeroteca; localStorage/HistoricoClient.tsx INTOCADOS na lógica.
//
// Missão APOTEOSE (crit.7 + crit.10 — onda CHROME): tickers com luz
// especular (.ticker-luz, primitiva da Onda 0 em cinema/ticker-luz.css) —
// esta página só APLICA a classe e garante --mx/--my por delegação
// (GradeFoco/usePonteiro, padrão já estabelecido: UM listener passivo para
// a lista inteira, zero mecanismo novo). Reduce/touch: a primitiva e o
// hook já são inertes por construção.
export default function HistoricoPage() {
  const exemplos = exemplosProntos();

  return (
    <>
      <Header />
      <main id="conteudo" className="bancada flex-1 gap-y-12 py-14">
        <div className="flex flex-col gap-3">
          <Reveal>
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              Seu extrato de auditoria
            </h1>
          </Reveal>
          <Reveal className="i-1">
            <p className="font-sans text-ui leading-relaxed text-ink-2">
              As teses que você gerou neste navegador, na ordem em que saíram.
              Reabrir não gera nada de novo: a tese é lida do registro
              original, com as mesmas citações e fontes.
            </p>
          </Reveal>
          <Reveal className="i-2">
            <p className="font-sans text-ui leading-relaxed text-ink-2">
              O registro fica só neste dispositivo — não sobe para servidor
              nenhum. Se você limpar, ele some daqui; as teses prontas da
              galeria continuam abertas para consulta.
            </p>
          </Reveal>
        </div>

        {/* E30 (correção-mãe, wt-horizonte 2026-07-14): as duas seções abaixo
            viviam em `.b-medida-esq` — o extrato é uma LISTA/tabela (dias +
            registros), não prosa (medida ≤68ch é lei só para prosa, §0.9);
            no formato antigo (`max-w-4xl`) ela já usava a largura cheia do
            container, e `.b-medida-esq` sozinho (só meia trilha de palco)
            fechava a rota ~48-50px mais estreita que a produção em
            768-1024px. `.b-palco` (as duas trilhas) devolve a paridade; o
            único parágrafo de prosa real (abaixo) já tinha `max-w-2xl`
            próprio — a lei tipográfica não muda para ele. */}
        <section
          aria-labelledby="extrato-titulo"
          className="b-palco flex flex-col gap-4"
        >
          <h2 id="extrato-titulo" className="sr-only">
            Extrato de auditoria
          </h2>
          <HistoricoClient />
        </section>

        <section
          aria-labelledby="exemplos-titulo"
          className="b-palco flex flex-col gap-3 border-t border-line pt-8"
        >
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
