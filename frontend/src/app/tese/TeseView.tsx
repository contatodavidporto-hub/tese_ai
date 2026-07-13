// Vista estruturada da tese: seções por dimensão (h2 do markdown do motor) com
// sumário e âncoras, citações com preview de fonte, lacunas destacadas e o
// registro auditável de fontes ao fim. Presentacional — sem estado próprio
// (o `useReveal`/Impressão de Régua agora mora em `SecaoChrome.tsx`, que
// também serve as 4 seções novas do envelope — ver import abaixo).

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
    <article className="flex w-full flex-col gap-10">
      {/* Régua de Leitura: barra de progresso de 2px em brasa no topo da
          página (CSS scroll-driven em globals.css, `.regua-leitura`); o
          scrollspy de fallback vive em `useSecaoAtiva`, logo acima. */}
      <div className="regua-leitura" aria-hidden />

      <AvisoBanner aviso={tese.aviso} />

      {/* Masthead do documento: cabeçalho de research report. `.aurora-
          masthead` (§4, direcao-de-arte-cinema.md — "aurora SÓ no
          masthead") pinta um pool de luz local atrás do título, ACIMA do
          `bg-card` opaco do card e ABAIXO do conteúdo — ver globals.css
          item 20. O masthead é IRMÃO de `.regua-leitura` (não ancestral),
          então `position:relative`/`isolation:isolate` da classe não
          reabrem a trava C2. Missão APOTEOSE (crit. 10): `.masthead-
          apoteose` (cinema/tese-apoteose.css) imprime a keyline ameixa no
          topo 1x no mount — entrada mais rica sem tocar no writer do
          <Reveal> (o keyframe anima só o ::after próprio); a aurora segue
          com o alfa CALIBRADO do globals (reuso, nunca boost local). */}
      <Reveal className="aurora-masthead masthead-apoteose flex flex-col gap-6 border-b-4 border-line-strong bg-card px-6 py-8 sm:px-8">
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
      </Reveal>

      {/* Lacunas em destaque: abstenção é informação, não rodapé — 1 de 3
          pontos de ênfase (header acima + este bloco + a seção "Lacunas"). */}
      {tese.lacunas.length > 0 && (
        <Reveal className="flex flex-wrap items-center gap-x-4 gap-y-3 border-l-4 border-aviso-borda bg-aviso-fundo px-5 py-4">
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
        <p className="border border-line bg-card p-5 text-ui text-ink-2">A tese não retornou conteúdo.</p>
      )}

      {documento && !temEstrutura && (
        <div className="max-w-[68ch] border border-line bg-card p-6 sm:p-8">
          <Blocos blocos={[...documento.intro]} refs={refs} hostsOk={hostsOk} />
        </div>
      )}

      {documento && temEstrutura && (
        <div className="grid gap-10 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-16">
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
      {tese.metricas_setor && tese.metricas_setor.length > 0 && (
        <SecaoEnvelope id="metricas-setor" titulo="Métricas do setor">
          <SecaoMetricasSetor metricas={tese.metricas_setor} />
        </SecaoEnvelope>
      )}

      {tese.valuation && (
        <SecaoEnvelope id="valuation" titulo="Valuation">
          <SecaoValuation valuation={tese.valuation} />
        </SecaoEnvelope>
      )}

      {tese.tecnica && (
        <SecaoEnvelope id="analise-tecnica" titulo="Análise técnica">
          <SecaoTecnica tecnica={tese.tecnica} graficos={tese.graficos ?? []} />
        </SecaoEnvelope>
      )}

      {tese.consenso && (
        <SecaoEnvelope id="consenso" titulo="Consenso de analistas">
          <SecaoConsenso consenso={tese.consenso} />
        </SecaoEnvelope>
      )}

      {/* Trilha auditável: citações numeradas + registro de fontes */}
      {(tese.citacoes.length > 0 || tese.fontes.length > 0) && (
        <section
          id="citacoes"
          aria-label="Citações e registro de fontes"
          className="flex flex-col gap-8 border border-line-strong bg-card px-6 py-8 sm:px-8"
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
                    <Reveal
                      variant="citacao-pin"
                      className={`flex gap-4 bg-realce py-4 pl-5 pr-4 ${i < 12 ? `i-${i + 1}` : ""}`}
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
              <ul className="flex flex-col divide-y divide-line">
                {tese.fontes.map((f, i) => (
                  <li key={f.id ?? i} className="flex flex-col gap-0.5 py-3 text-ui">
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

      {/* Metadados da geração — parte da trilha de auditoria */}
      <footer className="flex flex-wrap gap-x-6 gap-y-1 border-t border-line pt-4 font-mono text-meta text-ink-3">
        <span>id: {tese.id}</span>
        {tese.uso?.modelo && <span>modelo: {tese.uso.modelo}</span>}
        {typeof tese.uso?.custo_estimado_usd === "number" && (
          <span>custo estimado: US$ {tese.uso.custo_estimado_usd.toFixed(4)}</span>
        )}
      </footer>
    </article>
  );
}
