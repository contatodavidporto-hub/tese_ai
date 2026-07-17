// Vista estruturada da tese: seções por dimensão (h2 do markdown do motor) com
// sumário e âncoras, citações com preview de fonte, lacunas destacadas e o
// registro auditável de fontes ao fim. Presentacional — sem estado próprio
// (o `useReveal`/Impressão de Régua agora mora em `SecaoChrome.tsx`, que
// também serve as 4 seções novas do envelope — ver import abaixo).
//
// MISSÃO "HORIZONTE" (2026-07-14, raia 3A — C7 direção §9, "/tese — A Peça"):
// CSS-only, zero JS novo, delta gsap ZERO. `<article>` migra à BANCADA
// (aninhada — D3): o masthead vira capa de research report full-bleed
// (`.b-sangria`), o corpo segue `.b-palco` (largura >= à antiga, E30) e as
// linhas de fonte (citações + registro de fontes) ganham o relevo
// `.gema-chip__corpo` (D14, cinema/gema.css — dona: raia 1A). Régua/morph/
// `esperaViradaEmVoo`/skeleton/AvisoBanner/4-blocos-CVM: INTOCADOS.

import { Reveal } from "@/components/motion/Reveal";
import { useSecaoAtiva } from "@/components/motion/useSecaoAtiva";
import { papelPorTicker, slotVirada, type ClasseAtivo } from "@/lib/tickers";
import {
  Blocos,
  construirRefs,
  separarSecoes,
  type CitacaoRef,
  type Secao,
} from "./Markdown";
import { AvisoBanner, BadgeLacuna, CabecalhoSecao, SecaoEnvelope } from "./SecaoChrome";
import { SecaoConsenso } from "./SecaoConsenso";
import { SecaoMetricasSetor } from "./SecaoMetricasSetor";
import { SecaoTecnica } from "./SecaoTecnica";
import { SecaoValuation } from "./SecaoValuation";
import type { Fonte, TeseOut } from "./types";

function formatDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function formatData(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR");
}

// Só URLs http(s) viram link (javascript:, data:... -> texto). O backend já
// valida; esta é a segunda linha de defesa no render.
function urlHttp(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\//i.test(url);
}

// O motor emite exatamente "## 1. Fundamentos" ... "## 8. Lacunas"
// (backend/app/services/tese.py) — o número já vem no título; separamos a
// "cláusula numerada" (mono) do texto (serifa) para o tratamento editorial.
function splitClausula(titulo: string): { numero: string | null; texto: string } {
  const m = /^(\d{1,2})\.\s*(.*)$/.exec(titulo.trim());
  return m ? { numero: m[1], texto: m[2] } : { numero: null, texto: titulo };
}

function FonteLink({ fonte }: { fonte: Fonte }) {
  if (!urlHttp(fonte.url)) {
    return <span className="font-medium text-ink">{fonte.descricao}</span>;
  }
  return (
    <a
      href={fonte.url}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-ink underline decoration-line-strong underline-offset-2 hover:decoration-brasa-texto"
    >
      {fonte.descricao || fonte.url}
    </a>
  );
}

function ehSecaoLacunas(secao: Secao): boolean {
  return /lacunas/i.test(secao.titulo);
}

const ROTULO_POR_CLASSE: Record<ClasseAtivo, string> = {
  acao: "Ação",
  fii: "FII",
  renda_fixa: "Renda fixa",
};

// Rótulo curto da classe do ativo (Fase 2 multiativo) para o selo do
// masthead — FAIL-CLOSED (selo errado é pior que selo nenhum):
// 1) resposta com `classe_ativo` conhecida -> usa (backend é a autoridade);
// 2) resposta sem classe (NULL legado da migração 0005 / backend pré-Fase 2)
//    -> infere do catálogo local (TODOS_PAPEIS; ausência de `classe` no
//    catálogo == ação, convenção de lib/tickers.ts) — evita rotular HGLG11/
//    TD-* de "Ação" quando o backend ainda não envia o campo;
// 3) valor futuro desconhecido do backend, ou ticker fora do catálogo ->
//    `null` (nenhum selo; omitir > errar).
function rotuloClasse(tese: TeseOut): string | null {
  // Alarga para string: o contrato tipa a união, mas em runtime o backend
  // pode evoluir antes do front — string futura NUNCA pode virar "Ação".
  const classe: string | null | undefined = tese.classe_ativo;
  if (classe != null) {
    return Object.hasOwn(ROTULO_POR_CLASSE, classe)
      ? ROTULO_POR_CLASSE[classe as ClasseAtivo]
      : null;
  }
  const papel = papelPorTicker(tese.ticker);
  return papel ? ROTULO_POR_CLASSE[papel.classe ?? "acao"] : null;
}

