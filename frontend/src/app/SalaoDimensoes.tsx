"use client";

// ============================================================
// O SALÃO DE LAPIDAÇÃO — crit. 5 (raia 1C, missão FRONTEND HORIZONTE)
// LEI: .maestro/plano-horizonte.md §3 (C5) + §5 (E2/E3/E9/E10/E19/E20/E29)
//      .maestro/direcao-horizonte.md §7 (D25–D34)
// Folha dona do visual: src/styles/cinema/salao.css (leia o cabeçalho dela:
// os contratos --bolha-dy-*/--prog/--seg-*/--ilum/--poeira-x vivem lá).
// ============================================================
// O QUE ESTE COMPONENTE CORRIGE (diagnóstico verbatim do dono sobre o
// filmstrip que ele substitui): "possui o verdadeiro side scrolling, mas
// ficou feio, indisposto, limitado e antiharmônico. Dá a sensação de que a
// página está estática e tem uma box rolando apresentando as 5 fases. A
// conexão das boxes por linha ficou podre — visível dentro da box... Há um
// grande espaço vazio, e enquanto o side scrolling acontece parece que a
// página de baixo sobe junto, o que acaba com a continuidade."
//
//   (a) "box rolando" / "página de baixo sobe junto" → o pin acontecia num
//       wrapper DENTRO do container editorial (max-w-5xl): a janela do
//       travelling tinha ~976px e o resto da página seguia visível. Aqui a
//       SEÇÃO INTEIRA é o elemento pinado, é FILHA DIRETA do <main> (zero
//       ancestral flex — o bug histórico de pinSpacing) e ocupa
//       `100% × calc(100svh − var(--altura-tarja))`: a viewport inteira vira
//       o palco, nada da página de baixo aparece durante o travelling.
//   (b) "conexão das boxes por linha ficou podre" → o fio antigo ligava
//       CENTRO a CENTRO e cruzava os painéis por dentro. Aqui ele nasce na
//       BORDA (círculo publicado) de uma bolha e morre na BORDA da seguinte,
//       por FORA, com garantia geométrica (§ "O FIO", abaixo).
//   (c) "grande espaço vazio" → o vazio virou o palco: veludo com vinheta,
//       poeira de luz em paralaxe (0.55×), bolhas em 3 planos de
//       profundidade com sombra projetada no chão, e a catenária ocupando o
//       corredor entre elas.
//   (d) "sensação de que a página está estática" → a costura vertical→
//       horizontal→vertical tem 6% de "iluminação" na entrada e 6% de saída
//       espelhada (`--ilum`), e o snap inclui 0 e 1 como pontos (E10): zero
//       tranco na entrada (a página não "anda sozinha") e na saída (o
//       usuário não luta contra o snap para escapar).
//
// ESPINHA HERDADA NOMINALMENTE (checklist §7d — nada aqui é invenção):
// gate GATE_PINADO (= hover + MQ_PIN_FILMSTRIP) · boot por IO one-shot
// rootMargin 100% · carregarGsap() · gsap.matchMedia · tween ÚNICO
// x: −(scrollWidth−clientWidth) ease:none · pin:true + pinSpacing:true
// FORÇADO · start "top top+=" + altura da Tarja re-medida pelo seletor EXATO
// [role="note"][aria-label="Aviso regulatório"] · anticipatePin:1 ·
// invalidateOnRefresh · pontos de snap = offsets REAIS · snapTo nearest
// idempotente com guarda de projeção · refresh único pós document.fonts.ready
// · startTransition(setAtivo) · killTweensOf(window) no revert ·
// html.rolagem-pinada · overflow-x:clip (nunca hidden) · will-change só no
// pinado. R1: a seção fica FORA do CenaScrub; o pin jamais é ancestral da
// Tarja z-50 / régua z-55 (trava C2).
//
// O FIO POR FORA — a garantia, em três camadas (D29 + E2/E19):
//   1. LEI DE LAYOUT (o corredor existe ANTES da curva): bandas de x
//      disjuntas + alturas alternadas (baixo-alto-centro-alto-baixo) no
//      pinado; alternância de lados + banda livre do `gap` no colar. Entre
//      duas bolhas consecutivas SEMPRE existe um corredor sem bolha.
//   2. FECHO CONVEXO (a prova por construção): uma Bézier cúbica está
//      contida no fecho convexo de P0/C1/C2/P3. P0 e P3 nascem na BORDA
//      (pinado: no círculo publicado; colar: na aresta da caixa) e C1/C2
//      ficam DENTRO do corredor livre → a curva NÃO PODE entrar numa bolha.
//      A checagem forte é a do plano tangente: se C1, C2 e P3 estão todos
//      do lado de fora da tangente ao círculo em P0 (e simetricamente em
//      P3), o fecho convexo toca o disco no máximo em P0.
//   3. CINTO-E-SUSPENSÓRIO (asserção de regressão): amostragem
//      getPointAtLength a cada 12px contra as bolhas infladas +8px, no
//      onRefresh; colisão → empurra o corredor +16px na normal e re-testa
//      (máx 3 iterações). Log só em dev; `markers` JAMAIS.
//
//   ⚠ E2 (o erro que este componente NÃO comete): o offset vertical das
//   bolhas vive num `translate` CSS — e `translate` NÃO altera `offsetTop`.
//   Medir o centro só por offset publicaria os círculos nas posições ERRADAS,
//   o "corredor" seria falso e a catenária cortaria a bolha por dentro
//   (exatamente o defeito demolido). Fonte única: a folha publica
//   `--bolha-dy-1..5`, o `translate` CONSOME a var e o JS LÊ a MESMA var por
//   getComputedStyle. Zero getBoundingClientRect na geometria (imune ao x do
//   pin).
//
// CSP: zero `style=` / `setAttribute('style')`. Só classList, escritas CSSOM
// (`el.style.setProperty` — carve-out DESIGN-TOKENS.md), o motor GSAP e
// `setAttribute("d")` em <path> (atributo SVG ≠ estilo inline).

