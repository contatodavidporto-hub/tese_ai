"use client";

// Scrollspy compartilhado (D2, CORRECOES-RODADA-1.md): extraído de
// `app/tese/TeseView.tsx` para ser reusado também pelo IndiceNav de
// `/como-funciona` — mesmo padrão de "seção atual" nos dois sumários do
// produto (Sumario da tese e o índice das cinco dimensões).
//
// Fallback de wayfinding: em `/tese` isto roda ao lado da Régua de Leitura
// (`.regua-leitura`, animation-timeline: scroll() em globals.css) — a barra
// é a assinatura visual; isto é a rede de segurança que funciona em
// qualquer navegador, sem depender de suporte a scroll-timelines. Em
// `/como-funciona` (sem régua de leitura) é o único mecanismo de estado
// ativo do índice lateral.

import { useEffect, useState } from "react";

type OpcoesSecaoAtiva = {
  /**
   * Ambiente por seção (missão MATÉRIA VIVA, R7b/R11 — Onda 1A): quando
   * `true`, o hook ESPELHA a seção ativa em `body[data-secao="…"]` para o
   * CSS de ambiente (`cinema/luz.css` modula `--luz-aurora-alfa` por
   * capítulo, corte seco — sem promessa de interpolação). Escopo R11 (LEI):
   * default `false`; SÓ a ilha da landing passa `true` — /tese e
   * /como-funciona seguem usando o hook sem tocar o body (grep de auditoria
   * na Onda 3). O atributo é REMOVIDO no unmount da ilha e quando não há
   * seção ativa. É escrita de ATRIBUTO (dataset), nunca de estilo — CSP
   * intacta (mesma família do `classList` dos véus).
   */
  ambiente?: boolean;
};

/**
 * Observa os elementos com os `ids` informados e devolve o id da seção
 * "atual" (a mais próxima do topo da faixa de leitura, entre as visíveis).
 * `ids` pode conter ids que não existem no DOM desta página — o filtro
 * abaixo simplesmente os descarta, então é seguro passar uma lista fixa de
 * âncoras que dependem de conteúdo dinâmico (ex.: `secoes` de uma tese).
 *
 * Compat: a assinatura de 1 argumento (TeseView/IndiceNav) permanece
 * intocada — `opcoes` é opcional e `ambiente` tem default `false`.
 */
export function useSecaoAtiva(
  ids: readonly string[],
  { ambiente = false }: OpcoesSecaoAtiva = {},
): string | null {
  const [ativo, setAtivo] = useState<string | null>(null);
  // Chave estável: evita reassinar o observer a cada re-render só porque o
  // array `ids` foi recriado (identidade nova, mesmo conteúdo).
  const chave = ids.join("|");

  useEffect(() => {
    const elementos = (chave ? chave.split("|") : [])
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (elementos.length === 0) return;

    const observer = new IntersectionObserver(
      (entradas) => {
        setAtivo((atual) => {
          const visiveis = entradas.filter((e) => e.isIntersecting);
          if (visiveis.length === 0) return atual;
          // A seção mais próxima do topo entre as visíveis é a "atual" —
          // ordem de leitura, não a mais visível em área.
          const primeira = visiveis.reduce((a, b) =>
            b.boundingClientRect.top < a.boundingClientRect.top ? b : a,
          );
          return primeira.target.id;
        });
      },
      // Faixa de leitura: ignora a barra de topo (Tarja + masthead) e
      // considera "atual" a seção que ocupa a parte de cima da viewport.
      { rootMargin: "-112px 0px -65% 0px", threshold: 0 },
    );
    elementos.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [chave]);

  // Ambiente por seção (R7b/R11): espelha `ativo` em body[data-secao] — e
  // GARANTE a remoção tanto ao trocar de seção/perder o ativo quanto no
  // unmount da ilha (o cleanup roda em ambos): nenhuma outra rota herda o
  // atributo (R11 é gate de auditoria da Onda 3).
  useEffect(() => {
    if (!ambiente) return;
    if (ativo) {
      document.body.setAttribute("data-secao", ativo);
    } else {
      document.body.removeAttribute("data-secao");
    }
    return () => {
      document.body.removeAttribute("data-secao");
    };
  }, [ambiente, ativo]);

  return ativo;
}