// A seção "4. Camada geopolítica e correlações" é a D5 do ARQUITETURA.md — a
// única voz narrada em itálico Newsreader 500 (DESIGN-BRIEF.md §3 e §5).
function ehSecaoNarrada(secao: Secao): boolean {
  return /geopolít/i.test(secao.titulo);
}

function TextoCitado({ texto, url }: { texto: string; url: string | null | undefined }) {
  if (!urlHttp(url)) {
    return <span className="text-ink">“{texto}”</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-ink underline decoration-line-strong underline-offset-2 hover:decoration-brasa-texto"
    >
      “{texto}”
    </a>
  );
}

// Âncora extra do sumário para as 4 seções novas do envelope — não vêm do
// markdown (sem "N." de cláusula), por isso `numero` fica sempre `null`.
type AncoraExtra = { id: string; titulo: string };

function Sumario({ secoes, extras = [] }: { secoes: Secao[]; extras?: AncoraExtra[] }) {
  // D2 (CORRECOES-RODADA-1.md): hook extraído para módulo compartilhado
  // (src/components/motion/useSecaoAtiva.ts) — o mesmo scrollspy também
  // move o IndiceNav de /como-funciona. "citacoes" é a âncora fixa da
  // página (fora de `secoes`, ver JSX de TeseView) — inclui-se sempre; se o
  // bloco não existir nesta tese, `getElementById` só devolve `null` e o
  // hook descarta. `extras` (Métricas do setor/Valuation/Técnica/Consenso)
  // segue a mesma lógica: só existem no DOM se o bloco veio no envelope.
  const ativo = useSecaoAtiva([...secoes.map((s) => s.id), ...extras.map((e) => e.id), "citacoes"]);
  return (
    <nav aria-label="Sumário da tese">
      <p className="mb-3 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
        Sumário
      </p>
      <ol className="flex flex-col gap-0.5 border-l border-line">
        {secoes.map((s) => {
          const { numero, texto } = splitClausula(s.titulo);
          const lacunas = ehSecaoLacunas(s);
          const ehAtivo = ativo === s.id;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={ehAtivo ? "location" : undefined}
                className={`flex items-baseline gap-2 border-l-2 py-1 pl-3 text-ui leading-snug transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto hover:text-ink ${
                  ehAtivo
                    ? "border-brasa-texto text-ink"
                    : `border-transparent ${lacunas ? "text-aviso-texto" : "text-ink-2"}`
                }`}
              >
                {numero && <span className="font-mono text-meta text-ink-3">{numero}</span>}
                <span>{texto}</span>
              </a>
            </li>
          );
        })}
        {extras.map((e) => {
          const ehAtivo = ativo === e.id;
          return (
            <li key={e.id}>
              <a
                href={`#${e.id}`}
                aria-current={ehAtivo ? "location" : undefined}
                className={`flex items-baseline gap-2 border-l-2 py-1 pl-3 text-ui leading-snug transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto hover:text-ink ${
                  ehAtivo ? "border-brasa-texto text-ink" : "border-transparent text-ink-2"
                }`}
              >
                <span>{e.titulo}</span>
              </a>
            </li>
          );
        })}
        <li>
          <a
            href="#citacoes"
            aria-current={ativo === "citacoes" ? "location" : undefined}
            className={`flex items-baseline gap-2 border-l-2 py-1 pl-3 text-ui leading-snug transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto hover:text-ink ${
              ativo === "citacoes" ? "border-brasa-texto text-ink" : "border-transparent text-ink-2"
            }`}
          >
            <span aria-hidden className="font-mono text-meta text-ink-3">
              §
            </span>
            <span>Citações e registro de fontes</span>
          </a>
        </li>
      </ol>
    </nav>
  );
}