import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { carregarGsap, MQ_PIN_FILMSTRIP, type MotorGsap } from "@/lib/gsapSetup";

// ============================================================
// PERF — B2 (2026-07-14): A CASCA E CLIENT, O RECHEIO E DO SERVIDOR.
// ------------------------------------------------------------
// Atribuição medida na Onda 5 (`.maestro/evidencias/onda5/B-perf/`): a
// longtask dominante da landing no mobile-4x é o COMMIT DE HIDRATAÇÃO, e o
// custo é proporcional ao TAMANHO DA ÁRVORE que o cliente reconcilia —
// não a boot de efeito (ligar/desligar TODOS os efeitos deste componente
// não movia o número; Suspense/next/dynamic também não).
//
// A alavanca (provada pelo `#nascimento`, que custa ~0ms): o que um Server
// Component RENDERIZA e passa como slot/`children` para uma ilha client
// chega pronto no payload RSC — os elementos já vêm criados, fora da tarefa
// de hidratação. Por isso este componente deixou de RENDERIZAR as 5 bolhas
// (ele só recebe `bolhas: ReactNode`, montado em page.tsx) e passou a
// MEDIR/comandar as que já estão no DOM.
//
// Consequência de mecanismo (nada some, tudo muda de lugar):
//   • refs por bolha  → `querySelectorAll("li.bolha-bancada")` no trilho
//     (ordem de documento = ordem das dimensões; o `<li>` espaçador não
//     leva a classe, então fica fora da geometria, como sempre esteve);
//   • `dimensoes` (com ReactNode + TermoTooltip) → `rotulos` (só
//     `{numero,titulo}`): o que a CASCA precisa é o rótulo das talhas e o
//     texto do anúncio — a copy e as ilhas de tooltip vivem no servidor.
// Tudo o mais (pin, snap com 0 e 1, fio por fora, teclado 10/10, talhas,
// E9/E10/E17/E29) é bit-a-bit o mesmo.
// ============================================================

export type DimensaoSalao = {
  numero: string;
  titulo: string;
  fonte: string;
  /** `ReactNode` (não `string`) para a copy da Onda 2 poder trazer
   *  TermoTooltip DENTRO da bolha — é esse gatilho focável que faz o
   *  `focusin` → travelling ser um caminho REAL de teclado (e o pior caso
   *  1.4.13 da bolha da borda, E13). Strings seguem válidas.
   *  ⚠ Este tipo agora descreve o DADO que o SERVIDOR consome para montar
   *  as bolhas (page.tsx) — ele não cruza mais a fronteira client. */
  texto: ReactNode;
};

/** O que a CASCA client precisa saber de cada bolha: talha + anúncio. */
export type RotuloSalao = {
  numero: string;
  titulo: string;
};

/** Gate do modo pinado — a MQ canônica da casa composta com `hover:hover`. */
const GATE_PINADO = `(hover: hover) and ${MQ_PIN_FILMSTRIP}`;

/** Raio publicado da bolha = metade da diagonal + INFLA (direção §7c.2). */
const INFLA = 8;
/** Passo da amostragem de colisão (asserção de regressão). */
const PASSO_AMOSTRA = 12;
/** Máximo de empurrões do corredor antes de aceitar a curva (D29.5). */
const MAX_ITER = 3;

type Ponto = { x: number; y: number };
type Bolha = {
  cx: number;
  cy: number;
  r: number; // metade da diagonal + 8 (círculo publicado)
  esq: number;
  dir: number;
  topo: number;
  base: number; // caixa REAL (já com o dy aplicado)
};
type Curva = { p0: Ponto; c1: Ponto; c2: Ponto; p3: Ponto };

const limitar = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

/**
 * E2 — a medição que sustenta tudo. `translate` não entra em offsetTop:
 * o dy vem da MESMA var que a folha usa no `translate` (fonte única).
 * ⚠ o valor computado de uma custom property é o TOKEN (não um comprimento
 * resolvido) — por isso a folha declara os `--bolha-dy-*` em px puros.
 */
function medirBolhas(bolhas: HTMLLIElement[]): Bolha[] {
  return bolhas.map((li) => {
    const dy = Number.parseFloat(
      getComputedStyle(li).getPropertyValue("--bolha-dy").trim(),
    );
    const desloc = Number.isFinite(dy) ? dy : 0;
    const w = li.offsetWidth;
    const h = li.offsetHeight;
    const cx = li.offsetLeft + w / 2;
    const cy = li.offsetTop + h / 2 + desloc;
    return {
      cx,
      cy,
      r: Math.hypot(w, h) / 2 + INFLA,
      esq: cx - w / 2,
      dir: cx + w / 2,
      topo: cy - h / 2,
      base: cy + h / 2,
    };
  });
}

