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
//
// Copy HORIZONTE (copy-horizonte-spec.md §6, verbatim — só o `texto` de cada
// cláusula mudou; `titulo` é rótulo estável, não coberto pelo spec): as 4
// cláusulas viram placas gravadas (cinema/gema.css, `.placa-gravada` — D14/
// C6, "mesma gramática da Sala do Contrato").
const CLAUSULAS: Clausula[] = [
  {
    numero: "01",
    titulo: "Não emitimos ordem de compra nem de venda.",
    texto: (
      <>
        Nenhuma ordem de compra ou de venda, nenhum “alvo” de preço, nenhuma sugestão de
        momento. A ferramenta organiza o raciocínio e expõe os dois lados; a decisão é
        sempre do leitor — é o que a regulação da CVM espera, e é o que a casa trata como
        honra.
      </>
    ),
  },
  {
    numero: "02",
    titulo: "Todo número com fonte e data.",
    texto: (
      <>
        Toda afirmação factual sai com{" "}
        <TermoTooltip {...tooltipDe("citations")}>citação</TermoTooltip>, fonte pública e
        data. Um número inventado contaminaria a tese inteira — por isso a regra não tem
        exceção, nem para o dado mais banal.
      </>
    ),
  },
  {
    numero: "03",
    titulo: "Lacuna declarada, nunca preenchida.",
    texto: (
      <>
        Quando a fonte não tem o dado, a tese registra a{" "}
        <TermoTooltip {...tooltipDe("lacuna-declarada")}>lacuna</TermoTooltip> e segue.
        Abster é mais honesto que estimar: o buraco fica visível, e você sabe exatamente
        onde a evidência acaba.
      </>
    ),
  },
  {
    numero: "04",
    titulo: "O diferencial: elos causais narrados, com fonte nas duas pontas.",
    // Correção (defeito 5, gate copy wt-horizonte 2026-07-14): a 1ª frase do
    // corpo repetia o título verbatim (mesmo texto empilhado 2x na tela).
    // Reescrita sem duplicar o título e sem novo toque da metáfora da
    // joalheria (teto 2-3 no site, §11 do spec — nenhuma palavra nova).
    texto: (
      <>
        Aqui a tese interpreta, não só relata:{" "}
        <TermoTooltip {...tooltipDe("elo-causal")}>elos causais</TermoTooltip> narrados,
        com fonte nas duas pontas. É a parte interpretativa da tese — e justamente por
        isso a mais vigiada: vem rotulada como interpretação, em cenários condicionais,
        nunca como fato.
      </>
    ),
  },
];

// C6/E27 — coluna desalinhada: deslocamento CUMULATIVO de ~1rem por placa no
// desktop (mobile ~0,5rem) — a "escada" de A/C, mesma gramática da Sala do
// Contrato (page.tsx #postura). Zero style inline: só classes Tailwind.
const DESLOCAMENTO_PLACA = ["", "ml-2 md:ml-4", "ml-4 md:ml-8", "ml-6 md:ml-12"] as const;

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

