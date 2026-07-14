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
      {/* Migração à BANCADA (missão HORIZONTE, raia 3A, D5/E30): `<main>`
          deixa de ser um container estreito (`max-w-5xl mx-auto px-4…`) e
          vira o grid de colunas nomeadas — `--sangria` já cobre o respiro de
          borda que o `px-4/sm:px-6` fazia antes, então some daqui. Isto NÃO
          estreita a rota (E30): o intro fica em `.b-medida-esq` (mais largo
          que o `max-w-2xl` de antes) e o corpo (form/skeleton/documento,
          dentro de `<TeseClient>`/`TeseView.tsx`) vive em `.b-palco`, que em
          qualquer viewport plausível é >= à largura efetiva do antigo
          `max-w-5xl` (~976px) — nunca menor. `flex-1` permanece: propriedade
          do item flex no `<body class="flex flex-col">` do layout raiz
          (independe do PRÓPRIO `display` de `<main>`, que passa a ser grid). */}
      <main
        id="conteudo"
        // `newsreaderItalico.variable` (P1): esta página renderiza itálico de
        // verdade (voz narrada da D5 e <em> do markdown, via Markdown.tsx) —
        // liga a família itálica só aqui, não em toda rota do site.
        // `gap-y-10` (NUNCA `gap-10`): `<main>` é `.bancada` (display:grid, 6
        // colunas nomeadas) — o utilitário `gap-*` do Tailwind escreve
        // `row-gap` E `column-gap`; um `column-gap` de 2.5rem × 5 vãos
        // (160px) some da matemática do grid (calibrada com column-gap
        // ZERO) e a soma das trilhas passa a exceder a viewport — overflow-x
        // real, achado por teste em 390px (E3 proíbe exatamente isso). Só
        // `row-gap` (espaçamento vertical entre os filhos empilhados, o
        // mesmo papel do antigo `flex-col gap-10`) é seguro aqui.
        className={`virada-edicao ${newsreaderItalico.variable} bancada flex-1 gap-y-10 py-12 sm:py-16`}
      >
        <Reveal className="b-medida-esq flex flex-col gap-3 border-b border-line pb-8">
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
          {/* Linha-fina (copy-horizonte-spec.md §9, verbatim): traduz o
              formulário para qualquer pessoa antes do jargão de dimensões
              começar (D12 — jargão-zero é só do hero; aqui já cabe termo
              técnico, mas o spec não pediu tooltip nesta frase). */}
          <p className="text-body text-ink-2">
            Informe o código de uma ação da B3, de um FII ou de um título do
            Tesouro Direto. A tese sai estruturada em dimensões, com citação,
            fonte e data em toda afirmação factual — e sem recomendação de
            compra ou venda.
          </p>
        </Reveal>

        <div className="b-palco flex w-full flex-col gap-4">
          <TeseClient tickerInicial={ticker} autoIniciar={autoIniciar} idInicial={id} />
          {/* Corpo NOVO "sob o form" (copy-horizonte-spec.md §9): acolhimento
              do dono (§1 da direção) para quem chega sem saber por onde
              começar — convite ao exemplo pronto, sem prometer nada que o
              motor não entrega. Vive DEPOIS de `<TeseClient>` porque o
              componente (fora da posse desta raia) já concentra form +
              estados de carregamento/erro/pronto num único bloco — no
              estado ocioso (o mais comum para quem lê esta frase pela
              primeira vez) nada mais renderiza abaixo do form, então o
              texto cai exatamente sob ele. */}
          <p className="text-ui text-ink-3">
            Primeira vez aqui? Um exemplo pronto abre na hora e mostra o
            formato inteiro do documento, antes de você esperar uma geração.
          </p>
        </div>
      </main>
      <Footer />
    </>
  );
}
