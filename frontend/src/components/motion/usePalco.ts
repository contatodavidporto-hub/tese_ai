"use client";

/**
 * usePalco — mola do palco 3D da Banca (APOTEOSE, crit. 3 / LEI S1+D3;
 * folha irmã e dona dos estáticos: cinema/palco.css).
 *
 * DIVISÃO DE ESCRITORES (um por propriedade):
 *   - `scale`/`opacity`/`box-shadow` do cartão: 100% CSS (palco.css —
 *     estados :hover/:focus-visible/irmãos). Este hook NÃO os toca.
 *   - `transform` (tilt): a DECLARAÇÃO vive em palco.css e consome
 *     `--palco-rx`/`--palco-ry` (unitless → ×1deg na folha); este hook é o
 *     ÚNICO escritor dessas vars, via gsap.quickTo (CSSOM — carve-out
 *     formal; nunca setAttribute('style')).
 *
 * MOLA (2ª exceção formal de spring — DESIGN-TOKENS.md §3, emenda
 * APOTEOSE): follow por quickTo power3.out (~0.4s, mesmo núcleo do
 * .magnetico) e retorno elastic.out(1,0.45) a zero no leave — REVERSÍVEL
 * por contrato (as vars são removidas ao assentar; nada "gruda").
 * Clamp duro no teto S1: |tilt| ≤ --palco-tilt (≤2.5deg), lido do token.
 *
 * GATES: só (hover:hover) and (pointer:fine); inerte sob
 * prefers-reduced-motion (reage ao vivo — useSyncExternalStore);
 * pointerType 'touch' ignorado (defesa em híbridos). GSAP só via
 * carregarGsap() (R5 — import dinâmico; NUNCA @gsap/react). Antes de o
 * chunk resolver, o palco CSS (zoom/dim/sombra) já funciona 100%.
 * ESCOPO: delegação no `.banca-rail` — /teses usa o mesmo CartaoTese fora
 * do rail e nunca liga esta física (S1 vale só para a Banca).
 */

import { useEffect, useSyncExternalStore, type RefObject } from "react";

import { carregarGsap, type MotorGsap } from "@/lib/gsapSetup";

const QUERY_REDUZIDO = "(prefers-reduced-motion: reduce)";
const QUERY_HOVER_FINO = "(hover: hover) and (pointer: fine)";
const SELETOR_RAIL = ".banca-rail";
const SELETOR_CARD = ".cartao-ticker";
const TILT_TETO = 2.5; // teto S1 — clamp duro mesmo se o token crescer
const DUR_FOLLOW = 0.4; // s — quickTo (núcleo do follow)
const DUR_RETORNO = 0.6; // s — elastic.out(1,0.45), retorno da mola

type QuickTo = ReturnType<MotorGsap["gsap"]["quickTo"]>;

function inscreverReduzido(notificar: () => void): () => void {
  const mql = window.matchMedia(QUERY_REDUZIDO);
  mql.addEventListener("change", notificar);
  return () => mql.removeEventListener("change", notificar);
}
function instantaneoReduzido(): boolean {
  return window.matchMedia(QUERY_REDUZIDO).matches;
}
function instantaneoReduzidoServidor(): boolean {
  return false;
}
function usePrefereReduzidoLocal(): boolean {
  return useSyncExternalStore(
    inscreverReduzido,
    instantaneoReduzido,
    instantaneoReduzidoServidor,
  );
}

