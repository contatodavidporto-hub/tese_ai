"use client";

/**
 * CenaScrub — motor de cena da landing (Onda 1B, missão MATÉRIA VIVA).
 * Plano: .maestro/plano-imersivo.md §3 crit.2 + emendas R1/R5/R12g (LEI).
 * Folha CSS irmã (estáticos + reduce): src/styles/cinema/secoes.css.
 *
 * O QUE FAZ: envolve UMA seção da landing (a <section class="capitulo"
 * data-cena="..."> marcada pela Onda 2) e monta 1 timeline GSAP
 * ScrollTrigger com scrub 0.6 e 3 atos — estado = função do scroll: descer
 * imprime, subir desimprime, repetir repete.
 *
 *   ato 1 · entrada (0–35%):  [data-cena-el] escalonados, y 16px→0 +
 *                             opacity 0→1 (stagger por amount).
 *   ato 2 · platô  (35–75%):  nada muda (leitura).
 *   ato 3 · saída  (75–100%): y→−12px, opacity→PISO 0.55 — nunca abaixo
 *                             (conteúdo permanece legível p/ Tab/âncora).
 *
 * A saída SÓ atua na borda superior do viewport: com o trigger em
 * `start: "top 85%" / end: "bottom 15%"`, o trecho 75–100% do progresso
 * corresponde à seção atravessando a borda de cima (verificado para
 * h≈0.4vh–2vh). Elementos [data-cvm] (faixa CVM / aviso regulatório):
 * opacity TRAVADA em 1 — recebem só translateY, nos dois atos.
 *
 * CONTRATO DE MARCAÇÃO (Onda 2):
 *   <CenaScrub><section className="capitulo ..." data-cena="prova"> ...
 *   </section></CenaScrub>
 *   - alvos internos: atributo data-cena-el (o elemento inteiro entra no
 *     escalonamento; sem data-cena-el nenhum conteúdo é tweenado);
 *   - faixa CVM: data-cvm no próprio elemento OU num ancestral do alvo;
 *   - fio da fonte: se a seção contém um <FioDaFonte/> (path
 *     [data-fio-path]), o desenho (strokeDashoffset 1→0) é integrado NESTA
 *     timeline, do meio da entrada ao fim do platô (decisão documentada em
 *     FioDaFonte.tsx: integração na timeline, não CSS var por quadro).
 *
 * R1 (LEI): NENHUM tween de transform em ancestral de elemento pinado — a
 * seção do FILMSTRIP (dimensões) fica FORA do CenaScrub; para casos
 * residuais existe a prop `excluir` (seletor): elementos que casam com ela,
 * seus descendentes E seus ancestrais marcados são removidos dos alvos.
 *
 * UM ESCRITOR POR PROPRIEDADE: elemento com [data-cena-el] NÃO pode ter
 * .reveal/.citacao-pin (transition de transform/opacity do motor Reveal
 * brigaria com o estilo inline do GSAP) — a Onda 2 remove essas classes dos
 * elementos migrados (diff explícito; grep de auditoria na Onda 3).
 *
 * LCP/SSR: o componente renderiza os filhos SEMPRE (RSC children intactos;
 * o wrapper é display:contents — zero box, zero stacking context, trava C2
 * preservada por construção). SSR NUNCA emite opacity:0 — estados iniciais
 * são escritos SÓ no cliente (fromTo dentro de gsap.matchMedia pós-load).
 * O hero NÃO usa CenaScrub (fica acima da dobra, Onda 2).
 *
 * R5 (LEI): gsap chega SÓ via carregarGsap() (import() dinâmico), disparado
 * no primeiro idle OU primeiro sinal de scroll-intent — nunca no caminho
 * crítico da hidratação. DECISÃO 1B: useGSAP (@gsap/react) NÃO é usado —
 * o pacote faz `import gsap from "gsap"` ESTÁTICO, o que puxaria o gsap
 * para o chunk da página (violaria R5). O contrato de cleanup do useGSAP é
 * replicado aqui: gsap.matchMedia().revert() no unmount + flag de
 * cancelamento (StrictMode-safe: o 1º ciclo efeito/cleanup do React 19 dev
 * aborta o load pendente antes de criar qualquer trigger).
 *
 * REDUCED MOTION: triggers só nascem dentro de gsap.matchMedia(MQ_SEM_REDUCE)
 * — sob reduce NENHUM trigger é criado e nenhum estado inicial é escrito
 * (se reduce está ativo no primeiro sinal, o gsap nem é baixado; se o
 * usuário desligar reduce depois, o listener de mudança baixa e monta).
 * O bloco reduce de cinema/secoes.css é o cinto-e-suspensório (!important
 * vence o estilo inline do GSAP para quem liga reduce em pleno voo).
 *
 * CSP: zero delta — GSAP escreve via CSSOM (element.style), carve-out
 * formal do DESIGN-TOKENS.md; markers:false sempre; plugin Flip proibido.
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

// ---------------------------------------------------------------------------
// Geometria dos 3 atos (frações da timeline normalizada em 1.0).
// entrada = duração 0.2 + stagger amount 0.15 → ocupa exatamente 0–0.35.
// ---------------------------------------------------------------------------
const ENTRADA_DURACAO = 0.2;
const ENTRADA_STAGGER = 0.15;
const ENTRADA_Y = 16;
const SAIDA_INICIO = 0.75;
const SAIDA_DURACAO = 0.25;
const SAIDA_Y = -12;
/** Piso de opacidade da saída (≥0.55 é LEI — conteúdo nunca fica oculto). */
const PISO_OPACIDADE = 0.55;
/** Fio da fonte: desenha do meio da entrada ao fim do platô (0.20–0.65). */
const FIO_INICIO = 0.2;
const FIO_DURACAO = 0.45;
/** Janela do trigger — mapeia o ato 3 para a borda superior do viewport. */
const TRIGGER_START = "top 85%";
const TRIGGER_END = "bottom 15%";
const SCRUB = 0.6;

