import Link from "next/link";

import { Reveal } from "@/components/motion/Reveal";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta — mesma regra de toda página
// nova (ARQUITETURA.md, rail 5).
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Como funciona",
  description:
    "Como o motor do Tese AI monta uma tese: as cinco dimensões de dados com suas fontes oficiais, a síntese com citações verificáveis e a tese auditável que sai no fim — sem recomendação de compra ou venda.",
};

// Etapas do pipeline (ARQUITETURA.md, contrato TeseOut + orquestracao.py do
// backend): ticker validado → ingestão por dimensão → síntese com citações
// (Anthropic Citations) → documento com bull×bear e lacunas declaradas.
const ETAPAS = [
  {
    rotulo: "Ticker",
    texto: "Código B3 validado no formato oficial de negociação.",
  },
  {
    rotulo: "Ingestão",
    texto: "As cinco dimensões abaixo, cada uma buscada na sua fonte oficial.",
  },
  {
    rotulo: "Síntese com citações",
    texto: "Anthropic Citations: cada afirmação factual sai ligada ao trecho-fonte.",
  },
  {
    rotulo: "Tese auditável",
    texto: "Síntese e contra-tese (bull × bear), com lacunas declaradas, nunca estimadas.",
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
  "Registro de fontes: link, hospedeiro e o trecho exato citado.",
  "Lacunas declaradas como “dado não encontrado” quando a fonte não sustenta a afirmação — nunca uma estimativa.",
] as const;

const NAO_ENTREGA = [
  "Recomendação de compra, venda ou manutenção.",
  "Preço-alvo ou qualquer sugestão de timing de mercado.",
  "Personalização ao perfil do investidor — a ferramenta estrutura o raciocínio; a decisão é sempre do leitor.",
] as const;

const INDICE = [
  { href: "#pipeline", label: "O pipeline" },
  ...CLAUSULAS.map((c) => ({ href: `#clausula-${c.numero}`, label: `${c.numero} · ${c.titulo}` })),
  { href: "#entrega", label: "O que a tese entrega" },
] as const;

function IndiceNav() {
  return (
    <nav aria-label="Sumário desta página" className="text-ui">
      <p className="mb-3 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3 [font-stretch:72%]">
        Sumário
      </p>
      <ol className="flex flex-col gap-1 border-l border-line">
        {INDICE.map((item) => (
          <li key={item.href}>
            <a
              href={item.href}
              className="sublinhado-brasa block border-l-2 border-transparent py-1 pl-3 font-sans text-ui leading-snug text-ink-2 hover:text-ink"
            >
              {item.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function ChipFonte({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 border border-line-strong bg-card px-2 py-1 font-mono text-meta uppercase tracking-wide text-ink-3">
      Fonte · {children}
    </span>
  );
}

// Diagrama estrutural da dimensão 05 — SVG inline estático (sem
// dangerouslySetInnerHTML, CSP-safe). As classes `traco-elo`/`ponto-elo` são
// os ganchos que a onda de motion vai animar (stroke-dasharray/dashoffset +
// pulso único do ponto de origem, brief seção 4, assinatura 7); aqui a
// estrutura fica semântica e sempre visível mesmo sem a animação.
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
        className="h-auto w-full max-w-2xl text-line-strong"
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
            />
          );
        })}
        {nós.map((no) => (
          <g key={no.rotulo}>
            <circle className="ponto-elo fill-brasa" cx={no.x} cy={y} r={5} />
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
      <main id="conteudo" className="flex-1">
        <div className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
          <Reveal className="max-w-2xl">
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              Como funciona
            </h1>
            <p className="mt-3 text-body leading-relaxed text-ink-2">
              O motor monta a tese por camadas: cinco dimensões de dados, cada uma com sua fonte
              oficial, sintetizadas com citações verificáveis até um documento auditável — nunca
              uma recomendação.
            </p>
          </Reveal>

          <div className="mt-10 grid gap-10 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-12">
            {/* Sumário: fixo na lateral no desktop, dobrável no mobile — mesmo
                padrão do sumário da tese (TeseView.tsx). */}
            <div className="lg:sticky lg:top-24 lg:self-start">
              <details className="border border-line bg-card px-4 py-3 lg:hidden">
                <summary className="cursor-pointer font-sans text-ui font-medium text-ink">
                  Sumário
                </summary>
                <div className="pt-3">
                  <IndiceNav />
                </div>
              </details>
              <div className="hidden lg:block">
                <IndiceNav />
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
                  <ol className="stagger grid gap-px overflow-hidden border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
                    {ETAPAS.map((etapa, i) => (
                      <li key={etapa.rotulo} className={`reveal-ticker i-${i + 1} flex flex-col gap-2 bg-card p-5`}>
                        <span className="font-mono text-meta text-ink-3">{`0${i + 1}`}</span>
                        <span className="font-sans text-ui font-semibold text-ink">{etapa.rotulo}</span>
                        <p className="text-ui leading-relaxed text-ink-2">{etapa.texto}</p>
                      </li>
                    ))}
                  </ol>
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
                    Cada cláusula abaixo é buscada e citada na fonte oficial correspondente; a
                    síntese final separa sempre o que é fato do que é interpretação.
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
                        <span aria-hidden className="font-mono text-h1 font-semibold text-line-strong">
                          {c.numero}
                        </span>
                        <div className="flex flex-col gap-2">
                          <h3 id={`clausula-${c.numero}-titulo`} className="font-display text-h3 font-semibold text-ink">
                            {c.numero} · {c.titulo}
                          </h3>
                          <p
                            className={
                              c.narrada
                                ? "max-w-prose font-display text-lede italic font-medium leading-relaxed text-ink-2"
                                : "max-w-prose text-body leading-relaxed text-ink-2"
                            }
                          >
                            {c.descricao}
                          </p>
                          <ChipFonte>{c.fonte}</ChipFonte>
                          {c.narrada && (
                            <div className="mt-2">
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
                    A ferramenta estrutura o raciocínio de investimento; a decisão é sempre do
                    leitor — postura alinhada à regulação da CVM.
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
                    Quer ver o resultado? Abra uma tese pronta ou gere a de um ticker da B3.
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