// Migração HORIZONTE (D3/D5/E30, "A Bancada" — cinema/bancada.css): os 3
// containers `mx-auto max-w-5xl` da recon (sobre:120/148/237) viram grades
// `.bancada`. E30 — mini-gate de largura: o masthead fica em `medida`
// (prosa ≤68ch, lei D3 — já era ~max-w-2xl/672px antes, não regride); as
// duas seções de conteúdo (cláusulas+aside e o fecho) usam `.b-palco`
// (~96rem/1536px de teto) — MAIS largas que o max-w-5xl (1024px) anterior,
// nunca mais estreitas (prova: screenshot local vs baseline :3010).
export default function Sobre() {
  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        <section aria-labelledby="sobre-titulo" className="border-b border-line">
          <div className="bancada gap-y-4 py-14 sm:py-20">
            {/* D7 (baixa): `atraso-regua` presume uma régua irmã logo antes —
                aqui não há nenhuma. Stagger simples (.i-N).
                E30 (correção-mãe, wt-horizonte 2026-07-14): este masthead
                vivia no default `.bancada > *` (medida sozinha, sem palco
                nenhum) — a pior das três rotas regredidas (-50px em
                768–1024px). Eyebrow e H1 não são prosa (medida ≤68ch é lei só
                para prosa, §0.9): ganham `.b-palco`. Os dois parágrafos de
                prosa real ganham `.b-medida-esq` (mais generoso que a medida
                pura, ainda ≤68ch de fato — nunca mais estreito que antes). */}
            <Reveal className="b-palco i-1">
              <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
                Sobre
              </p>
            </Reveal>
            <Reveal className="b-palco i-2">
              <h1
                id="sobre-titulo"
                className="font-display text-h1 font-semibold tracking-tight text-ink"
              >
                Quatro cláusulas. Nenhuma promessa que não se possa auditar.
              </h1>
            </Reveal>
            <Reveal className="b-medida-esq i-3">
              <p className="text-body leading-relaxed text-ink-2">
                O Tese AI faz uma coisa só: estrutura o raciocínio de investimento com
                evidência verificável. Esta página é o contrato de leitura — e vale para
                toda tese que sai do motor, sem exceção.
              </p>
            </Reveal>
            {/* Corpo NOVO (copy-horizonte-spec.md §6). */}
            <Reveal className="b-medida-esq i-4">
              <p className="text-body leading-relaxed text-ink-2">
                Não há letra miúda depois. As quatro cláusulas abaixo são o produto
                inteiro: se alguma delas for quebrada em qualquer tese, é defeito — e
                você tem como provar, porque o caminho do número está impresso.
              </p>
            </Reveal>
          </div>
        </section>

        <div className="bancada py-14">
          <div className="b-palco grid gap-12 md:grid-cols-[1.6fr_1fr]">
            {/* Manifesto — cláusulas numeradas viram placas gravadas
                (cinema/gema.css `.placa-gravada`, D14/C6 — ELEMENTO NOVO
                principal desta rota, junto da faixa-assinatura do fecho). */}
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
                  className={`placa-gravada bg-card px-6 py-6 sm:px-8 ${
                    i > 0 ? "mt-6 sm:mt-8" : ""
                  } ${DESLOCAMENTO_PLACA[i] ?? ""}`}
                >
                  <Reveal
                    variant="reveal-ticker"
                    className={`stagger i-${i + 1} flex gap-6`}
                    threshold={0.15}
                  >
                    <span
                      aria-hidden
                      className="placa-gravada__numeral inline-block px-2 py-1 font-mono text-h2 font-semibold"
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

            {/* Coluna secundária: ficha técnica sobre câmara estreita
                (S5/D19-D20 — reusa `.camara-escopo` de cinema/vitrine.css:
                redeclara os semânticos consumidos por `text-ink`/`text-ink-2`/
                `text-ink-3`/`border-line`/`text-brasa-texto` abaixo — nenhum
                fork de token novo, o mesmo mecanismo da Vitrine/Salão).
                Borda = lábio de ouro da fronteira papel↔câmara, padronizado
                no dial --labio-alfa (0.5 congelado, §7-C3): no escuro é o
                separador funcional ≥3:1; no claro, decorativo (a fronteira
                lê pelo par de superfícies). */}
            <aside
              aria-labelledby="metodo-titulo"
              className="camara-escopo flex flex-col gap-10 border border-[color-mix(in_srgb,var(--accent-valor)_calc(var(--labio-alfa)*100%),transparent)] bg-[var(--camara-fundo)] px-6 py-8 sm:px-8"
            >
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
                      <span className="font-mono text-meta text-ink-3">
                        {dimensao.fonte}
                      </span>
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
                  Todas abertas: qualquer citação pode ser conferida na origem, sem
                  cadastro e sem intermediário.
                </p>
              </div>
            </aside>
          </div>
        </div>

        {/* Fecho — faixa-assinatura final full-bleed (ELEMENTO NOVO
            principal, junto das placas), aberta pelo `.fio-travessa` que se
            IMPRIME via scaleX no scroll (E27 — elemento-novo RESERVA,
            independente de qualquer glow/specular: é geometria pura). */}
        <section aria-labelledby="fecho-titulo" className="border-t border-line">
          <div className="bancada py-10">
            <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden>
              {null}
            </Reveal>
            <div className="b-palco mt-8 flex flex-wrap items-center gap-3 border border-line bg-card px-6 py-5">
              <p className="flex-1 text-ui text-ink-2">
                <span id="fecho-titulo" className="font-semibold text-ink">
                  O contrato acima não é aspiração
                </span>{" "}
                — é o que está impresso em cada tese da galeria, hoje. Abra uma com olho
                de auditor: escolha um número qualquer e siga até a fonte.
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
