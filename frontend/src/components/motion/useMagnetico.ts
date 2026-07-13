"use client";

/**
 * useMagnetico / IlhaMagnetica — física de cursor dos CTAs (Onda 1B).
 * Plano: .maestro/plano-imersivo.md §3 crit.5 + emendas R2/R5 (LEI).
 * Folha CSS irmã (estáticos + reduce): src/styles/cinema/magnetico.css.
 *
 * FÍSICA (assinatura única da casa — "núcleo rápido, corpo com atraso"):
 *   - atração: gsap.quickTo em x/y, 0.45s ease power3.out, deslocamento =
 *     (cursor − centro) × 0.35 com clamp ±8px (CTAs) ou ±5px (variante
 *     .magnetico-fino — setas/dots do filmstrip);
 *   - retorno: elastic.out(1, 0.45) em 0.6s no pointerleave — exceção
 *     REGISTRADA à regra do spring único (--ease-settle), válida SÓ para a
 *     física de cursor em CTA (DESIGN-TOKENS.md §3, emenda MATÉRIA VIVA);
 *     nunca entrada de conteúdo, nunca card;
 *   - peso de tinta: press = classe CSS .magnetico-press (scale 0.985/80ms
 *     via propriedade `scale` na folha — NÃO tween; `transform` tem um único
 *     escritor: o GSAP).
 *
 * GATES: só (hover:hover) and (pointer:fine), fora de prefers-reduced-motion
 * (reação a mudança ao vivo via useSyncExternalStore), pointerType "touch"
 * ignorado (defesa extra em híbridos). Touch/sem hover/reduce = inerte.
 *
 * R5 (lazy de verdade): o gsap só é baixado via carregarGsap() no PRIMEIRO
 * pointerenter/pointerover num .magnetico — nunca no mount, nunca na
 * hidratação. Antes de o motor chegar o botão funciona 100% (hover de cor,
 * press por classe); a atração começa quando o chunk resolve.
 *
 * R2 (LEI): magnéticos SÓ em ilhas da LANDING — CTAs do hero e da faixa
 * final + setas/dots do filmstrip. O Header NÃO importa este módulo nem
 * gsap; decisão final da 1D (Header.tsx): o CTA do Header fica SEM física
 * em todas as rotas (não recebe .magnetico). /tese segue com delta ZERO de
 * gsap.
 *
 * SEM tilt/levitação/parallax em cards (regra mantida); cursor-follower/
 * pena de tinta seguem FORA (gramática de template).
 *
 * CSP: zero delta — GSAP escreve transform via CSSOM (element.style,
 * carve-out formal); press/estado só por classList; cleanup remove a
 * propriedade via el.style.removeProperty (CSSOM).
 */

import { useEffect, useSyncExternalStore, type RefObject } from "react";

import { carregarGsap, type MotorGsap } from "@/lib/gsapSetup";

// ---------------------------------------------------------------------------
// prefers-reduced-motion — mesmo padrão de usePonteiro.ts/Reveal.tsx
// (useSyncExternalStore: sem mismatch de hidratação, reage à mudança ao
// vivo). Contrato pequeno replicado localmente, como lá.
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

/** Física de cursor só com hover real + ponteiro fino (mesmo gate da luz). */
const QUERY_HOVER_FINO = "(hover: hover) and (pointer: fine)";

// Classes LITERAIS do contrato (cinema/magnetico.css) — nunca em template
// string (Tailwind v4 purga literal não escaneável; estas vivem na folha
// cinema, mas a regra vale como disciplina).
const CLASSE_ALVO = "magnetico";
const CLASSE_FINO = "magnetico-fino";
const CLASSE_PRESS = "magnetico-press";

const ALCANCE_PADRAO = 8; // px — CTAs (hero, faixa final)
const ALCANCE_FINO = 5; // px — setas/dots do filmstrip (.magnetico-fino)
const FATOR_ATRACAO = 0.35;
const DURACAO_ATRACAO = 0.45; // s — quickTo
const DURACAO_RETORNO = 0.6; // s — elastic.out(1, 0.45)

type QuickTo = ReturnType<MotorGsap["gsap"]["quickTo"]>;

