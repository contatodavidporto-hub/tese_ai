import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { Reveal } from "@/components/motion/Reveal";
import { newsreaderItalico } from "@/lib/fontes";
import { EXEMPLOS_PRONTOS, TICKER_RE } from "@/lib/tickers";
import { TeseClient } from "./TeseClient";

// Renderização dinâmica: o CSP com nonce por requisição (src/proxy.ts) precisa que
// cada resposta HTML seja gerada por requisição para o nonce ser injetado.
export const dynamic = "force-dynamic";

// Metadata revisada (missão APOTEOSE, crit. 11 — vendedora-pela-verdade):
// zero superlativo não-auditável, zero número literal novo; "cinco
// dimensões" e "lacunas declaradas" são a copy estabelecida do site
// (landing/#dimensoes, /sobre). Disclaimer CVM permanece na description.
export const metadata = {
  title: "Gerar tese",
  description:
    "Estruture a tese de uma companhia aberta da B3, de um FII ou de um título do Tesouro Direto: até cinco dimensões — fundamentos, macro, pares globais e elos causais — com cada número ligado à fonte e à data, e lacunas declaradas em vez de estimadas. Não é recomendação de compra ou venda.",
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// No Next 16, `searchParams` de páginas é uma Promise — precisa de await.
// Doc instalada: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/page.md
export default async function TesePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;

  const brutoTicker = typeof sp.ticker === "string" ? sp.ticker.trim().toUpperCase() : "";
  const ticker = TICKER_RE.test(brutoTicker) ? brutoTicker : undefined;
  const brutoId = typeof sp.id === "string" ? sp.id.trim() : "";
  const id = UUID_RE.test(brutoId) ? brutoId : undefined;

  // Auto-início SÓ para a galeria de exemplos (cache aquecido, custo US$ 0):
  // um link externo com ?ticker=XXXX qualquer apenas pré-preenche o campo —
  // gerar tese nova exige um clique explícito (não viramos vetor de custo).
  const autoIniciar = !!ticker && (EXEMPLOS_PRONTOS as readonly string[]).includes(ticker);

  return (
    <>
      <Header />
      <main
        id="conteudo"
        // `newsreaderItalico.variable` (P1): esta página renderiza itálico de
        // verdade (voz narrada da D5 e <em> do markdown, via Markdown.tsx) —
        // liga a família itálica só aqui, não em toda rota do site.
        className={`virada-edicao ${newsreaderItalico.variable} mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-4 py-12 sm:px-6 sm:py-16`}
      >
        <Reveal className="flex max-w-2xl flex-col gap-3 border-b border-line pb-8">
          <p className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
            Nova tese
          </p>
          {/* Alvo do foco na chegada do morph (missão APOTEOSE, M-g):
              tabIndex={-1} = focável SÓ programaticamente — o TeseClient
              move o foco para cá quando a navegação chega pelo
              cartão-que-vira-página (leitor de tela anuncia o heading da
              rota; nada fica preso em overlay). Fora do morph, nada muda:
              -1 não entra na ordem de tabulação. */}
          <h1
            id="tese-titulo"
            tabIndex={-1}
            className="font-display text-h1 font-semibold tracking-tight text-ink"
          >
            Gerar tese
          </h1>
          <p className="text-body text-ink-2">
            Informe o ticker de uma companhia aberta da B3, um FII ou um código
            do Tesouro Direto. A tese sai estruturada em dimensões —
            fundamentos, macro, pares globais e geopolítica — com cada
            afirmação factual ligada à sua fonte, e sem recomendação de compra
            ou venda.
          </p>
        </Reveal>

        <TeseClient tickerInicial={ticker} autoIniciar={autoIniciar} idInicial={id} />
      </main>
      <Footer />
    </>
  );
}
