"use client";

// Fluxo de geração da tese. O cliente fala SÓ com a mesma origem (/api/...) por
// causa do CSP `connect-src 'self'`; os Route Handlers em src/app/api/teses
// repassam ao backend FastAPI no servidor.
//
// Caminhos:
//  - ticker novo: POST /api/teses -> polling do GET até ready/error;
//  - cache hit:   POST devolve `ready` -> GET imediato (abre na hora, custo 0);
//  - histórico:   GET /api/teses/{id} direto, sem POST (não regenera nada).

import { useCallback, useEffect, useRef, useState } from "react";

import {
  atualizarStatusHistorico,
  registrarNoHistorico,
} from "@/lib/historico";
import { EXEMPLOS_PRONTOS, TICKER_B3_RE } from "@/lib/tickers";
import { TeseView } from "./TeseView";
import { TickerCombobox } from "./TickerCombobox";
import type { CriarTeseResposta, TeseOut } from "./types";

const PRIMEIRA_ESPERA_MS = 1200;
const INTERVALO_MS = 2500;
const TEMPO_MAXIMO_MS = 240_000; // tese nova (5 dimensões + síntese) leva minutos

type UiState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "polling"; id: string; ticker: string; inicioEm: number }
  | { phase: "ready"; tese: TeseOut }
  | { phase: "error"; message: string; ticker?: string };

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

async function obterTese(id: string): Promise<TeseOut | { detail?: string } | null> {
  try {
    const res = await fetch(`/api/teses/${encodeURIComponent(id)}`);
    const data = (await res.json().catch(() => null)) as
      | TeseOut
      | { detail?: string }
      | null;
    if (res.ok && data && "status" in data) return data as TeseOut;
    if (res.status === 404) return { detail: "Tese não encontrada." };
    return null; // erro transitório: quem chama decide tentar de novo
  } catch {
    return null;
  }
}

type Props = {
  tickerInicial?: string;
  autoIniciar?: boolean;
  idInicial?: string;
};

