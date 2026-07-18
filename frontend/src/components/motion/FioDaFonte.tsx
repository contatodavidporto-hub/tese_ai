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
 * viva encontra o <path data-fio-path pathLength=100> e tweena
 * strokeDashoffset 100→0 (scrub 0.6) do meio da entrada ao fim do platô.
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
 *     (stroke-dashoffset:100 via folha, só sob no-preference) — decorativo,
 *     nenhum conteúdo depende dele;
 *   - reduced-motion: bloco reduce de cinema/secoes.css força
 *     stroke-dashoffset:0 !important — fio COMPLETO, estático (o traço da
 *     auditoria não some; ele só deixa de ser coreografado).
 *
 * COR: var(--accent-confianca) (safira — papel "trilha de auditoria" do
 * DESIGN-TOKENS.md), keyline ≤2px = micro-área; hue ~215°, fora da faixa
 * proibida 70–200°; decorativo, isento de AA.
 *
 * EXTENSÃO ADITIVA (Onda 1A, missão FRONTEND HORIZONTE, 2026-07-14) —
 * waypoints `[data-fio-via]`: o palco largo da Bancada (`cinema/
 * bancada.css`) torna a distância entre o `sup [1]` e a 1ª gema muito maior
 * que a antiga coluna `max-w-5xl` — uma única curva em "S" (2 pontos)
 * esticaria fino demais ou cortaria por cima de conteúdo no meio do
 * caminho. A prop nova `via` (seletor, default `[data-fio-via]`) deixa o
 * integrador marcar pontos intermediários; o fio passa a ser uma cadeia de
 * segmentos cúbicos (mesma fórmula de "barriga suave" de cada segmento,
 * encadeados ponta a ponta) em vez de um segmento único.
 *
 * CADEIA DE SEGMENTOS: com ZERO elementos `[data-fio-via]` no pai (o caso
 * do único consumidor de hoje) a lista de pontos é exatamente
 * `[origem, destino]` e o laço de construção do `d` roda UMA iteração com
 * a fórmula de controle `y1 + dy*0.45` / `y2 - dy*0.3`.
 *
 * ORIGEM NA BORDA DO BLOCO (missão ARREMATE, raia H — V4 da regra de
 * ferro). A origem ERA o centro-BASE da própria âncora
 * (`pOrigem.y + origem.offsetHeight`). Como a âncora do único consumidor
 * é um `<sup>` — conteúdo INLINE do parágrafo (page.tsx:507) —, esse
 * ponto fica DENTRO do rect do `<p>` POR CONSTRUÇÃO, e o fio só saía do
 * parágrafo depois de correr pelo interior dele. O varredor de conectoras
 * mediu, em REPOUSO TOTAL (passada reduced-motion: opacidade 1, escala 1,
 * zero transform do GSAP), corda 48,81px e profundidade 11,91px dentro de
 * `SECTION#prova > P.TEXT-BODY`, mais `ponta_sem_folga` com folga 0,00px
 * (mínimo 2,00) — 27 ocorrências de cada. Era a MAIOR corda do site.
 *
 * O conserto é por ÂNCORA, no padrão `naBorda()` do Salão
 * (SalaoDimensoes.tsx:203-209): a origem passa a nascer na aresta
 * INFERIOR do BLOCO QUE CONTÉM a âncora, na MESMA COLUNA x da âncora,
 * deslocada de `FOLGA_BORDA`. Assim o traço já nasce FORA do parágrafo e
 * nunca percorre o interior dele — o vão que ele atravessa passa a ser o
 * corredor vazio entre o bloco de texto e a fileira de gemas (na landing,
 * a calha de GAP-Y-6 da seção). "Bloco que contém" é resolvido subindo o
 * DOM enquanto o `display` for de nível inline (ou CONTENTS): parar no
 * primeiro INLINE-BLOCK deixaria a origem dentro do parágrafo de novo,
 * que é exatamente o defeito.
 *
 * PRECONDIÇÃO de montagem (não há guarda em código — é contrato): a
 * aresta inferior do bloco da âncora tem de estar ACIMA do destino. É o
 * caso do único consumidor (o `<p>` fecha o bloco de texto; a fileira de
 * gemas vem depois, na linha seguinte do grid). Um integrador que ancore
 * ABAIXO do destino verá o fio desenhar de baixo para cima.
 *
 * UM ÚNICO CONSUMIDOR (registro honesto, 2026-07-18): o `<FioDaFonte/>`
 * de `#postura` foi DEMOLIDO no commit 94f2084 (critério 3 do dono), e
 * com ele a regra `#postura [data-fio-path]` de cinema/secoes.css. Hoje o
 * componente é montado UMA vez, em page.tsx:472 (`#prova`). Este arquivo
 * já afirmou "retrocompatibilidade byte a byte do `d`" quando ganhou os
 * waypoints — a afirmação MORREU aqui: o `d` mudou de propósito, e não há
 * segundo consumidor para quem preservá-la.
 *
 * MEDIÇÃO (R12e, mesma lei): `offsetLeft/offsetTop` acumulados até o pai
 * (nunca `getBoundingClientRect`) — imune a `transform` de um CenaScrub
 * ancestral. Convenção do ponto de conexão: origem = coluna x da âncora ×
 * aresta inferior do bloco dela + folga; waypoints = CENTRO do próprio
 * elemento (`offsetWidth/2`, `offsetHeight/2` — um waypoint é "passe por
 * aqui", não "chegue por cima" como o destino); destino = topo, recuo
 * ≤28px da borda esquerda (INTOCADO: tangenciar o topo do chip é o padrão
 * já aceito). Um waypoint fora da cadeia de `offsetParent` até o pai
 * (contrato quebrado pelo integrador) é simplesmente IGNORADO — o fio
 * ainda desenha entre os pontos válidos restantes (degradação honesta,
 * nunca uma exceção que apaga o fio inteiro).
 *
 * O QUE ESTE CONSERTO NÃO ALCANÇA (medido, não suposto): o SVG é irmão
 * dos blocos e NÃO é `[data-cena-el]`, então o GSAP do CenaScrub move as
 * CAIXAS (ENTRADA_Y +16 → 0 → SAIDA_Y −12, com stagger de 0.15 entre
 * alvos — CenaScrub.tsx:107-117) enquanto o fio, medido em coordenadas de
 * LAYOUT, fica parado. Durante a entrada e a saída as caixas varrem o
 * traço: são violações TRANSITÓRIAS, de amplitude ≤ 28px, que nenhum
 * reancoramento resolve — só um dono comum de transform resolveria, e o
 * GSAP é dono único do transform dos `[data-cena-el]` por lei.
 */

import { useEffect, useRef } from "react";

type PropsFioDaFonte = {
  /** Seletor da âncora de ORIGEM (o sup [n]), resolvido no pai do SVG. */
  de?: string;
  /** Seletor da âncora de DESTINO (o chip de fonte), resolvido no pai. */
  ate?: string;
  /**
   * Seletor dos waypoints intermediários (extensão aditiva, 2026-07-14),
   * resolvidos no pai em ORDEM DE DOCUMENTO. Ausente ou sem matches ⇒
   * comportamento idêntico ao de antes desta extensão (segmento único
   * origem→destino).
   */
  via?: string;
  className?: string;
};

/** Arredonda para 0.1px — mantém o atributo `d` curto e estável. */
function arred(n: number): number {
  return Math.round(n * 10) / 10;
}

/**
 * Arredonda para 0.1px SEMPRE PARA CIMA (para longe do bloco de origem):
 * o `arred` normal pode comer 0,05px da folga, e a folga é justamente o
 * que o gate mede.
 */
function arredCima(n: number): number {
  return Math.ceil(n * 10) / 10;
}

/**
 * Folga de nascimento na aresta do bloco da âncora — padrão `naBorda()` do
 * Salão (SalaoDimensoes.tsx:203-209, `b.r + 2`), que é o mesmo FOLGA_MIN =
 * 2.0 do varredor global (.maestro/ferramentas/gate_conectoras.py:197).
 *
 * 3 e não 2 porque a medida vem de `offsetTop`/`offsetHeight`, que os
 * navegadores devolvem ARREDONDADOS A INTEIRO, enquanto o gate compara
 * contra o rect FRACIONÁRIO do `getBoundingClientRect`: a aresta real pode
 * estar até ~1px abaixo do que a soma dos offsets indica. 3 − 1 = 2 no
 * pior caso, 3 no melhor — e 3px é imperceptível na calha entre o
 * parágrafo e a fileira de gemas.
 */
const FOLGA_BORDA = 3;

export function FioDaFonte({
  de = "[data-fio-de]",
  ate = "[data-fio-ate]",
  via = "[data-fio-via]",
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

    // BLOCO QUE CONTÉM a âncora (ARREMATE raia H — ver cabeçalho): sobe do
    // próprio elemento enquanto o `display` for de nível INLINE (o `<sup>`
    // da prova viva é INLINE dentro do `<p>`) ou CONTENTS (não gera caixa
    // nenhuma, logo não tem aresta para nascer). Para no primeiro elemento
    // que gera caixa de BLOCO e nunca ultrapassa o pai.
    // `startsWith("inline")` cobre de propósito INLINE-BLOCK, INLINE-FLEX,
    // INLINE-GRID e INLINE-TABLE: parar num deles devolveria uma aresta que
    // ainda está DENTRO do parágrafo — o defeito que este conserto mata.
    const blocoQueContem = (el: HTMLElement): HTMLElement => {
      let atual: HTMLElement = el;
      while (atual !== pai) {
        const disp = window.getComputedStyle(atual).display;
        if (!disp.startsWith("inline") && disp !== "contents") break;
        const acima = atual.parentElement;
        if (!acima) break;
        atual = acima;
      }
      return atual;
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
      // Nasce na ARESTA INFERIOR do bloco da âncora (+FOLGA_BORDA), na
      // coluna x da âncora; chega no topo do chip, perto da borda esquerda
      // (onde mora o fio duplo de citação) — teto de 28px de recuo.
      const bloco = blocoQueContem(origem);
      const pBloco = bloco === origem ? pOrigem : posLocal(bloco);
      if (!pBloco) {
        trilho.removeAttribute("d");
        return;
      }
      const pontos: Array<{ x: number; y: number }> = [
        {
          x: arred(pOrigem.x + origem.offsetWidth / 2),
          y: arredCima(pBloco.y + bloco.offsetHeight + FOLGA_BORDA),
        },
      ];
      // Waypoints (extensão aditiva): centro do próprio elemento, em ordem
      // de documento; fora da cadeia offsetParent→pai é ignorado (degrada
      // sem apagar o fio inteiro).
      if (via) {
        const viasEl = Array.from(pai.querySelectorAll<HTMLElement>(via));
        for (const elVia of viasEl) {
          const pVia = posLocal(elVia);
          if (!pVia) continue;
          pontos.push({
            x: arred(pVia.x + elVia.offsetWidth / 2),
            y: arred(pVia.y + elVia.offsetHeight / 2),
          });
        }
      }
      pontos.push({
        x: arred(pDestino.x + Math.min(destino.offsetWidth / 2, 28)),
        y: arred(pDestino.y),
      });
      if (pontos.length < 2) {
        trilho.removeAttribute("d");
        return;
      }
      // Cadeia de curvas cúbicas com barriga suave por segmento (funciona
      // subindo/descendo em qualquer trecho) — com 0 waypoints (o caso do
      // único consumidor) roda 1 iteração. As duas abscissas de controle
      // são as dos próprios extremos e as ordenadas caem em
      // `y1 + dy*0.45` e `y2 − dy*0.3`, ambas DENTRO de [y1, y2]: a curva
      // nunca escapa da faixa vertical entre os dois pontos, então a
      // origem na borda garante que o traço inteiro corre no corredor
      // vazio, e não só o seu primeiro pixel.
      let d = `M ${pontos[0].x} ${pontos[0].y}`;
      for (let i = 0; i < pontos.length - 1; i += 1) {
        const p1 = pontos[i];
        const p2 = pontos[i + 1];
        const dy = p2.y - p1.y;
        d += ` C ${p1.x} ${arred(p1.y + dy * 0.45)}, ${p2.x} ${arred(
          p2.y - dy * 0.3,
        )}, ${p2.x} ${p2.y}`;
      }
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
  }, [de, ate, via]);

  return (
    <svg
      ref={svgRef}
      aria-hidden="true"
      focusable="false"
      className={className ? `fio-da-fonte ${className}` : "fio-da-fonte"}
    >
      {/* pathLength=100 normaliza o comprimento: dasharray/dashoffset operam
          em 0–100 para QUALQUER geometria (mesmo truque da dataviz).
          OURIVESARIA 3A (registro-2a d.2): era 1 — o escritor de
          strokeDashoffset serializa px INTEIROS, e no range [0,1] o desenho
          virava binário (1px↔0px, sem intermediários; provado no obase por
          sonda_2a_fio_prova). Com 100, o scrub ganha ~100 degraus (desenho
          progressivo de verdade). VALOR SINCRONIZADO com: CenaScrub.tsx
          (fromTo 100→0) e secoes.css (.fio-da-fonte dasharray/dashoffset
          100). O reduce (dashoffset 0 !important) independe do range. */}
      <path data-fio-path="" pathLength={100} />
    </svg>
  );
}
