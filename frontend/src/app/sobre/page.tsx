import type { Metadata } from "next";
import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { Reveal } from "@/components/motion/Reveal";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sobre",
  description:
    "Os princípios do Tese AI: não recomenda compra ou venda, todo número vem com fonte e data, lacuna é declarada e nunca preenchida por chute.",
};

type Clausula = {
  numero: string;
  titulo: string;
  texto: string;
};

// Enxerto NORMA #3 (unânime): os princípios inegociáveis do produto, não
// slogans — cada um corresponde a uma regra aplicada no motor (AGENTS.md /
// ARQUITETURA.md).
const CLAUSULAS: Clausula[] = [
  {
    numero: "01",
    titulo: "Não recomendamos compra nem venda.",
    texto:
      "O Tese AI estrutura o raciocínio de investimento; não emite “compre”, “venda” ou preço-alvo. A decisão é sempre do leitor — postura alinhada à regulação da CVM.",
  },
  {
    numero: "02",
    titulo: "Todo número com fonte e data.",
    texto:
      "Cada afirmação factual sai ancorada em citações verificáveis (Anthropic Citations), com link e data da fonte pública de origem. Sem citação, a afirmação não entra como fato.",
  },
  {
    numero: "03",
    titulo: "Lacuna declarada, nunca preenchida.",
    texto:
      "Quando o dado público não existe ou não foi encontrado, a tese registra “dado não encontrado” e segue adiante. Abster é mais honesto do que estimar — uma lacuna nunca vira número inventado.",
  },
  {
    numero: "04",
    titulo: "O diferencial: elos causais narrados, com fonte nas duas pontas.",
    texto:
      "A camada que liga evento, commodity, setor e empresa é interpretação — marcada como tal, em cenários condicionais — mas nunca solta: cada ponta do elo carrega sua própria fonte e data.",
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
                Quatro cláusulas que valem mais do que qualquer slogan.
              </h1>
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
                O quadro completo vale para as ações da B3; FIIs e títulos do Tesouro Direto usam
                um subconjunto próprio de dimensões, cada uma com sua fonte.
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
            </div>
          </aside>
        </div>
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
