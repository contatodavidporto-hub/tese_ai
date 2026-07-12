import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { FocoLuz } from "@/components/motion/FocoLuz";
import { GradeFoco } from "@/components/motion/GradeFoco";
import { Reveal } from "@/components/motion/Reveal";
import { CartaoTese } from "@/components/teses/CartaoTese";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tese AI — a tese inteira, com a fonte de cada número",
  description:
    "Gere teses de investimento estruturadas para ações da B3, FIIs e Tesouro Direto cruzando fundamentos, macro e geopolítica — cada número com fonte e data, cada lacuna declarada. Não é recomendação de compra ou venda.",
};

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatPct(pct: number): string {
  return pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

// Dimensões canônicas D1…D5 (ARQUITETURA.md — verificadas em
// backend/app/services/orquestracao.py). Copy derivada do texto já auditado
// da landing anterior, redistribuída em 5 cláusulas por fonte oficial — sem
// afirmação nova.
const DIMENSOES = [
  {
    numero: "D1",
    titulo: "Fundamentos",
    fonte: "CVM",
    texto:
      "Demonstrações e cadastro públicos da CVM: receita, margens, dívida e as derivadas que o dado permite calcular — nada além do que a fonte sustenta.",
  },
  {
    numero: "D2",
    titulo: "Pares globais",
    fonte: "SEC EDGAR",
    texto:
      "Comparáveis internacionais a partir de arquivos da SEC — sempre com a ressalva de padrão contábil e moeda, como comparação selecionada, não equivalência.",
  },
  {
    numero: "D3",
    titulo: "Macro Brasil",
    fonte: "BCB",
    texto:
      "Séries oficiais do Banco Central do Brasil — juros, câmbio e atividade — e o preço do petróleo Brent, com o rótulo e a data de cada série.",
  },
  {
    numero: "D4",
    titulo: "Macro global",
    fonte: "World Bank + Tesouro",
    texto:
      "Séries internacionais do Banco Mundial e do Tesouro: atividade, juros e comparáveis macro fora do Brasil, com o rótulo e a data de cada série.",
  },
  {
    numero: "D5",
    titulo: "Elos causais",
    fonte: "fonte nas duas pontas",
    texto:
      "Elos causais entre evento, commodity, setor e empresa — marcados como interpretação, em cenários condicionais, com fonte nas duas pontas de cada elo.",
  },
] as const;

const PRINCIPIOS = [
  {
    titulo: "Não recomenda",
    texto:
      "Nenhum “compre”, “venda” ou preço-alvo. A ferramenta estrutura o raciocínio; a decisão é do leitor — postura alinhada à regulação da CVM.",
  },
  {
    titulo: "Cada número com fonte",
    texto:
      "As afirmações factuais saem ancoradas em citações verificáveis, com link e data da fonte pública. O que não tem fonte não entra como fato.",
  },
  {
    titulo: "Lacunas declaradas",
    texto:
      "Quando o dado não existe, a tese registra “dado não encontrado” e segue — abster é mais honesto que estimar.",
  },
] as const;

export default function Home() {
  const exemplos = exemplosProntos();
  const primeiroTicker = exemplos[0]?.ticker ?? "VALE3";
  // Prova viva: os 3 maiores pesos reais da carteira teórica do Ibovespa
  // (fonte B3, mesma data em todo o produto) — nenhum número aqui é inventado.
  const provaViva = exemplos.slice(0, 3);
  const dataCarteira = formatDataIso(DATA_CARTEIRA_IBOV);
  // Contagem derivada do catálogo (nunca hardcoded, ver app/teses/page.tsx).
  const acoesExemplo = exemplos.filter((p) => (p.classe ?? "acao") === "acao").length;
  const multiativoExemplo = exemplos.length - acoesExemplo;

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Hero — P2 (CORRECOES-RODADA-1.md): acima da dobra, então SEM Reveal
            (opacity:0 preso a IntersectionObserver atrasaria o LCP à toa, já
            que o hero está na viewport desde o load). `.entrada-hero` anima
            só `transform`, incondicionalmente, via keyframe CSS — o conteúdo
            nasce pintável (opacity:1) no primeiro frame. Reveal (com fade de
            opacidade) fica reservado para as seções abaixo da dobra, logo a
            seguir. */}
        {/* `.tem-foco` + <FocoLuz/> (spike cinema, §2): luminária fria que
            segue o ponteiro dentro do hero — pico 7% claro/10% escuro
            (--luz-foco-alfa), só pointer:fine+hover (M7), invisível em
            reduced-motion/touch. Camada puramente decorativa, `z-index`
            abaixo de todo o conteúdo (globals.css `.foco-luz`) — nunca toca
            o chip de citação (M3). */}
        <section className="tem-foco border-b border-line" aria-labelledby="hero-titulo">
          <FocoLuz />
          <div className="mx-auto flex w-full max-w-5xl flex-col items-start gap-6 px-4 py-16 sm:px-6 sm:py-24">
            <div className="entrada-hero i-1">
              <p className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
                Teses de investimento · B3 e Tesouro Direto
              </p>
            </div>
            <div className="entrada-hero i-2">
              <h1
                id="hero-titulo"
                className="max-w-3xl font-display text-hero font-semibold tracking-tight text-ink"
              >
                A tese inteira, com a <span className="text-brasa-texto">fonte</span>
                {/* Pin de citação sobrescrito (§2, cena 3): resolve scale+opacity
                    com o spring --ease-settle 1 beat depois do H1 assentar —
                    CSS puro incondicional (.pin-hero), nunca gate de IO (o
                    hero é LCP). O mesmo [1] reaparece na linha de fonte viva
                    abaixo dos CTAs — é a mesma citação. */}
                <sup className="pin-hero font-mono text-ui text-brasa-texto">[1]</sup>{" "}
                de cada número.
              </h1>
            </div>
            <div className="entrada-hero i-3">
              <p className="max-w-2xl text-lede leading-relaxed text-ink-2">
                O Tese AI estrutura teses de investimento cruzando fundamentos, contexto macro,
                pares globais e geopolítica. Cada afirmação factual é rastreável até o dado
                público de origem, interpretação vem rotulada como tal — e cada lacuna é
                declarada, nunca preenchida com chute.
              </p>
            </div>
            <div className="entrada-hero i-4">
              <div className="flex flex-wrap items-center gap-3">
                <Link
                  href="/tese"
                  className="bg-brasa px-6 py-3 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                >
                  Gerar tese
                </Link>
                <Link
                  href={`/tese?ticker=${encodeURIComponent(primeiroTicker)}`}
                  className="border border-field px-6 py-3 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto"
                >
                  Ver exemplo: {primeiroTicker}
                </Link>
              </div>
            </div>
            {/* Linha de fonte viva (§2, cena 4): mesma anatomia de citação da
                "prova viva" abaixo — chip bg-realce OPACO, acima da luz (M3),
                borda-esquerda 2px brasa imprimindo. Mesmo [1] do H1, mesma
                fonte/data que a prova viva já usa (DATA_CARTEIRA_IBOV) —
                nenhum número novo. */}
            <p className="citacao-pin-hero w-fit bg-realce py-2 pl-4 pr-4 font-mono text-meta text-ink-2">
              <sup className="text-brasa-texto">[1]</sup> Fonte: B3 · Carteira teórica do
              Ibovespa · {dataCarteira}
            </p>
            <div className="entrada-hero i-5">
              <p className="text-ui text-ink-3">
                Ferramenta de estruturação — não é recomendação de compra ou venda.
              </p>
            </div>
          </div>
        </section>

        {/* Prova viva: anatomia de uma citação, com números reais e auditados */}
        <section aria-labelledby="prova-titulo" className="border-b border-line">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <Reveal>
              <div className="flex flex-col gap-2">
                <h2
                  id="prova-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Prova viva: assim nasce um número na tese
                </h2>
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  Todo dado factual segue o mesmo caminho: número em mono, marcado com uma
                  citação, ligado a uma fonte e uma data — sem exceção. Exemplo real, com a
                  carteira teórica do Ibovespa (B3, {dataCarteira}):
                </p>
              </div>
            </Reveal>

            <ol className="stagger grid gap-3 sm:grid-cols-3">
              {provaViva.map((papel, i) => (
                <li key={papel.ticker}>
                  <Reveal variant="citacao-pin" className={`i-${i + 1} flex h-full flex-col gap-2 bg-realce px-4 py-4`}>
                    <span className="flex flex-wrap items-baseline gap-x-2 font-mono text-ui text-ink">
                      <span className="font-semibold">{papel.ticker}</span>
                      <span>·</span>
                      <span>{formatPct(papel.participacaoPct)}% do IBOV</span>
                      <sup className="text-brasa-texto">[{i + 1}]</sup>
                    </span>
                    {/* A4 (contraste 1.4.3): text-ink-3 sobre bg-realce reprova por
                        0,011 — text-ink-2 verifica em 7.11:1 no mesmo par. */}
                    <span className="font-mono text-meta text-ink-2">
                      Fonte: B3 · Carteira teórica do Ibovespa · {dataCarteira}
                    </span>
                  </Reveal>
                </li>
              ))}
            </ol>

            <Reveal>
              <p className="max-w-2xl text-ui text-ink-3">
                Assim é toda citação da plataforma: o número no corpo do texto, a nota entre
                colchetes e a fonte com a data logo abaixo — nunca escondida em rodapé.
              </p>
            </Reveal>
          </div>
        </section>

        {/* Galeria teaser */}
        <section aria-labelledby="galeria-titulo" className="border-b border-line">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-14 sm:px-6">
            <Reveal>
              <div className="flex flex-col gap-2">
                <h2
                  id="galeria-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Teses de exemplo — abrem na hora
                </h2>
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  Pré-geradas pelo motor: os {acoesExemplo} maiores pesos da carteira teórica
                  do Ibovespa (B3, {dataCarteira}) e {multiativoExemplo} exemplos multiativo — um
                  FII, um título do Tesouro Direto — mantidos em cache. Clique e leia a tese
                  completa, com citações e fontes — se o cache tiver expirado, ela é regenerada
                  na hora.
                </p>
              </div>
            </Reveal>
            {/* D3 (CORRECOES-RODADA-1.md): mesma anatomia de card-manchete da
                galeria — reusa <CartaoTese> em vez de uma segunda anatomia
                inline (o diretor de design reprovou as duas versões
                divergentes). */}
            {/* GradeFoco (spike cinema, §4): delegação de pointermove — 1
                listener para a grade inteira liga --mx/--my no
                `.cartao-ticker` sob o cursor (mais barato que 1 hook por
                card). Server Component da grade continua page.tsx; só esta
                borda vira client. */}
            <GradeFoco
              seletorAlvo=".cartao-ticker"
              className="stagger grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
            >
              {exemplos.map((papel, i) => (
                <li key={papel.ticker}>
                  <Reveal variant="reveal-ticker" className={i < 12 ? `i-${i + 1}` : undefined}>
                    <CartaoTese papel={papel} dataCarteira={DATA_CARTEIRA_IBOV} />
                  </Reveal>
                </li>
              ))}
            </GradeFoco>
            <Reveal>
              <Link href="/teses" className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto">
                Ver todas as teses de exemplo →
              </Link>
            </Reveal>
          </div>
        </section>

        {/* As cinco dimensões */}
        <section aria-labelledby="dimensoes-titulo" className="border-b border-line">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <Reveal>
              <div className="flex flex-col gap-2">
                <h2
                  id="dimensoes-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Cinco dimensões, uma tese
                </h2>
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  O motor monta a tese por camadas e fecha com síntese e contra-tese (bull ×
                  bear). Fato e interpretação vêm sempre separados no texto — cada camada com a
                  fonte oficial que a sustenta. O quadro completo vale para as ações; FIIs e
                  títulos do Tesouro Direto usam um subconjunto próprio de dimensões — sem
                  pares globais nem macro global dedicada.
                </p>
              </div>
            </Reveal>
            <ol className="stagger flex flex-col">
              {DIMENSOES.map((d, i) => (
                <li key={d.numero} className="flex flex-col gap-3 py-6">
                  <Reveal
                    variant="reveal-regua"
                    className={`i-${i + 1} h-px w-full bg-line-strong`}
                    aria-hidden
                  >
                    {null}
                  </Reveal>
                  <Reveal className={`i-${i + 1} atraso-regua flex flex-col gap-1.5`}>
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-mono text-h3 text-line-strong">{d.numero}</span>
                      <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink">
                        {d.titulo}
                      </span>
                      <span aria-hidden className="text-ink-3">
                        ·
                      </span>
                      <span className="font-mono text-meta text-brasa-texto">{d.fonte}</span>
                    </div>
                    <p className="max-w-2xl text-body leading-relaxed text-ink-2">{d.texto}</p>
                  </Reveal>
                </li>
              ))}
            </ol>
            <Reveal>
              <Link
                href="/como-funciona"
                className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
              >
                Como o motor funciona, passo a passo →
              </Link>
            </Reveal>
          </div>
        </section>

        {/* Postura */}
        <section aria-labelledby="postura-titulo">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-14 sm:px-6">
            <Reveal>
              <h2
                id="postura-titulo"
                className="font-display text-h2 font-semibold tracking-tight text-ink"
              >
                Auditável por construção
              </h2>
            </Reveal>
            <ol className="stagger grid gap-6 sm:grid-cols-3">
              {PRINCIPIOS.map((p, i) => (
                <li key={p.titulo}>
                  <Reveal
                    variant="reveal-ticker"
                    className={`i-${i + 1} flex h-full flex-col gap-2 border border-line bg-card px-6 py-6`}
                  >
                    <span className="font-mono text-h3 text-line-strong">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="font-display text-lede font-semibold text-ink">{p.titulo}</h3>
                    <p className="text-ui leading-relaxed text-ink-2">{p.texto}</p>
                  </Reveal>
                </li>
              ))}
            </ol>

            {/* Faixa-brasão: o aviso CVM tratado como manchete, não letra miúda */}
            <Reveal>
              <div
                role="note"
                aria-label="Aviso regulatório"
                className="flex flex-col items-center gap-2 border-y-2 border-aviso-borda bg-aviso-fundo px-6 py-8 text-center sm:px-10"
              >
                <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-aviso-texto">
                  Aviso CVM
                </span>
                <p className="font-display text-h2 font-semibold tracking-tight text-aviso-texto">
                  Não é recomendação de investimento.
                </p>
                <p className="max-w-2xl font-sans text-ui text-aviso-texto">
                  Cada tese estrutura o raciocínio a partir de dados públicos, com fonte e data
                  em toda afirmação factual — a decisão de compra ou venda é sempre do leitor.
                </p>
              </div>
            </Reveal>

            <Reveal>
              <div className="flex flex-wrap items-center gap-3 border border-line bg-card px-6 py-5">
                <p className="flex-1 text-ui text-ink-2">
                  Pronto para ver como fica? Gere a tese de uma ação da B3, de um FII ou de um
                  título do Tesouro Direto — ou abra um exemplo pronto.
                </p>
                <Link
                  href="/tese"
                  className="bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                >
                  Gerar tese
                </Link>
              </div>
            </Reveal>
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
