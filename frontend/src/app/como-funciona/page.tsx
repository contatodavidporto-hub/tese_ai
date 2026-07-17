import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { CenaNascimento } from "@/components/cena/CenaNascimento";
import { Reveal } from "@/components/motion/Reveal";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { TermoTooltip } from "@/components/ui/TermoTooltip";
import { tooltipDe } from "@/lib/glossario";
import { newsreaderItalico } from "@/lib/fontes";
import { IndiceNav } from "./IndiceNav";
// Folha NOVA, exclusiva desta rota (posse da raia 3C) — importada aqui em
// vez de entrar na lista central de globals.css (posse do integrador),
// suportado nativamente pelo App Router (ver cabeçalho do arquivo).
import "@/styles/cinema/como-funciona.css";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta — mesma regra de toda página
// nova (ARQUITETURA.md, rail 5).
export const dynamic = "force-dynamic";

// Copy reescrita na missão FRONTEND HORIZONTE (direção §9 "A Oficina",
// copy-horizonte-spec.md §3): tooltips consomem lib/glossario.ts (D7);
// âncoras e IndiceNav preservados.
export const metadata: Metadata = {
  title: "Como funciona",
  description:
    "Como o motor do Tese AI monta uma tese: até cinco dimensões de dados com fontes oficiais (CVM, SEC EDGAR, BCB, World Bank, STN), síntese com citações verificáveis e um documento auditável no fim — sem recomendação de compra ou venda.",
  openGraph: {
    title: "Como funciona — Tese AI",
    description:
      "Do ticker à tese auditável: dimensões de dados com fontes oficiais, citações verificáveis e lacunas declaradas — inclusive o que o motor se recusa a entregar.",
  },
};

// Etapas do pipeline (ARQUITETURA.md, contrato TeseOut + orquestracao.py do
// backend): ticker validado → ingestão por dimensão → síntese com citações
// (Anthropic Citations) → documento com bull×bear e lacunas declaradas.
const ETAPAS: readonly { rotulo: string; texto: ReactNode }[] = [
  {
    rotulo: "Ticker",
    texto: (
      <>
        Você informa o código do ativo — o{" "}
        <TermoTooltip {...tooltipDe("ticker")}>ticker</TermoTooltip> de uma ação da B3,
        de um FII ou de um título do Tesouro Direto. Dele o motor resolve a classe do
        ativo e quais dimensões a tese vai cruzar.
      </>
    ),
  },
  {
    rotulo: "Ingestão",
    texto:
      "O motor busca os dados nas fontes públicas — CVM, SEC EDGAR, Banco Central, Banco Mundial, Tesouro Nacional e B3 — e guarda, junto de cada valor, o documento e a data de onde ele saiu.",
  },
  {
    rotulo: "Síntese com citações",
    texto: (
      <>
        A síntese é escrita com{" "}
        <TermoTooltip {...tooltipDe("citations")}>Anthropic Citations</TermoTooltip>:
        cada afirmação factual fica presa ao trecho exato do documento de origem.
        Afirmação sem trecho de origem não vira fato — ou é rotulada como
        interpretação, ou sai do texto.
      </>
    ),
  },
  {
    rotulo: "Tese auditável",
    texto: (
      <>
        Sai um documento com seção por dimensão, citações numeradas, registro de
        fontes com data,{" "}
        <TermoTooltip {...tooltipDe("contra-tese")}>contra-tese</TermoTooltip> (
        <TermoTooltip {...tooltipDe("bull-bear")}>bull × bear</TermoTooltip>) e a lista
        do que não foi encontrado. É o que você abre — e pode contestar linha por
        linha.
      </>
    ),
  },
] as const;

// As cinco dimensões canônicas do motor (verificadas em
// backend/app/services/orquestracao.py — fonte factual desta tela, não o
// enunciado genérico do brief de design). D3 é o contexto macro do Brasil;
// D4 é o contexto macro além da fronteira — dimensões distintas, nunca
// confundidas sob um rótulo só de "governo".
type Clausula = {
  numero: string;
  titulo: string;
  fonte: string;
  descricao: string;
  narrada?: boolean;
};

