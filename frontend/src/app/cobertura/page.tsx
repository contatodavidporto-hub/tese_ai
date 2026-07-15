import type { Metadata } from "next";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { Reveal } from "@/components/motion/Reveal";
import { TermoTooltip } from "@/components/ui/TermoTooltip";
import { tooltipDe } from "@/lib/glossario";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

// ---------------------------------------------------------------------------
// HORIZONTE (2026-07-14, Onda 3 · raia 3B) — "AS TRÊS VITRINES".
// Direção §9: TRÍPTICO full-bleed — 3 painéis-vitrine (ações dominante 1.6fr,
// FII, renda fixa), cada um com SELO DE FONTES e PEDESTAL (`.vitrine-pedestal`,
// folha da raia 1B: elipse de sombra no chão + keyline ouro no aro).
// ELEMENTO NOVO (principal): ARO SPECULAR no hover/focus-within do painel
// (S4 contido, teto homologado `--bolha-specular-alfa` = 0.10) — keyline ouro
// + calota de luz no quadrante superior-esquerdo, `.painel-vitrine` (emenda de
// rito S3 em cinema/palco.css).
// ELEMENTO NOVO (reserva, E27 — SEM glow/specular/sombra): o SELO DE FONTES
// acende (ink-3 -> ink) e IMPRIME sua régua (hairline scaleX da esquerda) no
// hover/focus-within — sobrevive intacto ao recuo binário do S4 no AA.
// Layout: `.bancada` — prosa na medida (<=68ch); tríptico no `.b-palco` (até
// 96rem: MAIS largo que o antigo max-w-5xl/64rem — mini-gate E30).
// Copy: `.maestro/ondas/copy-horizonte-spec.md` §5, verbatim. Selo dormente
// "Em breve" preservado (só renderiza se `disponivel: false`).
// ---------------------------------------------------------------------------
export const metadata: Metadata = {
  title: "Cobertura",
  description:
    "O que o Tese AI cobre hoje: teses completas para ações da B3, FIIs pelo informe mensal da CVM e títulos do Tesouro Direto — a mesma disciplina de fonte e citação nas três classes, com teses prontas que abrem na hora.",
  openGraph: {
    title: "Cobertura — Tese AI",
    description:
      "Ações da B3, FIIs e Tesouro Direto — a mesma disciplina de fonte e citação nas três classes, com teses prontas que abrem na hora.",
  },
};

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

type ClasseInvestimento = {
  numero: string;
  titulo: string;
  descricao: ReactNode;
  // Selo de fontes do painel (D19/§9: "rótulos = dados com fonte"). É a MESMA
  // régua factual que o CartaoTese imprime por classe (REGUA_POR_CLASSE em
  // components/teses/CartaoTese.tsx — fonte oficial por dimensão, verificada
  // em orquestracao.py/app/services/ativos/*.py). Nenhum número novo, nenhuma
  // métrica de "cobertura" fabricada.
  selo: string;
  seloDetalhe?: string;
  disponivel: boolean;
  // Exemplo pronto (cache aquecido) desta classe — cada classe leva a um
  // ticker distinto em vez do genérico "/tese" (Fase 2 multiativo).
  href: string;
};