export function usePalco(envelopeRef: RefObject<HTMLElement | null>): void {
  const prefereReduzido = usePrefereReduzidoLocal();

  useEffect(() => {
    const envelope = envelopeRef.current;
    if (!envelope || prefereReduzido) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia(QUERY_HOVER_FINO).matches) return;
    const rail = envelope.querySelector<HTMLElement>(SELETOR_RAIL);
    if (!rail) return;

    let motor: MotorGsap | null = null;
    let cardAtivo: HTMLElement | null = null;
    let rxTo: QuickTo | null = null;
    let ryTo: QuickTo | null = null;
    let pendente: { x: number; y: number } | null = null;
    let agendado = false;
    let idQuadro = 0;
    // Token lido 1x (o teto S1 é clampado por cima, sempre).
    const tokenTilt = parseFloat(
      getComputedStyle(rail).getPropertyValue("--palco-tilt"),
    );
    const tiltMax = Math.min(
      Number.isFinite(tokenTilt) ? Math.abs(tokenTilt) : TILT_TETO,
      TILT_TETO,
    );

    const zerarSeco = (card: HTMLElement) => {
      motor?.gsap.killTweensOf(card);
      card.style.removeProperty("--palco-rx"); // CSSOM — carve-out
      card.style.removeProperty("--palco-ry");
    };

    const assentar = (card: HTMLElement) => {
      if (!motor) {
        zerarSeco(card);
        return;
      }
      // Retorno da mola (a exceção registrada): elástico curto a zero,
      // depois REMOVE as vars — reversível de verdade, sem resíduo.
      motor.gsap.to(card, {
        "--palco-rx": 0,
        "--palco-ry": 0,
        duration: DUR_RETORNO,
        ease: "elastic.out(1,0.45)",
        overwrite: "auto",
        onComplete: () => {
          card.style.removeProperty("--palco-rx");
          card.style.removeProperty("--palco-ry");
        },
      });
    };

    const aplicar = () => {
      agendado = false;
      if (!pendente || !cardAtivo || !rxTo || !ryTo) return;
      const r = cardAtivo.getBoundingClientRect(); // 1 leitura por quadro
      if (r.width === 0 || r.height === 0) return;
      const nx = Math.max(
        -1,
        Math.min(1, (pendente.x - (r.left + r.width / 2)) / (r.width / 2)),
      );
      const ny = Math.max(
        -1,
        Math.min(1, (pendente.y - (r.top + r.height / 2)) / (r.height / 2)),
      );
      // Inclina "para" o cursor: topo afasta quando o cursor sobe.
      rxTo(-ny * tiltMax);
      ryTo(nx * tiltMax);
    };

    const agendar = () => {
      if (agendado) return;
      agendado = true;
      idQuadro = window.requestAnimationFrame(aplicar);
    };

    const ativar = (card: HTMLElement) => {
      if (cardAtivo === card) return;
      if (cardAtivo) assentar(cardAtivo);
      cardAtivo = card;
      rxTo = null;
      ryTo = null;
      // Semente numérica p/ o CSSPlugin ler valor inicial (CSSOM).
      card.style.setProperty("--palco-rx", "0");
      card.style.setProperty("--palco-ry", "0");
      carregarGsap()
        .then((m) => {
          motor = m;
          if (cardAtivo !== card) return; // saiu antes do motor chegar
          rxTo = m.gsap.quickTo(card, "--palco-rx", {
            duration: DUR_FOLLOW,
            ease: "power3.out",
            overwrite: "auto",
          });
          ryTo = m.gsap.quickTo(card, "--palco-ry", {
            duration: DUR_FOLLOW,
            ease: "power3.out",
            overwrite: "auto",
          });
          if (pendente) agendar();
        })
        .catch(() => {
          // Sem mola (rede): palco CSS segue 100% funcional.
        });
    };

    const desativar = () => {
      if (!cardAtivo) return;
      assentar(cardAtivo);
      cardAtivo = null;
      rxTo = null;
      ryTo = null;
      pendente = null;
    };

    const aoMover = (ev: PointerEvent) => {
      if (ev.pointerType === "touch") return;
      const card =
        (ev.target as HTMLElement | null)?.closest<HTMLElement>(SELETOR_CARD) ??
        null;
      // Durante o drag do rail a captura re-alveja os eventos para o
      // próprio rail → card null → a mola assenta sozinha. De propósito.
      if (!card) {
        desativar();
        return;
      }
      if (card !== cardAtivo) ativar(card);
      pendente = { x: ev.clientX, y: ev.clientY };
      agendar();
    };

    const aoSair = () => desativar();

    rail.addEventListener("pointermove", aoMover, { passive: true });
    rail.addEventListener("pointerleave", aoSair, { passive: true });
    rail.addEventListener("pointercancel", aoSair, { passive: true });

    return () => {
      rail.removeEventListener("pointermove", aoMover);
      rail.removeEventListener("pointerleave", aoSair);
      rail.removeEventListener("pointercancel", aoSair);
      window.cancelAnimationFrame(idQuadro);
      cardAtivo = null;
      // Nenhum tween (nem retorno em voo) sobrevive ao unmount; vars fora.
      rail.querySelectorAll<HTMLElement>(SELETOR_CARD).forEach(zerarSeco);
    };
  }, [envelopeRef, prefereReduzido]);
}
