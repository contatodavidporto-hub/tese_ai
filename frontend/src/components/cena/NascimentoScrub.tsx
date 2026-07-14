"use client";

/**
 * NascimentoScrub — ilha client (~1.5KB) que dá vida à cena do nascimento
 * (D15, §5c da direção). Monta UMA timeline GSAP `scrub: 0.8` amarrada ao
 * `.nascimento-rolo` (240svh) — o `.nascimento-cena` já é `position:
 * sticky` puro (CSS, `cinema/lapidacao.css`); esta ilha NUNCA usa
 * `pin:true` (diferente do Salão — sem GSAP pin não há pinSpacing, não há
 * `vw`, não há a armadilha E1/E3 da barra de rolagem do Windows).
 *
 * `fromTo` POR CIMA dos defaults (D16, LEI): `cinema/lapidacao.css` já
 * declara todo `[data-plano]` visível/assentado — os `fromTo` abaixo só
 * escrevem o estado ESCONDIDO/inicial no CLIENTE, depois de montar (nunca
 * no SSR). Path-morph PROIBIDO: nenhum tween toca o atributo `d` — as
 * facetas são "camadas de opacity" (D18), só `transform`/`opacity`/
 * `stroke-dashoffset` (compositor).
 *
 * REDUCED MOTION: `gsap.matchMedia(MQ_SEM_REDUCE)` — sob reduce a timeline
 * NEM NASCE (nenhum estado inicial é escrito; o diagrama fica no default
 * completo de `lapidacao.css`, e o próprio rig deixa de fazer scroll-jack —
 * ver o bloco reduce da folha). Padrão idêntico a `CenaScrub.tsx`
 * (`aoPrimeiroSinal`/`quandoPermitirMovimento`), duplicado aqui DE
 * PROPÓSITO: `CenaScrub.tsx` não exporta essas funções (são internas ao
 * arquivo, fora da posse desta raia) — duplicar ~30 linhas de utilitário
 * puro é mais seguro do que criar uma dependência cross-raia num arquivo
 * que não é meu.
 *
 * CSP: gsap chega SÓ via `carregarGsap()` (import() dinâmico, R5); zero
 * `style={}`, zero `setAttribute('style')`, zero markers/Flip.
 */

import { useEffect, useRef, type ReactNode } from "react";

import {
  carregarGsap,
  ehReduce,
  MQ_REDUCE,
  MQ_SEM_REDUCE,
  type MotorGsap,
} from "@/lib/gsapSetup";

type MatchMediaGsap = ReturnType<MotorGsap["gsap"]["matchMedia"]>;

const SCRUB = 0.8;

/** Idêntico ao helper de CenaScrub.tsx — duplicado por posse de arquivo (ver doc acima). */
function aoPrimeiroSinal(acao: () => void): () => void {
  const eventos = ["scroll", "wheel", "touchstart", "pointerdown"] as const;
  let disparado = false;
  let idIdle = 0;
  let idTimeout: number | undefined;

  const limpar = () => {
    for (const nome of eventos) window.removeEventListener(nome, disparar);
    if (typeof window.cancelIdleCallback === "function") {
      window.cancelIdleCallback(idIdle);
    }
    if (idTimeout !== undefined) window.clearTimeout(idTimeout);
  };

  function disparar(): void {
    if (disparado) return;
    disparado = true;
    limpar();
    acao();
  }

  for (const nome of eventos) {
    window.addEventListener(nome, disparar, { passive: true, once: true });
  }
  if (typeof window.requestIdleCallback === "function") {
    idIdle = window.requestIdleCallback(disparar, { timeout: 1600 });
  } else {
    idTimeout = window.setTimeout(disparar, 1200);
  }
  return limpar;
}

/** Idêntico ao helper de CenaScrub.tsx — duplicado por posse de arquivo (ver doc acima). */
function quandoPermitirMovimento(acao: () => void): () => void {
  if (!ehReduce()) {
    acao();
    return () => {};
  }
  const mql = window.matchMedia(MQ_REDUCE);
  const aoMudar = () => {
    if (mql.matches) return;
    mql.removeEventListener("change", aoMudar);
    acao();
  };
  mql.addEventListener("change", aoMudar);
  return () => mql.removeEventListener("change", aoMudar);
}

type PropsNascimentoScrub = {
  /**
   * Contrato de montagem (mesmo padrão de CenaScrub.tsx): envolver o
   * markup do rig inteiro —
   *   <NascimentoScrub>
   *     <section id="nascimento" className="nascimento-rolo b-sangria">
   *       <div className="nascimento-cena">
   *         <CenaNascimento />
   *       </div>
   *     </section>
   *   </NascimentoScrub>
   * O wrapper é `display: contents` (cinema/lapidacao.css) — zero box,
   * zero stacking context (C2); a `<section>` continua filha direta de
   * `<main>` para R1 (fora do CenaScrub) e para o cálculo de sticky.
   */
  children: ReactNode;
};