const CLASSES: ClasseInvestimento[] = [
  {
    numero: "01",
    titulo: "Ações B3",
    descricao: (
      <>
        A classe com o quadro completo: fundamentos da CVM, pares globais na SEC,
        macro do Brasil e do mundo, elos causais e{" "}
        <TermoTooltip {...tooltipDe("contra-tese")}>contra-tese</TermoTooltip>. É
        onde a tese vai mais fundo — e onde há mais número para você conferir.
      </>
    ),
    selo: "D1 CVM · D2 SEC · D3 BCB · D4 WB · D5 ELOS",
    disponivel: true,
    href: "/tese",
  },
  {
    numero: "02",
    titulo: "FIIs",
    descricao: (
      <>
        Fundos imobiliários listados, pelo{" "}
        <TermoTooltip {...tooltipDe("informe-mensal-cvm")}>informe mensal</TermoTooltip>{" "}
        que o fundo entrega à CVM: carteira, receitas, vacância e distribuições. Sem
        pares globais e sem macro global dedicada — a tese diz quais dimensões
        ficaram de fora.
      </>
    ),
    selo: "D1 CVM · D3 BCB · D5 ELOS",
    seloDetalhe: "Informe mensal CVM",
    disponivel: true,
    href: "/tese?ticker=HGLG11",
  },
  {
    numero: "03",
    titulo: "Renda fixa / Tesouro",
    descricao: (
      <>
        Títulos públicos, pelos dados abertos do Tesouro Nacional: taxa e preço sempre
        com a <TermoTooltip {...tooltipDe("data-base")}>data base</TermoTooltip>,{" "}
        <TermoTooltip {...tooltipDe("marcacao-a-mercado")}>
          marcação a mercado
        </TermoTooltip>{" "}
        e <TermoTooltip {...tooltipDe("carrego")}>carrego</TermoTooltip> descritos como
        conceito — nunca como sugestão de montar ou desfazer posição.
      </>
    ),
    selo: "D1 STN · D3 BCB · D5 ELOS",
    seloDetalhe: "Tesouro Transparente + Focus",
    disponivel: true,
    href: "/tese?ticker=TD-IPCA-2035",
  },
];

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
      "Você informa o código do ativo e o motor monta a tese do zero, com as dimensões daquela classe. Leva alguns minutos — e sai com a mesma trilha de citações da galeria.",
  },
  {
    numero: "02",
    titulo: "Teses prontas da galeria",
    descricao:
      "Já geradas e renovadas em ciclo diário: abrem na hora. A régua de auditoria não muda por ser exemplo — é o mesmo documento, com as mesmas citações e datas.",
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
  const dataCarteira = formatDataIso(DATA_CARTEIRA_IBOV);

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Abertura — E30 (correção-mãe, wt-horizonte 2026-07-14): eyebrow e H1
            NÃO são prosa (medida ≤68ch é lei só para prosa, §0.9) — vão no
            `.b-palco` (sangram, e é o que garante que a rota nunca fecha mais
            estreita que a produção em 768–1024px: `.b-medida-esq` sozinho
            perdia 25px ali, porque só herda MEIA trilha de palco). Os dois
            parágrafos de prosa real continuam em `.b-medida-esq` (≤68ch,
            lei intacta). */}
        <section className="bancada gap-y-4 py-14 sm:py-20">
          <Reveal className="b-palco i-1">
            <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
              Cobertura
            </p>
          </Reveal>
          <Reveal className="b-palco i-2">
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              O que está impresso nesta edição.
            </h1>
          </Reveal>
          <Reveal className="b-medida-esq i-3">
            <p className="text-lede leading-relaxed text-ink-2">
              Três classes de ativo, uma só régua. O que muda de uma para outra é o
              conjunto de dimensões; o que nunca muda é a regra: todo número com fonte
              e data, toda lacuna declarada.
            </p>
          </Reveal>
          <Reveal className="b-medida-esq i-4">
            <p className="text-ui leading-relaxed text-ink-2">
              Se você está começando, comece pelas ações — é a classe com o quadro
              completo de dimensões. Se já acompanha o mercado, vá direto ao que lhe
              interessa: as três colunas abaixo dizem exatamente quais fontes sustentam
              cada tese.
            </p>
          </Reveal>
        </section>

        {/* O TRÍPTICO — 3 painéis-vitrine (ações dominante 1.6fr), cada um com
            pedestal + selo de fontes. Palco largo (E30: até 96rem, contra o
            antigo max-w-5xl). */}
        <section aria-labelledby="classes-titulo" className="bancada gap-y-8 pb-14">
          <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden>
            {null}
          </Reveal>
          <h2
            id="classes-titulo"
            className="b-medida-esq atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
          >
            Classes de investimento
          </h2>
          {/* As 3 classes estão `disponivel: true` hoje (Fase 2 multiativo); o
              selo "Em breve" fica dormente, pronto para uma futura classe ainda
              não coberta, sem reescrever o layout. */}
          <ul className="b-palco stagger grid gap-4 lg:grid-cols-[1.6fr_1fr_1fr]">
            {CLASSES.map((classe, i) => (
              <li key={classe.numero} className="vitrine-pedestal">
                <Reveal
                  variant="reveal-ticker"
                  className={`painel-vitrine i-${i + 1} flex h-full flex-col gap-4 border border-line bg-card p-6 sm:p-8`}
                >
                  <div className="flex items-start justify-between gap-3">
                    {/* `.paralaxe-numero`: o folio grande desloca alguns px num
                        ritmo distinto do resto ao rolar (scroll-driven,
                        @supports + fallback estático; globals.css). */}
                    <span
                      aria-hidden
                      className={`paralaxe-numero font-mono font-semibold text-line-strong ${
                        i === 0 ? "text-h1" : "text-h3"
                      }`}
                    >
                      {classe.numero}
                    </span>
                    {!classe.disponivel && (
                      <span className="border border-aviso-borda bg-aviso-fundo px-2 py-1 font-sans text-label font-semibold uppercase tracking-[0.16em] text-aviso-texto">
                        Em breve
                      </span>
                    )}
                  </div>
                  <h3
                    className={`font-display font-semibold tracking-tight text-ink ${
                      i === 0 ? "text-h1" : "text-h3"
                    }`}
                  >
                    {classe.titulo}
                  </h3>
                  <p className="max-w-[68ch] text-ui leading-relaxed text-ink-2">
                    {classe.descricao}
                  </p>
                  {/* SELO DE FONTES (elemento-novo reserva, E27): acende e
                      imprime a régua no hover/focus-within — as dimensões que o
                      motor monta para a classe, com a fonte oficial de cada uma
                      (mesma régua factual do CartaoTese). */}
                  <p className="painel-selo mt-auto flex flex-col gap-0.5 border-t border-line pt-3 font-mono text-meta tracking-wide">
                    <span>{classe.selo}</span>
                    {classe.seloDetalhe && <span>{classe.seloDetalhe}</span>}
                  </p>
                  {classe.disponivel ? (
                    <Link
                      href={classe.href}
                      className="inline-flex min-h-11 w-fit items-center bg-brasa px-6 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                    >
                      Gerar tese →
                    </Link>
                  ) : (
                    <p className="font-sans text-meta text-ink-3">
                      Em desenvolvimento — parte da Fase 2 multiativo do motor. Sem
                      previsão de data.
                    </p>
                  )}
                </Reveal>
              </li>
            ))}
          </ul>
        </section>

        {/* Tipos de tese */}
        <section aria-labelledby="tipos-titulo" className="bancada gap-y-8 pb-14">
          <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden>
            {null}
          </Reveal>
          <h2
            id="tipos-titulo"
            className="b-medida-esq atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
          >
            Tipos de tese
          </h2>
          <ul className="b-palco stagger grid gap-4 sm:grid-cols-2">
            {TIPOS.map((tipo, i) => (
              <li key={tipo.numero} className="vitrine-pedestal">
                <Reveal
                  variant="reveal-ticker"
                  className={`painel-vitrine i-${i + 1} flex h-full flex-col gap-2 border border-line bg-card p-6`}
                >
                  <span
                    aria-hidden
                    className="paralaxe-numero font-mono text-h3 font-semibold text-line-strong"
                  >
                    {tipo.numero}
                  </span>
                  <h3 className="font-display text-h3 font-semibold text-ink">
                    {tipo.titulo}
                  </h3>
                  <p className="max-w-[68ch] text-ui leading-relaxed text-ink-2">
                    {tipo.descricao}
                  </p>
                </Reveal>
              </li>
            ))}
          </ul>
          <p className="b-medida-esq font-mono text-meta leading-relaxed text-ink-3">
            {exemplos.length} teses prontas · {acoes} ações · {fiis} FII · {rendaFixa}{" "}
            Tesouro Direto · fonte dos pesos:{" "}
            <TermoTooltip {...tooltipDe("carteira-teorica")}>
              carteira teórica do Ibovespa
            </TermoTooltip>{" "}
            (B3) · {dataCarteira} ·{" "}
            <Link href="/teses" className="sublinhado-brasa text-brasa-texto">
              ver a galeria completa
            </Link>
          </p>
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
