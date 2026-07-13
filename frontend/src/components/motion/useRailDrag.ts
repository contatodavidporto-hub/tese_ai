"use client";

/**
 * useRailDrag — arrasto de MOUSE com inércia no rail da Banca (APOTEOSE,
 * crit. 5 / LEI §3.5 + D6; dossiê .maestro/recon/rail-sem-barra.md).
 * Lado CSS do contrato: cinema/banca.css (.banca-arrastando, hairline).
 *
 * DOUTRINA (INP/CSP/one-writer):
 *   - Escreve SEMPRE `rail.scrollLeft` (propriedade DOM de scroll — nunca
 *     transform, nunca estilo): view(inline) do carimbo, IO do card ativo,
 *     snap e hairline continuam funcionando porque o scroll é REAL.
 *   - ZERO listener `passive:false` (a razão do veto ao Lenis): pointer
 *     events não bloqueiam pan nativo; quem governa touch é `touch-action`
 *     (default). Touch/caneta ficam 100% nativos: drag SÓ
 *     `pointerType === 'mouse'` e `button === 0`.
 *   - Threshold 6px antes de capturar (clique/foco dos cartões-link fluem
 *     intactos abaixo disso); `setPointerCapture` só então; supressão de
 *     `click` em FASE DE CAPTURA apenas quando houve drag de fato.
 *   - snap-mandatory OFF via classList durante o drag (senão o engine
 *     re-snapa cada escrita programática) → no release, o destino é
 *     PROJETADO pela velocidade, CLAMPADO no snap-point vizinho, e um
 *     decay rAF (~0.93/frame, dt-normalizado) leva até o ponto EXATO —
 *     só então o snap religa (jump zero por construção).
 *   - `pointercancel` + `lostpointercapture` tratados (alt-tab, captura
 *     roubada); `scrollend` com guard `'onscrollend' in window` (fallback
 *     debounce de scroll) como rede de segurança do estado.
 *   - prefers-reduced-motion: o arrasto (manipulação direta) segue; o
 *     decay vira `scrollTo(auto)` direto no snap-point (sem animação).
 */

import { useEffect, type RefObject } from "react";

const CLASSE_DRAG = "banca-arrastando";
const SELETOR_RAIL = ".banca-rail";
const LIMIAR_PX = 6;
const DECAY = 0.93; // por quadro de 60fps, normalizado por dt
const QUADRO_MS = 1000 / 60;
const JANELA_VELOCIDADE_MS = 100; // amostras mais velhas não contam
const QUERY_REDUZIDO = "(prefers-reduced-motion: reduce)";

type Amostra = { x: number; t: number };

