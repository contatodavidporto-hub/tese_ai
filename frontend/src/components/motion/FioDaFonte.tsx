"use client";

/**
 * FioDaFonte — fio de tinta SVG da prova viva (Onda 1B, missão MATÉRIA VIVA).
 * Plano: .maestro/plano-imersivo.md §3 crit.6 + emenda R12e (LEI).
 * Folha CSS irmã (estáticos + reduce): src/styles/cinema/secoes.css.
 *
 * O QUE É: um SVG puramente decorativo (aria-hidden) que liga o sobrescrito
 * [n] da prova viva ao chip de fonte com um fio contínuo — a rastreabilidade
 * (o argumento do produto) virando coreografia. Só PROGRESSO DE DESENHO:
 * "números voando"/count-up seguem PROIBIDOS por lei da missão.
 *
 * DECISÃO DE INTEGRAÇÃO (contrato com CenaScrub, documentada nos dois
 * lados): o desenho é INTEGRADO NA TIMELINE da seção — o CenaScrub da prova
 * viva encontra o <path data-fio-path pathLength=1> e tweena
 * strokeDashoffset 1→0 (scrub 0.6) do meio da entrada ao fim do platô.
 * A alternativa (CSS var de progresso escrita por quadro na folha do path)
 * foi descartada: teria dois mecanismos para o mesmo progresso e uma
 * escrita extra de propriedade por quadro. Um escritor por propriedade:
 * o GSAP é o único dono dinâmico de stroke-dashoffset; esta ilha só escreve
 * GEOMETRIA (atributos d/viewBox — não é estilo; CSP intacta).
 *
 * CONTRATO DE MONTAGEM (Onda 2):
 *   <div className="relative ..."> (container da seção, position:relative)
 *     <FioDaFonte />            ← PRIMEIRO filho (pinta sob o conteúdo)
 *     ... conteúdo com as âncoras ...
 *   </div>
 *   - âncoras: por padrão o fio sai de [data-fio-de] (o sup [n]) e chega em
 *     [data-fio-ate] (o chip/linha de fonte) — a Onda 2 marca os dois
 *     elementos com esses atributos (ou passa seletores próprios via props
 *     `de`/`ate`, resolvidos DENTRO do container pai);
 *   - o componente precisa estar DENTRO da <section data-cena> envolvida
 *     pelo CenaScrub (é a timeline dela que desenha o fio);
 *   - o pai imediato PRECISA ser position:relative (o SVG é absolute
 *     inset-0 e as medidas são relativas a ele).
 *
 * R12e (LEI): NUNCA medir com getBoundingClientRect global durante tween —
 * aqui não há gBCR NENHUM: as âncoras são medidas por acumulação de
 * offsetLeft/offsetTop até o pai (coordenadas de LAYOUT, imunes a transform
 * — o scrub do CenaScrub translada a seção sem invalidar a medida), 1x no
 * mount + document.fonts.ready + ResizeObserver do pai (rAF-coalescido).
 *
 * FALLBACKS (estado digno em cada degrau):
 *   - sem JS: SSR emite o SVG sem `d` — nada é desenhado, nada é oculto
 *     (decorativo por construção);
 *   - com JS sem gsap (falha de chunk): o fio fica recolhido
 *     (stroke-dashoffset:1 via folha, só sob no-preference) — decorativo,
 *     nenhum conteúdo depende dele;
 *   - reduced-motion: bloco reduce de cinema/secoes.css força
 *     stroke-dashoffset:0 !important — fio COMPLETO, estático (o traço da
 *     auditoria não some; ele só deixa de ser coreografado).
 *
 * COR: var(--accent-confianca) (safira — papel "trilha de auditoria" do
 * DESIGN-TOKENS.md), keyline ≤2px = micro-área; hue ~215°, fora da faixa
 * proibida 70–200°; decorativo, isento de AA.
 */

import { useEffect, useRef } from "react";

type PropsFioDaFonte = {
  /** Seletor da âncora de ORIGEM (o sup [n]), resolvido no pai do SVG. */
  de?: string;
  /** Seletor da âncora de DESTINO (o chip de fonte), resolvido no pai. */
  ate?: string;
  className?: string;
};