const CLAUSULAS: readonly Clausula[] = [
  {
    numero: "01",
    titulo: "Fundamentos",
    fonte: "CVM",
    descricao:
      "Demonstrações e cadastro públicos da CVM: receita, margens, dívida e as derivadas que o dado permite calcular — nada além do que a fonte sustenta.",
  },
  {
    numero: "02",
    titulo: "Pares globais",
    fonte: "SEC EDGAR",
    descricao:
      "Comparáveis internacionais a partir de arquivos da SEC — sempre com a ressalva de padrão contábil e moeda, como comparação selecionada, não equivalência.",
  },
  {
    numero: "03",
    titulo: "Macro Brasil",
    fonte: "BCB · Brent",
    descricao:
      "Séries oficiais do Banco Central do Brasil — juros, câmbio, atividade — e o preço do petróleo Brent: o pano de fundo macroeconômico em que a empresa opera, com rótulo e data de cada série.",
  },
  {
    numero: "04",
    titulo: "Macro global",
    fonte: "World Bank · Treasury",
    descricao:
      "Séries do Banco Mundial e do Tesouro dos EUA (Treasury): atividade e taxas de referência além da fronteira — o contexto internacional que também pressiona a tese, com rótulo e data de cada série.",
  },
  {
    numero: "05",
    titulo: "Elos causais",
    fonte: "Interpretação — fonte nas duas pontas",
    descricao:
      "Elos causais entre evento, commodity, setor e empresa — marcados como interpretação, em cenários condicionais, com fonte nas duas pontas de cada elo.",
    narrada: true,
  },
] as const;

const ENTREGA = [
  "Uma seção por dimensão (01–05), com fato e interpretação sempre separados no texto.",
  "Citações numeradas [n], remetendo ao registro de fontes ao final do documento.",
  "Registro de fontes: link, hospedeiro e o trecho exato citado — o caminho de auditoria de cada número.",
  "Lacunas declaradas como “dado não encontrado” quando a fonte não sustenta a afirmação — nunca uma estimativa.",
] as const;

const NAO_ENTREGA = [
  "Recomendação de compra, venda ou manutenção — em nenhuma hipótese.",
  "“Alvo” de preço ou qualquer sugestão de timing de mercado.",
  "Personalização ao perfil do investidor — a ferramenta estrutura o raciocínio; a decisão é sempre do leitor.",
] as const;

const INDICE = [
  { href: "#pipeline", label: "O pipeline" },
  ...CLAUSULAS.map((c) => ({ href: `#clausula-${c.numero}`, label: `${c.numero} · ${c.titulo}` })),
  { href: "#entrega", label: "O que a tese entrega" },
] as const;

function ChipFonte({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 border border-line-strong bg-card px-2 py-1 font-mono text-meta uppercase tracking-wide text-ink-3">
      Fonte · {children}
    </span>
  );
}

