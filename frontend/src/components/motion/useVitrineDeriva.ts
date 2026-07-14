"use client";

/**
 * useVitrineDeriva — motor da "vitrine giratória" da Banca de Teses (missão
 * FRONTEND HORIZONTE, raia 1B VITRINE; LEI: .maestro/plano-horizonte.md
 * §1.1 + §5 emendas E7/E8/E15/E16/E21/E24 + .maestro/direcao-horizonte.md
 * D21-D24). Folha CSS irmã: cinema/vitrine.css (controle) + cinema/banca.css
 * (emenda `.banca-derivando`, espelho de `.banca-arrastando`).
 *
 * EXCEÇÃO ÚNICA 2.2.2 do site: a única animação contínua sem gesto do
 * usuário — por isso o protocolo de posse/pausa abaixo é contrato de
 * segurança, não polimento.
 *
 * ⚠ E7 (a falha SILENCIOSA que este hook existe para evitar): a 12px/s a
 * 60fps o incremento é 0,2px/quadro; `scrollLeft` é um INTEIRO (arredondado
 * pelo engine) — ler-e-somar (`rail.scrollLeft += delta`) trunca o delta a
 * cada quadro e a vitrine NUNCA acumula (ou anda aos solavancos de 1px a
 * cada ~5 quadros). Este hook mantém um ACUMULADOR FLOAT interno (posição
 * virtual, `pos`) e escreve sempre o valor ABSOLUTO
 * (`rail.scrollLeft = Math.round(pos)`), nunca lê-e-soma. A posição virtual
 * é RE-SINCRONIZADA a partir do `scrollLeft` REAL sempre que outro dono
 * (drag/voo/snap) tem ou pode ter mexido no scroll.
 *
 * PROTOCOLO DE POSSE DO `scrollLeft` (3 donos nomeados — deriva | drag
 * (useRailDrag.ts) | snap nativo):
 *   - `pointerdown` em QUALQUER lugar do envelope CEDE NA HORA (sem rampa)
 *     — cobre tanto o início de um drag (useRailDrag só arma a classe
 *     `.banca-arrastando` depois de 6px de limiar) quanto o clique que
 *     dispara o morph cartão→página (E21) quanto um clique num dot que
 *     dispara `scrollIntoView`: por isto o cede acontece ANTES de
 *     qualquer um desses três decidir o que fazer, eliminando a corrida
 *     (o clique nasce de pointerdown→pointerup→click; a captura da View
 *     Transition só ocorre depois — a esta altura a deriva já parou de
 *     escrever).
 *   - `.banca-arrastando` presente (useRailDrag ativo) → cede duro
 *     enquanto durar (checado a cada quadro — cobre também o decay de
 *     inércia, que sobrevive ao pointerup).
 *   - voo do morph em andamento (`esperaViradaEmVoo() !== null`,
 *     `useViradaCartao.ts` — INTOCADO, consumido só por LEITURA) → cede
 *     duro, parada IMEDIATA sem rampa, ANTES da captura (E21).
 *   - hover (`pointerenter`/`pointerleave` no rail), foco-dentro
 *     (`focusin`/`focusout` no envelope) e toque em andamento
 *     (`touchstart`/`touchend` no rail) → pausa SUAVE (rampa 400ms) — o
 *     usuário pode só estar lendo, sem necessariamente clicar/arrastar.
 *
 * ⚠ E8 (retomada por ESTADO, nunca por timer): só volta a derivar quando
 * TODAS as condições ficam limpas ao mesmo tempo — sem hover, sem
 * foco-dentro, sem toque em andamento, sem cede duro, sem pausa do
 * controle on-page, seção visível (IO), documento visível
 * (`visibilitychange`) E o scroll do rail está QUIESCENTE (`scrollend` com
 * fallback por debounce — Safari pode não ter `scrollend`). O
 * "quiescente" existe para não atropelar o assentamento do snap/drag/
 * momentum do touch com uma nova escrita de `scrollLeft` — e também para
 * não reacender a deriva no meio do PRÓPRIO assentamento suave que este
 * hook dispara ao parar (ver `assentarNoPontoVizinho`).
 *
 * Reduced motion (D24 — "deriva nem monta"): gate via `usePrefereReduzido`
 * — a mesma interface pública CONGELADA de `usePonteiro.ts` (reaproveitada,
 * não duplicada; ver DESIGN-TOKENS.md "interface usePonteiro congelada").
 *
 * E24 — perf: acumula os últimos ~90 quadros de duração; se o p95 estourar
 * 20ms (jank sustentado — sobretudo Firefox, único engine sem
 * scroll-timeline nativa concorrendo por main thread com esta escrita), a
 * escrita de `scrollLeft` recua para ~30fps (1 a cada 2 quadros) — recuo
 * BINÁRIO, nunca volta a 60fps sozinho (mesma doutrina de recuo do design
 * system: nunca iterar às cegas).
 */

