import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { Reveal } from "@/components/motion/Reveal";
import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { TermoTooltip } from "@/components/ui/TermoTooltip";
import { tooltipDe } from "@/lib/glossario";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

// Copy reescrita na missão APOTEOSE (crit. 11): vendedora pela verdade
// auditável — zero superlativo não-auditável, zero recomendação, número só
// derivado do catálogo. Tooltips consomem lib/glossario.ts (D7).
export const metadata: Metadata = {
  title: "Sobre",
  description:
    "O contrato de leitura do Tese AI: nenhuma ordem de compra ou de venda, todo número com fonte e data, lacuna declarada — e elos causais com fonte nas duas pontas. A postura da regulação CVM tratada como honra, não como letra miúda.",
  openGraph: {
    title: "Sobre — Tese AI",
    description:
      "Quatro cláusulas auditáveis: sem ordem de compra ou de venda, todo número com fonte e data, lacuna declarada, elo causal com fonte nas duas pontas.",
  },
};

type Clausula = {
  numero: string;
  titulo: string;
  texto: ReactNode;
};

// Enxerto NORMA #3 (unânime): os princípios inegociáveis do produto, não
// slogans — cada um corresponde a uma regra aplicada no motor (AGENTS.md /
// ARQUITETURA.md). Reescrita APOTEOSE: mesmo contrato, mais contexto — a
// cláusula diz o que o motor faz E por que isso protege quem lê.
const CLAUSULAS: Clausula[] = [
  {
    numero: "01",
    titulo: "Não emitimos ordem de compra nem de venda.",
    texto: (
      <>
        A plataforma estrutura a tese — síntese,{" "}
        <TermoTooltip {...tooltipDe("contra-tese")}>contra-tese</TermoTooltip>, riscos e
        elos — e para ali, deliberadamente. Nenhuma frase diz o que fazer com o ativo:
        sem ordem de compra ou de venda, sem “alvo” de preço, sem timing. A decisão é
        sempre do leitor. Tratamos a postura que a regulação da CVM espera de uma
        ferramenta de estruturação como honra da casa, não como letra miúda — é o que
        separa análise organizada de recomendação disfarçada.
      </>
    ),
  },
  {
    numero: "02",
    titulo: "Todo número com fonte e data.",
    texto: (
      <>
        Cada afirmação factual sai ancorada em citação verificável (
        <TermoTooltip {...tooltipDe("citations")}>Anthropic Citations</TermoTooltip>
        ): link, hospedeiro e o trecho exato do documento público de origem, com a data.
        Sem citação, a afirmação não entra como fato — ou vira interpretação rotulada,
        ou sai do texto. Qualquer leitor pode refazer o caminho de qualquer número até a
        fonte.
      </>
    ),
  },
  {
    numero: "03",
    titulo: "Lacuna declarada, nunca preenchida.",
    texto: (
      <>
        Quando o dado público não existe, não foi publicado ou não foi encontrado, a
        tese registra “dado não encontrado” no lugar exato onde o número estaria — e
        segue. Abster é mais honesto do que estimar: a lacuna visível preserva a
        auditoria; um número inventado contaminaria a tese inteira.
      </>
    ),
  },
  {
    numero: "04",
    titulo: "O diferencial: elos causais narrados, com fonte nas duas pontas.",
    texto: (
      <>
        A camada que liga evento, commodity, setor e empresa é interpretação — e é
        apresentada como tal, em cenários condicionais, nunca como fato. A disciplina:
        cada ponta do <TermoTooltip {...tooltipDe("elo-causal")}>elo</TermoTooltip>{" "}
        carrega sua própria fonte e data. É o diferencial do motor — e, por isso mesmo,
        a parte mais vigiada dele.
      </>
    ),
  },
];

// Método resumido — dimensões canônicas verificadas em
// backend/app/services/orquestracao.py (ARQUITETURA.md, fonte factual).
const METODO = [
  { id: "D1", titulo: "Fundamentos", fonte: "CVM" },
  { id: "D2", titulo: "Pares globais", fonte: "SEC EDGAR" },
  { id: "D3", titulo: "Macro Brasil", fonte: "BCB, Brent" },
  { id: "D4", titulo: "Macro global", fonte: "World Bank, Treasury" },
  { id: "D5", titulo: "Elos causais", fonte: "cross-dimensão" },
] as const;

const FONTES_PUBLICAS = [
  "CVM",
  "SEC EDGAR",
  "Banco Central do Brasil (BCB)",
  "World Bank",
  "Tesouro Nacional",
] as const;