// Diagrama estrutural da dimensão 05 — SVG inline estático (sem
// dangerouslySetInnerHTML, CSP-safe). As classes `traco-elo`/`ponto-elo`
// (+ `ponto-elo-1`…`-4`, para o pulso em sequência) são os ganchos que o CSS
// de motion anima (stroke-dasharray/dashoffset + pulso único do ponto de
// origem, brief seção 4, assinatura 7 — ver globals.css). `pathLength={1}`
// normaliza o dash em 0–1 independente da geometria real de cada segmento.
// Fallback sem JS/CSS de motion: nenhuma classe esconde nada — o traço fica
// estático e sempre visível.
function TracoDoElo() {
  const nós = [
    { x: 40, rotulo: "Evento" },
    { x: 220, rotulo: "Commodity" },
    { x: 400, rotulo: "Setor" },
    { x: 580, rotulo: "Empresa" },
  ] as const;
  const y = 60;

  return (
    <figure className="flex flex-col gap-3">
      <svg
        viewBox="0 0 620 120"
        role="img"
        aria-labelledby="traco-elo-titulo"
        aria-describedby="traco-elo-desc"
        className="h-auto w-full max-w-none text-line-strong"
      >
        <title id="traco-elo-titulo">Diagrama causal: do evento geopolítico à empresa</title>
        <desc id="traco-elo-desc">
          Cadeia ilustrativa em quatro elos — evento geopolítico, commodity, setor e empresa —
          usada pela dimensão 05 para narrar interpretações, sempre com fonte nas duas pontas de
          cada elo.
        </desc>
        {nós.slice(0, -1).map((no, i) => {
          const proximo = nós[i + 1];
          return (
            <path
              key={no.rotulo}
              className="traco-elo"
              d={`M ${no.x + 8} ${y} L ${proximo.x - 8} ${y}`}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              pathLength={1}
            />
          );
        })}
        {nós.map((no, i) => (
          <g key={no.rotulo}>
            <circle className={`ponto-elo ponto-elo-${i + 1} fill-brasa`} cx={no.x} cy={y} r={5} />
            <text
              x={no.x}
              y={y + 28}
              textAnchor="middle"
              className="fill-ink-2 font-mono text-meta uppercase tracking-wide"
            >
              {no.rotulo}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="max-w-2xl font-sans text-ui text-ink-3">
        Ilustração estrutural do elo causal — não uma tese real; cada afirmação concreta continua
        exigindo fonte nas duas pontas.
      </figcaption>
    </figure>
  );
}

export default function ComoFuncionaPage() {
  return (
    <>
      <Header />
      {/* `newsreaderItalico.variable` (P1): a única outra rota (além de
          /tese) que renderiza itálico de verdade — a voz narrada da
          cláusula 05. */}
      <main id="conteudo" className={`${newsreaderItalico.variable} flex-1`}>
        {/* Masthead full-bleed (D5/E30 — migrado para a Bancada; o palco
            chega a 96rem, bem mais largo que o max-w-6xl de antes). Abre com
            o fio lapidário sangria-a-sangria (assinatura `.fio-travessa` de
            bancada.css + `.reveal-regua` — o "clac" de régua na largura
            inteira da viewport, não só do container). `.fio-travessa` só
            funciona como item DIRETO do grid `.bancada` (grid-column
            depende do container pai) — por isso vive dentro dele, não como
            irmão solto. */}
        <div className="bancada py-10 sm:py-14">
          <Reveal
            variant="reveal-regua"
            className="fio-travessa origin-left bg-line-strong"
            aria-hidden="true"
          >
            {null}
          </Reveal>
          <Reveal className="b-medida-esq mt-8 flex flex-col gap-3">
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              Como o motor monta uma tese
            </h1>
            <p className="text-body leading-relaxed text-ink-2">
              Do código do ativo ao documento auditável, em quatro etapas. Nenhuma delas
              é caixa-preta: no fim, dá para conferir de onde veio cada número —
              inclusive o que o motor se recusou a entregar.
            </p>
            <p className="text-body leading-relaxed text-ink-2">
              Você não precisa saber ler um balanço para usar a página: o motor faz o
              cruzamento e mostra o caminho. Quem já lê balanço ganha outra coisa — a
              chance de conferir cada passo, em vez de confiar na conclusão.
            </p>
            <p className="text-ui text-ink-3">
              Toda etapa abaixo termina do mesmo jeito: um número, uma fonte, uma data.
            </p>
          </Reveal>

          {/* ELEMENTO NOVO principal (direção §9): a mesma `CenaNascimento`
              (Server, SVG, ZERO JS) da landing, reusada aqui em versão
              ESTÁTICA — scrubbed por uma view-timeline NOMEADA CSS-only
              (`.oficina-cena-scrub`, cinema/como-funciona.css). R2 absoluto
              desta missão: zero gsap em rota interna — por isso NÃO importa
              `NascimentoScrub`. Sob `@supports not`, a regra some inteira e
              o SVG fica no estado FINAL (D16, lapidacao.css) — diagrama
              completo, nunca uma tela vazia. */}
          <div className="b-palco mt-12">
            <p className="mx-auto mb-4 max-w-2xl text-ui text-ink-3">
              Veja o mesmo processo em ação, com um número real: da fonte pública até a
              citação carimbada na tese.
            </p>
            <div className="oficina-cena-scrub">
              <CenaNascimento />
            </div>
          </div>
        </div>

        <div className="bancada py-10">
          <div className="b-palco grid gap-10 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-12">
            {/* Sumário: fixo na lateral no desktop, dobrável no mobile — mesmo
                padrão do sumário da tese (TeseView.tsx). */}
            <div className="lg:sticky lg:top-24 lg:self-start">
              {/* A3 (alvo ≥24px, WCAG 2.5.8): padding vai NO <summary> — é o
                  elemento focável/clicável de verdade; o <details> só molda
                  o card por fora. */}
              <details className="border border-line bg-card px-4 lg:hidden">
                <summary className="flex min-h-11 cursor-pointer items-center font-sans text-ui font-medium text-ink">
                  Sumário
                </summary>
                <div className="pb-3">
                  <IndiceNav items={INDICE} />
                </div>
              </details>
              <div className="hidden lg:block">
                <IndiceNav items={INDICE} />
              </div>
            </div>

            <div className="flex min-w-0 flex-col gap-16">
              {/* O pipeline */}
              <section id="pipeline" aria-labelledby="pipeline-titulo" className="flex flex-col gap-6">
                <Reveal variant="reveal-regua" className="h-px w-full bg-line-strong" aria-hidden="true">{null}</Reveal>
                <Reveal className="atraso-regua flex flex-col gap-6">
                  <h2 id="pipeline-titulo" className="font-display text-h2 font-semibold tracking-tight text-ink">
                    O pipeline
                  </h2>
                  {/* SEM overflow-hidden (a11y #1, 2026-07-13): os popups dos
                      4 <TermoTooltip> destas células abrem para CIMA e eram
                      clipados pelo ol — quebrava WCAG 1.4.13 (hoverable: o
                      mouse não alcançava o popup para ler/clicar "ver
                      glossário"). Custo: o reveal-ticker (translateY 12px,
                      opacity 0→1) transborda ≤12px durante a entrada —
                      imperceptível com o fade.

                      HORIZONTE (direção §9): as 4 células viram "estações de
                      bancada" — reusam o bisel/relevo de `.gema-chip`/
                      `.gema-chip__corpo` (gema.css, raia 1A) — numa fila
                      ASSIMÉTRICA (deslocamento vertical alternado por `<li>`,
                      nó DIFERENTE do que o Reveal anima — zero colisão de
                      escritor de `transform`), ligadas por um fio ESTÁTICO
                      "por fora das caixas" (linha absoluta atrás da fileira,
                      -z-10, decorativa). */}
                  <div className="relative">
                    <div
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-x-6 top-1/2 -z-10 hidden border-t border-line-strong sm:block"
                    />
                    <ol className="stagger grid gap-6 sm:grid-cols-2 lg:grid-cols-4 lg:gap-8">
                      {ETAPAS.map((etapa, i) => {
                        const desvio = [
                          "",
                          "lg:-translate-y-5",
                          "lg:translate-y-5",
                          "lg:-translate-y-2",
                        ][i];
                        return (
                          <li key={etapa.rotulo} className={desvio}>
                            <Reveal
                              variant="reveal-ticker"
                              className={`i-${i + 1} gema-chip block h-full`}
                            >
                              <div className="gema-chip__corpo flex h-full flex-col gap-2 bg-card p-5">
                                <span className="font-mono text-meta text-ink-3">{`0${i + 1}`}</span>
                                <span className="font-sans text-ui font-semibold text-ink">{etapa.rotulo}</span>
                                <p className="text-ui leading-relaxed text-ink-2">{etapa.texto}</p>
                              </div>
                            </Reveal>
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                </Reveal>
              </section>

              {/* As cinco dimensões */}
              <section id="dimensoes" aria-labelledby="dimensoes-titulo" className="flex flex-col gap-6">
                <Reveal variant="reveal-regua" className="h-px w-full bg-line-strong" aria-hidden="true">{null}</Reveal>
                <Reveal className="atraso-regua flex flex-col gap-2">
                  <h2 id="dimensoes-titulo" className="font-display text-h2 font-semibold tracking-tight text-ink">
                    As cinco dimensões
                  </h2>
                  <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                    Cada dimensão é uma camada de evidência com uma fonte oficial atrás:
                    demonstrações da CVM,{" "}
                    <TermoTooltip {...tooltipDe("informe-mensal-cvm")}>
                      informe mensal
                    </TermoTooltip>{" "}
                    dos FIIs, arquivos da SEC, séries do Banco Central e do Banco Mundial,
                    dados do{" "}
                    <TermoTooltip {...tooltipDe("stn")}>Tesouro Nacional</TermoTooltip>. A
                    régua impressa em cada tese mostra quais camadas entraram naquele ativo —
                    e quais não se aplicam.
                  </p>
                </Reveal>

                <div className="stagger flex flex-col gap-4">
                  {CLAUSULAS.map((c, i) => (
                    <Reveal
                      key={c.numero}
                      variant="reveal-ticker"
                      className={`i-${i + 1} grid gap-4 border border-line bg-card p-6 sm:grid-cols-[5rem_1fr]`}
                    >
                      <section
                        id={`clausula-${c.numero}`}
                        aria-labelledby={`clausula-${c.numero}-titulo`}
                        className="contents"
                      >
                        {/* `.paralaxe-numero` (2.4, propagação Onda 1D): mesmo
                            tratamento de /cobertura — profundidade de
                            camadas no folio grande da cláusula. */}
                        <span aria-hidden className="paralaxe-numero font-mono text-h1 font-semibold text-line-strong">
                          {c.numero}
                        </span>
                        <div className="flex flex-col gap-2">
                          <h3 id={`clausula-${c.numero}-titulo`} className="font-display text-h3 font-semibold text-ink">
                            {c.numero} · {c.titulo}
                          </h3>
                          {c.narrada ? (
                            // HORIZONTE (direção §9): a cláusula narrada ganha
                            // moldura de pull-quote em `--moldura-tinta`
                            // (nome antigo *ameixa* aposentado — rename atômico
                            // da Onda 0.5 OURIVESARIA, achado 39; DESIGN-TOKENS.md,
                            // "keyline 1px de molduras editoriais... pull-
                            // quotes"), reusando o mesmo Tailwind estático de
                            // /tese (`border-moldura-tinta`) — zero CSS novo.
                            <blockquote className="max-w-prose border-l-2 border-moldura-tinta pl-5 font-display-italico text-lede italic font-medium leading-relaxed text-ink-2">
                              {c.descricao}
                            </blockquote>
                          ) : (
                            <p className="max-w-prose text-body leading-relaxed text-ink-2">
                              {c.descricao}
                            </p>
                          )}
                          <ChipFonte>{c.fonte}</ChipFonte>
                          {c.narrada && (
                            // "TracoDoElo ganha palco largo" (direção §9): o
                            // diagrama deixa de ficar preso ao max-w-2xl da
                            // coluna estreita — o card em si já é bem mais
                            // largo agora (rota migrada ao b-palco, D5/E30),
                            // então liberar a largura do SVG aqui é o que o
                            // torna visivelmente maior.
                            <div className="mt-2 w-full">
                              <TracoDoElo />
                            </div>
                          )}
                        </div>
                      </section>
                    </Reveal>
                  ))}
                </div>
              </section>

              {/* O que entrega / não entrega — faixa de postura CVM */}
              <section id="entrega" aria-labelledby="entrega-titulo" className="flex flex-col gap-6">
                <Reveal variant="reveal-regua" className="h-px w-full bg-line-strong" aria-hidden="true">{null}</Reveal>
                <Reveal className="atraso-regua flex flex-col gap-2">
                  <h2 id="entrega-titulo" className="font-display text-h2 font-semibold tracking-tight text-ink">
                    O que a tese entrega — e o que não entrega
                  </h2>
                  <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                    A lista abaixo é curta de propósito. O que está à esquerda, você pode
                    auditar; o que está à direita, não existe aqui — e não vai passar a
                    existir.
                  </p>
                </Reveal>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-3 border border-line bg-card p-6">
                    <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3 [font-stretch:72%]">
                      Entrega
                    </span>
                    <ul className="flex flex-col gap-2">
                      {ENTREGA.map((item) => (
                        <li key={item} className="flex gap-2 text-ui leading-relaxed text-ink-2">
                          <span aria-hidden className="font-mono text-brasa-texto">
                            →
                          </span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="flex flex-col gap-3 border border-line bg-card p-6">
                    <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3 [font-stretch:72%]">
                      Não entrega
                    </span>
                    <ul className="flex flex-col gap-2">
                      {NAO_ENTREGA.map((item) => (
                        <li key={item} className="flex gap-2 text-ui leading-relaxed text-ink-2">
                          <span aria-hidden className="font-mono text-ink-3">
                            —
                          </span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 border border-line bg-card px-6 py-5">
                  <p className="flex-1 text-ui text-ink-2">
                    Quer ver esse pipeline aplicado a um caso real? Abra uma tese pronta e
                    siga qualquer número até a fonte.
                  </p>
                  <Link
                    href="/teses"
                    className="sublinhado-brasa font-sans text-ui font-semibold text-brasa-texto"
                  >
                    Ver teses →
                  </Link>
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
