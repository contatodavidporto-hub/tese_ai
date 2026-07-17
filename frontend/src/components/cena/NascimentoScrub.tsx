"use client";

/**
 * NascimentoScrub — ilha client (~2KB) que dá vida à cena do nascimento
 * (ESTENDIDA a 8 planos/420svh pela missão OURIVESARIA, raia 1C —
 * §3-C3/§7-B5). Monta UMA timeline GSAP `scrub: 0.8` amarrada ao
 * `.nascimento-rolo` (420svh) — o `.nascimento-cena` já é `position:
 * sticky` puro (CSS, `cinema/nascimento.css`); esta ilha NUNCA usa
 * `pin:true` (sem GSAP pin não há pinSpacing, não há `vw`, não há a
 * armadilha E1/E3 da barra de rolagem do Windows).
 *
 * `fromTo` POR CIMA dos defaults (D16, LEI): as folhas declaram todo
 * `[data-plano]` visível/assentado — os `fromTo` abaixo só escrevem o
 * estado ESCONDIDO/inicial no CLIENTE, depois de montar (nunca no SSR).
 * Path-morph PROIBIDO: nenhum tween toca `d` — só `transform`/`opacity`/
 * `stroke-dashoffset` (compositor) e, nas LEGENDAS, `color`/`zIndex`.
 *
 * MAPA NORMATIVO DOS 8 PLANOS (§7-B5 — frações absolutas da timeline):
 *   p1 0–0.09 · p2 0.11–0.21 · p3 0.23–0.38 · p4 0.40–0.50 ·
 *   p5 0.52–0.62 · p6 0.64–0.74 · p7 0.76–0.86 · p8 0.88–0.98
 *   (+ tl.set final em t=1 para o último beat não espichar).
 *
 * LEGENDAS (E-A3/§7-B3): o GSAP é o dono ÚNICO de `color` dos <li>
 * (ativa = valor de --ink-primary, irmãs = valor de --ink-tertiary —
 * "anima para o VALOR do token", par 7,11:1 provado no protótipo 0.3;
 * opacity NUNCA é animada) e de `zIndex` (a legenda da vez sobe ao topo
 * da caixa empilhada; z cresce monotônico 1..8, então o scrub reverso
 * restaura a anterior por natureza). A classe `.nascimento-cena--viva`
 * (classList — canal permitido, precedente `.bolha-ativa`) liga a
 * apresentação de scrub da folha; sem JS/sob reduce ela nunca nasce e o
 * default (8 legendas plenas em fluxo) fica de pé.
 *
 * ATMOSFERA (E-A4): `--nasc-lume` 0.35→1 escrita no onUpdate COALESCIDO
 * (só quando o valor muda — precedente exato do `--ilum` do Salão;
 * CSSOM `setProperty`, carve-out formal). Default CSS = 1 (sala acesa).
 *
 * REDUCED MOTION: `gsap.matchMedia(MQ_SEM_REDUCE)` — sob reduce a
 * timeline NEM NASCE (nenhum estado inicial é escrito; nem o chunk do
 * gsap desce — `quandoPermitirMovimento`); o cleanup do contexto remove
 * a classe e a var se o usuário ligar reduce ao vivo.
 *
 * BOOT: IO one-shot com rootMargin 100% (padrão do Salão) — a timeline
 * nasce UMA viewport antes da cena; o load não paga nada (lei das ilhas:
 * este componente RECEBE o SVG server-rendered como children).
 *
 * CSP: gsap chega SÓ via `carregarGsap()` (import() dinâmico, R5); zero
 * `style={}`, zero `setAttribute('style')`, zero markers/Flip; escrita
 * de estilo só por CSSOM (GSAP + setProperty da var — carve-out).
 */

import { useEffect, useRef, type ReactNode } from "react";

import {
  carregarGsap,
  ehReduce,
  MQ_REDUCE,
  MQ_SEM_REDUCE,
  type MotorGsap,
} from "@/lib/gsapSetup";

import "@/styles/cinema/nascimento.css";

type MatchMediaGsap = ReturnType<MotorGsap["gsap"]["matchMedia"]>;

const SCRUB = 0.8;

/** §7-B5: início de cada plano 2..8 — transição de legenda + beat novo. */
const INICIOS_PLANOS = [0.11, 0.23, 0.4, 0.52, 0.64, 0.76, 0.88] as const;