import { useEffect, useRef, type RefObject } from "react";

import { usePrefereReduzido } from "@/components/motion/usePonteiro";
import { esperaViradaEmVoo } from "@/components/motion/useViradaCartao";

const SELETOR_RAIL = ".banca-rail";
const CLASSE_DRAG = "banca-arrastando"; // dono: useRailDrag.ts — só LEITURA aqui
const CLASSE_DERIVA = "banca-derivando"; // dono: este hook (banca.css consome)

const RAMPA_PARTIDA_MS = 800;
const RAMPA_PARADA_MS = 400;
const RESPIRO_MS = 1200;
const QUIESCENCIA_DEBOUNCE_MS = 150;
const JANELA_FRAMES_PERF = 90; // ~1,5s a 60fps
const LIMIAR_P95_MS = 20; // p95 acima disto = jank sustentado (<~50fps)
const VELOCIDADE_PADRAO = 12; // px/s — fallback se o token não resolver

type Fase = "parado" | "acelerando" | "cruzeiro" | "freando" | "respirando";

export type OpcoesVitrineDeriva = {
  /** true = pausado pelo controle on-page (o CHAMADOR já fez a leitura
   * SÍNCRONA do localStorage antes do 1º render — E16; este hook só lê o
   * valor corrente a cada quadro via ref, nunca localStorage). */
  pausadoPeloControle: boolean;
  /** Disparado SÓ nas transições (nunca por quadro) quando o motor entra/
   * sai de um episódio ativo de deriva. `derivando:false` chega exatamente
   * no instante do assentamento (E24 — o consumidor usa este sinal para
   * recalcular o "ativo" dos dots UMA vez, em vez de a cada limiar de IO
   * durante a deriva). */
  aoMudarEstado?: (info: { derivando: boolean }) => void;
};

/** Ease quadrático (mesma família de `ease-ink`: sai rápido, assenta —
 * aqui em forma fechada por ser aplicado dentro do próprio loop, não CSS). */
function facilitarQuadratico(t: number): number {
  const c = Math.min(Math.max(t, 0), 1);
  return 1 - (1 - c) * (1 - c);
}

