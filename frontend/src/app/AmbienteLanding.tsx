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

// IDs canônicos do contrato cinema/luz.css: as seções da landing levam id
// hero/prova/nascimento/galeria/dimensoes/postura (page.tsx).
//
// E25 (missão FRONTEND HORIZONTE, Onda 2 — integração): "nascimento" entrou
// nesta lista. A raia 1A escreveu a regra `body[data-secao="nascimento"]` em
// cinema/luz.css (capítulo "papel" entre #prova e #galeria, ritmo D6), mas a
// lista de ids observados vive AQUI — sem esta linha a regra seria dead code
// e a seção nova herdaria o ambiente da anterior (a aurora ficaria no alfa de
// #prova durante os 240svh da cena). Ordem = ordem de leitura do DOM.
const SECOES_LANDING = [
  "hero",
  "prova",
  "nascimento",
  "galeria",
  "dimensoes",
  "postura",
] as const;

export function AmbienteLanding(): null {
  useSecaoAtiva(SECOES_LANDING, { ambiente: true });
  return null;
}
