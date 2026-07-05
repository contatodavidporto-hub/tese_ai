"use client";

import { useCallback, useRef, useState } from "react";
import { Markdown } from "./Markdown";
import type { CriarTeseResposta, Fonte, TeseOut } from "./types";

// O cliente fala SÓ com a mesma origem (/api/...) por causa do CSP `connect-src 'self'`.
// Os Route Handlers em src/app/api/teses repassam ao backend FastAPI no servidor.
const POLL_INTERVAL_MS = 2000;
const MAX_TRIES = 30;

type UiState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "polling"; id: string; ticker: string }
  | { phase: "ready"; tese: TeseOut }
  | { phase: "error"; message: string };

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function messageFrom(data: unknown, fallback: string): string {
  if (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    typeof (data as { detail?: unknown }).detail === "string"
  ) {
    return (data as { detail: string }).detail;
  }
  return fallback;
}

export function TeseClient() {
  const [ticker, setTicker] = useState("PETR4");
  const [state, setState] = useState<UiState>({ phase: "idle" });
  // Guarda o ticker da execução em curso para ignorar respostas obsoletas.
  const runIdRef = useRef(0);

  const isBusy = state.phase === "submitting" || state.phase === "polling";

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const normalized = ticker.trim().toUpperCase();
      if (!normalized || isBusy) return;

      const runId = ++runIdRef.current;
      setState({ phase: "submitting" });

      let id: string;
      try {
        const res = await fetch("/api/teses", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker: normalized }),
        });
        const data = (await res.json().catch(() => null)) as
          | CriarTeseResposta
          | { detail?: string }
          | null;

        if (!res.ok || !data || !("id" in data) || !data.id) {
          setState({
            phase: "error",
            message: messageFrom(data, `Falha ao criar a tese (HTTP ${res.status}).`),
          });
          return;
        }
        id = data.id;
      } catch {
        setState({
          phase: "error",
          message: "Não foi possível enviar a solicitação. Tente novamente.",
        });
        return;
      }

      if (runIdRef.current !== runId) return;
      setState({ phase: "polling", id, ticker: normalized });

      for (let attempt = 0; attempt < MAX_TRIES; attempt++) {
        await sleep(POLL_INTERVAL_MS);
        if (runIdRef.current !== runId) return; // execução substituída

        let tese: TeseOut | null = null;
        try {
          const res = await fetch(`/api/teses/${encodeURIComponent(id)}`);
          const data = (await res.json().catch(() => null)) as
            | TeseOut
            | { detail?: string }
            | null;
          if (res.ok && data && "status" in data) {
            tese = data as TeseOut;
          } else if (!res.ok) {
            // erro transitório do proxy/backend: tenta de novo até esgotar
            continue;
          }
        } catch {
          continue; // rede instável: nova tentativa
        }

        if (!tese) continue;
        if (runIdRef.current !== runId) return;

        if (tese.status === "ready") {
          setState({ phase: "ready", tese });
          return;
        }
        if (tese.status === "error") {
          setState({
            phase: "error",
            message:
              tese.erro?.trim() ||
              "A geração da tese falhou. Verifique a configuração do backend e tente novamente.",
          });
          return;
        }
        // status === "processing": continua o polling
      }

      if (runIdRef.current === runId) {
        setState({
          phase: "error",
          message:
            "Tempo esgotado aguardando a tese. O processamento pode estar demorando — tente novamente em instantes.",
        });
      }
    },
    [ticker, isBusy],
  );

  return (
    <div className="flex w-full max-w-2xl flex-col gap-6">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-xl border border-neutral-200 bg-white p-5 shadow-sm sm:flex-row sm:items-end dark:border-neutral-800 dark:bg-neutral-900"
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <label
            htmlFor="ticker"
            className="text-sm font-medium text-neutral-700 dark:text-neutral-300"
          >
            Ticker
          </label>
          <input
            id="ticker"
            name="ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="PETR4"
            autoComplete="off"
            spellCheck={false}
            disabled={isBusy}
            aria-describedby="ticker-hint"
            className="rounded-lg border border-neutral-300 bg-white px-3 py-2 font-mono text-sm text-neutral-900 outline-none focus:border-neutral-500 focus:ring-2 focus:ring-neutral-400/40 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100"
          />
          <span
            id="ticker-hint"
            className="text-xs text-neutral-400 dark:text-neutral-500"
          >
            Ex.: PETR4, VALE3, ITUB4.
          </span>
        </div>
        <button
          type="submit"
          disabled={isBusy || ticker.trim() === ""}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-neutral-400/50 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
        >
          {isBusy ? (
            <>
              <Spinner />
              Gerando...
            </>
          ) : (
            "Gerar tese"
          )}
        </button>
      </form>

      <div aria-live="polite" className="flex flex-col gap-6">
        {state.phase === "submitting" && (
          <LoadingCard label="Enviando solicitação..." />
        )}
        {state.phase === "polling" && (
          <LoadingCard
            label={`Processando a tese de ${state.ticker}... isso pode levar alguns segundos.`}
          />
        )}
        {state.phase === "error" && <ErrorCard message={state.message} />}
        {state.phase === "ready" && <Resultado tese={state.tese} />}
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <span
      className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden
    />
  );
}