export function useVitrineDeriva(
  envelopeRef: RefObject<HTMLElement | null>,
  opcoes: OpcoesVitrineDeriva,
): void {
  const prefereReduzido = usePrefereReduzido();

  // Refs sincronizadas a CADA commit (nunca durante o render — React 19
  // proíbe escrever em ref.current no corpo do componente): o loop rAF vive
  // numa única closure de longa duração e não pode reassinar o efeito
  // principal toda vez que `pausadoPeloControle`/`aoMudarEstado` mudam de
  // valor. Sem array de deps: roda em TODO commit, sempre antes do próximo
  // quadro do loop (que só é agendado pelo efeito principal, abaixo).
  const pausadoRef = useRef(opcoes.pausadoPeloControle);
  const aoMudarEstadoRef = useRef(opcoes.aoMudarEstado);
  useEffect(() => {
    pausadoRef.current = opcoes.pausadoPeloControle;
    aoMudarEstadoRef.current = opcoes.aoMudarEstado;
  });

  useEffect(() => {
    const envelope = envelopeRef.current;
    if (!envelope || prefereReduzido || typeof window === "undefined") return;
    const rail = envelope.querySelector<HTMLElement>(SELETOR_RAIL);
    if (!rail) return;

    // ---------------- estado do motor (imperativo, 1 loop) ----------------
    let fase: Fase = "parado";
    let direcao: 1 | -1 = 1;
    let velAtual = 0;
    let pos = rail.scrollLeft; // acumulador FLOAT (E7) — nunca somado de volta ao DOM
    let tsInicioFase = 0;
    let velInicioFreio = 0;
    let maxScroll = Math.max(0, rail.scrollWidth - rail.clientWidth);
    let derivandoAntes = false; // só dispara aoMudarEstado na transição

    // Velocidade-base lida 1x por getComputedStyle (token --deriva-vel já
    // resolve 12/8 conforme o breakpoint vigente no momento do mount).
    const tokenVel = parseFloat(getComputedStyle(rail).getPropertyValue("--deriva-vel"));
    const velBase = Number.isFinite(tokenVel) && tokenVel > 0 ? tokenVel : VELOCIDADE_PADRAO;

    // ---------------- gates de vida/posse ----------------
    let hover = false;
    let focoDentro = false;
    let tocando = false;
    let cedidoDuro = false; // pointerdown em curso no envelope (drag OU clique/morph)
    let visivel = false; // IO da seção
    let documentoVisivel = document.visibilityState === "visible";
    let scrollQuiescente = true;

    // ---------------- recuo automático de perf (E24) ----------------
    const duracoesQuadro: number[] = [];
    let modo30fps = false;
    let pularProximaEscrita = false;

    const podeContinuar = (): boolean =>
      !pausadoRef.current &&
      visivel &&
      documentoVisivel &&
      !cedidoDuro &&
      !hover &&
      !focoDentro &&
      !tocando;

    const podeIniciar = (): boolean => podeContinuar() && scrollQuiescente;

    const marcarDerivando = (agora: boolean) => {
      if (agora === derivandoAntes) return;
      derivandoAntes = agora;
      rail.classList.toggle(CLASSE_DERIVA, agora);
      aoMudarEstadoRef.current?.({ derivando: agora });
    };

    // Snap-points reais (mesmo algoritmo de useRailDrag.ts, duplicado de
    // propósito: aquele hook é INTOCADO — D24 — e não os exporta).
    const pontosDeSnap = (): number[] => {
      const pad = parseFloat(getComputedStyle(rail).scrollPaddingLeft) || 0;
      const base = rail.getBoundingClientRect().left;
      const max = rail.scrollWidth - rail.clientWidth;
      return Array.from(rail.children).map((li) => {
        const alvo = li.getBoundingClientRect().left - base + rail.scrollLeft - pad;
        return Math.min(Math.max(alvo, 0), max);
      });
    };
    const pontoMaisProximo = (pontos: number[], x: number): number | null => {
      if (pontos.length === 0) return null;
      let melhor = pontos[0];
      for (let i = 1; i < pontos.length; i++) {
        if (Math.abs(pontos[i] - x) < Math.abs(melhor - x)) melhor = pontos[i];
      }
      return melhor;
    };

    // Ao parar por uma razão SUAVE (nunca por cede duro — quem assume,
    // drag/voo, cuida do próprio destino): religa o snap (a classe some no
    // fim de `quadro()`) e assenta no ponto vizinho — "reuse a projeção do
    // useRailDrag" (D21/D23). Scroll curto e suave: nunca some no meio de
    // um cartão.
    const assentarNoPontoVizinho = () => {
      const alvo = pontoMaisProximo(pontosDeSnap(), rail.scrollLeft);
      if (alvo === null) return;
      rail.scrollTo({ left: alvo, behavior: prefereReduzido ? "auto" : "smooth" });
    };

    // ---------------- loop principal ----------------
    let rafId = 0;
    let ultimoTs = 0;

    const avancar = (ts: number, dtSeg: number) => {
      if (maxScroll <= 0) return;
      pos += direcao * velAtual * dtSeg;
      if (pos >= maxScroll) {
        pos = maxScroll;
        fase = "respirando";
        tsInicioFase = ts;
        velAtual = 0;
      } else if (pos <= 0) {
        pos = 0;
        fase = "respirando";
        tsInicioFase = ts;
        velAtual = 0;
      }
      if (modo30fps) {
        pularProximaEscrita = !pularProximaEscrita;
        if (pularProximaEscrita) return; // 1 escrita a cada 2 quadros
      }
      // E7 — SEMPRE valor ABSOLUTO, nunca `+=` (read-modify-write trunca).
      rail.scrollLeft = Math.round(pos);
    };

    const quadro = (ts: number) => {
      rafId = window.requestAnimationFrame(quadro);
      const dtBrutoMs = ultimoTs ? Math.min(ts - ultimoTs, 100) : 16.7;
      ultimoTs = ts;
      const dtSeg = dtBrutoMs / 1000;

      // Recuo automático de perf (E24) — latch binário, nunca oscila.
      if (!modo30fps) {
        duracoesQuadro.push(dtBrutoMs);
        if (duracoesQuadro.length > JANELA_FRAMES_PERF) duracoesQuadro.shift();
        if (duracoesQuadro.length === JANELA_FRAMES_PERF) {
          const ordenado = [...duracoesQuadro].sort((a, b) => a - b);
          const p95 = ordenado[Math.floor(ordenado.length * 0.95)];
          if (p95 > LIMIAR_P95_MS) modo30fps = true;
        }
      }

      // ---- posse dura: drag ativo OU voo do morph em curso (E7/E21) ----
      const dragAtivo = rail.classList.contains(CLASSE_DRAG);
      const vooAtivoAgora = esperaViradaEmVoo() !== null;
      if (cedidoDuro || dragAtivo || vooAtivoAgora) {
        if (fase !== "parado") {
          fase = "parado";
          velAtual = 0;
        }
        pos = rail.scrollLeft; // re-sincroniza a posição virtual (E7)
        marcarDerivando(false);
        return;
      }

      switch (fase) {
        case "parado": {
          pos = rail.scrollLeft; // qualquer coisa pode ter rolado enquanto parado
          if (podeIniciar()) {
            fase = "acelerando";
            tsInicioFase = ts;
          }
          break;
        }
        case "acelerando": {
          if (!podeContinuar()) {
            fase = "freando";
            tsInicioFase = ts;
            velInicioFreio = velAtual;
            break;
          }
          const t = (ts - tsInicioFase) / RAMPA_PARTIDA_MS;
          velAtual = velBase * facilitarQuadratico(t);
          if (t >= 1) fase = "cruzeiro";
          avancar(ts, dtSeg);
          break;
        }
        case "cruzeiro": {
          if (!podeContinuar()) {
            fase = "freando";
            tsInicioFase = ts;
            velInicioFreio = velAtual;
            break;
          }
          velAtual = velBase;
          avancar(ts, dtSeg);
          break;
        }
        case "freando": {
          const t = (ts - tsInicioFase) / RAMPA_PARADA_MS;
          velAtual = velInicioFreio * (1 - facilitarQuadratico(t));
          avancar(ts, dtSeg);
          if (t >= 1) {
            velAtual = 0;
            fase = "parado";
            assentarNoPontoVizinho();
          }
          break;
        }
        case "respirando": {
          if (!podeContinuar()) {
            fase = "parado";
            assentarNoPontoVizinho(); // já está numa ponta; idempotente se lá for o snap
            break;
          }
          if (ts - tsInicioFase >= RESPIRO_MS) {
            direcao = direcao === 1 ? -1 : 1;
            fase = "acelerando";
            tsInicioFase = ts;
          }
          break;
        }
      }

      marcarDerivando(fase !== "parado");
    };

    // ---------------- listeners de posse/gates ----------------
    // Hover: só no RAIL (área de leitura dos cartões) — pausa suave.
    const aoEntrarRail = () => {
      hover = true;
    };
    const aoSairRail = () => {
      hover = false;
    };
    // Toque: só no RAIL — pausa suave (o momentum pós-touchend é coberto
    // pelo gate de scroll quiescente, não por este flag).
    const aoTocar = () => {
      tocando = true;
    };
    const aoDestocar = () => {
      tocando = false;
    };
    // pointerdown no ENVELOPE INTEIRO (rail + dots + setas + controle)
    // CEDE NA HORA (sem rampa) — cobre drag, clique de morph E clique de
    // dot (que dispara scrollIntoView nativo): ver comentário-lei no topo.
    const aoPressionar = () => {
      cedidoDuro = true;
    };
    const aoLiberarPressao = () => {
      cedidoDuro = false;
    };
    // Foco-dentro (teclado — cartões/dots/setas) — pausa suave. Recomputa
    // via `document.activeElement` em AMBAS as direções (nunca fixa `true`
    // direto no `focusin`): o `[data-vitrine-nao-pausa]` (marcado no botão
    // do controle, GaleriaBanca.tsx) fica de FORA desta contagem — sem
    // isto, o próprio clique no controle prende o foco nele (comportamento
    // nativo do <button>) e a deriva NUNCA retomaria após "retomar" (o
    // controle que acabou de MANDAR reiniciar ficaria, ele mesmo, travando
    // o reinício por focus-within — bug encontrado na prova local desta
    // raia). Cartões/dots/setas continuam pausando normalmente.
    const recalcularFoco = () => {
      queueMicrotask(() => {
        const ativo = document.activeElement;
        focoDentro =
          !!ativo &&
          envelope.contains(ativo) &&
          !(ativo as Element).closest("[data-vitrine-nao-pausa]");
      });
    };
    const aoMudarVisibilidade = () => {
      documentoVisivel = document.visibilityState === "visible";
    };

    let idDebounceScroll = 0;
    const marcarQuiescente = () => {
      scrollQuiescente = true;
    };
    const marcarNaoQuiescente = () => {
      scrollQuiescente = false;
    };
    const aoRolarSemScrollEnd = () => {
      scrollQuiescente = false;
      window.clearTimeout(idDebounceScroll);
      idDebounceScroll = window.setTimeout(marcarQuiescente, QUIESCENCIA_DEBOUNCE_MS);
    };
    const temScrollEnd = "onscrollend" in window;

    const io = new IntersectionObserver(
      (entradas) => {
        const entrada = entradas[entradas.length - 1];
        visivel = entrada?.isIntersecting ?? false;
      },
      { threshold: 0 },
    );
    io.observe(envelope);

    // maxScroll recalculado só em mudanças de layout reais (nunca por
    // quadro — evita reflow forçado a 60fps): resize do rail + fontes.
    const ro = new ResizeObserver(() => {
      maxScroll = Math.max(0, rail.scrollWidth - rail.clientWidth);
    });
    ro.observe(rail);
    document.fonts?.ready
      .then(() => {
        maxScroll = Math.max(0, rail.scrollWidth - rail.clientWidth);
      })
      .catch(() => {});

    rail.addEventListener("pointerenter", aoEntrarRail, { passive: true });
    rail.addEventListener("pointerleave", aoSairRail, { passive: true });
    rail.addEventListener("touchstart", aoTocar, { passive: true });
    rail.addEventListener("touchend", aoDestocar, { passive: true });
    rail.addEventListener("touchcancel", aoDestocar, { passive: true });
    envelope.addEventListener("pointerdown", aoPressionar, { passive: true });
    window.addEventListener("pointerup", aoLiberarPressao, { passive: true });
    window.addEventListener("pointercancel", aoLiberarPressao, { passive: true });
    envelope.addEventListener("focusin", recalcularFoco);
    envelope.addEventListener("focusout", recalcularFoco);
    document.addEventListener("visibilitychange", aoMudarVisibilidade);
    if (temScrollEnd) {
      rail.addEventListener("scroll", marcarNaoQuiescente, { passive: true });
      rail.addEventListener("scrollend", marcarQuiescente, { passive: true });
    } else {
      rail.addEventListener("scroll", aoRolarSemScrollEnd, { passive: true });
    }

    rafId = window.requestAnimationFrame(quadro);

    return () => {
      // E21/D24: o loop MORRE no unmount — nenhum rAF órfão sobrevive.
      window.cancelAnimationFrame(rafId);
      io.disconnect();
      ro.disconnect();
      window.clearTimeout(idDebounceScroll);
      rail.removeEventListener("pointerenter", aoEntrarRail);
      rail.removeEventListener("pointerleave", aoSairRail);
      rail.removeEventListener("touchstart", aoTocar);
      rail.removeEventListener("touchend", aoDestocar);
      rail.removeEventListener("touchcancel", aoDestocar);
      envelope.removeEventListener("pointerdown", aoPressionar);
      window.removeEventListener("pointerup", aoLiberarPressao);
      window.removeEventListener("pointercancel", aoLiberarPressao);
      envelope.removeEventListener("focusin", recalcularFoco);
      envelope.removeEventListener("focusout", recalcularFoco);
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
      if (temScrollEnd) {
        rail.removeEventListener("scroll", marcarNaoQuiescente);
        rail.removeEventListener("scrollend", marcarQuiescente);
      } else {
        rail.removeEventListener("scroll", aoRolarSemScrollEnd);
      }
      rail.classList.remove(CLASSE_DERIVA);
    };
  }, [envelopeRef, prefereReduzido]);
}
