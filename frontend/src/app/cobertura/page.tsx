import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { Reveal } from "@/components/motion/Reveal";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Cobertura",
  description:
    "O que o Tese AI cobre hoje: teses completas para ações da B3, FIIs e títulos do Tesouro Direto, com exemplos pré-gerados que abrem na hora.",
};

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

type ClasseInvestimento = {
  numero: string;
  titulo: string;
  descricao: string;
  disponivel: boolean;
  // Exemplo pronto (cache aquecido) desta classe — cada classe leva a um
  // ticker distinto em vez do genérico "/tese" (Fase 2 multiativo).
  href: string;
};

const CLASSES: ClasseInvestimento[] = [
  {
    numero: "01",
    titulo: "Ações B3",
    descricao:
      "Qualquer companhia aberta com cadastro na CVM. A tese cruza fundamentos, pares globais, macro e geopolítica em cinco dimensões, fechada com síntese e contra-tese.",
    disponivel: true,
    href: "/tese",
  },
  {
    numero: "02",
    titulo: "FIIs",
    descricao:
      "Fundos de investimento imobiliário listados na B3 — mesma disciplina de fonte e citação das ações, com o informe mensal da CVM como eixo próprio de fundamentos.",
    disponivel: true,
    href: "/tese?ticker=HGLG11",
  },
  {
    numero: "03",
    titulo: "Renda fixa / Tesouro",
    descricao:
      "Títulos públicos do Tesouro Direto — taxas e preços com Data Base, marcação a mercado e cenário de juros e inflação, sempre separados de qualquer sugestão de compra ou carrego.",
    disponivel: true,
    href: "/tese?ticker=TD-IPCA-2035",
  },
];

// D6 (hierarquia de banca, CORRECOES-RODADA-1.md): Ações é sempre a
// capa-lead (primeira entrada de CLASSES); FIIs e Renda fixa formam o par
// secundário abaixo dela.
const [CLASSE_LEAD, ...CLASSES_SECUNDARIAS] = CLASSES;

type TipoDeTese = {
  numero: string;
  titulo: string;
  descricao: string;
};

const TIPOS: TipoDeTese[] = [
  {
    numero: "01",
    titulo: "Tese completa sob demanda",
    descricao:
      "Processada na hora para qualquer código válido — ação da B3, FII ou título do Tesouro Direto. As dimensões variam por classe: ações cruzam cinco (fundamentos, pares globais, macro Brasil, macro global e elos causais); FIIs, três (informe mensal CVM, macro de juros e elos); Tesouro, três (taxas e preços da STN, juros e inflação e elos) — cada uma com sua fonte.",
  },
  {
    numero: "02",
    titulo: "Exemplos pré-gerados",
    descricao:
      "Um lote fixo de ativos mantido em cache pelo motor e renovado a cada ciclo diário: abrem instantaneamente, sem custo de geração, com a mesma trilha de citações.",
  },
];