/**
 * Ponto onde o raio (centro → alvo) fura o círculo publicado da bolha, com
 * 2px de folga de nascimento: ancorar EXATAMENTE sobre o círculo deixa o
 * ponto na aresta do gate (a serialização do `d` com 1 casa decimal punha a
 * amostra 0,05px DENTRO do círculo e a asserção acusava colisão de 1 ponto).
 */
function naBorda(b: Bolha, alvo: Ponto): Ponto {
  const dx = alvo.x - b.cx;
  const dy = alvo.y - b.cy;
  const m = Math.hypot(dx, dy) || 1;
  const raio = b.r + 2;
  return { x: b.cx + (dx / m) * raio, y: b.cy + (dy / m) * raio };
}

/**
 * PINADO — catenária alternante: se a bolha seguinte está mais ALTA, o fio
 * verga por BAIXO; se está mais baixa, arqueia por CIMA. Os controles vão
 * para o corredor livre do lado do sag (fecho convexo).
 */
function curvaPinada(a: Bolha, b: Bolha, iter: number): Curva {
  const maisBaixa = b.cy > a.cy; // y cresce para baixo
  const lado = maisBaixa ? -1 : 1; // -1 = corredor ACIMA, +1 = ABAIXO
  const dist = Math.hypot(b.cx - a.cx, b.cy - a.cy);
  const sag = limitar(0.1 * dist, 28, 72) + iter * 16;
  const yCorr =
    lado > 0 ? Math.max(a.base, b.base) + sag : Math.min(a.topo, b.topo) - sag;
  const c1: Ponto = { x: a.cx + 0.35 * (b.cx - a.cx), y: yCorr };
  const c2: Ponto = { x: a.cx + 0.65 * (b.cx - a.cx), y: yCorr };
  return { p0: naBorda(a, c1), c1, c2, p3: naBorda(b, c2) };
}

/**
 * COLAR (E19) — o fio vive na BANDA LIVRE entre as duas bolhas (a faixa
 * horizontal do `gap`, onde não existe bolha nenhuma): P0 na aresta de baixo
 * de A, P3 na aresta de cima de B, controles com y DENTRO da banda. O fecho
 * convexo dos 4 pontos está contido na banda → o fio não cruza bolha, nem em
 * 375px. Zero rail horizontal: é o mesmo DOM, empilhado.
 */
function curvaColar(a: Bolha, b: Bolha, iter: number): Curva {
  const folga = 10 + iter * 4;
  const yA = a.base + folga;
  const yB = b.topo - folga;
  const banda = Math.max(yB - yA, 8);
  const paraDireita = b.cx > a.cx;
  const recuo = 28;
  const p0: Ponto = { x: paraDireita ? a.dir - recuo : a.esq + recuo, y: yA };
  const p3: Ponto = { x: paraDireita ? b.esq + recuo : b.dir - recuo, y: yB };
  return {
    p0,
    c1: { x: p0.x, y: yA + banda * 0.5 },
    c2: { x: p3.x, y: yB - banda * 0.5 },
    p3,
  };
}

function dDaCurva(c: Curva): string {
  const n = (v: number) => v.toFixed(1);
  return `M ${n(c.p0.x)} ${n(c.p0.y)} C ${n(c.c1.x)} ${n(c.c1.y)}, ${n(c.c2.x)} ${n(c.c2.y)}, ${n(c.p3.x)} ${n(c.p3.y)}`;
}

/**
 * Asserção de regressão (D29.5): amostra o path a cada 12px e testa contra
 * as 5 bolhas. Pinado = círculos publicados (metade da diagonal + 8px, o
 * modelo da direção). Colar = caixas infladas +8px — num colar de 375px os
 * círculos circunscritos de bolhas VIZINHAS se sobrepõem entre si (a
 * distância entre centros é menor que a soma dos raios), então nenhuma curva
 * — nem uma reta vertical — poderia ficar fora deles: o invariante que
 * importa (e que o dono cobrou) é a CAIXA PINTADA, e é ela que provamos lá.
 */
function colide(path: SVGPathElement, bolhas: Bolha[], circulos: boolean): boolean {
  const total = path.getTotalLength();
  if (!Number.isFinite(total) || total <= 0) return false;
  for (let s = 0; s <= total; s += PASSO_AMOSTRA) {
    const p = path.getPointAtLength(Math.min(s, total));
    for (const b of bolhas) {
      if (circulos) {
        if (Math.hypot(p.x - b.cx, p.y - b.cy) < b.r) return true;
      } else if (
        p.x > b.esq - INFLA &&
        p.x < b.dir + INFLA &&
        p.y > b.topo - INFLA &&
        p.y < b.base + INFLA
      ) {
        return true;
      }
    }
  }
  return false;
}

