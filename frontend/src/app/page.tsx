import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { CenaNascimento } from "@/components/cena/CenaNascimento";
import { NascimentoScrub } from "@/components/cena/NascimentoScrub";
import { CampoBrasa } from "@/components/motion/CampoBrasa";
import { CenaScrub } from "@/components/motion/CenaScrub";
import { FioDaFonte } from "@/components/motion/FioDaFonte";
import { FocoLuz } from "@/components/motion/FocoLuz";
import { LinkCinema } from "@/components/motion/LinkCinema";
import { MedidaCromo } from "@/components/motion/MedidaCromo";
import { Reveal } from "@/components/motion/Reveal";
import { IlhaMagnetica } from "@/components/motion/useMagnetico";
import { OrganismoH1 } from "@/components/motion/useOrganismoH1";
import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { CartaoTese } from "@/components/teses/CartaoTese";
import { TermoTooltip } from "@/components/ui/TermoTooltip";
import { tooltipDe } from "@/lib/glossario";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";
import { AmbienteLanding } from "./AmbienteLanding";
import GaleriaBanca from "./GaleriaBanca";
import { SalaoDimensoes, type DimensaoSalao } from "./SalaoDimensoes";
// salao.css é EXCLUSIVA da landing (E23) — importada aqui, não em globals.css,
// para não pesar no CSS render-blocking das outras 7 rotas (mesmo precedente
// de como-funciona.css). A ordem relativa às folhas de globals é preservada:
// só a landing carrega esta, e nada nela sobrescreve tese-apoteose.css.
import "@/styles/cinema/salao.css";

// Renderização dinâmica: necessária para o CSP com nonce por requisição
// (src/proxy.ts) ser aplicado em cada resposta.
export const dynamic = "force-dynamic";
//
// ============================================================
// PERF — A LEI DAS ILHAS DESTA PÁGINA (rodada B2, 2026-07-14)
// ------------------------------------------------------------
// DIAGNÓSTICO (medido, `.maestro/evidencias/onda5/B-perf/` + `…/B2-perf/`):
// o excedente de TBT mobile-4x da landing NÃO vem de um boot atrasável — vem
// do COMMIT DE HIDRATAÇÃO, e o custo é proporcional ao tamanho da árvore que
// o CLIENTE reconcilia. Provas: (a) ligar/desligar todos os efeitos do Salão
// não movia o número; (b) `<Suspense>`, `next/dynamic` e uma fronteira de
// streaming SSR real também não (o chunk resolve rápido demais em rede local
// — lazy não vira tarefa separada); (c) atribuição por remoção: #nascimento
// ≈ 0ms, #dimensoes ≈ 60–70ms, #galeria ≈ 60–70ms.
//
// A ALAVANCA (a que o próprio `#nascimento` já provava): ele custa ~0ms
// porque o SVG pesado é SERVER-RENDERED e entra na ilha client como
// `children` — conteúdo que um Server Component passa como slot para um
// Client Component chega pelo payload RSC já criado, fora da tarefa de
// hidratação. REGRA DESTA PÁGINA, daqui em diante:
//
//   ⚠ ILHA CLIENT DA LANDING RECEBE CONTEÚDO — NÃO O RENDERIZA.
//     A ilha é a CASCA (refs, listeners, geometria, estado); o RECHEIO
//     (bolhas do Salão, cartões da Vitrine) é montado AQUI, no servidor, e
//     desce como slot (`bolhas`, `cartoes`). Voltar a mapear a lista dentro
//     do componente client re-abre o buraco de TBT.
//
// Imports seguem ESTÁTICOS de propósito (o `next/dynamic` foi desfeito na
// rodada anterior por não mover métrica — doutrina: otimização que não move
// número e adiciona complexidade, desfaz-se).
// ============================================================

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

const MESES = [
  "JAN",
  "FEV",
  "MAR",
  "ABR",
  "MAI",
  "JUN",
  "JUL",
  "AGO",
  "SET",
  "OUT",
  "NOV",
  "DEZ",
] as const;

// Timbre editorial da orelha direita da capa (copy-horizonte-spec §2.1): a
// MESMA string do masthead do Header (`edicaoDeHoje()`), duplicada aqui de
// propósito — o Header é chrome INTOCADO nesta missão (D4) e não exporta o
// helper. Não é dado factual do produto (é a data do render server-side; a
// rota já é force-dynamic), então não carrega fonte: os DADOS da orelha são
// a lista de fontes, e todo número factual da página segue com fonte+data.
function edicaoDeHoje(): string {
  const agora = new Date();
  const dia = String(agora.getDate()).padStart(2, "0");
  const mes = MESES[agora.getMonth()];
  return `EDIÇÃO DE ${dia} ${mes} ${agora.getFullYear()}`;
}

