"use client";

// Ambiente por seção da LANDING (missão MATÉRIA VIVA, Onda 2 — R7b/R11).
// Ilha mínima que espelha a seção ativa em `body[data-secao="…"]` via
// useSecaoAtiva({ ambiente: true }) — o CSS correspondente é da Onda 1A
// (cinema/luz.css modula --luz-aurora-alfa por capítulo, corte seco).
//
// R11 (LEI): SÓ esta ilha passa `ambiente: true` em todo o produto — /tese
// e /como-funciona seguem usando o hook sem tocar o body (grep de auditoria
// na Onda 3). O atributo é REMOVIDO no unmount (cleanup do próprio hook),
// então nenhuma outra rota herda o ambiente. Escrita de ATRIBUTO (dataset),
// nunca de estilo — CSP intacta.

import { useSecaoAtiva } from "@/components/motion/useSecaoAtiva";

// IDs canônicos do contrato cinema/luz.css (Onda 1A): as 5 seções da
// landing levam id hero/prova/galeria/dimensoes/postura (page.tsx).
const SECOES_LANDING = [
  "hero",
  "prova",
  "galeria",
  "dimensoes",
  "postura",
] as const;

export function AmbienteLanding(): null {
  useSecaoAtiva(SECOES_LANDING, { ambiente: true });
  return null;
}
