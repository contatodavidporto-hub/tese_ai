"use client";

// Lista das teses geradas NESTE navegador (localStorage — ver src/lib/historico.ts).
// Reabrir usa GET /api/teses/{id} direto (via /tese?id=...): nunca dispara POST,
// logo nunca regenera nem custa nada.
//
// Enxerto NORMA #4 (DESIGN-BRIEF.md §5): extrato de auditoria SEM cards — só
// linhas e réguas, agrupadas por dia com cabeçalho sticky. O CONTRATO de
// ItemHistorico (id, ticker, status, criadoEm) não muda aqui — só o visual.

import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";

import { Reveal } from "@/components/motion/Reveal";
import {
  assinarHistorico,
  HISTORICO_VAZIO,
  lerHistoricoSnapshot,
  limparHistorico,
  type ItemHistorico,
} from "@/lib/historico";

const ROTULO_STATUS: Record<ItemHistorico["status"], string> = {
  ready: "pronta",
  processing: "processando",
  error: "falhou",
};

// Cor do status segue a hierarquia do design system: "pronta" usa a brasa
// (ação normal, tese pode ser aberta); "processando" usa o par aviso;
// "falhou" usa o par erro (falha técnica) — nunca o inverso.
const CLASSE_STATUS: Record<ItemHistorico["status"], string> = {
  ready: "text-brasa-texto",
  processing: "text-aviso-texto",
  error: "text-erro-texto",
};

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

function formatHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

// Chave estável de agrupamento (data local, não UTC — evita que um registro
// das 23h vire "dia seguinte" só por causa do fuso).
function chaveDia(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "indefinido";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function rotuloDia(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "DATA INDEFINIDA";
  const dia = String(d.getDate()).padStart(2, "0");
  const mes = MESES[d.getMonth()];
  return `${dia} ${mes} ${d.getFullYear()}`;
}

type Grupo = { chave: string; rotulo: string; itens: ItemHistorico[] };

// Os itens já chegam ordenados do mais recente para o mais antigo
// (registrarNoHistorico prepende) — o agrupamento preserva essa ordem.
function agruparPorDia(itens: ItemHistorico[]): Grupo[] {
  const grupos: Grupo[] = [];
  const porChave = new Map<string, Grupo>();
  for (const item of itens) {
    const chave = chaveDia(item.criadoEm);
    let grupo = porChave.get(chave);
    if (!grupo) {
      grupo = { chave, rotulo: rotuloDia(item.criadoEm), itens: [] };
      porChave.set(chave, grupo);
      grupos.push(grupo);
    }
    grupo.itens.push(item);
  }
  return grupos;
}

export function HistoricoClient() {
  // localStorage é um sistema externo: useSyncExternalStore lê o snapshot no
  // cliente (o servidor rende a lista vazia) e reage a mudanças — inclusive de
  // outras abas, via evento `storage`.
  const itens = useSyncExternalStore(
    assinarHistorico,
    lerHistoricoSnapshot,
    () => HISTORICO_VAZIO,
  );

  const grupos = useMemo(() => agruparPorDia(itens), [itens]);

  if (itens.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 border border-line bg-card px-6 py-8">
        {/* Microcopy da casa (enxerto Noturna #11): sem ilustração fofa. */}
        <p className="font-sans text-ui text-ink-2">nenhum registro neste período.</p>
        <Link
          href="/tese"
          className="flex min-h-11 items-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
        >
          Gerar a primeira tese
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {grupos.map((grupo) => (
        <section key={grupo.chave} aria-labelledby={`dia-${grupo.chave}`}>
          {/* Offset aproximado da Tarja regulatória (sticky top-0, z-50) —
              o cabeçalho de dia fica logo abaixo dela ao rolar. */}
          <h2
            id={`dia-${grupo.chave}`}
            className="sticky top-10 z-10 border-b border-line-strong bg-page py-2 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3"
          >
            {grupo.rotulo}
          </h2>
          <ul className="flex flex-col">
            {grupo.itens.map((item) => (
              <li key={item.id} className="border-b border-line">
                <Reveal>
                  {/* A1 (foco não obscurecido, 2.4.11): id estável herda
                      `[id] { scroll-margin-top: 6rem }` (globals.css) — sem
                      isso, focar este link por teclado e rolar até ele o
                      deixava colado sob o cabeçalho de dia sticky (top-10). */}
                  <Link
                    id={`registro-${item.id}`}
                    href={`/tese?id=${encodeURIComponent(item.id)}&ticker=${encodeURIComponent(item.ticker)}`}
                    // D8: a linha inteira já É o link — o "abrir →" era um CTA
                    // redundante (grid de 2 colunas agora, não 3).
                    className="grid min-h-11 grid-cols-[4.5rem_1fr] items-center gap-4 py-3 transition-colors duration-[var(--dur-tick)] hover:bg-card sm:grid-cols-[5.5rem_1fr]"
                  >
                    <span className="font-mono text-meta text-ink-3">
                      {formatHora(item.criadoEm)}
                    </span>
                    <span className="flex min-w-0 items-baseline gap-3">
                      <span className="truncate font-mono text-ui font-semibold text-ink">
                        {item.ticker}
                      </span>
                      <span
                        className={`font-mono text-meta uppercase tracking-wide ${CLASSE_STATUS[item.status]}`}
                      >
                        {ROTULO_STATUS[item.status]}
                      </span>
                    </span>
                  </Link>
                </Reveal>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <button
        type="button"
        onClick={() => limparHistorico()}
        className="flex min-h-11 w-fit items-center font-sans text-ui text-ink-3 underline underline-offset-4 hover:text-ink"
      >
        Limpar histórico deste navegador
      </button>
    </div>
  );
}