// Dimensões canônicas D1…D5 (ARQUITETURA.md — verificadas em
// backend/app/services/orquestracao.py). `numero`/`titulo`/`fonte` INTACTOS;
// `texto` = copy nova, TRANSCRITA byte-fiel de .maestro/copy-ourivesaria.md
// §2 (COPY CONGELADA da missão Ourivesaria — §7-E5: divergência sobe ao
// maestro, nunca se resolve aqui). `texto` é ReactNode (contrato do
// SalaoDimensoes, raia 1C): é aqui que entram os TermoTooltip DENTRO das
// bolhas — o gatilho focável é o que torna `focusin → travelling` um caminho
// REAL de teclado (e o pior caso 1.4.13 da bolha da borda, E13). Tooltips nos
// MESMOS termos/slugs de antes; slugs SÓ de src/lib/glossario.ts (D7).
const DIMENSOES: readonly DimensaoSalao[] = [
  {
    numero: "D1",
    titulo: "Fundamentos",
    fonte: "CVM",
    texto:
      "O que a empresa declara ao regulador: receita, margens, dívida e caixa, direto das demonstrações públicas arquivadas na CVM. A tese não completa o que o documento não diz — cada linha vem do arquivo, com data de publicação.",
  },
  {
    numero: "D2",
    titulo: "Pares globais",
    fonte: "SEC EDGAR",
    texto: (
      <>
        Como empresas parecidas aparecem nos{" "}
        <TermoTooltip {...tooltipDe("sec-edgar")}>arquivos da SEC</TermoTooltip>, lá fora. A
        comparação é selecionada e rotulada: moeda, padrão contábil e porte entram como
        ressalva explícita, porque semelhança não é equivalência.
      </>
    ),
  },
  {
    numero: "D3",
    titulo: "Macro Brasil",
    fonte: "BCB",
    texto: (
      <>
        O chão em que a empresa pisa: juros, câmbio e atividade nas séries abertas do Banco
        Central, e o preço do petróleo <TermoTooltip {...tooltipDe("brent")}>Brent</TermoTooltip>.
        Cada série chega com rótulo, unidade e data — nunca um índice sem origem.
      </>
    ),
  },
  {
    numero: "D4",
    titulo: "Macro global",
    fonte: "World Bank + Tesouro",
    texto:
      "O vento que vem de fora: atividade global pelo Banco Mundial e juros longos pelo Tesouro dos EUA. É o contexto que pressiona a tese de longe — medido, datado e citado como tudo o mais.",
  },
  {
    numero: "D5",
    titulo: "Elos causais",
    fonte: "fonte nas duas pontas",
    texto: (
      <>
        A ligação narrada entre evento, commodity, setor e empresa. É interpretação — e é
        marcada como interpretação, com fonte nas duas pontas de cada{" "}
        <TermoTooltip {...tooltipDe("elo-causal")}>elo</TermoTooltip>. Você pode discordar do
        meio segurando as duas pontas.
      </>
    ),
  },
];

// Desalinho das placas da Sala do Contrato (D35 — "placas gravadas
// desalinhadas"): classes LITERAIS por índice (nunca template string — o JIT
// do Tailwind v4 escaneia texto literal do código-fonte). Só a partir de `sm`
// (empilhadas no mobile, onde desalinho vira buraco).
const DESALINHO_PLACA = ["sm:mt-0", "sm:mt-8", "sm:mt-16"] as const;