export default function Sobre() {
  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        <section aria-labelledby="sobre-titulo" className="border-b border-line">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-14 sm:px-6 sm:py-20">
            {/* D7 (baixa): `atraso-regua` presume uma régua irmã logo antes —
                aqui não há nenhuma. Stagger simples (.i-N). */}
            <Reveal className="i-1">
              <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
                Sobre
              </p>
            </Reveal>
            <Reveal className="i-2">
              <h1
                id="sobre-titulo"
                className="max-w-2xl font-display text-h1 font-semibold tracking-tight text-ink"
              >
                Quatro cláusulas. Nenhuma promessa que não se possa auditar.
              </h1>
            </Reveal>
            <Reveal className="i-3">
              <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                O Tese AI faz uma coisa: estrutura o raciocínio de investimento com
                evidência verificável. O que a plataforma afirma, ela mostra de onde
                veio; o que não consegue sustentar, declara que falta. Esta página é o
                contrato de leitura — e ele vale para toda tese que sai do motor, sem
                exceção.
              </p>
            </Reveal>
          </div>
        </section>

        <div className="mx-auto grid w-full max-w-5xl gap-12 px-4 py-14 sm:px-6 md:grid-cols-[1.6fr_1fr]">
          {/* Manifesto — cláusulas numeradas */}
          <section aria-labelledby="clausulas-titulo" className="flex flex-col">
            <h2 id="clausulas-titulo" className="sr-only">
              Princípios
            </h2>
            <Reveal
              variant="reveal-regua"
              className="mb-8 h-px w-full origin-left bg-line-strong"
              aria-hidden
            >
              {null}
            </Reveal>
            {CLAUSULAS.map((clausula, i) => (
              <article
                key={clausula.numero}
                className={i > 0 ? "mt-10 border-t border-line-strong pt-10" : ""}
              >
                <Reveal className={`stagger i-${i + 1} flex gap-6`}>
                  <span
                    aria-hidden
                    className="font-mono text-h2 font-semibold text-line-strong"
                  >
                    {clausula.numero}
                  </span>
                  <div className="flex flex-col gap-3">
                    <h3 className="font-display text-h2 font-semibold leading-tight tracking-tight text-ink">
                      {clausula.titulo}
                    </h3>
                    <p className="max-w-[65ch] text-body leading-relaxed text-ink-2">
                      {clausula.texto}
                    </p>
                  </div>
                </Reveal>
              </article>
            ))}
          </section>

          {/* Coluna secundária: método + fontes */}
          <aside aria-labelledby="metodo-titulo" className="flex flex-col gap-10">
            <div className="flex flex-col gap-4">
              <h2
                id="metodo-titulo"
                className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3"
              >
                Método — até cinco dimensões
              </h2>
              <ol className="flex flex-col gap-3 border-t border-line">
                {METODO.map((dimensao) => (
                  <li
                    key={dimensao.id}
                    className="flex items-baseline justify-between gap-3 border-b border-line py-2"
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="font-mono text-meta font-semibold text-brasa-texto">
                        {dimensao.id}
                      </span>
                      <span className="text-ui text-ink">{dimensao.titulo}</span>
                    </span>
                    <span className="font-mono text-meta text-ink-3">{dimensao.fonte}</span>
                  </li>
                ))}
              </ol>
              <p className="font-mono text-meta text-ink-3">
                O quadro completo vale para as ações da B3; FIIs e títulos do Tesouro
                Direto usam um subconjunto próprio de dimensões, cada uma com sua fonte —
                a régua impressa em cada tese mostra exatamente quais entraram.
              </p>
            </div>

            <div className="flex flex-col gap-4">
              <h2 className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
                Fontes públicas usadas
              </h2>
              <ul className="flex flex-col gap-1 font-mono text-meta text-ink-2">
                {FONTES_PUBLICAS.map((fonte) => (
                  <li key={fonte}>{fonte}</li>
                ))}
              </ul>
              <p className="font-mono text-meta text-ink-3">
                Todas abertas: qualquer citação de qualquer tese pode ser conferida na
                origem, sem cadastro e sem intermediário.
              </p>
            </div>
          </aside>
        </div>

        {/* Fecho — o contrato aplicado, não prometido. */}
        <section aria-labelledby="fecho-titulo" className="border-t border-line">
          <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
            <div className="flex flex-wrap items-center gap-3 border border-line bg-card px-6 py-5">
              <p className="flex-1 text-ui text-ink-2">
                <span id="fecho-titulo" className="font-semibold text-ink">
                  O contrato acima não é aspiração
                </span>{" "}
                — é o que está impresso em cada tese da galeria, hoje. Abra uma com olho
                de auditor: siga um número qualquer até a fonte.
              </p>
              <LinkCinema
                href="/teses"
                className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
              >
                Ver as teses prontas →
              </LinkCinema>
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
