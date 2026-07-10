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

import { classesReveal, useReveal } from "@/components/motion/Reveal";
import {
  atualizarStatusHistorico,
  registrarNoHistorico,
} from "@/lib/historico";
import { EXEMPLOS_PRONTOS, TICKER_RE } from "@/lib/tickers";
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
  // Fluxos automáticos (galeria/histórico) já NASCEM em "submitting": o primeiro
  // paint mostra cartão + skeleton, evitando layout shift quando o efeito dispara
  // (CLS medido caiu de 0,17 para perto de zero com isso).
  const comecaOcupado =
    Boolean(idInicial) ||
    Boolean(
      autoIniciar &&
        tickerInicial &&
        (EXEMPLOS_PRONTOS as readonly string[]).includes(tickerInicial),
    );
  const [state, setState] = useState<UiState>(
    comecaOcupado ? { phase: "submitting" } : { phase: "idle" },
  );
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
      if (!TICKER_RE.test(normalizado)) {
        setErroLocal(
          "Ticker fora do formato aceito — ex.: PETR4, HGLG11, TD-IPCA-2035. Confira o código e tente de novo — nenhuma chamada foi feita.",
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
          // 429 (rate-limit do backend) devolve {"error": ...}, não {"detail"}:
          // traduzimos para uma mensagem acionável em vez de "HTTP 429".
          const fallback =
            res.status === 429
              ? "Muitas gerações em sequência. Aguarde alguns minutos e tente novamente."
              : `Falha ao criar a tese (HTTP ${res.status}).`;
          setState({
            phase: "error",
            message: messageFrom(data, fallback),
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
    return () => {
      // StrictMode (dev) monta-desmonta-remonta: sem resetar o guard aqui, o
      // clearTimeout cancelaria o disparo e a remontagem nunca re-agendaria.
      autoDisparadoRef.current = false;
      window.clearTimeout(timer);
    };
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
    // devolve o foco ao campo (senão cai no <body> quando o botão some)
    document.getElementById("ticker")?.focus();
  }, []);

  const segundosDecorridos =
    state.phase === "polling" && agora > state.inicioEm
      ? Math.floor((agora - state.inicioEm) / 1000)
      : 0;

  return (
    <div className="flex w-full flex-col gap-8">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 border border-line bg-card p-6 sm:flex-row sm:items-start"
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <label
            htmlFor="ticker"
            className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3"
          >
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
            erroId={erroLocal ? "ticker-erro" : undefined}
          />
          <div aria-live="polite">
            {erroLocal && (
              <p id="ticker-erro" className="mt-1 text-ui font-medium text-erro-texto">
                {erroLocal}
              </p>
            )}
          </div>
        </div>
        <button
          type="submit"
          disabled={isBusy || ticker.trim() === ""}
          className="inline-flex min-h-11 items-center justify-center bg-brasa px-6 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte disabled:cursor-not-allowed disabled:opacity-60 sm:mt-7"
        >
          {isBusy ? "Gerando…" : "Gerar tese"}
        </button>
      </form>

      {/* aria-live SÓ no rótulo curto (dentro do CartaoCarregando/CartaoErro):
          um live region no documento inteiro faria o leitor de tela anunciar o
          contador a cada segundo e reler a tese toda ao ficar pronta. */}
      <div className="flex flex-col gap-8">
        {(state.phase === "submitting" || state.phase === "polling") && (
          <div className="flex flex-col gap-5">
            <CartaoCarregando
              rotulo={
                state.phase === "submitting"
                  ? "Enviando solicitação…"
                  : `Estruturando a tese de ${state.ticker}`
              }
              contadorSegundos={
                state.phase === "polling" ? segundosDecorridos : undefined
              }
              detalhe="O motor reúne dados públicos (CVM, Banco Central, FRED, SEC), monta as dimensões e sintetiza com citações. Cache abre na hora; tese nova pode levar alguns minutos."
              onCancelar={state.phase === "polling" ? cancelar : undefined}
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
          <div className="flex flex-col gap-5">
            <p role="status" className="sr-only">
              Tese de {state.tese.ticker} pronta.
            </p>
            <TeseView tese={state.tese} />
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  runIdRef.current++;
                  setState({ phase: "idle" });
                  setTicker("");
                  document.getElementById("ticker")?.focus();
                }}
                className="min-h-11 border border-field bg-card px-5 font-sans text-ui font-medium text-ink hover:border-brasa-texto"
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

// Impressão de Régua num elemento próprio (sem <div> extra de children) —
// exatamente o padrão de `useReveal` para uma <hr>/barra fina (DESIGN-
// TOKENS.md §3): usado nas barras "vazias" do loading e do skeleton.
function ReguaImpressa({ className }: { className: string }) {
  const { ref, armado, revelado } = useReveal<HTMLDivElement>();
  return <div ref={ref} className={classesReveal("reveal-regua", armado, revelado, className)} />;
}

// Rótulo curto + contador REAL (não telemetria simulada: o polling só sabe
// "processing"/"ready"/"error" — nenhuma barra de progresso finge fases que o
// backend não expõe). A régua acima do rótulo imprime 1x ao montar (sem loop).
function CartaoCarregando({
  rotulo,
  contadorSegundos,
  detalhe,
  onCancelar,
}: {
  rotulo: string;
  contadorSegundos?: number;
  detalhe?: string;
  onCancelar?: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 border border-line bg-card px-6 py-5">
      <ReguaImpressa className="h-1 w-20 bg-brasa" />
      <div className="atraso-regua flex flex-wrap items-center gap-3">
        <span role="status" className="font-sans text-ui font-semibold text-ink">
          {rotulo}
        </span>
        {typeof contadorSegundos === "number" && contadorSegundos > 0 && (
          <span aria-hidden className="font-mono text-meta text-ink-3">
            {contadorSegundos}s
          </span>
        )}
        {onCancelar && (
          <button
            type="button"
            onClick={onCancelar}
            className="-m-2 ml-auto p-2 font-sans text-ui text-ink-3 underline underline-offset-2 hover:text-ink"
          >
            Cancelar
          </button>
        )}
      </div>
      {detalhe && <p className="atraso-regua text-ui text-ink-2">{detalhe}</p>}
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
    <div role="alert" className="flex flex-col gap-2 border border-erro-borda bg-erro-fundo px-6 py-5 text-ui text-erro-texto">
      <p className="font-sans font-semibold">Não foi possível gerar a tese</p>
      <p>{mensagem}</p>
      {onTentarDeNovo && (
        <button
          type="button"
          onClick={onTentarDeNovo}
          className="mt-2 min-h-11 w-fit border border-erro-borda px-4 font-sans text-ui font-semibold hover:bg-erro-borda/20"
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}

// Skeleton com o formato do documento final (evita layout shift na chegada):
// hairlines que "se imprimem" 1x (Impressão de Régua) — sem loop, sem shimmer.
function EsqueletoTese() {
  return (
    <div aria-hidden className="flex flex-col gap-8">
      <div className="flex flex-col gap-3 border border-line bg-card px-6 py-6">
        <ReguaImpressa className="h-2 w-24 bg-line-strong" />
        <div className="h-6 w-40 bg-line-strong" />
        <div className="h-3 w-56 bg-line" />
      </div>
      <div className="grid gap-10 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-16">
        <div className="hidden flex-col gap-3 lg:flex">
          <ReguaImpressa className="h-2 w-11/12 bg-line" />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-2 w-11/12 bg-line" />
          ))}
        </div>
        <div className="flex flex-col gap-8">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex flex-col gap-3 border-t-2 border-line-strong pt-4">
              <ReguaImpressa className={`h-2 w-1/3 bg-line-strong i-${i + 1}`} />
              <div className="flex flex-col gap-2">
                <div className="h-2 w-full bg-line" />
                <div className="h-2 w-11/12 bg-line" />
                <div className="h-2 w-4/5 bg-line" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