export default function Home() {
  const exemplos = exemplosProntos();
  const primeiroTicker = exemplos[0]?.ticker ?? "VALE3";
  // Prova viva: os 3 maiores pesos reais da carteira teórica do Ibovespa
  // (fonte B3, mesma data em todo o produto) — nenhum número aqui é inventado.
  const provaViva = exemplos.slice(0, 3);
  const dataCarteira = formatDataIso(DATA_CARTEIRA_IBOV);
  const edicao = edicaoDeHoje();
  // Contagens DERIVADAS do catálogo (nunca hardcoded — §0.3 do spec de copy).
  const totalExemplos = exemplos.length;
  const acoesExemplo = exemplos.filter((p) => (p.classe ?? "acao") === "acao").length;
  const multiativoExemplo = exemplos.length - acoesExemplo;
  // Exemplos-vivos das placas (D35): citação REAL derivada de exemplosProntos()
  // — nunca literal. O 3º é a lacuna (não tem número, por definição).
  const exemplo1 = provaViva[0];
  const exemplo2 = provaViva[1];

  // Princípios da Sala do Contrato (copy-horizonte-spec §2.6). `texto` é
  // ReactNode (tooltip na placa 02); `exemplo` é a linha mono do `.exemplo-vivo`.
  const PRINCIPIOS: ReadonlyArray<{
    titulo: string;
    texto: React.ReactNode;
    exemplo: string;
  }> = [
    {
      titulo: "Não recomenda",
      texto:
        "Nenhuma ordem de compra ou de venda, nenhum “alvo” de preço, nenhuma sugestão de momento de mercado. A ferramenta estrutura o raciocínio; a decisão é do leitor — a postura que a regulação da CVM espera, tratada aqui como honra da casa.",
      exemplo: exemplo1
        ? `${exemplo1.ticker} · ${formatPct(exemplo1.participacaoPct)}% do IBOV [1] · fonte B3 · ${dataCarteira}`
        : "dado não encontrado — lacuna declarada",
    },
    {
      titulo: "Cada número com fonte",
      texto: (
        <>
          As afirmações factuais saem ancoradas em{" "}
          <TermoTooltip {...tooltipDe("citations")}>citações</TermoTooltip> verificáveis, com
          link e data da fonte pública. O que não tem fonte não entra como fato — e qualquer
          leitor, com ou sem experiência, pode refazer o caminho até o documento de origem.
        </>
      ),
      exemplo: exemplo2
        ? `${exemplo2.ticker} · ${formatPct(exemplo2.participacaoPct)}% do IBOV [2] · fonte B3 · ${dataCarteira}`
        : "dado não encontrado — lacuna declarada",
    },
    {
      titulo: "Lacunas declaradas",
      texto:
        "Quando o dado não existe na fonte, a tese registra “dado não encontrado” e segue em frente — abster é mais honesto que estimar. Lacuna visível vale mais que número inventado: ela mostra exatamente onde a evidência acaba.",
      exemplo: "dado não encontrado — lacuna declarada",
    },
  ];

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Ilhas globais da LANDING (renderizam null — zero box):
            - AmbienteLanding (R7b/R11 + E25): useSecaoAtiva({ambiente:true})
              espelha a seção ativa em body[data-secao] p/ o ambiente por
              capítulo da cinema/luz.css; SÓ aqui em todo o produto, removido
              no unmount. A lista de ids inclui "nascimento" (E25).
            - IlhaMagnetica (R2/R5): delegação em document que liga a física
              de cursor nos .magnetico da landing (CTAs do hero/faixa final);
              gsap só desce no 1º pointerenter.
            - MedidaCromo (HORIZONTE E4c): backstop dos contratos de altura —
              mede Tarja/Header (ResizeObserver + fonts.ready) e corrige
              --altura-tarja/--altura-header por CSSOM quando zoom de texto
              200%/text-spacing refluem o chrome. As vars estáticas do
              globals.css seguem donas do first-paint (CLS zero); só a landing
              consome as vars, então só ela paga esta ilha. */}
        <AmbienteLanding />
        <IlhaMagnetica />
        <MedidaCromo />

        {/* ============================================================
            1. A CAPA (crit. 2) — hero em tela cheia.
            E1 (red-team, SUBSTITUI D9): NENHUM wrapper novo. Header e
            <main id="conteudo"> ficam exatamente onde estavam (o <header>
            fora do <main> preserva o role `banner`; o #hero DENTRO do <main>
            preserva o alvo do skip-link). A altura de "tela cheia" é uma
            regra do PRÓPRIO #hero (cinema/hero.css §6):
              min-block-size: calc(100svh − var(--altura-tarja) − var(--altura-header))
            Hero é LCP: sem Reveal, sem CenaScrub, nada nasce opacity:0.
            D12: hero é jargão-zero — ZERO TermoTooltip aqui dentro.
            D13: H1-organismo/sheen/CampoBrasa/FocoLuz/entrada-hero/
            IlhaMagnetica INTOCADOS — só escala e disposição mudaram.
            ============================================================ */}
        <section id="hero" className="tem-foco" aria-labelledby="hero-titulo">
          {/* GLIFO-FANTASMA "[1]" — o monumento da capa (D10/D13), ~52vw
              sangrando pela borda direita: a ESCALA APROVADA está intacta.
              O que mudou (rodada B2, perf — ver cinema/hero.css §3): ele
              deixou de ser um NÓ DE TEXTO e passou a ser o CONTORNO VETORIAL
              do próprio glifo. Motivo, medido: pela spec de LCP, "bloco que
              contém nós de texto" é candidato — e a 52vw o glifo (≈550.000px²)
              goleava qualquer palavra do H1 (≈49.000px², a cascata D13 quebra
              o H1 em spans por palavra) e VENCIA o LCP, atrasando o relógio
              (112ms → 148ms). `<path>` NÃO é candidato (a lista da spec só
              admite <img>, <image>, poster de <video>, background-image e
              bloco com TEXTO) — provado por medição, junto com o que NÃO
              funciona: <svg><text> AINDA é candidato (o PaintTimingDetector
              conta texto SVG), texto dentro de <mask> também, e
              `transform: scale()` não engana (o rect é mapeado).
              O desenho é o MESMO: são as curvas reais da Newsreader wght 500 /
              opsz 72 (o opsz que o `font-optical-sizing: auto` já escolhia a
              748px), com os avanços e o letter-spacing -0.04em embutidos — a
              largura da caixa bate com a do <span> a 0,01px. Bônus: o glifo
              não depende mais do swap da webfont para pintar.
              `aria-hidden` + decorativo, como sempre foi. */}
          <svg
            aria-hidden="true"
            className="glifo-fantasma"
            viewBox="0 0 2182 1800"
            preserveAspectRatio="none"
          >
            <path d="M183.2 1598.1V-93.9H571.4V-62.7L344.4 -37.5V1541.7L571.4 1566.9V1598.1ZM1080.8 1289.3V62.7L1216.6 136.1L689.0 268.5L678.4 233.3L1300.4 -75.9H1337.2V1289.3L1625.6 1340.3V1370.1H775.8V1340.3ZM2078.8 -93.9V1598.1H1690.6V1566.9L1917.6 1541.7V-37.5L1690.6 -62.7V-93.9Z" />
          </svg>
          <CampoBrasa />
          <FocoLuz />
          {/* H1-organismo (APOTEOSE crit.2): sonda <span hidden aria-hidden>
              (display:none, zero box) — filha DIRETA do .tem-foco, como as
              demais ilhas de luz; zero classe nova no h1. */}
          <OrganismoH1 />

          {/* A grade da capa (cinema/hero.css §7): 4 linhas nomeadas
              topo→meio→base→dobra (ordem do DOM = ordem de leitura; `order`
              CSS é proibido). É a própria Bancada (grid de colunas nomeadas)
              com `--medida` de display. Filha DIRETA do #hero e IRMÃ das
              camadas de luz — nunca wrapper delas (trava C2). */}
          <div className="bancada bancada--display capa-grade">
            {/* Referência de geometria do uMask (cinema/hero.css §8): elemento
                vazio, sem pintura, que marca a faixa de coluna do texto para o
                shader do CampoBrasa (trava M3 — a brasa nunca banha número/
                citação). Zero mudança de motor: o alvo [data-mascara-brasa]
                apenas mudou de nó. */}
            <div aria-hidden="true" data-mascara-brasa="" className="capa-mascara" />

            {/* TOPO — as duas orelhas. A ESQUERDA é o verbatim CVM (D11): a
                negação explícita continua na 1ª dobra, exatamente uma vez. */}
            <div className="capa-linha--topo flex flex-wrap items-start justify-between gap-x-6 gap-y-1">
              <p className="capa-orelha capa-orelha--esq">
                Ferramenta de estruturação — não é recomendação de compra ou venda.
              </p>
              <p className="capa-orelha capa-orelha--dir">
                {edicao} · fontes: B3 · CVM · SEC · BCB · WB · STN
              </p>
            </div>

            {/* MEIO — cartola + manchete + linha-fina em 2 colunas.
                `.b-medida-esq`: a coluna de texto ancora na borda do palco e
                termina no fim da medida (a MESMA faixa que a .capa-mascara). */}
            <div className="capa-linha--meio b-medida-esq">
              <div className="entrada-hero i-1">
                <p className="capa-cartola">Teses de investimento · B3 e Tesouro Direto</p>
              </div>
              {/* H1 palavra a palavra (D13 — INTOCADO): spans ESTÁTICOS
                  server-rendered, classes LITERAIS .palavra-1…N (nunca
                  template string — Tailwind v4 purga), espaço real entre spans
                  ({" "}), sem role/aria extra. Só a ESCALA mudou: `text-capa`
                  (--text-capa, com o teto svh do E11) no lugar de `text-hero`;
                  o tracking vem do próprio par --text-capa--letter-spacing
                  (nunca `tracking-tight`, que o sobrescreveria). */}
              <h1 id="hero-titulo" className="font-display text-capa font-semibold text-ink">
                <span className="palavra-hero palavra-1">A</span>{" "}
                <span className="palavra-hero palavra-2">tese</span>{" "}
                <span className="palavra-hero palavra-3">inteira,</span>{" "}
                <span className="palavra-hero palavra-4">com</span>{" "}
                <span className="palavra-hero palavra-5">a</span>{" "}
                <span className="palavra-hero palavra-hero-fonte palavra-6">fonte</span>
                {/* aria-hidden: o pin é reforço visual — a citação legível está
                    na gema logo abaixo (é a MESMA citação). */}
                <sup aria-hidden="true" className="pin-hero font-mono text-ui text-brasa-texto">
                  [1]
                </sup>{" "}
                <span className="palavra-hero palavra-7">de</span>{" "}
                <span className="palavra-hero palavra-8">cada</span>{" "}
                <span className="palavra-hero palavra-9">número.</span>
              </h1>
              <div className="entrada-hero i-3">
                <div className="capa-linha-fina">
                  <p className="text-body leading-relaxed text-ink-2">
                    Um relatório de análise pede a sua confiança. Este pede a sua conferência:
                    cada número aparece com a fonte pública e a data ao lado, no próprio
                    texto.
                  </p>
                  <p className="text-body leading-relaxed text-ink-2">
                    E quando o dado não existe na fonte, a tese escreve que não existe — em
                    vez de inventar. Ela organiza o raciocínio inteiro; a decisão continua
                    sendo sua.
                  </p>
                </div>
              </div>
            </div>

            {/* BASE — CTAs (esquerda) + a 1ª gema (direita). */}
            <div className="capa-linha--base flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
              <div className="flex flex-col gap-3">
                <div className="entrada-hero i-4">
                  {/* .magnetico (R2): física de cursor SÓ nas ilhas da landing.
                      CTAs de capa: px-8/py-4 + text-lede (crit. 2). */}
                  <div data-capa-ctas="" className="flex flex-wrap items-center gap-3">
                    <Link
                      href="/tese"
                      className="magnetico bg-brasa px-8 py-4 font-sans text-lede font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
                    >
                      Gerar tese
                    </Link>
                    <Link
                      href={`/tese?ticker=${encodeURIComponent(primeiroTicker)}`}
                      className="magnetico border border-field px-8 py-4 font-sans text-lede font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto"
                    >
                      Ver um exemplo real: {primeiroTicker}
                    </Link>
                  </div>
                </div>
                <div className="entrada-hero i-5">
                  <p className="text-ui text-ink-3">
                    Não precisa ser analista: abra um exemplo pronto e siga qualquer número
                    até a fonte.
                  </p>
                </div>
              </div>
              {/* A 1ª GEMA (D14): mesma anatomia de citação da prova viva — chip
                  bg-realce OPACO (trava M3), agora com o bisel/elevação do
                  `.gema-chip__corpo`. Reuso "sem o filho" (gema.css): a classe
                  do CORPO entra direto neste <p> (ele já anima a si mesmo pelo
                  keyframe .citacao-pin-hero; nenhum dos dois toca box-shadow).
                  Mesmo [1] do H1, mesma fonte/data da prova viva — nenhum
                  número novo. */}
              <p className="citacao-pin-hero gema-chip__corpo w-fit bg-realce px-4 py-2 font-mono text-meta text-ink-2">
                <sup aria-hidden="true" className="text-brasa-texto">
                  [1]
                </sup>{" "}
                Fonte: B3 · Carteira teórica do Ibovespa · {dataCarteira}
              </p>
            </div>

            {/* DOBRA — o vinco sobre o fio full-bleed, no limite dos 100svh. */}
            <div className="capa-linha--dobra">
              <div aria-hidden="true" className="fio-travessa" />
              <span aria-hidden="true" className="capa-vinco">
                continua abaixo da dobra ↓
              </span>
            </div>
          </div>
        </section>
        {/* Fio de prumo (D10): hairline vertical que se desenha com o scroll e
            mergulha na seção seguinte. IRMÃO de #hero (nunca dentro: o
            .tem-foco é overflow:hidden e o clipa) — o seletor `#hero +
            .fio-de-prumo` (cinema/hero.css §9) dá a geometria só a ESTA
            instância. Progresso puro (scroll(root)): isento de reduce, como a
            régua de leitura. */}
        <div aria-hidden="true" className="fio-de-prumo" />

        {/* ============================================================
            2. PROVA VIVA (crit. 3a/3b) — a anatomia de uma citação, com
            números reais e auditados, agora no palco largo da Bancada.
            CAPÍTULO scrubado (CenaScrub): os blocos [data-cena-el] imprimem/
            desimprimem atados ao scroll (3 atos, piso 0.55). Um escritor por
            propriedade: o GSAP é dono único de transform/opacity dos
            [data-cena-el]; o relevo/lift das gemas vive no FILHO
            `.gema-chip__corpo` (nó que o GSAP nunca toca).
            ============================================================ */}
        <CenaScrub>
          <section
            id="prova"
            data-cena="prova"
            aria-labelledby="prova-titulo"
            className="capitulo bancada relative gap-y-8 py-14"
          >
            {/* `relative` na SEÇÃO: containing block + offsetParent do
                <FioDaFonte/> (SVG absolute, PRIMEIRO filho — pinta sob as
                gemas, que são position:relative). `.b-sangria` dá a ele a
                coluna inteira do grid: a caixa do SVG volta a ser exatamente o
                padding-box da seção (o mesmo `inset:0` de antes; sem isso o
                default `.bancada > *` o encolheria à coluna da medida e o
                path — medido em coordenadas da SEÇÃO — sairia deslocado). */}
            <FioDaFonte className="b-sangria" />

            {/* Assinatura de abertura de capítulo (D6): hairline full-bleed que
                se imprime como uma régua ("clac"). */}
            <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden="true">
              {null}
            </Reveal>

            <div data-cena-el="" className="b-medida-esq flex flex-col gap-3">
              <h2
                id="prova-titulo"
                className="atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
              >
                Prova viva: assim nasce um número na tese
              </h2>
              <p className="text-lede leading-relaxed text-ink-2">
                Como saber se dá pra confiar numa tese escrita por máquina? Você não precisa
                acreditar: pode conferir — o caminho de cada número fica impresso na página.
              </p>
              {/* Tooltip DENTRO de [data-cena-el] (permitido): o gatilho do
                  TermoTooltip só transiciona color/border-color e o popup anima
                  a si mesmo — NUNCA acrescentar classe de transform/opacity ao
                  gatilho (um-escritor: o CenaScrub é o dono deste bloco). */}
              <p className="text-body leading-relaxed text-ink-2">
                Todo dado factual segue o mesmo caminho: o número em mono, marcado com uma{" "}
                <TermoTooltip {...tooltipDe("citations")}>citação</TermoTooltip>, ligado a uma
                fonte e a uma data — sem exceção. É a mesma anatomia que um auditor
                procuraria: quem afirmou, com base em quê, apurado quando. Exemplo real, com
                a{" "}
                <TermoTooltip {...tooltipDe("carteira-teorica")}>
                  carteira teórica do Ibovespa
                </TermoTooltip>{" "}
                (B3, {dataCarteira})
                <sup data-fio-de="" className="font-mono text-brasa-texto">
                  [1]
                </sup>
                :
              </p>
            </div>

            {/* As três gemas atravessando o palco (crit. 3b). O <li> é o alvo
                estável; o [data-cena-el] é o `.gema-chip` (wrapper estrutural
                do GSAP) e o relevo mora no `.gema-chip__corpo` — o MESMO nó que
                pinta o bg-realce (um box-shadow inset só é visível no nó que
                tem o background opaco). */}
            <ol className="b-palco grid gap-3 sm:grid-cols-3">
              {provaViva.map((papel, i) => (
                <li key={papel.ticker}>
                  <div
                    data-cena-el=""
                    data-fio-ate={i === 0 ? "" : undefined}
                    className="gema-chip h-full"
                  >
                    <div className="gema-chip__corpo flex h-full flex-col gap-2 border-l-2 border-brasa bg-realce px-4 py-4">
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
                  </div>
                </li>
              ))}
            </ol>

            <p data-cena-el="" className="b-medida-esq text-ui leading-relaxed text-ink-3">
              Assim é toda citação da plataforma: o número no corpo do texto, a nota entre
              colchetes e a fonte com a data logo abaixo — nunca escondida em rodapé. Número
              sem esse rastro não entra como fato.
            </p>
          </section>
        </CenaScrub>

        {/* ============================================================
            3. A CENA DO NASCIMENTO (crit. 3) — 8 planos em 420svh (missão
            OURIVESARIA 1C, §3-C3/§7-B5), FORA de qualquer CenaScrub (R1:
            nenhum ancestral do sticky pode receber transform — grep de
            auditoria). O cabeçalho e o colofão ficam FORA do rolo de
            420svh: o `.nascimento-cena` é o ÚNICO filho do rolo, então o
            sticky começa exatamente onde a timeline do NascimentoScrub
            começa (trigger "top top" do rolo). Um cabeçalho dentro do rolo
            dessincronizaria o scrub do grude. `aria-labelledby` cruza a
            fronteira por ID — o nome acessível da seção continua sendo o
            h2 visível. `legendasVisiveis` liga o letreiro (E-A3: o próprio
            <ol>, fonte única); `.nascimento-poeira` é camada decorativa da
            atmosfera --nasc-lume (aria-hidden, cinema/nascimento.css).
            ============================================================ */}
        <div className="bancada gap-y-3 pt-14">
          <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden="true">
            {null}
          </Reveal>
          <div className="b-medida-esq flex flex-col gap-3">
            <h2
              id="nascimento-titulo"
              className="atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
            >
              Do dado bruto ao número que você confere
            </h2>
            <p className="text-lede leading-relaxed text-ink-2">
              Acompanhe um número real saindo da fonte oficial e chegando à linha da tese.
              Nenhuma etapa é enfeite: cada uma existe para você poder refazer o caminho de
              trás para frente.
            </p>
          </div>
        </div>
        <NascimentoScrub>
          <section
            id="nascimento"
            aria-labelledby="nascimento-titulo"
            className="nascimento-rolo b-sangria"
          >
            <div className="nascimento-cena">
              <CenaNascimento legendasVisiveis />
              <div aria-hidden="true" className="nascimento-poeira" />
            </div>
          </section>
        </NascimentoScrub>
        <div className="bancada gap-y-3 pb-14">
          <p className="b-medida-esq text-ui leading-relaxed text-ink-3">
            Assim nasce cada número da tese: com fonte e data — ou não entra.
          </p>
        </div>

        {/* ============================================================
            4. A VITRINE (crit. 4) — a faixa de veludo full-bleed. O `.b-sangria`
            no <section> é inerte aqui (o <main> não é grade — e não pode ser:
            um ancestral flex/grid desliga o pinSpacing do Salão logo abaixo);
            fica registrado porque a faixa JÁ é borda-a-borda por ser um bloco
            de nível de <main>. `.veludo-escopo` re-declara os PARES COMPLETOS
            de tokens semânticos (E5/E6) — por isso `text-ink`/`text-ink-2` aqui
            dentro já saem claros nos DOIS temas, sem fork de componente.
            E18: o <div> que envolve <GaleriaBanca> NÃO leva [data-cena-el] — o
            cabeçalho com o controle de pausa (1º controle WCAG 2.2.2 do site)
            jamais pode desbotar a 0,55 na saída da cena, justo quando é
            exigido.
            ============================================================ */}
        <CenaScrub>
          <section
            id="galeria"
            data-cena="galeria"
            aria-labelledby="galeria-titulo"
            className="capitulo vitrine-veludo veludo-escopo b-sangria"
          >
            <div className="bancada gap-y-6">
              <div data-cena-el="" className="b-medida-esq flex flex-col gap-3">
                <h2
                  id="galeria-titulo"
                  className="font-display text-h2 font-semibold tracking-tight text-ink"
                >
                  Teses prontas — abrem na hora
                </h2>
                <p className="text-lede leading-relaxed text-ink-2">
                  Comece por uma que já existe: são {totalExemplos} teses geradas pelo motor e
                  renovadas em ciclo diário. Abrem na hora, sem espera e sem cadastro.
                </p>
                <p className="text-body leading-relaxed text-ink-2">
                  Estão aqui os {acoesExemplo} maiores pesos da carteira teórica do Ibovespa
                  (B3, {dataCarteira}) e mais {multiativoExemplo} exemplos multiativo — um FII
                  e um título do Tesouro Direto. Abra qualquer uma com olho de auditor:
                  escolha um número, siga a citação até a fonte e volte.
                </p>
              </div>
              <div className="b-palco">
                {/* PERF (regra das ilhas, topo do arquivo): a casca client
                    recebe os cartões PRONTOS do servidor. O `<li>` é o alvo
                    estável de snap/IO e o wrapper `.banca-carimbo
                    .vitrine-pedestal` é quem anima (D19/D24) — nunca o <li>
                    (transform no alvo de snap desloca a snap area) e nunca
                    dentro do CartaoTese (D24: intocado). */}
                <GaleriaBanca
                  tickers={exemplos.map((papel) => papel.ticker)}
                  cartoes={exemplos.map((papel) => (
                    <li key={papel.ticker} className="w-64 shrink-0 snap-start">
                      <div className="banca-carimbo vitrine-pedestal h-full">
                        <CartaoTese papel={papel} dataCarteira={DATA_CARTEIRA_IBOV} />
                      </div>
                    </li>
                  ))}
                />
              </div>
              <div data-cena-el="" className="b-medida-esq flex flex-col gap-3">
                <p className="text-ui leading-relaxed text-ink-3">
                  Se uma tese pronta tiver expirado, o motor a regenera na hora — com as
                  mesmas regras de citação, fonte e data.
                </p>
                <LinkCinema
                  href="/teses"
                  className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
                >
                  Ver todas as teses de exemplo →
                </LinkCinema>
              </div>
            </div>
          </section>
        </CenaScrub>

        {/* ============================================================
            5. O SALÃO DE LAPIDAÇÃO (crit. 5) — o travelling de página inteira.
            O componente renderiza, num fragmento, o PÓRTICO (o veludo que
            escurece; recebe este cabeçalho como children) e a própria
            <section id="dimensoes">: os dois viram FILHOS DIRETOS de <main>.
            NENHUM wrapper aqui — um ancestral flex/grid desliga o pinSpacing,
            o documento não cresce e a página acaba no meio do travelling (o
            bug histórico de 2026-07-12). A seção fica FORA do CenaScrub (R1).
            Os TermoTooltip das bolhas vivem em DIMENSOES.texto (ReactNode).
            ============================================================ */}
        <SalaoDimensoes
          rotulos={DIMENSOES.map(({ numero, titulo }) => ({ numero, titulo }))}
          bolhas={DIMENSOES.map((d) => (
            // PERF (regra das ilhas, topo do arquivo): a bolha inteira é
            // montada AQUI, no servidor — inclusive os TermoTooltip de
            // `d.texto`, que continuam sendo ilhas próprias. A casca client
            // (SalaoDimensoes) só as acha por `li.bolha-bancada` e as mede.
            // Anatomia (D27) e nomes de classe: contrato de cinema/salao.css
            // — não mexer sem a folha dona.
            <li key={d.numero} className="bolha-bancada">
              <div className="bolha-miolo">
                <p aria-hidden className="salao-camada bolha-numeral">
                  {d.numero}
                </p>
                <h3 className="salao-camada bolha-titulo">
                  <span className="sr-only">{`${d.numero} — `}</span>
                  {d.titulo}
                </h3>
                <p className="salao-camada bolha-texto">{d.texto}</p>
                <p className="salao-camada bolha-selo">
                  <span aria-hidden className="bolha-selo__marca">
                    ◈
                  </span>
                  <span>
                    <span className="sr-only">Fonte: </span>
                    {d.fonte}
                  </span>
                </p>
              </div>
            </li>
          ))}
        >
          <div className="bancada gap-y-3">
            <div className="b-medida-esq flex flex-col gap-3">
              <h2
                id="dimensoes-titulo"
                className="font-display text-h2 font-semibold tracking-tight text-ink"
              >
                Cinco dimensões, uma tese
              </h2>
              <p className="text-lede leading-relaxed text-ink-2">
                É aqui que a tese é lapidada, camada por camada: cada dimensão entra com a
                fonte oficial que a sustenta.
              </p>
              <p className="text-body leading-relaxed text-ink-2">
                O motor monta a tese por camadas e fecha com síntese e{" "}
                <TermoTooltip {...tooltipDe("contra-tese")}>contra-tese</TermoTooltip> (
                <TermoTooltip {...tooltipDe("bull-bear")}>bull × bear</TermoTooltip>) — os
                dois lados do mesmo dado, lado a lado, para você julgar. Fato e interpretação
                vêm sempre separados no texto. O quadro completo vale para as ações; FIIs e
                títulos do Tesouro Direto usam um subconjunto próprio de dimensões — sem pares
                globais nem macro global dedicada —, e a régua impressa em cada tese mostra
                exatamente quais entraram.
              </p>
              <p className="text-ui leading-relaxed text-ink-3">
                Nenhuma camada é opinião solta: cada uma carrega o nome da fonte que a
                sustenta.
              </p>
              <LinkCinema
                href="/como-funciona"
                className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
              >
                Como o motor funciona, passo a passo →
              </LinkCinema>
            </div>
          </div>
        </SalaoDimensoes>

        {/* ============================================================
            6. A SALA DO CONTRATO (crit. 6) — #postura. CAPÍTULO scrubado.
            A faixa CVM leva [data-cvm]: o CenaScrub trava a opacity dela em 1
            — o aviso regulatório se move com o capítulo, mas JAMAIS esmaece.
            Texto da box: VERBATIM, intocado (compliance).
            ============================================================ */}
        <CenaScrub>
          <section
            id="postura"
            data-cena="postura"
            aria-labelledby="postura-titulo"
            className="capitulo bancada gap-y-6 py-14"
          >
            <Reveal variant="reveal-regua" className="fio-travessa" aria-hidden="true">
              {null}
            </Reveal>
            <h2
              data-cena-el=""
              id="postura-titulo"
              className="b-medida-esq atraso-regua font-display text-h2 font-semibold tracking-tight text-ink"
            >
              Auditável por construção
            </h2>
            <p
              data-cena-el=""
              className="b-medida-esq text-lede leading-relaxed text-ink-2"
            >
              Não pedimos que você acredite na tese. Pedimos que você a audite — e deixamos
              todas as portas abertas para isso.
            </p>
            <p data-cena-el="" className="b-medida-esq text-body leading-relaxed text-ink-2">
              Por que isso é raro? A maioria das análises entrega a conclusão e guarda o
              caminho: você lê o número, não o que o sustenta. Aqui o caminho é o produto.
              Toda afirmação factual sai com citação, fonte e data; toda interpretação vem
              rotulada como interpretação; e o que não foi encontrado na fonte pública é
              declarado como{" "}
              <TermoTooltip {...tooltipDe("lacuna-declarada")}>lacuna</TermoTooltip> — nunca
              preenchido com estimativa. Dá mais trabalho e rende menos frase de efeito. Em
              compensação, permite a você — iniciante ou profissional — discordar da tese com
              o dado na mão.
            </p>

            {/* As 3 placas gravadas, desalinhadas à direita (D35). O
                `.exemplo-vivo` é a citação REAL derivada de exemplosProntos()
                — espaço SEMPRE reservado no DOM (CLS-safe), revelado por
                opacity no hover/foco e sempre visível em touch/reduce. */}
            <ol className="b-medida-dir mt-2 grid gap-6 sm:grid-cols-3">
              {PRINCIPIOS.map((p, i) => (
                <li key={p.titulo} className={DESALINHO_PLACA[i]}>
                  <div
                    data-cena-el=""
                    className="placa-gravada flex h-full flex-col gap-2 bg-card px-6 py-6"
                  >
                    <span className="placa-gravada__numeral font-mono text-h3">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="font-display text-lede font-semibold text-ink">
                      {p.titulo}
                    </h3>
                    <p className="text-ui leading-relaxed text-ink-2">{p.texto}</p>
                    <p className="exemplo-vivo mt-auto pt-2 font-mono text-meta text-ink-3">
                      {p.exemplo}
                    </p>
                  </div>
                </li>
              ))}
            </ol>

            {/* Faixa-brasão: o aviso CVM tratado como manchete, não letra miúda.
                Peça de honra (APOTEOSE C9/D5): o pai [data-cena-el][data-cvm]
                é container liso — o GSAP do CenaScrub segue dono único do
                transform(y) dele (opacity travada em 1). O filho .cvm-honra
                leva as classes visuais + a levitação/keyline de cinema/
                secoes.css — um-escritor: o float por keyframe mora no FILHO.
                HORIZONTE: só a ÂNCORA mudou (`.b-palco` — a peça agora atravessa
                o palco largo). Texto VERBATIM (compliance — não mudar uma
                vírgula). */}
            {/* aria-label DISTINTO da Tarja sticky (gate visual 2026-07-13):
                dois role=note com o mesmo rótulo confundem a navegação por
                landmark em leitor de tela — e o seletor do pin do Salão
                ('[role="note"][aria-label="Aviso regulatório"]') passa a casar
                SÓ com a Tarja, por construção. */}
            <div
              data-cena-el=""
              data-cvm=""
              role="note"
              aria-label="Postura regulatória"
              className="b-palco mt-4"
            >
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
              className="b-palco flex flex-wrap items-center gap-4 border border-line bg-card px-6 py-5"
            >
              <p className="flex-1 text-ui leading-relaxed text-ink-2">
                Pronto para auditar uma? Gere a tese de uma ação da B3, de um FII ou de um
                título do Tesouro Direto — ou abra uma tese pronta e siga um número até a
                fonte.
              </p>
              {/* CTA da faixa final — .magnetico (R2: ilha da landing). */}
              <Link
                href="/tese"
                className="magnetico bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
              >
                Gerar tese
              </Link>
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