function LoadingCard({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-xl border border-neutral-200 bg-white px-5 py-4 text-sm text-neutral-600 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300"
    >
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
    >
      <p className="font-medium">Não foi possível gerar a tese</p>
      <p className="mt-1 text-red-700 dark:text-red-300">{message}</p>
    </div>
  );
}

// Disclaimer regulatório de NÃO-recomendação. NUNCA pode sumir: se o backend
// não enviar o aviso, caímos numa constante fixa no front (controle de conformidade).
const AVISO_PADRAO =
  "Não é recomendação de investimento. Tese estruturada a partir de dados públicos; a decisão é do leitor.";

function AvisoBanner({ aviso }: { aviso: string }) {
  const texto = aviso?.trim() || AVISO_PADRAO;
  return (
    <div
      role="note"
      className="rounded-xl border border-amber-300 bg-amber-50 px-5 py-4 text-sm text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <span className="font-semibold">Aviso: </span>
      {texto}
    </div>
  );
}

// Só URLs http(s) viram link (javascript:, data:... -> texto). O backend já
// valida; esta é a segunda linha de defesa no render.
function urlHttp(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\//i.test(url);
}

function FonteLink({ fonte }: { fonte: Fonte }) {
  // Sem URL http(s) -> texto, não link quebrado.
  if (!urlHttp(fonte.url)) {
    return (
      <span className="font-medium text-neutral-700 dark:text-neutral-300">
        {fonte.descricao}
      </span>
    );
  }
  return (
    <a
      href={fonte.url}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-neutral-900 underline decoration-neutral-400 underline-offset-2 hover:decoration-neutral-700 dark:text-neutral-100 dark:decoration-neutral-600 dark:hover:decoration-neutral-300"
    >
      {fonte.descricao || fonte.url}
    </a>
  );
}

function Resultado({ tese }: { tese: TeseOut }) {
  return (
    <article className="flex flex-col gap-6">
      <AvisoBanner aviso={tese.aviso} />

      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-mono text-lg font-semibold text-neutral-900 dark:text-neutral-100">
          {tese.ticker}
        </h2>
        {tese.criado_em && (
          <time
            dateTime={tese.criado_em}
            className="text-xs text-neutral-400 dark:text-neutral-500"
          >
            {formatData(tese.criado_em)}
          </time>
        )}
      </header>

      <section className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        {tese.markdown?.trim() ? (
          <Markdown source={tese.markdown} />
        ) : (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            A tese não retornou conteúdo.
          </p>
        )}
      </section>

      {tese.citacoes.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            Citações
          </h3>
          <ul className="flex flex-col gap-2">
            {tese.citacoes.map((c, i) => (
              <li
                key={i}
                className="rounded-lg border border-neutral-200 bg-white px-4 py-3 text-sm shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
              >
                {urlHttp(c.fonte?.url) ? (
                  <a
                    href={c.fonte!.url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-neutral-800 underline decoration-neutral-400 underline-offset-2 hover:decoration-neutral-700 dark:text-neutral-200 dark:decoration-neutral-600 dark:hover:decoration-neutral-300"
                  >
                    “{c.texto_citado}”
                  </a>
                ) : (
                  <span className="text-neutral-800 dark:text-neutral-200">
                    “{c.texto_citado}”
                  </span>
                )}
                {(c.titulo_documento || c.fonte) && (
                  <p className="mt-1 text-xs text-neutral-400 dark:text-neutral-500">
                    {c.titulo_documento || c.fonte?.descricao}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tese.fontes.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            Fontes
          </h3>
          <ul className="flex flex-col gap-2">
            {tese.fontes.map((f) => (
              <li
                key={f.id}
                className="flex flex-col gap-0.5 rounded-lg border border-neutral-200 bg-white px-4 py-3 text-sm shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
              >
                <FonteLink fonte={f} />
                {f.dt_referencia && (
                  <span className="text-xs text-neutral-400 dark:text-neutral-500">
                    Referência: {formatData(f.dt_referencia)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tese.lacunas.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
            Lacunas (dados não encontrados)
          </h3>
          <ul className="list-disc space-y-1 rounded-lg border border-neutral-200 bg-white px-5 py-4 pl-8 text-sm text-neutral-700 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300">
            {tese.lacunas.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}

      {tese.uso?.modelo && (
        <p className="font-mono text-xs text-neutral-400 dark:text-neutral-500">
          modelo: {tese.uso.modelo}
          {typeof tese.uso.custo_estimado_usd === "number" &&
            ` · custo estimado: US$ ${tese.uso.custo_estimado_usd.toFixed(4)}`}
        </p>
      )}
    </article>
  );
}

function formatData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}
