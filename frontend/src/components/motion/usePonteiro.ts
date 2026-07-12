"use client";

import { useEffect, useSyncExternalStore, type RefObject } from "react";

// ---------------------------------------------------------------------------
// prefers-reduced-motion — mesmo padrão de Reveal.tsx (useSyncExternalStore:
// evita mismatch de hidratação e o anti-padrão de setState direto num
// efeito). `usePrefereReduzido` não é exportado de Reveal.tsx (é interno ao
// motor de revelação por IntersectionObserver, que esta luminária não usa),
// então replica-se aqui o pequeno contrato — mesmo texto/raciocínio do
// original, escopo isolado neste arquivo.
// ---------------------------------------------------------------------------
const QUERY_REDUZIDO = "(prefers-reduced-motion: reduce)";

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

// Luz por ponteiro só em dispositivo com hover real + ponteiro fino (M7,
// direcao-de-arte-cinema.md §2/§4) — touch nunca liga o listener abaixo.
const QUERY_HOVER_FINO = "(hover: hover) and (pointer: fine)";

type OpcoesPonteiro = {
  /**
   * Seletor CSS do elemento que recebe `--mx`/`--my` sob o ponteiro,
   * DENTRO do container observado — habilita delegação (ex.: `.cartao-ticker`
   * numa grade inteira, um único listener para N cards, em vez de um hook
   * por card). Omitido: o próprio container recebe as variáveis (uso de
   * superfície única, ex. o hero).
   */
  seletorAlvo?: string;
};

/**
 * Luminária de ponteiro (§2/§4, .maestro/direcao-de-arte-cinema.md) — liga
 * `--mx`/`--my` (tokens de globals.css, consumidos por `.foco-luz` e
 * `.cartao-ticker.tem-foco::after`) ao movimento do ponteiro dentro do
 * `containerRef` informado.
 *
 * Contrato CSP/perf (C2, redteam-frontend-cinema.md): `pointermove` PASSIVO,
 * coalescido em `requestAnimationFrame` (no máximo 1 escrita de estilo por
 * quadro); as variáveis são setadas via `el.style.setProperty` — CSSOM, não
 * `setAttribute('style', …)` nem `style=` em JSX. `pointerleave` só REMOVE a
 * propriedade (volta ao valor neutro herdado de `:root`); o glide de volta é
 * 100% CSS (`transition` em `.foco-luz`/`::after`), nunca uma animação
 * dirigida por JS.
 *
 * Inerte (não liga nenhum listener) quando `prefers-reduced-motion: reduce`
 * está ativo OU o dispositivo não tem `(hover: hover) and (pointer: fine)`
 * — a camada CSS correspondente também fica oculta nesses casos (defesa em
 * profundidade: globals.css, `.foco-luz`/reduced-motion).
 */
export function usePonteiro<T extends HTMLElement>(
  containerRef: RefObject<T | null>,
  { seletorAlvo }: OpcoesPonteiro = {},
): void {
  const prefereReduzido = usePrefereReduzidoLocal();

  useEffect(() => {
    const container = containerRef.current;
    if (!container || prefereReduzido) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia(QUERY_HOVER_FINO).matches) return;

    // Elemento que recebeu --mx/--my por último (o card sob o cursor, na
    // delegação; ou o próprio container, no uso de superfície única) — só
    // ele precisa ser limpo ao trocar de alvo ou ao sair.
    let alvoAtual: HTMLElement | null = null;
    // Última leitura de pointermove pendente de aplicar no próximo quadro.
    let pendente: { x: number; y: number; alvo: HTMLElement } | null = null;
    let quadroAgendado = false;
    let idQuadro = 0;

    function limpar(alvo: HTMLElement | null) {
      alvo?.style.removeProperty("--mx");
      alvo?.style.removeProperty("--my");
    }

    // Roda no máximo 1x por quadro (rAF): lê a geometria do alvo e escreve
    // --mx/--my relativos ao CENTRO dele (a camada de luz já nasce
    // centralizada — ver `calc(var(--mx) - 60vmax)` em globals.css — então
    // um deslocamento a partir do centro é exatamente o que a mantém sob o
    // ponteiro).
    function aplicar() {
      quadroAgendado = false;
      if (!pendente) return;
      const { x, y, alvo } = pendente;
      const r = alvo.getBoundingClientRect();
      alvo.style.setProperty("--mx", `${x - (r.left + r.width / 2)}px`);
      alvo.style.setProperty("--my", `${y - (r.top + r.height / 2)}px`);
    }

    function aoMover(ev: PointerEvent) {
      // Defesa extra em dispositivo híbrido (touch + mouse): só mouse/caneta
      // acionam a luminária, mesmo que o listener esteja ligado porque o
      // ponteiro PRIMÁRIO do aparelho é fino (matchMedia acima).
      if (ev.pointerType === "touch") return;

      const alvo = seletorAlvo
        ? ((ev.target as HTMLElement | null)?.closest<HTMLElement>(seletorAlvo) ?? null)
        : container;

      if (!alvo) {
        if (alvoAtual) {
          limpar(alvoAtual);
          alvoAtual = null;
        }
        return;
      }
      if (alvo !== alvoAtual) {
        limpar(alvoAtual);
        alvoAtual = alvo;
      }
      pendente = { x: ev.clientX, y: ev.clientY, alvo };
      if (!quadroAgendado) {
        quadroAgendado = true;
        idQuadro = window.requestAnimationFrame(aplicar);
      }
    }

    function aoSair() {
      limpar(alvoAtual);
      alvoAtual = null;
      pendente = null;
    }

    container.addEventListener("pointermove", aoMover, { passive: true });
    container.addEventListener("pointerleave", aoSair, { passive: true });
    // pointercancel (raro com mouse/caneta, possível em híbridos): mesmo
    // tratamento de saída — limpa e volta ao neutro via transition CSS.
    container.addEventListener("pointercancel", aoSair, { passive: true });

    return () => {
      container.removeEventListener("pointermove", aoMover);
      container.removeEventListener("pointerleave", aoSair);
      container.removeEventListener("pointercancel", aoSair);
      // Cancela quadro pendente para nenhum `aplicar()` órfão escrever em nó
      // desmontado após o cleanup.
      window.cancelAnimationFrame(idQuadro);
      limpar(alvoAtual);
    };
  }, [containerRef, seletorAlvo, prefereReduzido]);
}