type EstadoIma = {
  xTo: QuickTo | null;
  yTo: QuickTo | null;
  ultimoX: number;
  ultimoY: number;
  temPonteiro: boolean;
  quadro: number;
  agendado: boolean;
  desligar: () => void;
};

/** Motor memoizado (referência local pós-resolve; módulo é singleton). */
let motor: MotorGsap | null = null;

/** Ímãs com listeners ativos no momento (1 por elemento sob o cursor). */
const imasAtivos = new Map<HTMLElement, EstadoIma>();

function limitar(valor: number, alcance: number): number {
  return Math.min(alcance, Math.max(-alcance, valor));
}

/**
 * Liga a física num .magnetico a partir do pointerenter/over. Listeners de
 * move/leave/press ficam no PRÓPRIO elemento enquanto o cursor está nele;
 * leitura de layout só dentro de rAF coalescido (máx. 1 gBCR por quadro —
 * precedente do usePonteiro), com o centro corrigido pela translação
 * corrente do próprio ímã (o rect acompanha o tween).
 */
function ativarIma(el: HTMLElement): void {
  if (imasAtivos.has(el)) return;
  const alcance = el.classList.contains(CLASSE_FINO) ? ALCANCE_FINO : ALCANCE_PADRAO;

  const estado: EstadoIma = {
    xTo: null,
    yTo: null,
    ultimoX: 0,
    ultimoY: 0,
    temPonteiro: false,
    quadro: 0,
    agendado: false,
    desligar: () => {},
  };

  const aplicar = () => {
    estado.agendado = false;
    if (!estado.temPonteiro || !estado.xTo || !estado.yTo || !motor) return;
    const r = el.getBoundingClientRect();
    const tx = Number(motor.gsap.getProperty(el, "x")) || 0;
    const ty = Number(motor.gsap.getProperty(el, "y")) || 0;
    const cx = r.left + r.width / 2 - tx;
    const cy = r.top + r.height / 2 - ty;
    estado.xTo(limitar((estado.ultimoX - cx) * FATOR_ATRACAO, alcance));
    estado.yTo(limitar((estado.ultimoY - cy) * FATOR_ATRACAO, alcance));
  };

  const agendar = () => {
    if (estado.agendado) return;
    estado.agendado = true;
    estado.quadro = window.requestAnimationFrame(aplicar);
  };

  const aoMover = (ev: PointerEvent) => {
    if (ev.pointerType === "touch") return;
    estado.ultimoX = ev.clientX;
    estado.ultimoY = ev.clientY;
    estado.temPonteiro = true;
    agendar();
  };

  // Peso de tinta: só classe (a folha anima `scale`, propriedade
  // independente — não briga com o transform do GSAP).
  const aoPressionar = (ev: PointerEvent) => {
    if (ev.pointerType === "touch") return;
    el.classList.add(CLASSE_PRESS);
  };
  const aoSoltar = () => el.classList.remove(CLASSE_PRESS);
  const aoSair = () => desativarIma(el, true);

  el.addEventListener("pointermove", aoMover, { passive: true });
  el.addEventListener("pointerdown", aoPressionar, { passive: true });
  el.addEventListener("pointerup", aoSoltar, { passive: true });
  el.addEventListener("pointerleave", aoSair, { passive: true });
  el.addEventListener("pointercancel", aoSair, { passive: true });

  estado.desligar = () => {
    el.removeEventListener("pointermove", aoMover);
    el.removeEventListener("pointerdown", aoPressionar);
    el.removeEventListener("pointerup", aoSoltar);
    el.removeEventListener("pointerleave", aoSair);
    el.removeEventListener("pointercancel", aoSair);
    window.cancelAnimationFrame(estado.quadro);
    el.classList.remove(CLASSE_PRESS);
  };
  imasAtivos.set(el, estado);

  // Lazy de verdade (R5): o chunk do gsap só desce aqui, no primeiro hover.
  carregarGsap()
    .then((m) => {
      motor = m;
      if (imasAtivos.get(el) !== estado) return; // saiu antes do motor chegar
      // quickTo com overwrite:"auto": a 1ª chamada mata o canal x/y de um
      // retorno elástico ainda em voo (re-entrada rápida).
      estado.xTo = m.gsap.quickTo(el, "x", {
        duration: DURACAO_ATRACAO,
        ease: "power3.out",
        overwrite: "auto",
      });
      estado.yTo = m.gsap.quickTo(el, "y", {
        duration: DURACAO_ATRACAO,
        ease: "power3.out",
        overwrite: "auto",
      });
      if (estado.temPonteiro) agendar();
    })
    .catch(() => {
      // Sem física; o CTA segue 100% funcional (hover de cor + press CSS).
    });
}

