"use client";

// Lista das teses geradas NESTE navegador (localStorage — ver src/lib/historico.ts).
// Reabrir usa GET /api/teses/{id} direto (via /tese?id=...): nunca dispara POST,
// logo nunca regenera nem custa nada.

import Link from "next/link";
import { useSyncExternalStore } from "react";

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

function formatDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
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

  if (itens.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border border-linha bg-cartao p-6 text-sm text-tinta-2">
        <p>
          Nenhuma tese gerada neste navegador ainda. O histórico fica só neste
          dispositivo — nada é enviado a servidores.
        </p>
        <Link
          href="/tese"
          className="rounded-lg bg-selo px-4 py-2 text-sm font-semibold text-sobre-selo hover:bg-selo-forte"
        >
          Gerar a primeira tese
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-2">
        {itens.map((item) => (
          <li key={item.id}>
            <Link
              href={`/tese?id=${encodeURIComponent(item.id)}&ticker=${encodeURIComponent(item.ticker)}`}
              className="flex items-baseline justify-between gap-4 rounded-xl border border-linha bg-cartao px-5 py-4 transition-colors hover:border-selo-texto"
            >
              <span className="font-mono text-base font-semibold text-tinta">
                {item.ticker}
              </span>
              <span className="min-w-0 flex-1 truncate text-right text-xs text-tinta-3">
                {formatDataHora(item.criadoEm)}
              </span>
              <span
                className={`rounded-full border px-2 py-0.5 font-mono text-[0.65rem] uppercase tracking-wide ${
                  item.status === "ready"
                    ? "border-linha text-selo-texto"
                    : item.status === "error"
                      ? "border-erro-borda text-erro-texto"
                      : "border-aviso-borda text-aviso-texto"
                }`}
              >
                {ROTULO_STATUS[item.status]}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => limparHistorico()}
        className="self-start text-xs text-tinta-3 underline underline-offset-2 hover:text-tinta"
      >
        Limpar histórico deste navegador
      </button>
    </div>
  );
}
