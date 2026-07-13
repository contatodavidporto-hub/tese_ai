"use client";

/**
 * useViradaCartao — "cartão-que-vira-página" (APOTEOSE, crit. 4 / LEI
 * §3.4 + D4 + M-g; dossiê .maestro/recon/view-transitions-vs-flip.md).
 * View Transition NATIVA same-document (API do navegador — React
 * <ViewTransition>/canary segue VETADO); folha irmã: cinema/virada.css.
 *
 * GATE QUÁDRUPLO (qualquer falha → return SEM preventDefault: o <Link>
 * navega como hoje e o véu `.virada-edicao` de /tese cobre a chegada):
 *   1. document.startViewTransition existe (~88,5% jul/2026);
 *   2. sem prefers-reduced-motion (não se chama a API — nem crossfade);
 *   3. ticker ∈ 13 EXEMPLOS_PRONTOS (slotVirada ≠ null — warm-cache
 *      garantido; ticker arbitrário nunca morfa);
 *   4. nenhuma transição em voo (nome duplicado = VT silenciosamente
 *      pulada; navegação concorrente = estado imprevisível).
 *
 * NO DISPARO (tudo síncrono, antes do freeze):
 *   - flag sessionStorage `tese-ai:morph-chegada` (contrato Onda 0: a
 *     onda TESE lê e suprime o véu de chegada em tese-apoteose.css);
 *   - `view-transition-name: cartao-tese` SÓ no cartão clicado, via CSSOM
 *     (el.style.setProperty — nunca classe estática na origem, nunca
 *     style= SSR'ado) com LIMPEZA no finally (senão o nome sombrearia os
 *     `.vt-tese-N` cross-document na próxima hard-nav);
 *   - classes `virada-em-voo` (rail) + `virada-origem` (cartão) — irmãos
 *     zoom-out+fade via CSS (virada.css), classList apenas.
 *
 * VOO: startViewTransition(() => promise resolvida quando a NOVA rota
 * COMMITA no DOM — sinal = cleanup de layout-effect deste hook no
 * unmount da página de origem (React roda o destroy no commit da troca;
 * a resolução vira microtask pós-commit — o snapshot "new" captura o
 * EsqueletoTese já pintável). É NAVEGAÇÃO, não modal (M-g): Esc durante o
 * voo → skipTransition() (a navegação SEGUE); timeout próprio de ~300ms
 * além do UA → skip + resolve (nunca congelar o leitor atrás de rede);
 * foco na chegada é dono da onda TESE (h1/masthead tabIndex=-1 + focus).
 * CSP: zero style inline/injetado; pseudos de autor na folha estática.
 */

import { useRouter } from "next/navigation";
import {
  startTransition,
  useCallback,
  useEffect,
  useLayoutEffect,
  type MouseEvent as MouseEventReact,
} from "react";

import { slotVirada } from "@/lib/tickers";

// useLayoutEffect avisa no render de servidor (client components também
// renderizam no SSR) — o cleanup só interessa no browser; no servidor o
// useEffect equivalente é um no-op silencioso.
const useLayoutEffectIsomorfico =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

const NOME_MORPH = "cartao-tese";
const FLAG_CHEGADA = "tese-ai:morph-chegada";
const CLASSE_VOO = "virada-em-voo";
const CLASSE_ORIGEM = "virada-origem";
const TIMEOUT_PINTURA_MS = 300;
const QUERY_REDUZIDO = "(prefers-reduced-motion: reduce)";

/** Tipagem defensiva (não depende da versão do lib.dom do TS). */
type ViewTransitionLike = {
  finished: Promise<void>;
  ready: Promise<void>;
  updateCallbackDone: Promise<void>;
  skipTransition: () => void;
};
type DocumentComVT = Document & {
  startViewTransition?: (
    atualizar: () => Promise<void> | void,
  ) => ViewTransitionLike;
};

// Estado de módulo: 1 voo por documento (gate 4) + resolvedor da pintura.
let vooAtivo = false;
let resolverPintura: (() => void) | null = null;

export function useViradaCartao(
  ticker: string,
  href: string,
): (ev: MouseEventReact<HTMLAnchorElement>) => void {
  const router = useRouter();

  // Sinal de "nova rota commitada": o destroy de layout-effect da página
  // de ORIGEM roda no commit que monta o destino; resolver aqui garante
  // que o snapshot "new" da VT já vê o DOM trocado (cleanup síncrono do
  // commit → resolução em microtask pós-commit). Deps vazias: só unmount.
  useLayoutEffectIsomorfico(() => {
    return () => {
      resolverPintura?.();
      resolverPintura = null;
    };
  }, []);

  return useCallback(
    (ev: MouseEventReact<HTMLAnchorElement>) => {
      // Cliques modificados/secundários (nova aba, download…): fluxo nativo.
      if (
        ev.defaultPrevented ||
        ev.button !== 0 ||
        ev.metaKey ||
        ev.ctrlKey ||
        ev.shiftKey ||
        ev.altKey
      ) {
        return;
      }

      const doc = document as DocumentComVT;
      // ---- GATE QUÁDRUPLO (fallback = comportamento atual) ----
      if (typeof doc.startViewTransition !== "function") return; // (1)
      if (window.matchMedia(QUERY_REDUZIDO).matches) return; // (2)
      if (slotVirada(ticker) === null) return; // (3)
      if (vooAtivo) return; // (4)

      ev.preventDefault();
      vooAtivo = true;

      const cartao = ev.currentTarget;
      const rail = cartao.closest<HTMLElement>(".banca-rail");

      // Contrato de chegada (dono da leitura: onda TESE).
      try {
        window.sessionStorage.setItem(FLAG_CHEGADA, "1");
      } catch {
        /* storage indisponível (modo privado estrito): véu normal na chegada */
      }

      // Nome único SÓ no cartão clicado — CSSOM (carve-out), limpo no finally.
      cartao.style.setProperty("view-transition-name", NOME_MORPH);
      cartao.classList.add(CLASSE_ORIGEM);
      rail?.classList.add(CLASSE_VOO);

      let idTimeout = 0;
      const aoTeclar = (kev: KeyboardEvent) => {
        // Esc = pular a ANIMAÇÃO; a navegação segue (M-g: não é modal).
        if (kev.key === "Escape") vt.skipTransition();
      };

      const vt = doc.startViewTransition(
        () =>
          new Promise<void>((resolver) => {
            resolverPintura = resolver;
            // Nunca segurar o leitor atrás de rede: além do timeout do UA
            // (~4s), corta em ~300ms — skip + swap limpo (véu suprimido,
            // chegada seca digna).
            idTimeout = window.setTimeout(() => {
              if (resolverPintura === resolver) resolverPintura = null;
              vt.skipTransition();
              resolver();
            }, TIMEOUT_PINTURA_MS);
            startTransition(() => {
              router.push(href);
            });
          }),
      );

      document.addEventListener("keydown", aoTeclar);
      vt.finished.finally(() => {
        // LIMPEZA OBRIGATÓRIA (D4): sem ela o nome custom sombreia os
        // .vt-tese-N cross-document; e o rail não pode ficar "em voo".
        window.clearTimeout(idTimeout);
        document.removeEventListener("keydown", aoTeclar);
        cartao.style.removeProperty("view-transition-name");
        cartao.classList.remove(CLASSE_ORIGEM);
        rail?.classList.remove(CLASSE_VOO);
        vooAtivo = false;
      });
    },
    [router, ticker, href],
  );
}