// Elementos com retorno elástico EM VOO (já fora de imasAtivos): o
// cleanup precisa alcançá-los — um tween de 0,6s não pode sobreviver ao
// unmount da ilha (auditoria final 2026-07-13, achado 8).
const retornosEmVoo = new Set<HTMLElement>();

function desativarIma(el: HTMLElement, comRetorno: boolean): void {
  const estado = imasAtivos.get(el);
  if (!estado) return;
  imasAtivos.delete(el);
  estado.desligar();
  if (!motor) return; // nada foi movido ainda
  if (comRetorno) {
    // Retorno elástico (exceção registrada ao spring único — só aqui).
    retornosEmVoo.add(el);
    motor.gsap.to(el, {
      x: 0,
      y: 0,
      duration: DURACAO_RETORNO,
      ease: "elastic.out(1,0.45)",
      overwrite: "auto",
      onComplete: () => retornosEmVoo.delete(el),
    });
  } else {
    // Desligamento seco (unmount/reduce ligado): zera sem animação.
    motor.gsap.killTweensOf(el);
    el.style.removeProperty("transform"); // CSSOM — carve-out
  }
}

function desativarTodos(): void {
  for (const el of Array.from(imasAtivos.keys())) desativarIma(el, false);
  // Retornos elásticos em voo: mata e zera (nó pode estar desmontando).
  for (const el of Array.from(retornosEmVoo)) {
    retornosEmVoo.delete(el);
    motor?.gsap.killTweensOf(el);
    el.style.removeProperty("transform"); // CSSOM — carve-out
  }
}

/**
 * Hook de elemento único — para quem já tem ref do alvo (ex.: Onda 1C nas
 * setas/dots do filmstrip, se preferir ligação direta em vez da ilha).
 * O elemento deve ter a classe .magnetico (e .magnetico-fino p/ clamp 5px)
 * e gerar box (flex item/inline-block/button — transform não se aplica a
 * inline puro).
 */
export function useMagnetico<T extends HTMLElement>(
  alvoRef: RefObject<T | null>,
): void {
  const prefereReduzido = usePrefereReduzidoLocal();

  useEffect(() => {
    const el = alvoRef.current;
    if (!el || prefereReduzido) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia(QUERY_HOVER_FINO).matches) return;

    const aoEntrar = (ev: PointerEvent) => {
      if (ev.pointerType === "touch") return;
      ativarIma(el);
    };
    el.addEventListener("pointerenter", aoEntrar, { passive: true });
    return () => {
      el.removeEventListener("pointerenter", aoEntrar);
      desativarIma(el, false);
    };
  }, [alvoRef, prefereReduzido]);
}

/**
 * Ilha de delegação da LANDING (renderiza null — sem JSX, arquivo .ts):
 * UM listener de pointerover em document liga a física em QUALQUER
 * .magnetico da página (CTAs server-rendered do hero/faixa final incluídos
 * — a Onda 2 só adiciona a classe e monta <IlhaMagnetica/> uma vez).
 * Montada SÓ na landing (R2); o unmount desliga tudo e zera transforms.
 */
export function IlhaMagnetica(): null {
  const prefereReduzido = usePrefereReduzidoLocal();

  useEffect(() => {
    if (prefereReduzido) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia(QUERY_HOVER_FINO).matches) return;

    const aoEntrar = (ev: Event) => {
      const pev = ev as PointerEvent;
      if (pev.pointerType === "touch") return;
      if (!(ev.target instanceof Element)) return;
      const alvo = ev.target.closest<HTMLElement>(`.${CLASSE_ALVO}`);
      if (!alvo) return;
      ativarIma(alvo);
    };

    document.addEventListener("pointerover", aoEntrar, { passive: true });
    return () => {
      document.removeEventListener("pointerover", aoEntrar);
      desativarTodos();
    };
  }, [prefereReduzido]);

  return null;
}