export function NascimentoScrub({ children }: PropsNascimentoScrub) {
  const escopoRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const escopo = escopoRef.current;
    if (!escopo) return;
    const rolo = escopo.querySelector<HTMLElement>(".nascimento-rolo");
    const cena = escopo.querySelector<HTMLElement>(".nascimento-cena");
    if (!rolo || !cena) return;

    let cancelado = false;
    let mm: MatchMediaGsap | null = null;

    const montar = (motor: MotorGsap) => {
      if (cancelado) return;
      const { gsap } = motor;
      mm = gsap.matchMedia();

      mm.add(MQ_SEM_REDUCE, () => {
        const selos = Array.from(
          escopo.querySelectorAll<SVGGElement>('[data-plano="1"] .nascimento-selo'),
        );
        const linhaExtracao = escopo.querySelector<SVGPathElement>(
          ".nascimento-linha-extracao",
        );
        const pedra = escopo.querySelector<SVGPathElement>(".nascimento-pedra-bruta");
        const dadoTexto = escopo.querySelector<SVGTextElement>(
          '[data-plano="2"] .nascimento-dado',
        );
        const facetas = Array.from(
          escopo.querySelectorAll<SVGGElement>(".nascimento-faceta"),
        );
        const aro = escopo.querySelector<SVGCircleElement>(".nascimento-aro");
        const gateTextos = Array.from(
          escopo.querySelectorAll<SVGTextElement>('[data-plano="4"] .nascimento-legenda-mono'),
        );
        const bandeja = escopo.querySelector<SVGGElement>(".nascimento-bandeja");
        const puncao = escopo.querySelector<SVGRectElement>(".nascimento-puncao");
        const citacaoTexto = escopo.querySelector<SVGTextElement>(".nascimento-citacao");
        const miniChip = escopo.querySelector<SVGGElement>(".nascimento-mini-chip");
        const gemaFinal = escopo.querySelector<SVGCircleElement>(".nascimento-gema-final");
        const fioSaida = escopo.querySelector<SVGPathElement>("[data-fio-saida]");

        // Scrub honesto (mesma assinatura física do CenaScrub): ease "none"
        // nos tweens — a inércia percebida vem do `scrub`, não da curva.
        const tl = gsap.timeline({
          defaults: { ease: "none" },
          scrollTrigger: {
            trigger: rolo,
            start: "top top",
            // Distância exata em que a cena permanece "grudada" sob a
            // Tarja: altura do rolo menos altura da cena sticky.
            end: () => "+=" + Math.max(rolo.offsetHeight - cena.offsetHeight, 1),
            scrub: SCRUB,
            invalidateOnRefresh: true,
            markers: false,
          },
        });

        // ---- Plano 1 · a mina (0–10%) ----
        if (selos.length > 0) {
          tl.fromTo(
            selos,
            { opacity: 0, scale: 1.15, transformOrigin: "center" },
            { opacity: 1, scale: 1, duration: 0.08, stagger: 0.015 },
            0,
          );
        }
        if (linhaExtracao) {
          tl.fromTo(linhaExtracao, { opacity: 0 }, { opacity: 1, duration: 0.06 }, 0.04);
        }

        // ---- Plano 2 · extração (10–25%) ----
        if (pedra && dadoTexto) {
          tl.fromTo(
            [pedra, dadoTexto],
            { x: -36, opacity: 0 },
            { x: 0, opacity: 1, duration: 0.15 },
            0.1,
          );
        }

        // ---- Plano 3 · lapidação (25–48%) ----
        if (facetas.length > 0) {
          tl.fromTo(
            facetas,
            { opacity: 0, scale: 0.55, transformOrigin: "center" },
            { opacity: 1, scale: 1, duration: 0.2, stagger: 0.025 },
            0.25,
          );
        }

        // ---- Plano 4 · o gate (50–68%) ----
        if (aro) {
          tl.fromTo(
            aro,
            { opacity: 0, scale: 0.5, transformOrigin: "center" },
            { opacity: 1, scale: 1, duration: 0.08 },
            0.5,
          );
        }
        if (gateTextos.length > 0) {
          tl.fromTo(
            gateTextos,
            { opacity: 0 },
            { opacity: 1, duration: 0.08, stagger: 0.03 },
            0.56,
          );
        }
        if (bandeja) {
          tl.fromTo(bandeja, { x: 24, opacity: 0 }, { x: 0, opacity: 1, duration: 0.12 }, 0.56);
        }

        // ---- Plano 5 · o carimbo (70–84%) ----
        if (puncao) {
          tl.fromTo(puncao, { y: -28, opacity: 0 }, { y: 0, opacity: 1, duration: 0.08 }, 0.7);
        }
        if (citacaoTexto) {
          tl.fromTo(citacaoTexto, { opacity: 0 }, { opacity: 1, duration: 0.08 }, 0.76);
        }

        // ---- Plano 6 · o engaste (85–100%) ----
        if (miniChip && gemaFinal) {
          tl.fromTo(
            [miniChip, gemaFinal],
            { y: 18, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.1 },
            0.85,
          );
        }
        if (fioSaida) {
          tl.fromTo(
            fioSaida,
            { strokeDashoffset: 1 },
            { strokeDashoffset: 0, duration: 0.08 },
            0.92,
          );
        }

        // Marcador vazio em t=1: mantém a duração total 1.0 mesmo que o
        // último tween termine antes (mesmo padrão de CenaScrub).
        tl.set(rolo, {}, 1);
      });
    };

    let limparReduce: () => void = () => {};
    const limparSinal = aoPrimeiroSinal(() => {
      limparReduce = quandoPermitirMovimento(() => {
        carregarGsap()
          .then(montar)
          .catch(() => {
            // Falha de rede no chunk: a cena fica no estado FINAL completo
            // (D16) — degradação aceita, nada quebra.
          });
      });
    });

    return () => {
      cancelado = true;
      limparSinal();
      limparReduce();
      mm?.revert();
    };
  }, []);

  // display:contents (cinema/lapidacao.css): o wrapper não gera box — a
  // <section> continua filha direta de <main>, e o wrapper não vira
  // containing block nem stacking context (C2). Mesmo padrão de
  // CenaScrub.tsx (cena-escopo).
  return (
    <div ref={escopoRef} className="nascimento-escopo">
      {children}
    </div>
  );
}
