// Vista estruturada da tese: seções por dimensão (h2 do markdown do motor) com
// sumário e âncoras, citações com preview de fonte, lacunas destacadas e o
// registro auditável de fontes ao fim. Presentacional — sem estado próprio.

import {
  Blocos,
  construirRefs,
  separarSecoes,
  type CitacaoRef,
  type Secao,
} from "./Markdown";
import type { Fonte, TeseOut } from "./types";
import { papelPorTicker } from "@/lib/tickers";

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

export function AvisoBanner({ aviso }: { aviso: string }) {
  // Disclaimer regulatório de NÃO-recomendação. NUNCA pode sumir: se o backend
  // não enviar o aviso, caímos numa constante fixa no front (conformidade).
  const texto =
    aviso?.trim() ||
    "Não é recomendação de investimento. Tese estruturada a partir de dados públicos; a decisão é do leitor.";
  return (
    <div
      role="note"
      className="rounded-xl border border-aviso-borda bg-aviso-fundo px-5 py-4 text-sm text-aviso-texto"
    >
      <span className="font-semibold">Aviso: </span>
      {texto}
    </div>
  );
}

function FonteLink({ fonte }: { fonte: Fonte }) {
  if (!urlHttp(fonte.url)) {
    return <span className="font-medium text-tinta">{fonte.descricao}</span>;
  }
  return (
    <a
      href={fonte.url}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-tinta underline decoration-linha-forte underline-offset-2 hover:decoration-selo-texto"
    >
      {fonte.descricao || fonte.url}
    </a>
  );
}

function ehSecaoLacunas(secao: Secao): boolean {
  return /lacunas/i.test(secao.titulo);
}

function TextoCitado({ texto, url }: { texto: string; url: string | null | undefined }) {
  if (!urlHttp(url)) {
    return <span className="text-tinta">“{texto}”</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-tinta underline decoration-linha-forte underline-offset-2 hover:decoration-selo-texto"
    >
      “{texto}”
    </a>
  );
}

function Sumario({ secoes }: { secoes: Secao[] }) {
  return (
    <nav aria-label="Sumário da tese" className="text-sm">
      <p className="mb-2 font-mono text-[0.65rem] uppercase tracking-widest text-tinta-3">
        Sumário
      </p>
      <ol className="flex flex-col gap-1 border-l border-linha">
        {secoes.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className={`block border-l-2 border-transparent py-0.5 pl-3 leading-snug hover:border-selo-texto hover:text-tinta ${
                ehSecaoLacunas(s) ? "text-aviso-texto" : "text-tinta-2"
              }`}
            >
              {s.titulo}
            </a>
          </li>
        ))}
        <li>
          <a
            href="#citacoes"
            className="block border-l-2 border-transparent py-0.5 pl-3 leading-snug text-tinta-2 hover:border-selo-texto hover:text-tinta"
          >
            Citações e registro de fontes
          </a>
        </li>
      </ol>
    </nav>
  );
}