export function useRailDrag(envelopeRef: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const envelope = envelopeRef.current;
    if (!envelope || typeof window === "undefined") return;
    const rail = envelope.querySelector<HTMLElement>(SELETOR_RAIL);
    if (!rail) return;

    // ------- estado da sessão de drag (1 ponteiro por vez) -------
    let idPonteiro = -1;
    let sessaoAtiva = false; // entre pointerdown e up/cancel (mouse b0)
    let arrastando = false; // passou do threshold e capturou
    let houveDrag = false; // arma a supressão do próximo click
    let x0 = 0;
    let scroll0 = 0;
    let xPendente = 0;
    let quadroDrag = 0;
    let dragAgendado = false;
    let amostras: Amostra[] = [];
    // ------- estado do decay de inércia -------
    let decayAtivo = false;
    let quadroDecay = 0;

    const aplicarDrag = () => {
      dragAgendado = false;
      if (!arrastando) return;
      rail.scrollLeft = scroll0 - (xPendente - x0);
    };

    const pontosDeSnap = (): number[] => {
      // Posição de scroll que alinha cada <li> (snap-start) respeitando o
      // scroll-padding-inline (scroll-px-4/6 do componente).
      const pad = parseFloat(getComputedStyle(rail).scrollPaddingLeft) || 0;
      const base = rail.getBoundingClientRect().left;
      const max = rail.scrollWidth - rail.clientWidth;
      return Array.from(rail.children).map((li) => {
        const alvo = li.getBoundingClientRect().left - base + rail.scrollLeft - pad;
        return Math.min(Math.max(alvo, 0), max);
      });
    };

    const indiceMaisProximo = (pontos: number[], x: number): number => {
      let melhor = 0;
      for (let i = 1; i < pontos.length; i++) {
        if (Math.abs(pontos[i] - x) < Math.abs(pontos[melhor] - x)) melhor = i;
      }
      return melhor;
    };

    const terminarDecay = (alvo: number) => {
      rail.scrollLeft = alvo; // ponto EXATO antes de religar o snap
      decayAtivo = false;
      rail.classList.remove(CLASSE_DRAG); // snap ON — já estamos nele: jump zero
    };

    const iniciarInercia = (vQuadro: number) => {
      const pontos = pontosDeSnap();
      if (pontos.length === 0) {
        rail.classList.remove(CLASSE_DRAG);
        return;
      }
      const x = rail.scrollLeft;
      const iAtual = indiceMaisProximo(pontos, x);
      // Projeção geométrica do decay: soma v·d/(1−d) além do ponto atual.
      const projetado = x + (vQuadro * DECAY) / (1 - DECAY);
      // Clamp no snap-point VIZINHO (LEI §3.5): no máximo 1 card além do
      // ponto onde o dedo soltou — flick digno, nunca voo cego.
      const iProj = indiceMaisProximo(pontos, projetado);
      const iAlvo = Math.min(Math.max(iProj, iAtual - 1), iAtual + 1);
      const alvo = pontos[iAlvo];

      if (window.matchMedia(QUERY_REDUZIDO).matches) {
        // Reduce: assentar direto, sem decay (registro em banca.css).
        rail.scrollTo({ left: alvo, behavior: "auto" });
        rail.classList.remove(CLASSE_DRAG);
        return;
      }

      decayAtivo = true;
      let resto = alvo - x;
      let tAnterior = performance.now();
      const passo = (t: number) => {
        if (!decayAtivo) return;
        const dt = Math.max(t - tAnterior, 0.001);
        tAnterior = t;
        resto *= Math.pow(DECAY, dt / QUADRO_MS);
        if (Math.abs(resto) < 0.5) {
          terminarDecay(alvo);
          return;
        }
        rail.scrollLeft = alvo - resto;
        quadroDecay = window.requestAnimationFrame(passo);
      };
      quadroDecay = window.requestAnimationFrame(passo);
    };

    const velocidadeQuadro = (): number => {
      // px/quadro do SCROLL (sinal oposto ao do ponteiro), média da janela.
      const agora = performance.now();
      const janela = amostras.filter((a) => agora - a.t <= JANELA_VELOCIDADE_MS);
      if (janela.length < 2) return 0;
      const a = janela[0];
      const b = janela[janela.length - 1];
      const dtMs = b.t - a.t;
      if (dtMs <= 0) return 0;
      return (-(b.x - a.x) / dtMs) * QUADRO_MS;
    };

    const finalizarSessao = (comInercia: boolean) => {
      if (!sessaoAtiva) return;
      sessaoAtiva = false;
      rail.removeEventListener("pointermove", aoMover);
      rail.removeEventListener("pointerup", aoSoltar);
      rail.removeEventListener("pointercancel", aoCancelar);
      rail.removeEventListener("lostpointercapture", aoPerderCaptura);
      window.cancelAnimationFrame(quadroDrag);
      dragAgendado = false;
      if (arrastando) {
        arrastando = false;
        try {
          rail.releasePointerCapture(idPonteiro);
        } catch {
          /* captura já perdida (lostpointercapture) — ok */
        }
        iniciarInercia(comInercia ? velocidadeQuadro() : 0);
      } else if (rail.classList.contains(CLASSE_DRAG) && !decayAtivo) {
        // Clique seco no meio de um decay interrompido: assenta no vizinho
        // mais próximo antes de religar o snap (nunca religar fora do ponto).
        iniciarInercia(0);
      }
      idPonteiro = -1;
    };

    const aoMover = (ev: PointerEvent) => {
      if (ev.pointerId !== idPonteiro) return;
      const dx = ev.clientX - x0;
      if (!arrastando) {
        if (Math.abs(dx) <= LIMIAR_PX) return;
        arrastando = true;
        houveDrag = true;
        try {
          rail.setPointerCapture(idPonteiro);
        } catch {
          /* ponteiro já inválido — a sessão morre no próximo evento */
        }
        rail.classList.add(CLASSE_DRAG); // snap OFF + user-select none + cursor
      }
      amostras.push({ x: ev.clientX, t: performance.now() });
      if (amostras.length > 8) amostras.shift();
      xPendente = ev.clientX;
      if (!dragAgendado) {
        dragAgendado = true;
        quadroDrag = window.requestAnimationFrame(aplicarDrag);
      }
    };

    const aoSoltar = (ev: PointerEvent) => {
      if (ev.pointerId !== idPonteiro) return;
      finalizarSessao(true);
    };
    const aoCancelar = (ev: PointerEvent) => {
      if (ev.pointerId !== idPonteiro) return;
      finalizarSessao(false); // sem velocidade confiável: assenta no vizinho
    };
    const aoPerderCaptura = (ev: PointerEvent) => {
      // Browser roubou a captura (alt-tab, etc.) com a sessão ainda viva.
      if (ev.pointerId !== idPonteiro || !arrastando) return;
      finalizarSessao(false);
    };

    const aoPressionar = (ev: PointerEvent) => {
      if (ev.pointerType !== "mouse" || ev.button !== 0) return;
      if (sessaoAtiva) return;
      // Agarrar durante a inércia: congela o decay onde está (o snap segue
      // OFF pela classe; o release desta nova sessão reprojeta e religa).
      if (decayAtivo) {
        decayAtivo = false;
        window.cancelAnimationFrame(quadroDecay);
      }
      houveDrag = false; // rearma a supressão de click desta sessão
      sessaoAtiva = true;
      arrastando = false;
      idPonteiro = ev.pointerId;
      x0 = ev.clientX;
      scroll0 = rail.scrollLeft;
      amostras = [{ x: ev.clientX, t: performance.now() }];
      // NUNCA preventDefault aqui: foco/click dos cartões-link fluem.
      rail.addEventListener("pointermove", aoMover);
      rail.addEventListener("pointerup", aoSoltar);
      rail.addEventListener("pointercancel", aoCancelar);
      rail.addEventListener("lostpointercapture", aoPerderCaptura);
    };

    // Supressão do clique fantasma — FASE DE CAPTURA, só quando houve drag.
    // Rearma-se aqui mesmo (e não só no pointerdown): um Enter de teclado
    // logo após um drag não pode ser engolido pela flag velha.
    const aoClicarCaptura = (ev: MouseEvent) => {
      if (!houveDrag) return;
      // Enter/Space num link dispara click com detail 0 — ativação de
      // teclado NUNCA é clique fantasma; não consome a flag.
      if (ev.detail === 0) return;
      houveDrag = false;
      ev.preventDefault();
      ev.stopPropagation();
    };

    // Anchors são arrastáveis nativamente (drag-and-drop de link roubaria
    // o pointermove no meio do gesto) — só durante uma sessão de drag.
    const aoDragStart = (ev: Event) => {
      if (sessaoAtiva) ev.preventDefault();
    };

    // Rede de segurança: se por qualquer corrida a classe ficou órfã após o
    // scroll assentar (sem sessão nem decay), religa o snap.
    const aoFimDoScroll = () => {
      if (!sessaoAtiva && !decayAtivo && rail.classList.contains(CLASSE_DRAG)) {
        rail.classList.remove(CLASSE_DRAG);
      }
    };
    let idDebounce = 0;
    const aoScrollFallback = () => {
      window.clearTimeout(idDebounce);
      idDebounce = window.setTimeout(aoFimDoScroll, 120);
    };
    const temScrollEnd = "onscrollend" in window;

    rail.addEventListener("pointerdown", aoPressionar);
    rail.addEventListener("click", aoClicarCaptura, { capture: true });
    rail.addEventListener("dragstart", aoDragStart);
    if (temScrollEnd) {
      rail.addEventListener("scrollend", aoFimDoScroll, { passive: true });
    } else {
      rail.addEventListener("scroll", aoScrollFallback, { passive: true });
    }

    return () => {
      finalizarSessao(false);
      decayAtivo = false;
      window.cancelAnimationFrame(quadroDecay);
      window.clearTimeout(idDebounce);
      rail.removeEventListener("pointerdown", aoPressionar);
      rail.removeEventListener("click", aoClicarCaptura, { capture: true });
      rail.removeEventListener("dragstart", aoDragStart);
      if (temScrollEnd) {
        rail.removeEventListener("scrollend", aoFimDoScroll);
      } else {
        rail.removeEventListener("scroll", aoScrollFallback);
      }
      rail.classList.remove(CLASSE_DRAG);
    };
  }, [envelopeRef]);
}