type PropsCenaScrub = {
  /**
   * Seletor de exclusão (R1): elementos que casam — e qualquer alvo que os
   * contenha ou esteja contido neles — NÃO recebem tween algum. Válvula de
   * segurança para conteúdo pinado; a seção do filmstrip inteira fica FORA
   * do CenaScrub por contrato (não confiar só nesta prop).
   */
  excluir?: string;
  children: ReactNode;
};

/**
 * Dispara `acao` UMA única vez no primeiro idle do navegador OU no primeiro
 * sinal de intenção de scroll (o que vier antes). requestIdleCallback com
 * fallback setTimeout (R12b — Safari não tem rIC). Retorna cleanup.
 */
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

/**
 * Chama `acao` imediatamente se o usuário NÃO pediu movimento reduzido;
 * caso contrário, espera o reduce ser DESLIGADO (perf: sob reduce o chunk
 * do gsap nem é baixado). Retorna cleanup do listener.
 */
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

export function CenaScrub({ excluir, children }: PropsCenaScrub) {
  const escopoRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const escopo = escopoRef.current;
    if (!escopo) return;
    // A seção-alvo é a [data-cena] marcada pela Onda 2 dentro do wrapper.
    const secao = escopo.querySelector<HTMLElement>("[data-cena]");
    if (!secao) return;

    let cancelado = false;
    let mm: MatchMediaGsap | null = null;

    const montar = (motor: MotorGsap) => {
      if (cancelado) return;
      const { gsap } = motor;
      mm = gsap.matchMedia();
      // Sob reduce este bloco nunca roda; se reduce ligar DEPOIS, o próprio
      // matchMedia reverte triggers e estilos inline automaticamente.
      mm.add(MQ_SEM_REDUCE, () => {
        const todos = Array.from(
          secao.querySelectorAll<HTMLElement>("[data-cena-el]"),
        );
        const excluidos = excluir
          ? Array.from(secao.querySelectorAll<HTMLElement>(excluir))
          : [];
        // R1: fora do jogo tanto o excluído/descendentes quanto qualquer
        // alvo que seja ANCESTRAL de um excluído (tween de transform num
        // ancestral de elemento pinado é proibido).
        const alvos = todos.filter(
          (el) => !excluidos.some((ex) => ex === el || ex.contains(el) || el.contains(ex)),
        );
        const alvosLivres = alvos.filter((el) => el.closest("[data-cvm]") === null);
        const alvosCvm = alvos.filter((el) => el.closest("[data-cvm]") !== null);
        const fio = secao.querySelector<SVGPathElement>("[data-fio-path]");
        if (alvosLivres.length === 0 && alvosCvm.length === 0 && !fio) return;

        // Scrub honesto: ease "none" nos tweens — a inércia percebida vem
        // do scrub 0.6 (assinatura física da casa), não de curva de tempo.
        const tl = gsap.timeline({
          defaults: { ease: "none" },
          scrollTrigger: {
            trigger: secao,
            start: TRIGGER_START,
            end: TRIGGER_END,
            scrub: SCRUB,
            markers: false,
          },
        });

        // fromTo com valores EXPLÍCITOS (nunca from puro): estados iniciais
        // nascem SÓ aqui, no cliente — SSR jamais emite conteúdo oculto.
        if (alvosLivres.length > 0) {
          tl.fromTo(
            alvosLivres,
            { y: ENTRADA_Y, opacity: 0 },
            {
              y: 0,
              opacity: 1,
              duration: ENTRADA_DURACAO,
              stagger: { amount: ENTRADA_STAGGER },
            },
            0,
          );
          tl.to(
            alvosLivres,
            { y: SAIDA_Y, opacity: PISO_OPACIDADE, duration: SAIDA_DURACAO },
            SAIDA_INICIO,
          );
        }
        // Faixa CVM: opacity travada em 1 — só translateY (LEI).
        if (alvosCvm.length > 0) {
          tl.fromTo(
            alvosCvm,
            { y: ENTRADA_Y },
            { y: 0, duration: ENTRADA_DURACAO, stagger: { amount: ENTRADA_STAGGER } },
            0,
          );
          tl.to(alvosCvm, { y: SAIDA_Y, duration: SAIDA_DURACAO }, SAIDA_INICIO);
        }
        // Fio da fonte: só progresso de desenho (rastreabilidade como
        // coreografia) — "números voando"/count-up seguem PROIBIDOS.
        if (fio) {
          tl.fromTo(
            fio,
            { strokeDashoffset: 1 },
            { strokeDashoffset: 0, duration: FIO_DURACAO },
            FIO_INICIO,
          );
        }
        // Marcador vazio em t=1: garante duração total 1.0 mesmo quando só
        // existe o fio (mantém o mapa dos 3 atos estável no range do trigger).
        tl.set(secao, {}, 1);
        // cleanup automático: mm.revert() desfaz triggers + estilos inline.
      });
    };

    let limparReduce: () => void = () => {};
    const limparSinal = aoPrimeiroSinal(() => {
      limparReduce = quandoPermitirMovimento(() => {
        carregarGsap()
          .then(montar)
          .catch(() => {
            // Falha de rede no chunk: página segue íntegra sem scrub
            // (fallback = experiência aprovada em produção). O loader
            // memoizado limpa a promise; outra instância pode tentar de novo.
          });
      });
    });

    return () => {
      cancelado = true;
      limparSinal();
      limparReduce();
      mm?.revert();
    };
  }, [excluir]);

  // display:contents (cinema/secoes.css): o wrapper não gera box — a
  // <section> continua filha direta do <main> para layout/estilos, e o
  // wrapper não pode virar containing block nem stacking context (C2).
  return (
    <div ref={escopoRef} className="cena-escopo">
      {children}
    </div>
  );
}