export function TeseView({ tese }: { tese: TeseOut }) {
  const documento = tese.markdown ? separarSecoes(tese.markdown) : null;
  const refs: CitacaoRef[] = construirRefs(tese.citacoes);
  const papel = papelPorTicker(tese.ticker);
  const secaoLacunas = documento?.secoes.find(ehSecaoLacunas);
  const temEstrutura = (documento?.secoes.length ?? 0) > 0;

  return (
    <article className="flex w-full flex-col gap-6">
      <AvisoBanner aviso={tese.aviso} />

      {/* Cabeçalho do documento */}
      <header className="rounded-xl border border-linha bg-cartao p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="font-mono text-2xl font-bold tracking-tight text-tinta">
            {tese.ticker}
          </h2>
          {tese.criado_em && (
            <time dateTime={tese.criado_em} className="text-xs text-tinta-3">
              Gerada em {formatDataHora(tese.criado_em)}
            </time>
          )}
        </div>
        {(papel || documento?.titulo) && (
          <p className="mt-1 font-display text-lg text-tinta-2">
            {papel?.nome ?? documento?.titulo}
          </p>
        )}
        <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 border-t border-linha pt-3 text-xs text-tinta-3">
          <div className="flex gap-1.5">
            <dt>Citações:</dt>
            <dd className="font-mono font-semibold text-tinta-2">
              {tese.citacoes.length}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt>Fontes:</dt>
            <dd className="font-mono font-semibold text-tinta-2">
              {tese.fontes.length}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt>Lacunas declaradas:</dt>
            <dd
              className={`font-mono font-semibold ${
                tese.lacunas.length > 0 ? "text-aviso-texto" : "text-tinta-2"
              }`}
            >
              {tese.lacunas.length}
            </dd>
          </div>
        </dl>
      </header>

      {/* Lacunas em destaque: abstenção é informação, não rodapé. */}
      {tese.lacunas.length > 0 && (
        <div
          className="rounded-xl border border-aviso-borda bg-aviso-fundo px-5 py-4 text-sm text-aviso-texto"
          role="note"
        >
          <p className="font-semibold">
            {tese.lacunas.length === 1
              ? "1 dado não encontrado — o motor absteve em vez de estimar."
              : `${tese.lacunas.length} dados não encontrados — o motor absteve em vez de estimar.`}
          </p>
          {secaoLacunas && (
            <a
              href={`#${secaoLacunas.id}`}
              className="mt-1 inline-block underline underline-offset-2"
            >
              Ver a lista completa na seção Lacunas
            </a>
          )}
        </div>
      )}

      {!tese.markdown?.trim() && (
        <p className="rounded-xl border border-linha bg-cartao p-5 text-sm text-tinta-2">
          A tese não retornou conteúdo.
        </p>
      )}

      {documento && !temEstrutura && (
        <div className="rounded-xl border border-linha bg-cartao p-6">
          <Blocos blocos={[...documento.intro]} refs={refs} />
        </div>
      )}

      {documento && temEstrutura && (
        <div className="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)]">
          {/* Sumário: fixo na lateral no desktop, dobrável no mobile */}
          <div className="lg:sticky lg:top-16 lg:self-start">
            <details className="rounded-xl border border-linha bg-cartao px-4 py-3 lg:hidden">
              <summary className="cursor-pointer text-sm font-medium text-tinta">
                Sumário
              </summary>
              <div className="pt-3">
                <Sumario secoes={documento.secoes} />
              </div>
            </details>
            <div className="hidden lg:block">
              <Sumario secoes={documento.secoes} />
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-5">
            {documento.intro.length > 0 && (
              <div className="rounded-xl border border-linha bg-cartao p-6">
                <Blocos blocos={documento.intro} refs={refs} />
              </div>
            )}
            {documento.secoes.map((secao) => {
              const lacunas = ehSecaoLacunas(secao);
              return (
                <section
                  key={secao.id}
                  id={secao.id}
                  aria-labelledby={`${secao.id}-titulo`}
                  className={`rounded-xl border p-6 ${
                    lacunas
                      ? "border-aviso-borda bg-aviso-fundo/60"
                      : "border-linha bg-cartao"
                  }`}
                >
                  <h3
                    id={`${secao.id}-titulo`}
                    className={`mb-4 border-b pb-3 font-display text-lg font-semibold tracking-tight ${
                      lacunas
                        ? "border-aviso-borda text-aviso-texto"
                        : "border-linha text-tinta"
                    }`}
                  >
                    {secao.titulo}
                  </h3>
                  <Blocos blocos={secao.blocos} refs={refs} />
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
          className="flex flex-col gap-6 rounded-xl border border-linha bg-cartao p-6"
        >
          {tese.citacoes.length > 0 && (
            <div>
              <h3 className="mb-3 font-display text-lg font-semibold tracking-tight text-tinta">
                Citações
              </h3>
              <p className="mb-3 text-xs text-tinta-3">
                Trechos literais ancorados nos documentos-fonte. Os marcadores{" "}
                <span className="font-mono">[n]</span> ao longo do texto apontam
                para esta lista.
              </p>
              <ol className="flex flex-col gap-2">
                {tese.citacoes.map((c, i) => (
                  <li
                    key={i}
                    id={`citacao-${i + 1}`}
                    className="flex gap-3 rounded-lg border border-linha bg-papel px-4 py-3 text-sm"
                  >
                    <span className="font-mono text-xs font-semibold text-selo-texto">
                      [{i + 1}]
                    </span>
                    <div className="min-w-0">
                      <TextoCitado texto={c.texto_citado} url={c.fonte?.url} />
                      {(c.titulo_documento || c.fonte) && (
                        <p className="mt-1 text-xs text-tinta-3">
                          {c.titulo_documento || c.fonte?.descricao}
                          {c.fonte?.dt_referencia &&
                            ` · ${formatData(c.fonte.dt_referencia)}`}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {tese.fontes.length > 0 && (
            <div id="registro-de-fontes">
              <h3 className="mb-3 font-display text-lg font-semibold tracking-tight text-tinta">
                Registro de fontes
              </h3>
              <ul className="flex flex-col gap-2">
                {tese.fontes.map((f, i) => (
                  <li
                    key={f.id ?? i}
                    className="flex flex-col gap-0.5 rounded-lg border border-linha bg-papel px-4 py-3 text-sm"
                  >
                    <FonteLink fonte={f} />
                    {f.dt_referencia && (
                      <span className="text-xs text-tinta-3">
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
      <footer className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-tinta-3">
        <span>id: {tese.id}</span>
        {tese.uso?.modelo && <span>modelo: {tese.uso.modelo}</span>}
        {typeof tese.uso?.custo_estimado_usd === "number" && (
          <span>custo estimado: US$ {tese.uso.custo_estimado_usd.toFixed(4)}</span>
        )}
      </footer>
    </article>
  );
}