/**
 * PERF — B2 (2026-07-14): BOOT POR PROXIMIDADE, NÃO POR OCIOSIDADE.
 * IO one-shot com `rootMargin: 100%` (padrão do Salão) — a timeline
 * nasce UMA viewport ANTES da cena aparecer; o load não paga o gsap
 * (histórico: por idle o conjunto virava longtask de ~104ms de TBT).
 */
function aoChegarPerto(alvo: Element, acao: () => void): () => void {
  const io = new IntersectionObserver(
    (entradas) => {
      if (!entradas.some((e) => e.isIntersecting)) return;
      io.disconnect();
      acao();
    },
    // uma viewport de antecedência (acima e abaixo) — mesma folga do Salão
    { rootMargin: "100% 0px 100% 0px" },
  );
  io.observe(alvo);
  return () => io.disconnect();
}

/** Idêntico ao helper de CenaScrub.tsx — duplicado por posse de arquivo. */
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
   *         <CenaNascimento legendasVisiveis />
   *         <div aria-hidden className="nascimento-poeira" />
   *       </div>
   *     </section>
   *   </NascimentoScrub>
   * O wrapper é `display: contents` (cinema/nascimento.css) — zero box,
   * zero stacking context (C2); a `<section>` continua filha direta de
   * `<main>` para R1 (fora do CenaScrub) e para o cálculo de sticky.
   * O rolo tem UM único filho (a cena); a cena tem a figura e o <ol>
   * de legendas como filhos DE FLUXO (h3 sr-only e poeira são absolute).
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
        // A apresentação de scrub da folha (block-size exato + caixa única
        // de legendas) só existe com a timeline viva — classList, canal
        // permitido. ANTES de medir: o `end` depende da altura travada.
        cena.classList.add("nascimento-cena--viva");

        // §7-B3: "anima para o VALOR de --ink-tertiary" — tokens resolvidos
        // no escopo da cena (por tema); o GSAP vira o dono único de color.
        const paleta = getComputedStyle(cena);
        const tintaAtiva = paleta.getPropertyValue("--ink-primary").trim();
        const tintaIrma = paleta.getPropertyValue("--ink-tertiary").trim();
        const legendas = Array.from(
          escopo.querySelectorAll<HTMLLIElement>(".nascimento-legendas > li"),
        );

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
        const trilha = escopo.querySelector<SVGPathElement>("[data-trilha]");
        const trilhaMarcas = Array.from(
          escopo.querySelectorAll<SVGElement>(
            ".nascimento-trilha-ponto, .nascimento-trilha-seta",
          ),
        );
        const fioSaida = escopo.querySelector<SVGPathElement>("[data-fio-saida]");

        // E-A4: lume 0.35→1 em função do progresso, escrita COALESCIDA
        // (só quando muda — precedente --ilum; 2 casas ≈ passos de 1%).
        let lumeAnterior = -1;
        const escreverLume = (p: number) => {
          const v = Number((0.35 + 0.65 * p).toFixed(2));
          if (v === lumeAnterior) return;
          lumeAnterior = v;
          cena.style.setProperty("--nasc-lume", String(v));
        };

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
            onUpdate: (auto) => escreverLume(auto.progress),
          },
        });

        // Estado de engate das legendas: a 1ª é a da vez (cor default
        // ink-primary + topo da pilha), irmãs esmaecem para o valor de
        // ink-tertiary — cor, NUNCA opacity (§7-B3).
        if (legendas.length > 0) {
          gsap.set(legendas.slice(1), { color: tintaIrma });
          gsap.set(legendas[0], { zIndex: 1 });
        }
        // Transição de legenda no INÍCIO de cada plano 2..8: a que entra
        // sobe (z monotônico) e escurece; a que sai esmaece. Reverso do
        // scrub desfaz na ordem certa por construção.
        INICIOS_PLANOS.forEach((pos, i) => {
          const anterior = legendas[i];
          const proxima = legendas[i + 1];
          if (!anterior || !proxima) return;
          tl.set(proxima, { zIndex: i + 2 }, pos);
          tl.to(proxima, { color: tintaAtiva, duration: 0.03 }, pos);
          tl.to(anterior, { color: tintaIrma, duration: 0.03 }, pos);
        });

        // ---- Plano 1 · as fontes (0–0.09) ----
        // STAGGER POR LAÇO de fromTo single-target (correção da 1C): o
        // `stagger` do gsap NÃO aplica o `from` dos sub-tweens 2..N na
        // criação (nem com immediateRender explícito — medido nesta
        // raia; quirk latente no obase: facetas 2..5 visíveis no
        // engate). Com 40svh/plano o pop ficaria visível; fromTo de alvo
        // único immediateRender-a de verdade (provado pelo aro).
        selos.forEach((selo, i) => {
          tl.fromTo(
            selo,
            { opacity: 0, scale: 1.15, transformOrigin: "center" },
            { opacity: 1, scale: 1, duration: 0.05 },
            i * 0.008,
          );
        });
        if (linhaExtracao) {
          tl.fromTo(linhaExtracao, { opacity: 0 }, { opacity: 1, duration: 0.04 }, 0.05);
        }

        // ---- Plano 2 · extração (0.11–0.21) ----
        if (pedra && dadoTexto) {
          tl.fromTo(
            [pedra, dadoTexto],
            { x: -36, opacity: 0 },
            { x: 0, opacity: 1, duration: 0.1 },
            0.11,
          );
        }

        // ---- Plano 3 · lapidação (0.23–0.38) ----
        facetas.forEach((faceta, i) => {
          tl.fromTo(
            faceta,
            { opacity: 0, scale: 0.55, transformOrigin: "center" },
            { opacity: 1, scale: 1, duration: 0.1 },
            0.23 + i * 0.0125,
          );
        });

        // ---- Plano 4 · a conferência (0.40–0.50) ----
        if (aro) {
          tl.fromTo(
            aro,
            { opacity: 0, scale: 0.5, transformOrigin: "center" },
            { opacity: 1, scale: 1, duration: 0.05 },
            0.4,
          );
        }
        gateTextos.forEach((texto, i) => {
          tl.fromTo(texto, { opacity: 0 }, { opacity: 1, duration: 0.04 }, 0.44 + i * 0.02);
        });

        // ---- Plano 5 · a contraprova (0.52–0.62) ----
        if (bandeja) {
          tl.fromTo(bandeja, { x: 24, opacity: 0 }, { x: 0, opacity: 1, duration: 0.09 }, 0.52);
        }

        // ---- Plano 6 · o carimbo (0.64–0.74) ----
        if (puncao) {
          tl.fromTo(puncao, { y: -28, opacity: 0 }, { y: 0, opacity: 1, duration: 0.05 }, 0.64);
        }
        if (citacaoTexto) {
          tl.fromTo(citacaoTexto, { opacity: 0 }, { opacity: 1, duration: 0.04 }, 0.7);
        }

        // ---- Plano 7 · o engaste (0.76–0.86) ----
        if (miniChip && gemaFinal) {
          tl.fromTo(
            [miniChip, gemaFinal],
            { y: 18, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.08 },
            0.76,
          );
        }

        // ---- Plano 8 · a trilha (0.88–0.98) ----
        if (trilha) {
          tl.fromTo(trilha, { opacity: 0 }, { opacity: 1, duration: 0.04 }, 0.88);
        }
        trilhaMarcas.forEach((marca, i) => {
          tl.fromTo(marca, { opacity: 0 }, { opacity: 1, duration: 0.03 }, 0.9 + i * 0.012);
        });
        // O fio de saída se DESENHA de verdade (consertado na 1C:
        // stroke-dasharray:1 na folha + pathLength=1 no path — o tween
        // era inerte na Horizonte por falta do dash pattern).
        if (fioSaida) {
          tl.fromTo(
            fioSaida,
            { strokeDashoffset: 1 },
            { strokeDashoffset: 0, duration: 0.07 },
            0.91,
          );
        }

        // Marcador vazio em t=1: mantém a duração total 1.0 mesmo que o
        // último beat termine em 0.98 (§7-B5 — nada espicha).
        tl.set(rolo, {}, 1);

        // Lume coerente já no engate (o onUpdate só dispara com scroll).
        escreverLume(tl.scrollTrigger?.progress ?? 0);

        // Cleanup do contexto (reduce ligado ao vivo / unmount): o gsap
        // reverte tweens e sets; aqui morre o que é nosso — a classe de
        // apresentação e a var de lume (default CSS volta a valer: sala
        // acesa, 8 legendas plenas em fluxo).
        return () => {
          cena.classList.remove("nascimento-cena--viva");
          cena.style.removeProperty("--nasc-lume");
        };
      });
    };

    let limparReduce: () => void = () => {};
    const limparSinal = aoChegarPerto(rolo, () => {
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

  // display:contents (cinema/nascimento.css): o wrapper não gera box — a
  // <section> continua filha direta de <main>, e o wrapper não vira
  // containing block nem stacking context (C2). Mesmo padrão de
  // CenaScrub.tsx (cena-escopo).
  return (
    <div ref={escopoRef} className="nascimento-escopo">
      {children}
    </div>
  );
}