export function SalaoDimensoes({
  rotulos,
  bolhas,
  rotuladoPor = "dimensoes-titulo",
  children,
}: {
  /** Talhas + anúncio (E17/D30). NUNCA a copy: ela é do servidor. */
  rotulos: readonly RotuloSalao[];
  /** SLOT SERVIDOR (perf/TBT): os 5 `<li class="bolha-bancada">` já
   *  renderizados — inclusive os TermoTooltip de dentro. Chegam pelo payload
   *  RSC, prontos; a casca só os mede e os comanda. */
  bolhas: ReactNode;
  rotuladoPor?: string;
  children?: React.ReactNode;
}) {
  const secaoRef = useRef<HTMLElement | null>(null);
  const trilhoRef = useRef<HTMLOListElement | null>(null);
  const fioRef = useRef<SVGSVGElement | null>(null);
  const barraRef = useRef<HTMLDivElement | null>(null);
  const poeiraRef = useRef<HTMLDivElement | null>(null);

  const [ativo, setAtivo] = useState(0);
  const [pinado, setPinado] = useState(false);
  const [dica, setDica] = useState(false);
  const [anuncio, setAnuncio] = useState("");
  /**
   * PERF — B2: a GEOMETRIA só acorda perto do salão.
   * A medição do fio (getComputedStyle das 5 bolhas + offsets + amostragem
   * getPointAtLength) força layout, e o salão está ~5 telas abaixo da dobra:
   * no load ela era trabalho puro de bloqueio por um fio que ninguém podia
   * ver. Mesmo gate do boot (IO one-shot, rootMargin 100% = uma viewport de
   * antecedência), então o fio SEMPRE chega desenhado antes de entrar em
   * cena. Sem JS/antes do gate: os `<path>` ficam sem `d` — nada é desenhado,
   * nada quebra (é decorativo por construção, como o FioDaFonte).
   */
  const [perto, setPerto] = useState(false);

  // Pontes para o mundo GSAP (mesma disciplina do filmstrip herdado).
  const rolarPinadoRef = useRef<((indice: number) => void) | null>(null);
  const pontosSnapRef = useRef<number[]>([]);
  /** Ponto de destino de uma navegação programática em voo (teclado/talha/
   *  focusin) — enquanto não é null, o `snapTo` obedece a ele. */
  const alvoNavRef = useRef<number | null>(null);
  const ativoPinadoRef = useRef(0);
  const refreshAposFontes = useRef(false);
  const acordadoRef = useRef(false);

  /**
   * As bolhas VIVAS, lidas do DOM (elas são server-rendered — não há mais um
   * ref por bolha). `li.bolha-bancada` em ordem de documento = ordem das
   * dimensões; o `<li class="salao-espaco">` (espaçador de fim) não casa com
   * o seletor e segue, como sempre, fora de toda a geometria.
   */
  const bolhasVivas = useCallback(
    () =>
      Array.from(
        trilhoRef.current?.querySelectorAll<HTMLLIElement>("li.bolha-bancada") ?? [],
      ),
    [],
  );

  /**
   * Geometria do fio — roda nos DOIS modos. Escritas: `setAttribute("d")` no
   * <path> (canal CSP homologado) e `--seg-fim`/`--seg-escala` por segmento
   * (só no pinado: o CSS multiplica, nunca divide por var). NUNCA em quadro
   * de scroll — só em refresh/resize/troca de modo.
   */
  const recalcularFio = useCallback(() => {
    const svg = fioRef.current;
    const secao = secaoRef.current;
    if (!svg || !secao) return;
    const bolhas = medirBolhas(bolhasVivas());
    if (bolhas.length < 2) return;
    const modoPinado = secao.classList.contains("salao-pinado");
    const pontos = pontosSnapRef.current;

    const segs = svg.querySelectorAll<SVGPathElement>(".salao-fio-seg");
    const faiscas = svg.querySelectorAll<SVGPathElement>(".salao-fio-faisca");

    segs.forEach((seg, i) => {
      const a = bolhas[i];
      const b = bolhas[i + 1];
      if (!a || !b) return;

      let d = "";
      for (let iter = 0; iter < MAX_ITER; iter += 1) {
        const curva = modoPinado ? curvaPinada(a, b, iter) : curvaColar(a, b, iter);
        d = dDaCurva(curva);
        seg.setAttribute("d", d);
        if (!colide(seg, bolhas, modoPinado)) break;
        // Colisão só é possível se a lei de layout degenerar (viewport
        // exótico): empurra o corredor e re-testa. Sem log em produção.
      }
      faiscas[i]?.setAttribute("d", d);

      if (modoPinado && pontos.length === bolhas.length) {
        // JANELA DE DESENHO — deslocada UM passo para trás em relação à
        // fórmula herdada do filmstrip (lá o elo completava quando o painel
        // i+1 aterrissava). Medido no palco novo: no ponto de repouso da
        // bolha i, a bolha i−1 está INTEIRAMENTE fora da tela (passo 576 >
        // largura 352) e a bolha i+1 está em cena — ou seja, o fio "de trás"
        // que a fórmula herdada acabava de desenhar não é visível, e o único
        // fio que o olho vê (o da frente) estaria 0% desenhado em TODO
        // repouso. Com a janela deslocada, o elo i completa quando a bolha i
        // pousa: na chegada o fio já convida o olho para a direita, e durante
        // o percurso ele se desenha à FRENTE, no vão entre as duas bolhas em
        // cena. Reversível de graça pelo scrub (função pura do progresso).
        const fim = pontos[i] ?? 0;
        const passo = (pontos[1] ?? 0.25) - (pontos[0] ?? 0);
        const ini = i > 0 ? (pontos[i - 1] ?? 0) : fim - passo;
        const escala = (1 / Math.max(fim - ini, 0.0001)).toFixed(4);
        for (const alvo of [seg, faiscas[i]]) {
          alvo?.style.setProperty("--seg-fim", fim.toFixed(4));
          alvo?.style.setProperty("--seg-escala", escala);
        }
      }
    });
  }, [bolhasVivas]);

  // PERF — B2: o gate de proximidade da geometria (ver `perto`, acima). IO
  // one-shot com a MESMA folga do boot do travelling (rootMargin 100%).
  useEffect(() => {
    const secao = secaoRef.current;
    if (!secao || perto) return;
    const io = new IntersectionObserver(
      (entradas) => {
        if (!entradas.some((e) => e.isIntersecting)) return;
        io.disconnect();
        setPerto(true);
      },
      { rootMargin: "100% 0px 100% 0px" },
    );
    io.observe(secao);
    return () => io.disconnect();
  }, [perto]);

  // Geometria: primeira medida (pós-fontes) + resize passivo rAF-coalescido +
  // toda troca de modo (o layout muda inteiro entre colar e travelling).
  // Só roda a partir do gate de proximidade (B2): no load, zero layout forçado.
  useEffect(() => {
    if (!perto) return;
    let quadro = 0;
    const agendar = () => {
      if (quadro) return;
      quadro = requestAnimationFrame(() => {
        quadro = 0;
        recalcularFio();
      });
    };
    agendar(); // chegada perto + toda troca de modo (colar ⇄ travelling)
    document.fonts.ready.then(agendar, () => undefined);
    // No travelling quem re-mede em resize é o `onRefresh` do ScrollTrigger
    // (junto dos pontos de snap, na ordem certa). O listener abaixo existe
    // para o COLAR — que não tem ScrollTrigger nenhum.
    if (!pinado) window.addEventListener("resize", agendar, { passive: true });
    return () => {
      if (quadro) cancelAnimationFrame(quadro);
      window.removeEventListener("resize", agendar);
    };
  }, [recalcularFio, pinado, perto]);

  // E9 — assentamento: a classe que LIBERA o keyframe (que nasce pausado na
  // folha) é aplicada UMA vez, quando a seção entra em cena. No load, com o
  // salão fora da tela, nada corre: o visitante vê as bolhas assentarem
  // quando CHEGA nelas. `infinite` está proibido (2.2.2).
  useEffect(() => {
    const secao = secaoRef.current;
    if (!secao || acordadoRef.current) return;
    const io = new IntersectionObserver(
      (entradas) => {
        if (!entradas.some((e) => e.isIntersecting)) return;
        acordadoRef.current = true;
        secao.classList.add("salao-acordado");
        io.disconnect();
      },
      { threshold: 0.15 },
    );
    io.observe(secao);
    return () => io.disconnect();
  }, []);

  // E17 — live region sem spam: só anuncia navegação iniciada pelo usuário
  // por TECLADO ou TALHA (nunca roda/gesto), 1 anúncio por assentamento.
  const anunciar = useCallback(
    (indice: number) => {
      const d = rotulos[indice];
      if (!d) return;
      setAnuncio(`Dimensão ${indice + 1} de ${rotulos.length} — ${d.titulo}`);
    },
    [rotulos],
  );

  const irPara = useCallback(
    (indice: number, origem: "teclado" | "talha" | null = null) => {
      setDica(false);
      const rolarPinado = rolarPinadoRef.current;
      if (rolarPinado) {
        rolarPinado(indice);
      } else {
        bolhasVivas()[indice]?.scrollIntoView({ block: "center" });
      }
      if (origem) window.setTimeout(() => anunciar(indice), 520);
    },
    [anunciar, bolhasVivas],
  );

  function aoTeclado(ev: React.KeyboardEvent<HTMLOListElement>) {
    const modoPinado = rolarPinadoRef.current !== null;
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      irPara(Math.min(ativo + 1, rotulos.length - 1), "teclado");
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      irPara(Math.max(ativo - 1, 0), "teclado");
    } else if (modoPinado && ev.key === "Home") {
      ev.preventDefault();
      irPara(0, "teclado");
    } else if (modoPinado && ev.key === "End") {
      ev.preventDefault();
      irPara(rotulos.length - 1, "teclado");
    }
  }

  // ------------------------------------------------------------
  // BOOT DO TRAVELLING — IO one-shot (rootMargin 100%) → carregarGsap() →
  // gsap.matchMedia(GATE_PINADO). Custo ZERO no load; em falha de rede o
  // colar segue intacto e um cruzamento futuro da MQ tenta de novo.
  // ------------------------------------------------------------
  useEffect(() => {
    const secao = secaoRef.current;
    const trilho = trilhoRef.current;
    if (!secao || !trilho) return;

    let cancelado = false;
    let bootIniciado = false;
    let mmGsap: { revert: () => void } | null = null;
    const mq = window.matchMedia(GATE_PINADO);

    const configurar = (motor: MotorGsap) => {
      const { gsap, ScrollTrigger } = motor;
      const mm = gsap.matchMedia();

      mm.add(GATE_PINADO, () => {
        const bolhas = bolhasVivas();
        const total = bolhas.length;
        if (total < 2) return;
        const svgFio = fioRef.current;
        const poeira = poeiraRef.current;

        secao.classList.add("salao-pinado");
        // R4: enquanto o modo existe, o smooth global do html morre (senão
        // ele interceptaria CADA escrita de scroll do snap/ScrollToPlugin).
        document.documentElement.classList.add("rolagem-pinada");
        setPinado(true);
        // E29 — descobribilidade: sem setas visíveis, nada anuncia ←/→. O
        // contador exibe a dica por UM ciclo e ASSENTA (jamais em loop —
        // 2.2.2). Vive aqui, no callback do gsap.matchMedia (sistema
        // externo), e não num efeito: setState síncrono em corpo de efeito é
        // erro de lint da casa (cascading renders).
        setDica(true);
        const tDica = window.setTimeout(() => setDica(false), 3200);

        const desligarBase = () => {
          alvoNavRef.current = null;
          secao.classList.remove("salao-pinado");
          document.documentElement.classList.remove("rolagem-pinada");
          secao.style.removeProperty("--ilum");
          barraRef.current?.style.removeProperty("--prog");
          svgFio?.style.removeProperty("--prog");
          poeira?.style.removeProperty("--poeira-x");
          // O tween do ScrollToPlugin nasce em handler (fora do mm.add
          // síncrono) e escaparia do revert(): a página não pode continuar
          // rolando sozinha depois de cruzar o gate (achado 7, 2026-07-13).
          gsap.killTweensOf(window);
          setPinado(false);
        };

        // `scrollWidth − clientWidth` do <ol> (que NÃO é scroll container em
        // modo nenhum: o overflow real é do transform). Cacheado a cada
        // refresh — nada de ler layout dentro do onUpdate (reflow por quadro).
        const distancia = () => Math.max(0, trilho.scrollWidth - trilho.clientWidth);
        let dist = distancia();

        // Pontos de snap = OFFSETS REAIS (nunca k/4). Com o espaçador de fim
        // da folha, eles caem em [0, .25, .5, .75, 1] — E10: 0 e 1 SÃO pontos
        // de snap, então o snap não puxa o scroll na entrada nem segura na
        // saída (as zonas mortas de 6%+6% ficam sem tranco).
        const recalcularPontos = () => {
          dist = distancia();
          const base = bolhas[0]?.offsetLeft ?? 0;
          pontosSnapRef.current = bolhas.map((b) =>
            dist > 0 ? limitar((b.offsetLeft - base) / dist, 0, 1) : 0,
          );
        };
        recalcularPontos();

        const pontoMaisProximo = (v: number) => {
          const pontos = pontosSnapRef.current;
          return pontos.reduce(
            (m, q) => (Math.abs(q - v) < Math.abs(m - v) ? q : m),
            pontos[0] ?? 0,
          );
        };
        const indiceMaisProximo = (v: number) => {
          const pontos = pontosSnapRef.current;
          return pontos.reduce(
            (mi, q, j) => (Math.abs(q - v) < Math.abs((pontos[mi] ?? 0) - v) ? j : mi),
            0,
          );
        };
        // E10: a guarda de projeção usa o GAP REAL entre vizinhos (o passo
        // médio 0.5/(n−1) mentiria assim que os pontos deixassem de ser
        // equidistantes — e as zonas mortas quebram a equidistância).
        const meioGapReal = (indice: number, direcao: number) => {
          const pontos = pontosSnapRef.current;
          const vizinho = limitar(indice + direcao, 0, pontos.length - 1);
          const gap = Math.abs((pontos[vizinho] ?? 0) - (pontos[indice] ?? 0));
          return (gap > 0 ? gap : 1 / Math.max(pontos.length - 1, 1)) * 0.5;
        };

        // "Iluminação" da costura: 6% de chegada + 6% de saída espelhada.
        // Escrita só quando MUDA (fora dessas faixas o valor é 1).
        let ilumAnterior = -1;
        const escreverIlum = (p: number) => {
          const bruto = Math.min(p / 0.06, (1 - p) / 0.06, 1);
          const t = limitar(bruto, 0, 1);
          const suave = Number((t * t * (3 - 2 * t)).toFixed(2)); // smoothstep
          if (suave === ilumAnterior) return;
          ilumAnterior = suave;
          secao.style.setProperty("--ilum", String(suave));
        };

        // TWEEN ÚNICO do travelling (1px de scroll ≈ 1px de travelling;
        // ease:none é OBRIGATÓRIO — é ele que faz o containerAnimation dos
        // estratos mapear posição↔progresso corretamente). O <svg> do fio é
        // o SEGUNDO alvo do MESMO tween: um escritor de transform por
        // elemento, x idêntico a cada quadro — o fio acompanha as bolhas
        // rigidamente, sem segundo relógio nem cópia com atraso de frame.
        const tween = gsap.to(svgFio ? [trilho, svgFio] : trilho, {
          x: () => -distancia(),
          ease: "none",
          scrollTrigger: {
            trigger: secao,
            pin: true, // a SEÇÃO inteira (filha direta do <main>) é o palco
            start: () => {
              const tarja = document.querySelector<HTMLElement>(
                '[role="note"][aria-label="Aviso regulatório"]',
              );
              return `top top+=${tarja?.offsetHeight ?? 0}`;
            },
            // D25: end = distância × 1.13 — os 13% extras são as duas zonas
            // mortas (6% de iluminação + 6% de saída) sem as quais a costura
            // vertical→horizontal daria um tranco.
            end: () => `+=${Math.round(distancia() * 1.13)}`,
            // pinSpacing FORÇADO: em pai flex/grid o ScrollTrigger o desliga
            // sozinho, o documento não cresce e a página ACABA no meio do
            // travelling (bug 2026-07-12). Aqui o pai é o <main> (bloco), mas
            // a trava fica explícita — é barata e o histórico é caro.
            pinSpacing: true,
            scrub: 1.2, // D32
            snap: {
              snapTo: (v: number, self?: ScrollTrigger) => {
                // Navegação PROGRAMÁTICA (teclado/talha/focusin) é soberana:
                // a guarda de projeção existe para o FLICK de roda. Sem esta
                // porta, o snap dispara com o scroll ainda em voo, mede um
                // `self.progress` intermediário e devolve o "vizinho" —
                // cuspindo o usuário de volta no meio do caminho (End caía na
                // bolha 3). Registrada como pegadinha da raia.
                const emVoo = alvoNavRef.current;
                if (emVoo !== null) return emVoo;
                const alvo = pontoMaisProximo(limitar(v, 0, 1));
                if (!self) return alvo;
                const atual = self.progress;
                const vizinho = pontoMaisProximo(atual);
                const iAtual = indiceMaisProximo(atual);
                const direcao = alvo >= vizinho ? 1 : -1;
                return Math.abs(alvo - atual) >
                  Math.abs(vizinho - atual) + meioGapReal(iAtual, direcao)
                  ? vizinho
                  : alvo;
              },
              duration: { min: 0.25, max: 0.6 }, // D32
              ease: "power2.inOut",
            },
            anticipatePin: 1,
            invalidateOnRefresh: true,
            markers: false, // LEI: nunca true (injetaria estilo inline)
            onEnter: () => {
              if (acordadoRef.current) return;
              acordadoRef.current = true;
              secao.classList.add("salao-acordado"); // E9 (cinto do IO)
            },
            onRefresh: () => {
              // Ordem: pontos primeiro — a geometria do fio consome os
              // pontos de snap recém-medidos nas janelas de desenho.
              recalcularPontos();
              recalcularFio();
            },
            onUpdate: (st) => {
              const prog = st.progress;
              const texto = prog.toFixed(4);
              // Custom property não herda entre irmãos: duas escritas (a
              // hairline consome a dela; do <svg> ela herda para os <path>).
              barraRef.current?.style.setProperty("--prog", texto);
              svgFio?.style.setProperty("--prog", texto);
              // Poeira a 0.55× (paralaxe scrubbed): mesmo quadro, mesmo
              // relógio, escritor único desta propriedade.
              poeira?.style.setProperty(
                "--poeira-x",
                `${(-dist * 0.55 * prog).toFixed(1)}px`,
              );
              escreverIlum(prog);
              const indice = indiceMaisProximo(prog);
              if (ativoPinadoRef.current !== indice) {
                ativoPinadoRef.current = indice;
                // startTransition: mitigação do glitch de raster do Chromium
                // no pin (herdado/aceito — diagnóstico da APOTEOSE).
                startTransition(() => setAtivo(indice));
              }
            },
          },
        });

        const st = tween.scrollTrigger;
        if (!st) {
          tween.kill();
          desligarBase();
          return;
        }
        ativoPinadoRef.current = indiceMaisProximo(st.progress);
        recalcularFio();

        // Estratos internos por containerAnimation (sem pin/snap aninhado —
        // restrição do mecanismo). Alvos: SÓ `.salao-camada` (nenhum outro
        // escritor de transform/opacity nelas).
        for (const bolha of bolhas.slice(1)) {
          const camadas = bolha.querySelectorAll<HTMLElement>(".salao-camada");
          if (camadas.length === 0) continue;
          gsap.fromTo(
            camadas,
            { x: 28, opacity: 0.35 },
            {
              x: 0,
              opacity: 1,
              ease: "none",
              stagger: 0.08,
              scrollTrigger: {
                trigger: bolha,
                containerAnimation: tween,
                start: "left right",
                end: "left 55%",
                scrub: true,
                markers: false,
              },
            },
          );
        }

        // Navegação por índice = tween do ScrollToPlugin no scroll VERTICAL
        // (nunca window.scrollTo: o smooth global está desligado e o snap do
        // ST precisa enxergar o movimento).
        const rolarPara = (indice: number) => {
          const ponto = pontosSnapRef.current[indice] ?? 0;
          alvoNavRef.current = ponto; // porta do snapTo enquanto o voo dura
          gsap.to(window, {
            scrollTo: Math.round(st.start + ponto * (st.end - st.start)),
            duration: 0.45,
            ease: "power2.out",
            overwrite: "auto",
            onComplete: () => {
              // solta a porta só depois do assentamento do snap (o delayedCall
              // do ScrollTrigger acorda ~scrub/2 após o último evento de
              // scroll); enquanto isso, o snapTo devolve o ponto pedido.
              window.setTimeout(() => {
                alvoNavRef.current = null;
              }, 900);
            },
            onInterrupt: () => {
              alvoNavRef.current = null;
            },
          });
        };
        rolarPinadoRef.current = rolarPara;

        // Foco por Tab dentro de uma bolha fora de cena → o salão VIAJA até
        // ela (foco nunca clipado pelo pin).
        const aoFocarDentro = (ev: FocusEvent) => {
          if (!(ev.target instanceof Element) || ev.target === trilho) return;
          const bolha = ev.target.closest("li");
          const indice = bolha ? bolhas.indexOf(bolha) : -1;
          if (indice >= 0) rolarPara(indice);
        };
        trilho.addEventListener("focusin", aoFocarDentro);

        // Refresh ÚNICO pós-fontes (CLS≈0): as fontes self-hosted mudam a
        // altura das bolhas → start/end/pontos/geometria re-medidos uma vez.
        if (!refreshAposFontes.current) {
          refreshAposFontes.current = true;
          document.fonts.ready.then(
            () => {
              if (!cancelado) ScrollTrigger.refresh();
            },
            () => undefined,
          );
        }

        return () => {
          window.clearTimeout(tDica);
          setDica(false);
          trilho.removeEventListener("focusin", aoFocarDentro);
          rolarPinadoRef.current = null;
          pontosSnapRef.current = [];
          desligarBase();
          // Colar de volta: a geometria do fio é refeita pelo efeito de
          // modo (dependência `pinado`), no modelo da banda livre.
        };
      });

      return mm;
    };

    const iniciar = () => {
      if (cancelado || bootIniciado) return;
      bootIniciado = true;
      carregarGsap()
        .then((motor) => {
          if (cancelado) return;
          mmGsap = configurar(motor);
        })
        .catch(() => {
          bootIniciado = false; // rede falhou: o colar segue; retry na MQ
        });
    };

    const aoMudarMq = (ev: MediaQueryListEvent) => {
      if (ev.matches) iniciar();
    };

    const io = new IntersectionObserver(
      (entradas) => {
        if (!entradas.some((e) => e.isIntersecting)) return;
        io.disconnect();
        mq.addEventListener("change", aoMudarMq);
        if (mq.matches) iniciar();
      },
      { rootMargin: "100% 0px 100% 0px" },
    );
    io.observe(secao);

    return () => {
      cancelado = true;
      io.disconnect();
      mq.removeEventListener("change", aoMudarMq);
      mmGsap?.revert();
      rolarPinadoRef.current = null;
    };
  }, [bolhasVivas, recalcularFio]);

  const elos = rotulos.slice(0, -1);

  return (
    <>
      {/* PÓRTICO — a chegada (D25/7a): o veludo da vitrine não termina,
          escurece. Cabeçalho + parágrafo vêm do integrador (children), sobre
          a MESMA superfície. Irmão direto do <main>, como a seção. */}
      <div className="salao-portico veludo-escopo">{children}</div>

      {/* A SEÇÃO É O PALCO: filha direta do <main>, sem container, sem
          ancestral flex (E1/E3) — é ela que o ScrollTrigger pina. */}
      <section
        ref={secaoRef}
        id="dimensoes"
        aria-labelledby={rotuladoPor}
        className="salao-fundo veludo-escopo"
      >
        <div ref={poeiraRef} aria-hidden className="salao-poeira" />

        <div className="salao-palco">
          {/* `role="list"` explícito: o preflight do Tailwind zera
              list-style e o Safari/VoiceOver deixa de expor listas sem
              marcador (mesma auditoria 1.3.1 do filmstrip). */}
          <ol
            ref={trilhoRef}
            tabIndex={0}
            role="list"
            aria-label="Cinco dimensões"
            aria-describedby="salao-instrucao"
            onKeyDown={aoTeclado}
            className="salao-trilho"
          >
            {/* AS 5 BOLHAS — slot SERVIDOR (perf/TBT, ver cabeçalho): chegam
                do payload RSC já renderizadas (numeral, título, texto com os
                TermoTooltip, selo). O cliente NÃO as reconcilia; ele as
                encontra por `li.bolha-bancada` e mede. */}
            {bolhas}
            {/* Espaçador de fim (ver salao.css §5): elemento REAL porque o
                `::after` de um flex container não entra no scrollWidth do
                Blink. `aria-hidden` → a lista segue com 5 itens para o leitor
                de tela; `.bolha-bancada` NÃO é aplicada, então ele fica fora
                de toda a geometria/refs. */}
            <li aria-hidden className="salao-espaco" />
          </ol>

          {/* O FIO — irmão do <ol> (nunca ancestral de nada), decorativo.
              `d` vem do onRefresh/resize por setAttribute; o desenho consome
              `--prog` (pinado) ou o view() da folha (colar). */}
          <svg ref={fioRef} aria-hidden="true" className="salao-fio">
            {elos.map((d, i) => (
              <path
                key={`seg-${d.numero}`}
                className={`salao-fio-seg salao-fio-seg--${i + 1}`}
                pathLength={1}
              />
            ))}
            {elos.map((d, i) => (
              <path
                key={`faisca-${d.numero}`}
                className={`salao-fio-faisca salao-fio-faisca--${i + 1}`}
                pathLength={1}
              />
            ))}
          </svg>
        </div>

        {/* HUD — SEM SETAS nos dois modos (decreto do dono, D30). Ficam: as
            5 marcas de talha (alvo ≥24px, aria-current) e o contador
            aria-hidden (que na 1ª interação vira a dica "← →" e assenta). */}
        <div className="salao-hud">
          <ul className="salao-talhas">
            {rotulos.map((d, i) => (
              <li key={d.numero}>
                <button
                  type="button"
                  onClick={() => irPara(i, "talha")}
                  aria-current={i === ativo ? "location" : undefined}
                  aria-label={`Ir para a dimensão ${i + 1}: ${d.titulo}`}
                  className="salao-talha"
                >
                  <span aria-hidden className="salao-talha__traco" />
                </button>
              </li>
            ))}
          </ul>
          <span
            aria-hidden
            className={`salao-contador${dica ? " salao-contador--dica" : ""}`}
          >
            {dica
              ? "← →"
              : `${String(ativo + 1).padStart(2, "0")} / ${String(rotulos.length).padStart(2, "0")}`}
          </span>
        </div>

        <div ref={barraRef} aria-hidden className="salao-progresso" />

        <p id="salao-instrucao" className="sr-only">
          Use as setas esquerda e direita do teclado para percorrer as cinco dimensões; Home
          e End levam à primeira e à última.
        </p>
        <p role="status" className="sr-only">
          {anuncio}
        </p>
      </section>
    </>
  );
}
