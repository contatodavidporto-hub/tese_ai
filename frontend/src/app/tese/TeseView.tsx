// Vista estruturada da tese: seções por dimensão (h2 do markdown do motor) com
// sumário e âncoras, citações com preview de fonte, lacunas destacadas e o
// registro auditável de fontes ao fim. Presentacional — sem estado próprio
// (só `useReveal` local para orquestrar a assinatura "Impressão de Régua").

import { classesReveal, Reveal, useReveal } from "@/components/motion/Reveal";
import { useSecaoAtiva } from "@/components/motion/useSecaoAtiva";
import { papelPorTicker, slotVirada } from "@/lib/tickers";
import {
  Blocos,
  construirRefs,
  separarSecoes,
  type CitacaoRef,
  type Secao,
} from "./Markdown";
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

export function AvisoBanner({ aviso }: { aviso: string }) {
  // Disclaimer regulatório de NÃO-recomendação. NUNCA pode sumir: se o backend
  // não enviar o aviso, caímos numa constante fixa no front (conformidade).
  const texto =
    aviso?.trim() ||
    "Não é recomendação de investimento. Tese estruturada a partir de dados públicos; a decisão é do leitor.";
  return (
    <div role="note" className="flex items-start gap-3 border-l-4 border-aviso-borda bg-aviso-fundo px-5 py-4">
      <span className="mt-0.5 shrink-0 font-sans text-label font-semibold uppercase tracking-[0.16em] text-aviso-texto">
        Aviso
      </span>
      <p className="text-ui text-aviso-texto">{texto}</p>
    </div>
  );
}

function BadgeLacuna({ texto }: { texto: string }) {
  // Lacuna Declarada (assinatura de motion): outline tracejado expande e
  // dissolve 1x — mesma hierarquia de uma citação, nunca a de erro.
  const { ref, armado, revelado } = useReveal<HTMLSpanElement>();
  return (
    <span
      ref={ref}
      className={classesReveal(
        "lacuna-declarada",
        armado,
        revelado,
        "inline-flex w-fit items-center bg-aviso-fundo px-2 py-1 font-mono text-meta font-semibold uppercase tracking-[0.1em] text-aviso-texto",
      )}
    >
      {texto}
    </span>
  );
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

// Rótulo curto da classe do ativo (Fase 2 multiativo) para o selo do
// masthead. `null`/ausente = ação — mesma convenção de `TeseOut.classe_ativo`
// (backend/app/schemas/tese.py: NULL no banco significa "acao", migração 0005).
function rotuloClasse(classe: TeseOut["classe_ativo"]): string {
  switch (classe) {
    case "fii":
      return "FII";
    case "renda_fixa":
      return "Renda fixa";
    default:
      return "Ação";
  }
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

function Sumario({ secoes }: { secoes: Secao[] }) {
  // D2 (CORRECOES-RODADA-1.md): hook extraído para módulo compartilhado
  // (src/components/motion/useSecaoAtiva.ts) — o mesmo scrollspy também
  // move o IndiceNav de /como-funciona. "citacoes" é a âncora fixa da
  // página (fora de `secoes`, ver JSX de TeseView) — inclui-se sempre; se o
  // bloco não existir nesta tese, `getElementById` só devolve `null` e o
  // hook descarta.
  const ativo = useSecaoAtiva([...secoes.map((s) => s.id), "citacoes"]);
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

// Impressão de Régua + cláusula numerada mono: abre cada seção do report.
// `useReveal` único (em vez de dois <Reveal>) para a régua e o título
// dispararem exatamente juntos, com o título assentando 80ms depois
// (`.atraso-regua`) — ver DESIGN-TOKENS.md §3.
function CabecalhoSecao({
  tituloId,
  numero,
  texto,
  lacunas,
}: {
  tituloId: string;
  numero: string | null;
  texto: string;
  lacunas: boolean;
}) {
  const { ref, armado, revelado } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} className="flex flex-col gap-4">
      <div
        className={classesReveal(
          "reveal-regua",
          armado,
          revelado,
          lacunas ? "h-1 w-full origin-left bg-aviso-borda" : "h-1 w-full origin-left bg-line-strong",
        )}
      />
      <h3
        id={tituloId}
        className={classesReveal(
          undefined,
          armado,
          revelado,
          `atraso-regua flex flex-wrap items-baseline gap-x-3 font-display text-h2 font-semibold tracking-tight ${
            lacunas ? "text-aviso-texto" : "text-ink"
          }`,
        )}
      >
        {numero && (
          <span
            className={`font-mono text-ui font-semibold ${lacunas ? "text-aviso-texto" : "text-brasa-texto"}`}
          >
            {numero}.
          </span>
        )}
        {texto}
      </h3>
    </div>
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
  // os 12 tickers pré-gerados recebem shared element (view-transition-name
  // via classe pré-declarada); os demais seguem sem nome, cobertos só pelo
  // véu de `.virada-edicao` (tese/page.tsx).
  const slotEdicao = slotVirada(tese.ticker);

  return (
    <article className="flex w-full flex-col gap-10">
      {/* Régua de Leitura: barra de progresso de 2px em brasa no topo da
          página (CSS scroll-driven em globals.css, `.regua-leitura`); o
          scrollspy de fallback vive em `useSecaoAtiva`, logo acima. */}
      <div className="regua-leitura" aria-hidden />

      <AvisoBanner aviso={tese.aviso} />

      {/* Masthead do documento: cabeçalho de research report */}
      <Reveal className="flex flex-col gap-6 border-b-4 border-line-strong bg-card px-6 py-8 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
          <div className="flex flex-col gap-1">
            <p className="flex flex-wrap items-center gap-x-2 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
              Research report
              {/* Selo discreto da classe do ativo (Fase 2 multiativo) — mesma
                  hierarquia tipográfica do eyebrow, só com borda para separar
                  visualmente sem introduzir uma cor nova (tokens BRASA). */}
              <span className="border border-line-strong px-1.5 py-0.5 text-ink-3">
                {rotuloClasse(tese.classe_ativo)}
              </span>
            </p>
            <h2
              className={`font-mono text-h1 font-bold tracking-tight text-ink${slotEdicao ? ` vt-tese-${slotEdicao}` : ""}`}
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
                <Sumario secoes={documento.secoes} />
              </div>
            </details>
            <div className="hidden lg:block">
              <Sumario secoes={documento.secoes} />
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