export function TeseClient({ tickerInicial, autoIniciar, idInicial }: Props) {
  const [ticker, setTicker] = useState(tickerInicial ?? "");
  const [erroLocal, setErroLocal] = useState<string | null>(null);
  const [state, setState] = useState<UiState>({ phase: "idle" });
  // Relógio para exibir o tempo decorrido durante o polling.
  const [agora, setAgora] = useState(0);
  // Invalida execuções antigas quando o usuário inicia outra (ou cancela).
  const runIdRef = useRef(0);
  const autoDisparadoRef = useRef(false);

  const isBusy = state.phase === "submitting" || state.phase === "polling";

  useEffect(() => {
    if (state.phase !== "polling") return;
    const timer = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [state.phase]);

  const finalizar = useCallback((runId: number, tese: TeseOut) => {
    if (runIdRef.current !== runId) return;
    atualizarStatusHistorico(tese.id, tese.status);
    if (tese.status === "error") {
      setState({
        phase: "error",
        message:
          tese.erro?.trim() ||
          "A geração da tese falhou. Tente novamente em instantes.",
        ticker: tese.ticker,
      });
      return;
    }
    setState({ phase: "ready", tese });
    // URL recarregável/compartilhável dentro da sessão (sem navegação).
    try {
      window.history.replaceState(
        null,
        "",
        `/tese?id=${encodeURIComponent(tese.id)}&ticker=${encodeURIComponent(tese.ticker)}`,
      );
    } catch {
      // cosmético: se falhar, o fluxo segue
    }
  }, []);

  const acompanhar = useCallback(
    async (runId: number, id: string, tickerAlvo: string, primeiraEsperaMs: number) => {
      if (runIdRef.current !== runId) return;
      setState({ phase: "polling", id, ticker: tickerAlvo, inicioEm: Date.now() });

      const limite = Date.now() + TEMPO_MAXIMO_MS;
      let espera = primeiraEsperaMs;
      while (Date.now() < limite) {
        await sleep(espera);
        espera = INTERVALO_MS;
        if (runIdRef.current !== runId) return;

        const resultado = await obterTese(id);
        if (runIdRef.current !== runId) return;
        if (resultado && "status" in resultado) {
          if (resultado.status === "ready" || resultado.status === "error") {
            finalizar(runId, resultado);
            return;
          }
          continue; // processing: segue acompanhando
        }
        if (resultado && "detail" in resultado && resultado.detail) {
          setState({ phase: "error", message: resultado.detail, ticker: tickerAlvo });
          return;
        }
        // null = erro transitório de rede/proxy: tenta de novo até o limite
      }

      if (runIdRef.current === runId) {
        setState({
          phase: "error",
          message:
            "Tempo esgotado aguardando a tese. O processamento pode continuar no servidor — confira o Histórico em instantes.",
          ticker: tickerAlvo,
        });
      }
    },
    [finalizar],
  );

  const iniciarPorTicker = useCallback(
    async (tickerBruto: string) => {
      const normalizado = tickerBruto.trim().toUpperCase();
      if (!TICKER_B3_RE.test(normalizado)) {
        setErroLocal(
          "Ticker fora do formato da B3 (ex.: PETR4, VALE3, TAEE11). Confira o código e tente de novo — nenhuma chamada foi feita.",
        );
        return;
      }
      setErroLocal(null);

      const runId = ++runIdRef.current;
      setState({ phase: "submitting" });

      let criada: CriarTeseResposta;
      try {
        const res = await fetch("/api/teses", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker: normalizado }),
        });
        const data = (await res.json().catch(() => null)) as
          | CriarTeseResposta
          | { detail?: string }
          | null;

        if (!res.ok || !data || !("id" in data) || !data.id) {
          if (runIdRef.current !== runId) return;
          setState({
            phase: "error",
            message: messageFrom(data, `Falha ao criar a tese (HTTP ${res.status}).`),
            ticker: normalizado,
          });
          return;
        }
        criada = data;
      } catch {
        if (runIdRef.current !== runId) return;
        setState({
          phase: "error",
          message: "Não foi possível enviar a solicitação. Verifique a conexão e tente novamente.",
          ticker: normalizado,
        });
        return;
      }

      if (runIdRef.current !== runId) return;
      registrarNoHistorico({
        id: criada.id,
        ticker: criada.ticker || normalizado,
        status: criada.status,
        criadoEm: new Date().toISOString(),
      });

      if (criada.status === "ready") {
        // Cache hit: sem espera — GET imediato abre a tese na hora.
        const pronta = await obterTese(criada.id);
        if (runIdRef.current !== runId) return;
        if (pronta && "status" in pronta && pronta.status === "ready") {
          finalizar(runId, pronta);
          return;
        }
        // Corrida rara (cache expirou entre POST e GET): cai no acompanhamento.
        await acompanhar(runId, criada.id, normalizado, PRIMEIRA_ESPERA_MS);
        return;
      }

      await acompanhar(runId, criada.id, normalizado, PRIMEIRA_ESPERA_MS);
    },
    [acompanhar, finalizar],
  );

  const carregarPorId = useCallback(
    async (id: string) => {
      const runId = ++runIdRef.current;
      setState({ phase: "submitting" });
      const resultado = await obterTese(id);
      if (runIdRef.current !== runId) return;
      if (resultado && "status" in resultado) {
        if (resultado.status === "processing") {
          setTicker(resultado.ticker);
          await acompanhar(runId, id, resultado.ticker, PRIMEIRA_ESPERA_MS);
          return;
        }
        setTicker(resultado.ticker);
        finalizar(runId, resultado);
        return;
      }
      setState({
        phase: "error",
        message: messageFrom(resultado, "Não foi possível carregar esta tese."),
      });
    },
    [acompanhar, finalizar],
  );

  // Auto-início: só para a galeria de exemplos (teses pré-geradas em cache) ou
  // para reabrir por id (histórico). O guard do ref evita o duplo disparo do
  // StrictMode em dev.
  useEffect(() => {
    if (autoDisparadoRef.current) return;
    autoDisparadoRef.current = true;
    // Dispara fora do corpo do effect (macrotask): o kick-off chama setState e
    // rodá-lo dentro do flush causaria render em cascata (react-hooks lint).
    const timer = window.setTimeout(() => {
      if (idInicial) {
        void carregarPorId(idInicial);
        return;
      }
      if (
        autoIniciar &&
        tickerInicial &&
        (EXEMPLOS_PRONTOS as readonly string[]).includes(tickerInicial)
      ) {
        void iniciarPorTicker(tickerInicial);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [autoIniciar, tickerInicial, idInicial, carregarPorId, iniciarPorTicker]);

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (isBusy) return;
      void iniciarPorTicker(ticker);
    },
    [ticker, isBusy, iniciarPorTicker],
  );

  const cancelar = useCallback(() => {
    runIdRef.current++;
    setState({ phase: "idle" });
  }, []);

  const segundosDecorridos =
    state.phase === "polling" && agora > state.inicioEm
      ? Math.floor((agora - state.inicioEm) / 1000)
      : 0;

  return (
    <div className="flex w-full flex-col gap-6">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-xl border border-linha bg-cartao p-5 sm:flex-row sm:items-start"
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <label htmlFor="ticker" className="text-sm font-medium text-tinta">
            Ticker
          </label>
          <TickerCombobox
            inputId="ticker"
            value={ticker}
            onChange={(v) => {
              setTicker(v);
              if (erroLocal) setErroLocal(null);
            }}
            disabled={isBusy}
          />
          <div aria-live="polite">
            {erroLocal && (
              <p className="mt-1 text-xs font-medium text-erro-texto">{erroLocal}</p>
            )}
          </div>
        </div>
        <button
          type="submit"
          disabled={isBusy || ticker.trim() === ""}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-selo px-5 py-2.5 text-sm font-semibold text-sobre-selo transition-colors hover:bg-selo-forte disabled:cursor-not-allowed disabled:opacity-60 sm:mt-7"
        >
          {isBusy ? (
            <>
              <Spinner />
              Gerando…
            </>
          ) : (
            "Gerar tese"
          )}
        </button>
      </form>

      <div aria-live="polite" className="flex flex-col gap-6">
        {state.phase === "submitting" && (
          <CartaoCarregando rotulo="Enviando solicitação…" />
        )}
        {state.phase === "polling" && (
          <div className="flex flex-col gap-4">
            <CartaoCarregando
              rotulo={`Estruturando a tese de ${state.ticker}${
                segundosDecorridos > 0 ? ` — ${segundosDecorridos}s` : ""
              }`}
              detalhe="O motor reúne dados públicos (CVM, Banco Central, FRED, SEC), monta as dimensões e sintetiza com citações. Cache abre na hora; tese nova pode levar até ~2 minutos."
              onCancelar={cancelar}
            />
            <EsqueletoTese />
          </div>
        )}
        {state.phase === "error" && (
          <CartaoErro
            mensagem={state.message}
            onTentarDeNovo={
              state.ticker ? () => void iniciarPorTicker(state.ticker!) : undefined
            }
          />
        )}
        {state.phase === "ready" && (
          <div className="flex flex-col gap-4">
            <TeseView tese={state.tese} />
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  runIdRef.current++;
                  setState({ phase: "idle" });
                  setTicker("");
                }}
                className="rounded-lg border border-linha-forte bg-cartao px-4 py-2 text-sm font-medium text-tinta hover:border-selo-texto"
              >
                Gerar outra tese
              </button>
            </div>
          </div>
        )}
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

function CartaoCarregando({
  rotulo,
  detalhe,
  onCancelar,
}: {
  rotulo: string;
  detalhe?: string;
  onCancelar?: () => void;
}) {
  return (
    <div
      role="status"
      className="flex flex-col gap-2 rounded-xl border border-linha bg-cartao px-5 py-4"
    >
      <div className="flex items-center gap-3 text-sm text-tinta">
        <Spinner />
        <span className="font-medium">{rotulo}</span>
        {onCancelar && (
          <button
            type="button"
            onClick={onCancelar}
            className="ml-auto text-xs text-tinta-3 underline underline-offset-2 hover:text-tinta"
          >
            Cancelar
          </button>
        )}
      </div>
      {detalhe && <p className="text-xs leading-relaxed text-tinta-3">{detalhe}</p>}
    </div>
  );
}

function CartaoErro({
  mensagem,
  onTentarDeNovo,
}: {
  mensagem: string;
  onTentarDeNovo?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-erro-borda bg-erro-fundo px-5 py-4 text-sm text-erro-texto"
    >
      <p className="font-semibold">Não foi possível gerar a tese</p>
      <p className="mt-1">{mensagem}</p>
      {onTentarDeNovo && (
        <button
          type="button"
          onClick={onTentarDeNovo}
          className="mt-3 rounded-lg border border-erro-borda px-3 py-1.5 text-xs font-semibold hover:bg-erro-borda/30"
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}

// Skeleton com o formato do documento final (evita layout shift na chegada).
function EsqueletoTese() {
  return (
    <div aria-hidden className="flex animate-pulse flex-col gap-5">
      <div className="h-24 rounded-xl border border-linha bg-cartao" />
      <div className="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <div className="hidden flex-col gap-2 lg:flex">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-3.5 w-11/12 rounded bg-cartao-2" />
          ))}
        </div>
        <div className="flex flex-col gap-5">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="flex flex-col gap-3 rounded-xl border border-linha bg-cartao p-6"
            >
              <div className="h-5 w-1/3 rounded bg-cartao-2" />
              <div className="h-3.5 w-full rounded bg-cartao-2" />
              <div className="h-3.5 w-11/12 rounded bg-cartao-2" />
              <div className="h-3.5 w-4/5 rounded bg-cartao-2" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
