import type { Metadata } from "next";
import Link from "next/link";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { CampoBrasa } from "@/components/motion/CampoBrasa";
import { CenaScrub } from "@/components/motion/CenaScrub";
import { FioDaFonte } from "@/components/motion/FioDaFonte";
import { FocoLuz } from "@/components/motion/FocoLuz";
import { Reveal } from "@/components/motion/Reveal";
import { IlhaMagnetica } from "@/components/motion/useMagnetico";
import { OrganismoH1 } from "@/components/motion/useOrganismoH1";
import { TermoTooltip } from "@/components/ui/TermoTooltip";
import { tooltipDe } from "@/lib/glossario";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";
import { AmbienteLanding } from "./AmbienteLanding";
import { FilmstripDimensoes } from "./FilmstripDimensoes";
import GaleriaBanca from "./GaleriaBanca";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tese AI — a tese inteira, com a fonte de cada número",
  description:
    "Teses de investimento estruturadas para ações da B3, FIIs e Tesouro Direto: fundamentos, macro, pares globais e geopolítica cruzados com cada número rastreável até a fonte pública, com data. Lacuna declarada, interpretação rotulada. Não é recomendação de compra ou venda.",
  openGraph: {
    title: "Tese AI — a tese inteira, com a fonte de cada número",
    description:
      "Teses estruturadas para B3, FIIs e Tesouro Direto — cada número rastreável até a fonte pública, com data. Não é recomendação de compra ou venda.",
  },
};

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatPct(pct: number): string {
  return pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

// Dimensões canônicas D1…D5 (ARQUITETURA.md — verificadas em
// backend/app/services/orquestracao.py). Textos aplicados LITERALMENTE de
// .maestro/ondas/copy-landing-spec.md §5 (onda COPY — vendedora pela
// verdade; sem afirmação nova); numero/titulo/fonte intactos.
const DIMENSOES = [
  {
    numero: "D1",
    titulo: "Fundamentos",
    fonte: "CVM",
    texto:
      "Demonstrações e cadastro públicos da CVM: receita, margens, dívida — e as derivadas que o dado permite calcular. Nada além do que a fonte sustenta.",
  },
  {
    numero: "D2",
    titulo: "Pares globais",
    fonte: "SEC EDGAR",
    texto:
      "Comparáveis internacionais a partir de arquivos da SEC — sempre com a ressalva de padrão contábil e moeda: comparação selecionada, nunca equivalência.",
  },
  {
    numero: "D3",
    titulo: "Macro Brasil",
    fonte: "BCB",
    texto:
      "Séries oficiais do Banco Central do Brasil — juros, câmbio e atividade — e o preço do petróleo Brent: o pano de fundo em que a empresa opera, com rótulo e data de cada série.",
  },
  {
    numero: "D4",
    titulo: "Macro global",
    fonte: "World Bank + Tesouro",
    texto:
      "Séries do Banco Mundial e do Tesouro dos EUA: atividade, juros e comparáveis fora do Brasil — o contexto que também pressiona a tese, com rótulo e data de cada série.",
  },
  {
    numero: "D5",
    titulo: "Elos causais",
    fonte: "fonte nas duas pontas",
    texto:
      "Elos causais entre evento, commodity, setor e empresa — narrados como interpretação, em cenários condicionais, com fonte nas duas pontas de cada elo.",
  },
] as const;

const PRINCIPIOS = [
  {
    titulo: "Não recomenda",
    texto:
      "Nenhuma ordem de compra ou de venda, nenhum “alvo” de preço. A ferramenta estrutura o raciocínio; a decisão é do leitor — a postura que a regulação da CVM espera, tratada como honra da casa.",
  },
  {
    titulo: "Cada número com fonte",
    texto:
      "As afirmações factuais saem ancoradas em citações verificáveis, com link e data da fonte pública. O que não tem fonte não entra como fato — e qualquer leitor pode refazer o caminho.",
  },
  {
    titulo: "Lacunas declaradas",
    texto:
      "Quando o dado não existe, a tese registra “dado não encontrado” e segue — abster é mais honesto que estimar. Lacuna visível vale mais que número inventado.",
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
        {/* Ilhas globais da LANDING (renderizam null — zero box):
            - AmbienteLanding (R7b/R11): useSecaoAtiva({ambiente:true}) espelha
              a seção ativa em body[data-secao] p/ o ambiente por capítulo da
              cinema/luz.css; SÓ aqui em todo o produto, removido no unmount.
            - IlhaMagnetica (R2/R5): delegação em document que liga a física
              de cursor nos .magnetico da landing (CTAs do hero/faixa final,
              setas/dots do filmstrip); gsap só desce no 1º pointerenter. */}
        <AmbienteLanding />
        <IlhaMagnetica />

        {/* Hero — P2 (CORRECOES-RODADA-1.md): acima da dobra, então SEM Reveal
            e SEM CenaScrub (hero é LCP; nada aqui nasce opacity:0 nem depende
            de JS/IO). O H1 se compõe palavra a palavra via keyframe CSS
            incondicional transform-only (.palavra-hero, cinema/hero.css) —
            pintável no primeiro frame. */}
        {/* Camadas decorativas z-index:-1, na ordem de pintura do DOM
            (cinema/hero.css, MATÉRIA VIVA Onda 1A→2): glifo-fantasma (fundo,
            contra-cursor) → CampoBrasa (canvas WebGL, monta pós-idle e só se
            passar nos gates) → FocoLuz (luminária dupla núcleo+bloom+penumbra
            por cima). Todas irmãs DIRETAS do .tem-foco — nunca wrappers
            (trava C2); FocoLuz descobre o glifo por querySelector e co-escreve
            --mx/--my na folha dele. */}
        <section id="hero" className="tem-foco border-b border-line" aria-labelledby="hero-titulo">
          <span aria-hidden="true" className="glifo-fantasma">
            [1]
          </span>
          <CampoBrasa />
          <FocoLuz />
          {/* H1-organismo (APOTEOSE crit.2): ilha que liga a proximidade por
              palavra (useOrganismoH1 → usePonteiro modo proximidade) na
              superfície do hero inteiro. A sonda é um <span hidden aria-hidden>
              (display:none, zero box/layout) — filha DIRETA do .tem-foco, como
              as demais ilhas; zero classe nova no h1, spans/nome acessível
              intocados (contrato .maestro/ondas/hero.md). */}
          <OrganismoH1 />
          <div data-mascara-brasa="" className="mx-auto flex w-full max-w-5xl flex-col items-start gap-6 px-4 py-16 sm:px-6 sm:py-24">
            <div className="entrada-hero i-1">
              <p className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
                Teses de investimento · B3 e Tesouro Direto
              </p>
            </div>
            {/* H1 palavra a palavra (crit.1b): spans ESTÁTICOS server-rendered,
                classes LITERAIS .palavra-1…N (nunca template string — Tailwind
                v4 purga), espaço real entre spans ({" "}), sem role/aria extra
                — o nome acessível do h1 permanece "A tese inteira, com a fonte
                de cada número." A cascata substitui o antigo .entrada-hero i-2
                deste bloco (um escritor por transform: agora são os keyframes
                das próprias palavras). A palavra "fonte" leva adicionalmente
                .palavra-hero-fonte (varredura especular única de ouro; sem
                utilitário de cor próprio — o fallback sem background-clip:text
                herda a tinta do H1, e text-* na palavra venceria a cascata e
                quebraria o clip). */}
            <h1
              id="hero-titulo"
              className="max-w-3xl font-display text-hero font-semibold tracking-tight text-ink"
            >
              <span className="palavra-hero palavra-1">A</span>{" "}
              <span className="palavra-hero palavra-2">tese</span>{" "}
              <span className="palavra-hero palavra-3">inteira,</span>{" "}
              <span className="palavra-hero palavra-4">com</span>{" "}
              <span className="palavra-hero palavra-5">a</span>{" "}
              <span className="palavra-hero palavra-hero-fonte palavra-6">fonte</span>
              {/* Pin de citação sobrescrito (§2, cena 3): resolve scale+opacity
                  com o spring --ease-settle 1 beat depois do H1 assentar —
                  CSS puro incondicional (.pin-hero), nunca gate de IO (o
                  hero é LCP). O mesmo [1] reaparece na linha de fonte viva
                  abaixo dos CTAs — é a mesma citação. */}
              {/* aria-hidden: o pin é reforço visual — sem ele o título
                  acessível viraria "…com a fonte um de cada número"; a
                  citação legível está na linha de fonte logo abaixo. */}
              <sup aria-hidden="true" className="pin-hero font-mono text-ui text-brasa-texto">
                [1]
              </sup>{" "}
              <span className="palavra-hero palavra-7">de</span>{" "}
              <span className="palavra-hero palavra-8">cada</span>{" "}
              <span className="palavra-hero palavra-9">número.</span>
            </h1>
            <div className="entrada-hero i-3">
              <p className="max-w-2xl text-lede leading-relaxed text-ink-2">
                O Tese AI estrutura teses de investimento cruzando fundamentos, contexto macro,
                pares globais e geopolítica. Cada afirmação factual é rastreável até o dado
                público de origem; interpretação vem rotulada como tal; cada lacuna é declarada,
                nunca preenchida com chute. A tese organiza — a decisão é sua.
              </p>
            </div>
            <div className="entrada-hero i-4">
              {/* .magnetico (R2): física de cursor SÓ nas ilhas da landing —
                  aqui, nos dois CTAs do hero (ligados pela IlhaMagnetica; o
                  transform é do GSAP, o peso de tinta/cores da folha
                  cinema/magnetico.css). Os botões são flex items (geram box). */}
              <div className="flex flex-wrap items-center gap-3">
                <Link
                  href="/tese"
                  className="magnetico bg-brasa px-6 py-3 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                >
                  Gerar tese
                </Link>
                <Link
                  href={`/tese?ticker=${encodeURIComponent(primeiroTicker)}`}
                  className="magnetico border border-field px-6 py-3 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto"
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
              <sup aria-hidden="true" className="text-brasa-texto">[1]</sup> Fonte: B3 · Carteira
              teórica do Ibovespa · {dataCarteira}
            </p>
            <div className="entrada-hero i-5">
              <p className="text-ui text-ink-3">
                Ferramenta de estruturação — não é recomendação de compra ou venda.
              </p>
            </div>
          </div>
        </section>

        {/* Prova viva: anatomia de uma citação, com números reais e auditados.
            CAPÍTULO scrubado (CenaScrub, Onda 1B→2): os blocos [data-cena-el]
            imprimem/desimprimem atados ao scroll (3 atos, piso 0.55). Um
            escritor por propriedade: os antigos <Reveal>/<Reveal
            variant="citacao-pin"> desta seção foram REMOVIDOS (o GSAP é o
            único dono de transform/opacity aqui); a borda-esquerda 2px brasa
            que o .citacao-pin imprimia virou keyline ESTÁTICA (border-l-2
            border-brasa) — a anatomia de evidência permanece. */}
        <CenaScrub>
          <section
            id="prova"
            data-cena="prova"
            aria-labelledby="prova-titulo"
            className="capitulo border-b border-line"
          >
            {/* `relative`: containing block do <FioDaFonte/> (SVG absolute
                inset-0, PRIMEIRO filho — pinta sob os chips, que são
                position:relative). O fio sai do sup [1] do parágrafo de
                abertura ([data-fio-de] — a MESMA citação B3/data que o chip
                detalha; nenhum número novo) e chega no TOPO do primeiro chip
                de fonte ([data-fio-ate]); é desenhado pela timeline do
                CenaScrub desta seção (rastreabilidade como coreografia). */}
            <div className="relative mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
              <FioDaFonte />
              <div data-cena-el="" className="flex flex-col gap-2">
                <h2
                  id="prova-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Prova viva: assim nasce um número na tese
                </h2>
                {/* Tooltip DENTRO de [data-cena-el] (spec §3): permitido porque
                    o gatilho do TermoTooltip só transiciona color/border-color
                    e o popup .tt-popup anima a si mesmo — NUNCA acrescentar
                    classe de transform/opacity ao gatilho (um-escritor: o
                    CenaScrub é o dono deste bloco). */}
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  Todo dado factual segue o mesmo caminho: número em mono, marcado com uma
                  citação, ligado a uma fonte e uma data — sem exceção. Exemplo real, com a{" "}
                  <TermoTooltip {...tooltipDe("carteira-teorica")}>
                    carteira teórica do Ibovespa
                  </TermoTooltip>{" "}
                  (B3, {dataCarteira})
                  <sup data-fio-de="" className="font-mono text-brasa-texto">[1]</sup>:
                </p>
              </div>

              <ol className="grid gap-3 sm:grid-cols-3">
                {provaViva.map((papel, i) => (
                  <li key={papel.ticker}>
                    <div
                      data-cena-el=""
                      data-fio-ate={i === 0 ? "" : undefined}
                      className="relative flex h-full flex-col gap-2 border-l-2 border-brasa bg-realce px-4 py-4"
                    >
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
                    </div>
                  </li>
                ))}
              </ol>

              <p data-cena-el="" className="max-w-2xl text-ui text-ink-3">
                Assim é toda citação da plataforma: o número no corpo do texto, a nota entre
                colchetes e a fonte com a data logo abaixo — nunca escondida em rodapé.
              </p>
            </div>
          </section>
        </CenaScrub>

        {/* Galeria teaser → BANCA DE TESES (Onda 1E→2): rail horizontal
            nativo snap-x com carimbo view(inline) por card — substitui a
            grade + <Reveal variant="reveal-ticker"> por card (a varredura do
            motor Reveal ignora clipagem por overflow e atropelaria os cards;
            sem .stagger/.i-N aqui). GradeFoco/CartaoTese continuam por dentro
            do GaleriaBanca (mesma anatomia, mesmo foco frio por delegação). */}
        <CenaScrub>
          <section
            id="galeria"
            data-cena="galeria"
            aria-labelledby="galeria-titulo"
            className="capitulo border-b border-line"
          >
            <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-14 sm:px-6">
              <div data-cena-el="" className="flex flex-col gap-2">
                <h2
                  id="galeria-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Teses de exemplo — abrem na hora
                </h2>
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  Pré-geradas pelo motor: os {acoesExemplo} maiores pesos da carteira teórica
                  do Ibovespa (B3, {dataCarteira}) e {multiativoExemplo} exemplos multiativo — um
                  FII, um título do Tesouro Direto — mantidos prontos e renovados a cada ciclo
                  diário. Clique e leia a tese completa, com citações e fontes; se tiver
                  expirado, ela é regenerada na hora.
                </p>
              </div>
              <div data-cena-el="">
                <GaleriaBanca papeis={exemplos} dataCarteira={DATA_CARTEIRA_IBOV} />
              </div>
              <LinkCinema
                data-cena-el=""
                href="/teses"
                className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
              >
                Ver todas as teses de exemplo →
              </LinkCinema>
            </div>
          </section>
        </CenaScrub>

        {/* As cinco dimensões — Filmstrip D1→D5 (§3, direcao-de-arte-cinema.md):
            "a tese se monta, camada por camada". Componente próprio
            (FilmstripDimensoes.tsx) porque carrega estado (painel ativo,
            trilho de progresso, teclado, modo pinado da Onda 1C) — page.tsx
            segue Server Component, só passa DIMENSOES como prop. */}
        {/* R1 (LEI DA MISSÃO): esta seção fica FORA do CenaScrub e SEM
            [data-cena] — nenhum tween de transform em ancestral do elemento
            pinado (o wrapper do FilmstripDimensoes é pinado pelo
            ScrollTrigger no modo travelling). Os <Reveal> daqui permanecem
            (nada migrou ao scrub: o motor Reveal segue o escritor deles). */}
        <section
          id="dimensoes"
          aria-labelledby="dimensoes-titulo"
          className="capitulo border-b border-line"
        >
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <Reveal>
              <div className="flex flex-col gap-2">
                <h2
                  id="dimensoes-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Cinco dimensões, uma tese
                </h2>
                {/* Tooltips liberados aqui: #dimensoes está FORA do scrub (R1)
                    — gatilhos sem transform/opacity próprios por construção
                    (spec §5; o Reveal anima o wrapper, não os spans). */}
                <p className="max-w-2xl text-body leading-relaxed text-ink-2">
                  O motor monta a tese por camadas e fecha com síntese e{" "}
                  <TermoTooltip {...tooltipDe("contra-tese")}>contra-tese</TermoTooltip> (
                  <TermoTooltip {...tooltipDe("bull-bear")}>bull × bear</TermoTooltip>). Fato e
                  interpretação vêm sempre separados no texto — cada camada com a fonte oficial
                  que a sustenta. O quadro completo vale para as ações; FIIs e títulos do
                  Tesouro Direto usam um subconjunto próprio de dimensões — sem pares globais
                  nem macro global dedicada.
                </p>
              </div>
            </Reveal>
            <FilmstripDimensoes dimensoes={DIMENSOES} />
            <Reveal>
              <LinkCinema
                href="/como-funciona"
                className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
              >
                Como o motor funciona, passo a passo →
              </LinkCinema>
            </Reveal>
          </div>
        </section>

        {/* Postura — CAPÍTULO scrubado. Os antigos <Reveal>/.stagger/.i-N
            desta seção foram removidos (migração ao CenaScrub, um escritor
            por propriedade). A faixa CVM leva [data-cvm]: o CenaScrub trava a
            opacity dela em 1 — o aviso regulatório se move com o capítulo,
            mas JAMAIS esmaece. */}
        <CenaScrub>
          <section id="postura" data-cena="postura" aria-labelledby="postura-titulo" className="capitulo">
            <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-14 sm:px-6">
              <h2
                data-cena-el=""
                id="postura-titulo"
                className="font-display text-h2 font-semibold tracking-tight text-ink"
              >
                Auditável por construção
              </h2>
              <ol className="grid gap-6 sm:grid-cols-3">
                {PRINCIPIOS.map((p, i) => (
                  <li key={p.titulo}>
                    <div
                      data-cena-el=""
                      className="flex h-full flex-col gap-2 border border-line bg-card px-6 py-6"
                    >
                      <span className="font-mono text-h3 text-line-strong">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <h3 className="font-display text-lede font-semibold text-ink">{p.titulo}</h3>
                      <p className="text-ui leading-relaxed text-ink-2">{p.texto}</p>
                    </div>
                  </li>
                ))}
              </ol>

              {/* Faixa-brasão: o aviso CVM tratado como manchete, não letra miúda.
                  Peça de honra (APOTEOSE C9/D5): o pai [data-cena-el][data-cvm]
                  vira container liso — o GSAP do CenaScrub segue dono único do
                  transform(y) dele (opacity travada em 1). O filho .cvm-honra
                  (novo, contrato .maestro/ondas/cena.md) leva as classes visuais
                  + a levitação/keyline de cinema/secoes.css — um-escritor: o
                  float por keyframe mora no FILHO, nunca no data-cena-el. Texto
                  VERBATIM (compliance — não mudar uma vírgula). */}
              {/* aria-label DISTINTO da Tarja sticky (gate visual 2026-07-13):
                  dois role=note com o mesmo rótulo confundem a navegação por
                  landmark em leitor de tela — e o seletor do filmstrip
                  ('[role="note"][aria-label="Aviso regulatório"]') passa a
                  casar SÓ com a Tarja, por construção. O texto do aviso em
                  si segue VERBATIM (aria-label não é conteúdo). */}
              <div data-cena-el="" data-cvm="" role="note" aria-label="Postura regulatória">
                <div className="cvm-honra flex flex-col items-center gap-2 border-y-2 border-aviso-borda bg-aviso-fundo px-6 py-8 text-center sm:px-10">
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
              </div>

              <div
                data-cena-el=""
                className="flex flex-wrap items-center gap-3 border border-line bg-card px-6 py-5"
              >
                <p className="flex-1 text-ui text-ink-2">
                  Pronto para auditar uma? Gere a tese de uma ação da B3, de um FII ou de um
                  título do Tesouro Direto — ou abra uma tese pronta da galeria.
                </p>
                {/* CTA da faixa final — .magnetico (R2: ilha da landing). */}
                <Link
                  href="/tese"
                  className="magnetico bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                >
                  Gerar tese
                </Link>
              </div>
            </div>
          </section>
        </CenaScrub>
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