/** Arredonda para 0.1px — mantém o atributo `d` curto e estável. */
function arred(n: number): number {
  return Math.round(n * 10) / 10;
}

export function FioDaFonte({
  de = "[data-fio-de]",
  ate = "[data-fio-ate]",
  className,
}: PropsFioDaFonte) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const pai = svg.parentElement;
    const trilho = svg.querySelector<SVGPathElement>("[data-fio-path]");
    if (!pai || !trilho) return;

    let vivo = true;
    let agendado = false;
    let idQuadro = 0;

    // Posição de LAYOUT do elemento relativa ao pai (acumula a cadeia de
    // offsetParent) — imune a transform (R12e). Devolve null se a cadeia
    // não passa pelo pai (ex.: pai sem position:relative — contrato violado;
    // o fio simplesmente não desenha, sem quebrar nada).
    const posLocal = (el: HTMLElement): { x: number; y: number } | null => {
      let x = 0;
      let y = 0;
      let atual: HTMLElement | null = el;
      while (atual && atual !== pai) {
        x += atual.offsetLeft;
        y += atual.offsetTop;
        atual =
          atual.offsetParent instanceof HTMLElement ? atual.offsetParent : null;
      }
      return atual === pai ? { x, y } : null;
    };

    const medir = () => {
      agendado = false;
      if (!vivo) return;
      const origem = pai.querySelector<HTMLElement>(de);
      const destino = pai.querySelector<HTMLElement>(ate);
      const largura = pai.clientWidth;
      const altura = pai.clientHeight;
      if (!origem || !destino || largura === 0 || altura === 0) {
        trilho.removeAttribute("d");
        return;
      }
      const pOrigem = posLocal(origem);
      const pDestino = posLocal(destino);
      if (!pOrigem || !pDestino) {
        trilho.removeAttribute("d");
        return;
      }
      // Sai do centro-base do [n]; chega no topo do chip, perto da borda
      // esquerda (onde mora o fio duplo de citação) — teto de 28px de recuo.
      const x1 = arred(pOrigem.x + origem.offsetWidth / 2);
      const y1 = arred(pOrigem.y + origem.offsetHeight);
      const x2 = arred(pDestino.x + Math.min(destino.offsetWidth / 2, 28));
      const y2 = arred(pDestino.y);
      const dy = y2 - y1;
      // Curva cúbica com barriga suave de tinta (funciona subindo/descendo).
      const d = `M ${x1} ${y1} C ${x1} ${arred(y1 + dy * 0.45)}, ${x2} ${arred(
        y2 - dy * 0.3,
      )}, ${x2} ${y2}`;
      // viewBox 1:1 com o box do pai → unidades do path = px CSS (o
      // stroke-width da folha vale literalmente). Atributos de GEOMETRIA,
      // não de estilo — fora do escopo de style-src.
      svg.setAttribute("viewBox", `0 0 ${largura} ${altura}`);
      trilho.setAttribute("d", d);
    };

    const agendarMedida = () => {
      if (!vivo || agendado) return;
      agendado = true;
      idQuadro = window.requestAnimationFrame(medir);
    };

    agendarMedida();
    // Fontes (Newsreader/Archivo/Plex) trocam métricas → âncoras mudam.
    void document.fonts.ready.then(agendarMedida);
    // Recalcula SÓ em resize/reflow do container (R12e) — nunca por scroll.
    const ro = new ResizeObserver(agendarMedida);
    ro.observe(pai);

    return () => {
      vivo = false;
      ro.disconnect();
      window.cancelAnimationFrame(idQuadro);
    };
  }, [de, ate]);

  return (
    <svg
      ref={svgRef}
      aria-hidden="true"
      focusable="false"
      className={className ? `fio-da-fonte ${className}` : "fio-da-fonte"}
    >
      {/* pathLength=1 normaliza o comprimento: dasharray/dashoffset operam
          em 0–1 para QUALQUER geometria (mesmo truque da dataviz). */}
      <path data-fio-path="" pathLength={1} />
    </svg>
  );
}