export default function Cobertura() {
  // Contagem derivada do catálogo (nunca hardcoded — mesma convenção de
  // app/teses/page.tsx): a copy não diverge do conjunto real quando um
  // exemplo entra/sai de EXEMPLOS_PRONTOS.
  const exemplos = exemplosProntos();
  const acoes = exemplos.filter((p) => (p.classe ?? "acao") === "acao").length;
  const fiis = exemplos.filter((p) => p.classe === "fii").length;
  const rendaFixa = exemplos.filter((p) => p.classe === "renda_fixa").length;

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Abertura */}
        <section className="border-b border-line">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-14 sm:px-6 sm:py-20">
            {/* D7 (baixa): `atraso-regua` presume uma régua irmã (Impressão de
                Régua) logo antes — aqui não há nenhuma, então o delay de
                80ms não tinha o que "esperar". Stagger simples (.i-N). */}
            <Reveal className="i-1">
              <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
                Cobertura
              </p>
            </Reveal>
            <Reveal className="i-2">
              <h1 className="max-w-2xl font-display text-h1 font-semibold tracking-tight text-ink">
                O que está impresso nesta edição.
              </h1>
            </Reveal>
            <Reveal className="i-3">
              <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                Cobertura completa para as ações da B3; FIIs pelo informe
                mensal da CVM; em renda fixa, os títulos públicos do Tesouro
                Direto — a mesma disciplina de fonte e citação nas três
                classes.
              </p>
            </Reveal>
          </div>
        </section>

        {/* Classes de investimento */}
        <section aria-labelledby="classes-titulo" className="border-b border-line">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <Reveal
              variant="reveal-regua"
              className="h-px w-full origin-left bg-line-strong"
              aria-hidden
            >
              {null}
            </Reveal>
            <h2
              id="classes-titulo"
              className="atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
            >
              Classes de investimento
            </h2>
            {/* D6 (hierarquia de banca): Ações é a capa-lead (largura/proeminência
                maior); FIIs + Renda fixa formam o par secundário abaixo — mesma
                estrutura completa. As 3 classes estão `disponivel: true` hoje
                (Fase 2 multiativo); o selo "Em breve" abaixo fica dormente,
                pronto para uma futura classe ainda não coberta, sem precisar
                reescrever o layout quando isso acontecer. */}
            <div className="stagger flex flex-col gap-4">
              <Reveal
                variant="reveal-ticker"
                className="cartao-ticker i-1 flex flex-col gap-5 border-2 border-line-strong bg-card p-8 sm:flex-row sm:items-center sm:gap-8"
              >
                <span
                  aria-hidden
                  className="font-mono text-h1 font-semibold text-line-strong sm:shrink-0"
                >
                  {CLASSE_LEAD.numero}
                </span>
                <div className="flex flex-1 flex-col gap-3">
                  <h3 className="font-display text-h1 font-semibold tracking-tight text-ink">
                    {CLASSE_LEAD.titulo}
                  </h3>
                  <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                    {CLASSE_LEAD.descricao}
                  </p>
                  {CLASSE_LEAD.disponivel && (
                    <Link
                      href={CLASSE_LEAD.href}
                      className="mt-1 inline-flex min-h-11 w-fit items-center bg-brasa px-6 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                    >
                      Gerar tese →
                    </Link>
                  )}
                </div>
              </Reveal>

              <ul className="grid gap-4 sm:grid-cols-2">
                {CLASSES_SECUNDARIAS.map((classe, i) => (
                  <li key={classe.numero}>
                    <Reveal
                      variant="reveal-ticker"
                      className={`cartao-ticker i-${i + 2} flex h-full flex-col gap-4 border border-line bg-card p-6`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <span
                          aria-hidden
                          className="font-mono text-h3 font-semibold text-line-strong"
                        >
                          {classe.numero}
                        </span>
                        {!classe.disponivel && (
                          <span className="border border-aviso-borda bg-aviso-fundo px-2 py-1 font-sans text-label font-semibold uppercase tracking-[0.16em] text-aviso-texto">
                            Em breve
                          </span>
                        )}
                      </div>
                      <div className="flex flex-1 flex-col gap-2">
                        <h3 className="font-display text-h3 font-semibold text-ink">
                          {classe.titulo}
                        </h3>
                        <p className="text-ui leading-relaxed text-ink-2">
                          {classe.descricao}
                        </p>
                      </div>
                      {classe.disponivel ? (
                        <Link
                          href={classe.href}
                          className="mt-2 inline-flex min-h-11 w-fit items-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                        >
                          Gerar tese →
                        </Link>
                      ) : (
                        <p className="mt-2 font-sans text-meta text-ink-3">
                          Em desenvolvimento — parte da Fase 2 multiativo do
                          motor. Sem previsão de data.
                        </p>
                      )}
                    </Reveal>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Tipos de tese */}
        <section aria-labelledby="tipos-titulo">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <Reveal
              variant="reveal-regua"
              className="h-px w-full origin-left bg-line-strong"
              aria-hidden
            >
              {null}
            </Reveal>
            <h2
              id="tipos-titulo"
              className="atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
            >
              Tipos de tese
            </h2>
            <ul className="stagger grid gap-4 sm:grid-cols-2">
              {TIPOS.map((tipo, i) => (
                <li key={tipo.numero}>
                  <Reveal
                    variant="reveal-ticker"
                    className={`i-${i + 1} flex h-full flex-col gap-2 border border-line bg-card p-6`}
                  >
                    <span
                      aria-hidden
                      className="font-mono text-h3 font-semibold text-line-strong"
                    >
                      {tipo.numero}
                    </span>
                    <h3 className="font-display text-h3 font-semibold text-ink">
                      {tipo.titulo}
                    </h3>
                    <p className="text-ui leading-relaxed text-ink-2">{tipo.descricao}</p>
                  </Reveal>
                </li>
              ))}
            </ul>
            <p className="font-mono text-meta text-ink-3">
              {exemplos.length} exemplos em cache · os {acoes} maiores pesos da
              carteira teórica do Ibovespa (B3, {formatDataIso(DATA_CARTEIRA_IBOV)}
              ) + {fiis} FII + {rendaFixa} Tesouro Direto ·{" "}
              <Link href="/teses" className="sublinhado-brasa text-brasa-texto">
                ver a galeria completa
              </Link>
            </p>
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
