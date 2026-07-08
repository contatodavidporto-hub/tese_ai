// Histórico de teses geradas NESTE navegador (localStorage). Não há endpoint de
// listagem no backend (decisão da Fase 4: não criar rota) — o histórico é local,
// sem dado sensível (só ticker + id + datas) e nunca sai do dispositivo.

import type { TeseStatus } from "@/app/tese/types";

export type ItemHistorico = {
  id: string;
  ticker: string;
  status: TeseStatus;
  criadoEm: string; // ISO — quando a tese foi gerada/aberta pela 1ª vez aqui
};

const CHAVE = "teseai.historico.v1";
const LIMITE = 50;

// --- mini-store para useSyncExternalStore -----------------------------------
// Snapshot cacheado por conteúdo bruto: getSnapshot precisa devolver a MESMA
// referência enquanto nada muda (Object.is), senão o React entra em loop.
export const HISTORICO_VAZIO: ItemHistorico[] = [];
let cacheBruto: string | null = null;
let cacheItens: ItemHistorico[] = HISTORICO_VAZIO;

const ouvintes = new Set<() => void>();

function notificar(): void {
  for (const fn of ouvintes) fn();
}

export function assinarHistorico(onChange: () => void): () => void {
  ouvintes.add(onChange);
  // evento `storage`: mudanças vindas de OUTRAS abas
  window.addEventListener("storage", onChange);
  return () => {
    ouvintes.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function lerHistoricoSnapshot(): ItemHistorico[] {
  const store = armazenamento();
  if (!store) return HISTORICO_VAZIO;
  let bruto: string | null = null;
  try {
    bruto = store.getItem(CHAVE);
  } catch {
    return HISTORICO_VAZIO;
  }
  if (bruto !== cacheBruto) {
    cacheBruto = bruto;
    cacheItens = decodificar(bruto);
  }
  return cacheItens;
}

function decodificar(bruto: string | null): ItemHistorico[] {
  if (!bruto) return HISTORICO_VAZIO;
  try {
    const dados: unknown = JSON.parse(bruto);
    if (!Array.isArray(dados)) return HISTORICO_VAZIO;
    const itens = dados.filter(valido);
    return itens.length > 0 ? itens : HISTORICO_VAZIO;
  } catch {
    return HISTORICO_VAZIO;
  }
}
// ----------------------------------------------------------------------------

function armazenamento(): Storage | null {
  // localStorage pode não existir (SSR) ou estar bloqueado (modo privado).
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function valido(item: unknown): item is ItemHistorico {
  if (typeof item !== "object" || item === null) return false;
  const o = item as Record<string, unknown>;
  return (
    typeof o.id === "string" &&
    typeof o.ticker === "string" &&
    (o.status === "processing" || o.status === "ready" || o.status === "error") &&
    typeof o.criadoEm === "string"
  );
}

export function listarHistorico(): ItemHistorico[] {
  return [...lerHistoricoSnapshot()];
}

function salvar(itens: ItemHistorico[]): void {
  const store = armazenamento();
  if (!store) return;
  try {
    store.setItem(CHAVE, JSON.stringify(itens.slice(0, LIMITE)));
  } catch {
    // quota/modo privado: histórico é conveniência, nunca bloqueia o fluxo
  }
  notificar();
}

export function registrarNoHistorico(item: ItemHistorico): void {
  const restantes = listarHistorico().filter((i) => i.id !== item.id);
  salvar([item, ...restantes]);
}

export function atualizarStatusHistorico(id: string, status: TeseStatus): void {
  // Nunca mutar os objetos do snapshot cacheado (useSyncExternalStore compara
  // por referência): produz itens novos.
  const itens = lerHistoricoSnapshot();
  if (!itens.some((i) => i.id === id && i.status !== status)) return;
  salvar(itens.map((i) => (i.id === id ? { ...i, status } : i)));
}

export function limparHistorico(): void {
  const store = armazenamento();
  if (!store) return;
  try {
    store.removeItem(CHAVE);
  } catch {
    // sem consequência
  }
  notificar();
}
