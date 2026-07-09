import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { Reveal } from "@/components/motion/Reveal";
import { DATA_CARTEIRA_IBOV, EXEMPLOS_PRONTOS } from "@/lib/tickers";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Cobertura",
  description:
    "O que o Tese AI cobre hoje: teses completas para qualquer papel da B3, exemplos pré-gerados que abrem na hora, e o roadmap honesto para FIIs e renda fixa.",
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
};

const CLASSES: ClasseInvestimento[] = [
  {
    numero: "01",
    titulo: "Ações B3",
    descricao:
      "Qualquer companhia aberta com cadastro na CVM. A tese cruza fundamentos, pares globais, macro e geopolítica em cinco dimensões, fechada com síntese e contra-tese.",
    disponivel: true,
  },
  {
    numero: "02",
    titulo: "FIIs",
    descricao:
      "Fundos de investimento imobiliário listados na B3 — mesma disciplina de fonte e citação das ações, adaptada aos indicadores do setor.",
    disponivel: false,
  },
  {
    numero: "03",
    titulo: "Renda fixa / Tesouro",
    descricao:
      "Títulos públicos e privados de renda fixa, com curva de juros e risco de crédito como eixos próprios de análise.",
    disponivel: false,
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
      "As cinco dimensões processadas na hora para qualquer ticker válido da B3 — fundamentos, pares globais, macro Brasil, macro global e elos causais, cada um com sua fonte.",
  },
  {
    numero: "02",
    titulo: "Exemplos pré-gerados",
    descricao:
      "Um lote fixo de papéis mantido em cache pelo motor e renovado a cada ciclo diário: abrem instantaneamente, sem custo de geração, com a mesma trilha de citações.",
  },
];

export default function Cobertura() {
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
                O que está impresso nesta edição — e o que ainda está no prelo.
              </h1>
            </Reveal>
            <Reveal className="i-3">
              <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                Ações da B3 têm cobertura completa hoje. FIIs e renda fixa
                estão no roadmap, anunciados com a mesma dignidade — sem data
                prometida, porque não temos uma para dar.
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
                estrutura completa (selo "Em breve" preservado, gaveta presente
                mas trancada, nunca meio-tom apagado). */}
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
                      href="/tese"
                      className="mt-1 inline-flex w-fit items-center bg-brasa px-6 py-3 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
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
                          href="/tese"
                          className="mt-2 inline-flex w-fit items-center bg-brasa px-4 py-2 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
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
              {EXEMPLOS_PRONTOS.length} exemplos em cache · carteira teórica do
              Ibovespa (B3, {formatDataIso(DATA_CARTEIRA_IBOV)}) ·{" "}
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