// Hosts das fontes registradas: só eles podem virar link clicável no markdown
// (um link do LLM para host fora do registro degrada para texto — anti-phishing).
function hostsDasFontes(tese: TeseOut): ReadonlySet<string> {
  const hosts = new Set<string>();
  const coletar = (url: string | null | undefined) => {
    if (!urlHttp(url)) return;
    try {
      hosts.add(new URL(url).hostname);
    } catch {
      // URL malformada não entra na allowlist
    }
  };
  for (const f of tese.fontes) coletar(f.url);
  for (const c of tese.citacoes) coletar(c.fonte?.url);
  return hosts;
}

export function TeseView({ tese }: { tese: TeseOut }) {
  const documento = tese.markdown ? separarSecoes(tese.markdown) : null;
  const refs: CitacaoRef[] = construirRefs(tese.citacoes);
  const hostsOk = hostsDasFontes(tese);
  const papel = papelPorTicker(tese.ticker);
  const secaoLacunas = documento?.secoes.find(ehSecaoLacunas);
  const temEstrutura = (documento?.secoes.length ?? 0) > 0;
  // Virada de Edição (motion): mesmo slot estático da galeria/teaser — só
  // os 13 tickers pré-gerados recebem shared element (view-transition-name
  // via classe pré-declarada); os demais seguem sem nome, cobertos só pelo
  // véu de `.virada-edicao` (tese/page.tsx).
  const slotEdicao = slotVirada(tese.ticker);
  // `null` = classe indeterminável -> nenhum selo (fail-closed, ver acima).
  const seloClasse = rotuloClasse(tese);
  // Âncoras extras do sumário — mesma condição de renderização das seções
  // novas mais abaixo no JSX (mantidas em sincronia manualmente: um bloco só
  // entra aqui se a seção correspondente realmente for renderizar).
  const extrasSumario: AncoraExtra[] = [
    ...(tese.metricas_setor && tese.metricas_setor.length > 0
      ? [{ id: "metricas-setor", titulo: "Métricas do setor" }]
      : []),
    ...(tese.valuation ? [{ id: "valuation", titulo: "Valuation" }] : []),
    ...(tese.tecnica ? [{ id: "analise-tecnica", titulo: "Análise técnica" }] : []),
    ...(tese.consenso ? [{ id: "consenso", titulo: "Consenso de analistas" }] : []),
  ];

  return (
    // Migração à BANCADA (missão HORIZONTE, raia 3A, C7 direção §9): o
    // `<article>` deixa de ser um `flex flex-col` estreito (herdava a
    // largura do `max-w-5xl` de page.tsx) e vira o próprio grid — NESTED
    // (D3 "aninhável"): `<main>` já é `.bancada` lá em cima, mas tudo o que
    // fica entre `<main>` e este `<article>` (TeseClient.tsx, fora da posse
    // desta raia) é `flex`/`w-full` comum, então os NOMES de linha do grid
    // de `<main>` não alcançam aqui (grid-column só resolve contra o
    // ANCESTOR GRID DIRETO) — precisa da própria instância. Cada filho
    // direto abaixo escolhe a coluna: `.b-sangria` só no masthead (a capa
    // full-bleed, C7), `.b-palco` no resto do corpo (largura >= à antiga,
    // E30), default `medida` (68ch) nos dois estados de fallback sem
    // estrutura — texto puro, sem prova de largura a proteger.
    // `gap-y-10` (NUNCA `gap-10`): mesma armadilha de page.tsx — este
    // `<article>` é `.bancada` (grid de 6 colunas nomeadas); `gap-10`
    // escreveria `column-gap` também, quebrando a soma das trilhas e
    // produzindo overflow-x real em viewports estreitos (achado por teste
    // em 390px, E3). `gap-y-10` é só o espaçamento vertical entre as
    // seções empilhadas — o mesmo papel do antigo `flex-col gap-10`.
    <article className="bancada gap-y-10">
      {/* Régua de Leitura: barra de progresso de 2px em brasa no topo da
          página (CSS scroll-driven em globals.css, `.regua-leitura`); o
          scrollspy de fallback vive em `useSecaoAtiva`, logo acima.
          `position:fixed` (globals.css item 8) — fica FORA do fluxo do
          grid, não participa do `.bancada` acima nem herda coluna. */}
      <div className="regua-leitura" aria-hidden />

      {/* `.b-palco` num wrapper PRÓPRIO (não uma prop nova em AvisoBanner,
          que é dos 4 blocos CVM verbatim — SecaoChrome.tsx só muda "se a
          copy exigir", e isto é layout, não copy): o aviso ganha a mesma
          largura do resto do corpo, sem tocar o componente. */}
      <div className="b-palco">
        <AvisoBanner aviso={tese.aviso} />
      </div>

      {/* Masthead do documento: "A CAPA" do research report — C7 direção
          §9 (raia 3A, missão HORIZONTE): "masthead vira capa de research
          report full-bleed (faixa bg-card ponta a ponta, réguas
          atravessando)". `.b-sangria` faz o card sangrar até a borda do
          grid do `<article>` (E30: sempre >= à largura do antigo
          `max-w-5xl` — nunca 100vw, E3 bane `vw` em largura de palco).
          O masthead SEGUE filho direto de `<article>` (nenhum wrapper novo
          o envolve) — trava C2 exige que ele continue IRMÃO de
          `.regua-leitura`, nunca ancestral dela; `.b-sangria` é só uma
          classe a mais no MESMO nó, não uma reparentagem. `.aurora-
          masthead` (§4, direcao-de-arte-cinema.md — "aurora SÓ no
          masthead") pinta um pool de luz local atrás do título, ACIMA do
          `bg-card` opaco do card e ABAIXO do conteúdo — ver globals.css
          item 20; ela cobre a caixa inteira via `inset:0`, então continua
          válida no card agora full-bleed. Missão APOTEOSE (crit. 10):
          `.masthead-apoteose` (cinema/tese-apoteose.css) imprime a keyline
          tinta (--moldura-tinta) no topo 1x no mount — entrada mais rica sem tocar no
          writer do <Reveal> (o keyframe anima só o ::after próprio); a
          aurora segue com o alfa CALIBRADO do globals (reuso, nunca boost
          local). Essa keyline + o `border-b-4` abaixo são as "réguas
          atravessando" da direção — nenhuma das duas é nova: só ficaram
          mais largas (o elemento-novo RESERVA independente de glow desta
          rota, E27 — se o AA reprovar qualquer specular da rota, esta
          keyline plana continua provando a capa sozinha).

          Dentro do card, um `.bancada` ANINHADO (D3) recria as colunas
          relativas à largura full-bleed — sem ele, `.b-palco` não teria
          contexto de grid próprio aqui dentro (linhas nomeadas só valem
          para filhos DIRETOS do grid que as declara). O conteúdo real
          (ticker/data + a `dl` de citações/fontes/lacunas) mora em
          `.b-palco` — largo, mas com o mesmo respiro do resto do corpo,
          nunca colado nas bordas físicas da tela. */}
      <Reveal className="aurora-masthead masthead-apoteose b-sangria border-b-4 border-line-strong bg-card">
        <div className="bancada">
          <div className="b-palco flex flex-col gap-6 px-6 py-8 sm:px-8">
            <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
              <div className="flex flex-col gap-1">
                <p className="flex flex-wrap items-center gap-x-2 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
                  Research report
                  {/* Selo discreto da classe do ativo (Fase 2 multiativo) — mesma
                      hierarquia tipográfica do eyebrow, só com borda para separar
                      visualmente sem introduzir uma cor nova (tokens BRASA).
                      Só renderiza quando a classe é determinável (fail-closed). */}
                  {seloClasse && (
                    <span className="border border-line-strong px-1.5 py-0.5 text-ink-3">
                      {seloClasse}
                    </span>
                  )}
                </p>
                {/* `.ticker-luz` (crit. 7, primitiva da Onda 0): specular
                    dourado contido que segue o ponteiro sobre o ticker —
                    `--mx`/`--my` chegam pela ilha delegada do TeseClient
                    (usePonteiro, seletorAlvo ".ticker-luz"). O sprite (::after,
                    z:-1 no contexto isolado do h2) fica clipado pelo
                    overflow:hidden do `.aurora-masthead` pai — "specular
                    contido" (S2), nunca névoa vazando do card. */}
                <h2
                  className={`ticker-luz font-mono text-h1 font-bold tracking-tight text-ink${slotEdicao ? ` vt-tese-${slotEdicao}` : ""}`}
                >
                  {tese.ticker}
                </h2>
                {(papel || documento?.titulo) && (
                  <p className="font-display text-lede text-ink-2">{papel?.nome ?? documento?.titulo}</p>
                )}
              </div>
              {tese.criado_em && (
                <time dateTime={tese.criado_em} className="font-mono text-meta text-ink-3">
                  Gerada em {formatDataHora(tese.criado_em)}
                </time>
              )}
            </div>

            <dl className="flex flex-wrap gap-x-8 gap-y-2 border-t border-line pt-4">
              <div className="flex items-baseline gap-1.5">
                <dt className="font-sans text-label uppercase tracking-[0.1em] text-ink-3">Citações</dt>
                <dd className="font-mono text-ui font-semibold text-ink">{tese.citacoes.length}</dd>
              </div>
              <div className="flex items-baseline gap-1.5">
                <dt className="font-sans text-label uppercase tracking-[0.1em] text-ink-3">Fontes</dt>
                <dd className="font-mono text-ui font-semibold text-ink">{tese.fontes.length}</dd>
              </div>
              <div className="flex items-baseline gap-1.5">
                <dt className="font-sans text-label uppercase tracking-[0.1em] text-ink-3">
                  Lacunas declaradas
                </dt>
                <dd
                  className={`font-mono text-ui font-semibold ${
                    tese.lacunas.length > 0 ? "text-aviso-texto" : "text-ink"
                  }`}
                >
                  {tese.lacunas.length}
                </dd>
              </div>
              {tese.uso?.modelo && (
                <div className="flex items-baseline gap-1.5">
                  <dt className="font-sans text-label uppercase tracking-[0.1em] text-ink-3">Modelo</dt>
                  <dd className="font-mono text-ui font-semibold text-ink">{tese.uso.modelo}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </Reveal>

      {/* Lacunas em destaque: abstenção é informação, não rodapé — 1 de 3
          pontos de ênfase (header acima + este bloco + a seção "Lacunas").
          `.b-palco`: mesma largura do resto do corpo (a capa acima é a
          ÚNICA seção full-bleed da rota). */}
      {tese.lacunas.length > 0 && (
        <Reveal className="b-palco flex flex-wrap items-center gap-x-4 gap-y-3 border-l-4 border-aviso-borda bg-aviso-fundo px-5 py-4">
          <BadgeLacuna texto="Dado não encontrado" />
          <p className="text-ui text-aviso-texto">
            {tese.lacunas.length === 1
              ? "1 dado não encontrado — o motor absteve em vez de estimar."
              : `${tese.lacunas.length} dados não encontrados — o motor absteve em vez de estimar.`}
            {secaoLacunas && (
              <>
                {" "}
                <a href={`#${secaoLacunas.id}`} className="sublinhado-brasa font-semibold text-aviso-texto">
                  Ver a lista completa
                </a>
              </>
            )}
          </p>
        </Reveal>
      )}

      {!tese.markdown?.trim() && (
        <p className="b-palco border border-line bg-card p-5 text-ui text-ink-2">
          A tese não retornou conteúdo.
        </p>
      )}

      {/* Fallback sem estrutura (raro): texto puro, sem cartão de sumário —
          medida default do grid (`.bancada > *`, 68ch) já é a lei
          tipográfica da casa; `max-w-[68ch]` some (redundante com o grid,
          D5: `max-w-*` internos obsoletos saem quando o grid já governa). */}
      {documento && !temEstrutura && (
        <div className="border border-line bg-card p-6 sm:p-8">
          <Blocos blocos={[...documento.intro]} refs={refs} hostsOk={hostsOk} />
        </div>
      )}

      {documento && temEstrutura && (
        <div className="b-palco grid gap-10 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-16">
          {/* Sumário: fixo na lateral no desktop, dobrável no mobile */}
          <div className="lg:sticky lg:top-16 lg:self-start">
            {/* A3 (alvo ≥24px, WCAG 2.5.8): padding vai NO <summary> — é o
                elemento focável/clicável de verdade; o <details> só molda
                o card por fora. */}
            <details className="border border-line bg-card px-4 lg:hidden">
              <summary className="flex min-h-11 cursor-pointer items-center font-sans text-ui font-medium text-ink">
                Sumário
              </summary>
              <div className="pb-3">
                <Sumario secoes={documento.secoes} extras={extrasSumario} />
              </div>
            </details>
            <div className="hidden lg:block">
              <Sumario secoes={documento.secoes} extras={extrasSumario} />
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-12">
            {documento.intro.length > 0 && (
              <div className="max-w-[68ch] border-b border-line-strong pb-8">
                <Blocos blocos={documento.intro} refs={refs} hostsOk={hostsOk} />
              </div>
            )}
            {documento.secoes.map((secao) => {
              const lacunas = ehSecaoLacunas(secao);
              const { numero, texto } = splitClausula(secao.titulo);
              return (
                <section key={secao.id} id={secao.id} aria-labelledby={`${secao.id}-titulo`} className="flex flex-col gap-6">
                  <CabecalhoSecao
                    tituloId={`${secao.id}-titulo`}
                    numero={numero}
                    texto={texto}
                    lacunas={lacunas}
                  />
                  <div
                    className={`max-w-[68ch] ${
                      lacunas ? "border-l-4 border-aviso-borda bg-aviso-fundo/30 px-5 py-4" : ""
                    }`}
                  >
                    <Blocos
                      blocos={secao.blocos}
                      refs={refs}
                      hostsOk={hostsOk}
                      narrada={ehSecaoNarrada(secao)}
                    />
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      )}

      {/* Blocos novos do envelope ("Tese Profunda" — contrato do envelope v3,
          .maestro/contrato-envelope-v3.md): ordem canônica fixada no
          contrato — Métricas do setor → Valuation → Análise técnica →
          Consenso. Cada seção só aparece se o backend enviou o bloco
          (ausência = tese legada válida ou fail-closed de gate bloqueado —
          o router não serve bloco novo nenhum nesse caso); dentro de cada
          seção presente, o aviso/nota correspondente fica SEMPRE visível e
          listas vazias (indicadores/modelos/itens) degradam para as
          lacunas declaradas, nunca para "seção sumiu". */}
      {/* `.b-palco` num wrapper próprio em cada bloco do envelope (mesma
          lógica do AvisoBanner acima): `SecaoEnvelope`/`SecaoChrome.tsx` não
          muda (nada de copy exigindo isso), então a largura entra por fora,
          sem tocar o componente nem o `id`/`aria-labelledby` que o sumário
          usa para scroll-to-anchor (o `id` continua no `<section>` interno,
          intocado pelo wrapper). */}
      {tese.metricas_setor && tese.metricas_setor.length > 0 && (
        <div className="b-palco">
          <SecaoEnvelope id="metricas-setor" titulo="Métricas do setor">
            <SecaoMetricasSetor metricas={tese.metricas_setor} />
          </SecaoEnvelope>
        </div>
      )}

      {tese.valuation && (
        <div className="b-palco">
          <SecaoEnvelope id="valuation" titulo="Valuation">
            <SecaoValuation valuation={tese.valuation} />
          </SecaoEnvelope>
        </div>
      )}

      {tese.tecnica && (
        <div className="b-palco">
          <SecaoEnvelope id="analise-tecnica" titulo="Análise técnica">
            <SecaoTecnica tecnica={tese.tecnica} graficos={tese.graficos ?? []} />
          </SecaoEnvelope>
        </div>
      )}

      {tese.consenso && (
        <div className="b-palco">
          <SecaoEnvelope id="consenso" titulo="Consenso de analistas">
            <SecaoConsenso consenso={tese.consenso} />
          </SecaoEnvelope>
        </div>
      )}

      {/* Trilha auditável: citações numeradas + registro de fontes.
          `.b-palco`: mesma largura do resto do corpo. */}
      {(tese.citacoes.length > 0 || tese.fontes.length > 0) && (
        <section
          id="citacoes"
          aria-label="Citações e registro de fontes"
          className="b-palco flex flex-col gap-8 border border-line-strong bg-card px-6 py-8 sm:px-8"
        >
          {tese.citacoes.length > 0 && (
            <div>
              <h3 className="mb-1 font-display text-h3 font-semibold tracking-tight text-ink">Citações</h3>
              <p className="mb-4 text-ui text-ink-3">
                Trechos literais ancorados nos documentos-fonte. Os marcadores{" "}
                <span className="font-mono text-brasa-texto">[n]</span> ao longo do texto apontam para
                esta lista.
              </p>
              <ol className="flex flex-col gap-3 stagger">
                {tese.citacoes.map((c, i) => (
                  <li key={i} id={`citacao-${i + 1}`}>
                    {/* `.gema-chip__corpo` (missão HORIZONTE, D14 — "linhas
                        de fonte de /tese viram .gema-chip"): reuso SEM
                        wrapper (gema.css, "REUSO SEM O FILHO"), exatamente
                        o padrão já aprovado em `.citacao-pin-hero` — este
                        `<div>` já tem `bg-realce` (o mesmo campo opaco
                        M3-b) e já anima A SI MESMO via `variant="citacao-
                        pin"` (opacity/`transform: scale` no `.is-armed/
                        .is-revealed`, globals.css item 4); `.gema-chip__corpo`
                        só acrescenta `box-shadow` (bisel) + `translate` no
                        hover/focus — propriedades DIFERENTES das que o
                        Reveal já escreve, zero colisão (um-escritor por
                        propriedade continua valendo, nó a nó). */}
                    <Reveal
                      variant="citacao-pin"
                      className={`gema-chip__corpo flex gap-4 bg-realce py-4 pl-5 pr-4 ${i < 12 ? `i-${i + 1}` : ""}`}
                    >
                      <span className="font-mono text-meta font-semibold text-brasa-texto">[{i + 1}]</span>
                      <div className="min-w-0 flex flex-col gap-1">
                        <TextoCitado texto={c.texto_citado} url={c.fonte?.url} />
                        {(c.titulo_documento || c.fonte) && (
                          // A4 (contraste 1.4.3): text-ink-3 sobre bg-realce reprova
                          // por 0,011 — text-ink-2 verifica em 7.11:1 no mesmo par.
                          <p className="font-mono text-meta text-ink-2">
                            {c.titulo_documento || c.fonte?.descricao}
                            {c.fonte?.dt_referencia && ` · ${formatData(c.fonte.dt_referencia)}`}
                          </p>
                        )}
                      </div>
                    </Reveal>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {tese.fontes.length > 0 && (
            <div id="registro-de-fontes">
              <h3 className="mb-4 font-display text-h3 font-semibold tracking-tight text-ink">
                Registro de fontes
              </h3>
              {/* "Registro de fontes" É, literalmente, "linhas de fonte de
                  /tese" (D14) — a lista deixa de ser uma divide-y simples e
                  cada linha vira um `.gema-chip__corpo` sobre `bg-realce`
                  (mesmo campo M3-b das citações acima e do
                  `.citacao-pin-hero` do hero): peso visual consistente na
                  MESMA seção "Citações e registro de fontes". Reuso sem
                  wrapper — este `<li>` não anima a si mesmo por nenhum
                  outro motor, então o bisel/lift do `.gema-chip__corpo`
                  fica livre (zero um-escritor a disputar). */}
              <ul className="flex flex-col gap-3">
                {tese.fontes.map((f, i) => (
                  <li
                    key={f.id ?? i}
                    className="gema-chip__corpo flex flex-col gap-0.5 bg-realce px-4 py-3 text-ui"
                  >
                    <FonteLink fonte={f} />
                    {f.dt_referencia && (
                      <span className="font-mono text-meta text-ink-3">
                        Data de referência: {formatData(f.dt_referencia)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Metadados da geração — parte da trilha de auditoria. `.b-palco`:
          mesma largura do resto do corpo. */}
      <footer className="b-palco flex flex-wrap gap-x-6 gap-y-1 border-t border-line pt-4 font-mono text-meta text-ink-3">
        <span>id: {tese.id}</span>
        {tese.uso?.modelo && <span>modelo: {tese.uso.modelo}</span>}
        {typeof tese.uso?.custo_estimado_usd === "number" && (
          <span>custo estimado: US$ {tese.uso.custo_estimado_usd.toFixed(4)}</span>
        )}
      </footer>
    </article>
  );
}
