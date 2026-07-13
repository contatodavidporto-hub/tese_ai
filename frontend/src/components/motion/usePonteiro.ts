"use client";

import { useEffect, useSyncExternalStore, type RefObject } from "react";

// ---------------------------------------------------------------------------
// prefers-reduced-motion — mesmo padrão de Reveal.tsx (useSyncExternalStore:
// evita mismatch de hidratação e o anti-padrão de setState direto num
// efeito). `usePrefereReduzido` não é exportado de Reveal.tsx (é interno ao
// motor de revelação por IntersectionObserver, que esta luminária não usa),
// então replica-se aqui o pequeno contrato — mesmo texto/raciocínio do
// original, escopo isolado neste arquivo.
// EXPORT ADITIVO (missão APOTEOSE 2026-07-13, LEI §4 — interface pública
// congelada, mudança só aditiva/retrocompatível): `usePrefereReduzido` e
// `QUERY_HOVER_FINO` passam a ser exportados para os hooks-irmãos da
// família de motion (ex.: useOrganismoH1) não abrirem uma TERCEIRA cópia
// do contrato. Nenhum consumidor existente muda.
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

export function usePrefereReduzido(): boolean {
  return useSyncExternalStore(
    inscreverReduzido,
    instantaneoReduzido,
    instantaneoReduzidoServidor,
  );
}

// Luz por ponteiro só em dispositivo com hover real + ponteiro fino (M7,
// direcao-de-arte-cinema.md §2/§4) — touch nunca liga o listener abaixo.
export const QUERY_HOVER_FINO = "(hover: hover) and (pointer: fine)";

/** Uma folha que consome `--mx`/`--my` (sprite de luz, glifo-fantasma…). */
type FolhaDeEscrita = RefObject<HTMLElement | null>;

/**
 * Modo por-folha de PROXIMIDADE (ADITIVO — missão APOTEOSE 2026-07-13,
 * LEI §3.2 "H1-organismo" + §4): além de (ou em vez de) `--mx`/`--my`, o
 * hook computa por FOLHA a proximidade do ponteiro (0..1, smoothstep sobre
 * a distância ao retângulo da folha) e escreve `propriedade` via CSSOM em
 * cada folha — o CSS consome com translate/scale/color-mix INDIVIDUAIS.
 *
 * Geometria: os retângulos das folhas são CACHEADOS em coordenadas de
 * PÁGINA (scroll-invariantes) — medidos via `offsetLeft/offsetTop/
 * offsetWidth/offsetHeight` (caixa de layout: imune ao transform do
 * keyframe `palavra-compoe` em voo, que contaminaria getBoundingClientRect)
 * ancorados no getBoundingClientRect do offsetParent (não-transformado por
 * construção — trava C2). Re-medição SÓ em `resize` (rAF-coalescida) e em
 * `document.fonts.ready` (o swap da Newsreader muda as métricas do H1) —
 * NUNCA por quadro (zero layout-read no caminho quente).
 *
 * Perf: escrita rAF-coalescida com skip-se-inalterado (|Δ| < 0.01) — custo
 * por quadro O(nº de folhas) só quando o valor muda de verdade.
 */
type OpcoesProximidade = {
  /** Seletor das folhas DENTRO do container (ex.: `.palavra-hero`). */
  seletor: string;
  /** Raio de influência em px (default 220 — vizinhas do span sob o cursor
      acendem parcialmente; a queda é smoothstep, orgânica). */
  alcance?: number;
  /** Custom property 0..1 escrita POR FOLHA (default `--palavra-prox`). */
  propriedade?: string;
  /**
   * Seletor (entre as folhas) da(s) que TAMBÉM recebem a posição X
   * normalizada 0..1 do cursor dentro da própria folha (default: nenhuma)
   * — usado pelo sheen responsivo da palavra "fonte" (background-position
   * derivada em CSS, range [5%,95%] garantido por construção no calc).
   */
  seletorX?: string;
  /** Custom property da posição X (default `--palavra-x`). */
  propriedadeX?: string;
};

type OpcoesPonteiro = {
  /**
   * Seletor CSS do elemento que recebe `--mx`/`--my` sob o ponteiro,
   * DENTRO do container observado — habilita delegação (ex.: `.cartao-ticker`
   * numa grade inteira, um único listener para N cards, em vez de um hook
   * por card). Omitido: o próprio container recebe as variáveis (uso de
   * superfície única, ex. o hero).
   */
  seletorAlvo?: string;
  /**
   * Folha(s) que RECEBEM a escrita de `--mx`/`--my` (perf, gate 3.2): custom
   * property herdada escrita num container invalida o estilo da subárvore
   * inteira a cada quadro; escrever direto em cada FOLHA que consome a var
   * (sprites `.foco-luz*`, `.glifo-fantasma`) invalida 1 elemento por folha
   * (~-80% de custo de recálculo medido no hero). Missão MATÉRIA VIVA
   * (Onda 1A): aceita também uma LISTA de folhas — a luminária dupla tem 3
   * sprites + o glifo-fantasma, todos alimentados por UM listener/rAF (as
   * escritas por quadro continuam O(nº de folhas), nunca de subárvore). A
   * GEOMETRIA continua medida no alvo/container (é a referência de centro).
   * A referência (ref único ou array) deve ser ESTÁVEL entre renders
   * (useRef/useMemo) — é dependência do efeito. Só faz sentido no modo de
   * superfície única — ignorado quando `seletorAlvo` está presente (nos
   * cards o `::after` precisa da var no próprio card).
   */
  escreverEm?: FolhaDeEscrita | ReadonlyArray<FolhaDeEscrita>;
  /**
   * NOVO (APOTEOSE, aditivo/retrocompatível — LEI §4): modo por-folha de
   * proximidade (ver `OpcoesProximidade`). Quando presente SEM
   * `seletorAlvo`/`escreverEm`, o hook NÃO escreve `--mx`/`--my` (escrever
   * custom property herdada num container-wrapper por quadro invalidaria a
   * subárvore inteira — exatamente o anti-padrão que `escreverEm` evita);
   * escreve SÓ as props de proximidade nas folhas. A referência deve ser
   * ESTÁVEL entre renders (module const/useMemo) — é dependência do efeito.
   * Consumidores existentes (FocoLuz/GradeFoco/ilha da TESE) não passam
   * este campo e mantêm comportamento idêntico.
   */
  proximidade?: OpcoesProximidade;
};

/** Retângulo de folha cacheado em coordenadas de PÁGINA + último valor
    escrito (skip-se-inalterado). */
type FolhaProximidade = {
  el: HTMLElement;
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  ultimoProx: number;
  ultimoX: number;
  recebeX: boolean;
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
  { seletorAlvo, escreverEm, proximidade }: OpcoesPonteiro = {},
): void {
  const prefereReduzido = usePrefereReduzido();

  useEffect(() => {
    const container = containerRef.current;
    if (!container || prefereReduzido) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia(QUERY_HOVER_FINO).matches) return;

    // ---- Modo proximidade (APOTEOSE, aditivo) — ver OpcoesProximidade ----
    // Alias já estreitado (o guard acima não atravessa function declaration
    // içada — TS18047 em `medir`).
    const raiz: HTMLElement = container;
    const alcanceProx = proximidade?.alcance ?? 220;
    const propProx = proximidade?.propriedade ?? "--palavra-prox";
    const propX = proximidade?.propriedadeX ?? "--palavra-x";
    // Proximidade "pura" (sem seletorAlvo/escreverEm) suprime --mx/--my:
    // o container do organismo é um wrapper com subárvore — custom property
    // herdada escrita nele por quadro invalidaria a subárvore inteira.
    const escreveMxMy = !proximidade || Boolean(seletorAlvo || escreverEm);
    let folhasProx: FolhaProximidade[] = [];
    let cancelado = false;
    let idQuadroMedida = 0;

    function medir() {
      if (!proximidade || cancelado) return;
      const els = raiz.querySelectorAll<HTMLElement>(proximidade.seletor);
      const novas: FolhaProximidade[] = [];
      els.forEach((el) => {
        // Caixa de LAYOUT (offset*): ignora o transform do próprio span
        // (keyframe palavra-compoe em voo) — o ancoradouro é o offsetParent,
        // que por trava C2 nunca é transformado (gBCR dele é confiável).
        const pai = el.offsetParent instanceof HTMLElement ? el.offsetParent : null;
        const base = pai ? pai.getBoundingClientRect() : { left: 0, top: 0 };
        const left = base.left + window.scrollX + el.offsetLeft;
        const top = base.top + window.scrollY + el.offsetTop;
        novas.push({
          el,
          left,
          top,
          right: left + el.offsetWidth,
          bottom: top + el.offsetHeight,
          width: el.offsetWidth || 1,
          ultimoProx: -1,
          ultimoX: -1,
          recebeX: proximidade.seletorX ? el.matches(proximidade.seletorX) : false,
        });
      });
      folhasProx = novas;
    }

    function limparProximidade() {
      for (const folha of folhasProx) {
        folha.el.style.removeProperty(propProx);
        if (folha.recebeX) folha.el.style.removeProperty(propX);
        folha.ultimoProx = -1;
        folha.ultimoX = -1;
      }
    }

    // Re-medição coalescida (resize) — nunca no caminho quente do pointermove.
    function aoRedimensionar() {
      window.cancelAnimationFrame(idQuadroMedida);
      idQuadroMedida = window.requestAnimationFrame(medir);
    }

    // Elemento que recebeu --mx/--my por último (o card sob o cursor, na
    // delegação; ou o próprio container, no uso de superfície única) — só
    // ele precisa ser limpo ao trocar de alvo ou ao sair.
    let alvoAtual: HTMLElement | null = null;
    // Última leitura de pointermove pendente de aplicar no próximo quadro.
    let pendente: { x: number; y: number; alvo: HTMLElement } | null = null;
    let quadroAgendado = false;
    let idQuadro = 0;

    function limpar(alvo: HTMLElement | null) {
      if (!alvo) return;
      for (const destino of destinosDeEscrita(alvo)) {
        destino.style.removeProperty("--mx");
        destino.style.removeProperty("--my");
      }
    }

    // Roda no máximo 1x por quadro (rAF): lê a geometria do alvo e escreve
    // --mx/--my relativos ao CENTRO dele (as camadas de luz já nascem
    // centralizadas — ver os offsets `calc(var(--mx) - Nvmax)` em
    // globals.css/cinema/luz.css — então um deslocamento a partir do centro
    // é exatamente o que as mantém sob o ponteiro).
    // Onde escrever: na delegação, sempre o card sob o cursor (o `::after`
    // dele precisa da var); em superfície única, a(s) folha(s) indicada(s)
    // por `escreverEm` (perf) ou o próprio container como fallback.
    function destinosDeEscrita(alvo: HTMLElement): HTMLElement[] {
      if (seletorAlvo || !escreverEm) return [alvo];
      const refs = Array.isArray(escreverEm) ? escreverEm : [escreverEm];
      const folhas: HTMLElement[] = [];
      for (const ref of refs) {
        if (ref.current) folhas.push(ref.current);
      }
      return folhas.length > 0 ? folhas : [alvo];
    }

    function aplicar() {
      quadroAgendado = false;
      if (!pendente) return;
      const { x, y, alvo } = pendente;
      if (escreveMxMy) {
        const r = alvo.getBoundingClientRect();
        const mx = `${x - (r.left + r.width / 2)}px`;
        const my = `${y - (r.top + r.height / 2)}px`;
        for (const destino of destinosDeEscrita(alvo)) {
          destino.style.setProperty("--mx", mx);
          destino.style.setProperty("--my", my);
        }
      }
      if (proximidade && folhasProx.length > 0) {
        // Cursor em coordenadas de página (compatível com o cache dos
        // rects — scroll entre o evento e o rAF é ≤1 quadro, irrelevante).
        const px = x + window.scrollX;
        const py = y + window.scrollY;
        for (const folha of folhasProx) {
          // Distância ao RETÂNGULO (não ao centro): cursor sobre qualquer
          // ponto de uma palavra larga = proximidade máxima; a queda começa
          // na borda. Smoothstep para o decaimento orgânico.
          const dx = px < folha.left ? folha.left - px : px > folha.right ? px - folha.right : 0;
          const dy = py < folha.top ? folha.top - py : py > folha.bottom ? py - folha.bottom : 0;
          const dist = Math.hypot(dx, dy);
          let t = 1 - dist / alcanceProx;
          let prox = 0;
          if (t > 0) {
            if (t > 1) t = 1;
            prox = t * t * (3 - 2 * t);
          }
          // Skip-se-inalterado (|Δ|<0.01); a 2ª cláusula garante o pouso
          // EXATO em 0 (nunca deixa resíduo 0.00x preso na folha).
          if (Math.abs(prox - folha.ultimoProx) >= 0.01 || (prox === 0 && folha.ultimoProx !== 0)) {
            folha.el.style.setProperty(propProx, prox.toFixed(3));
            folha.ultimoProx = prox;
          }
          if (folha.recebeX) {
            let nx = (px - folha.left) / folha.width;
            if (nx < 0) nx = 0;
            else if (nx > 1) nx = 1;
            if (Math.abs(nx - folha.ultimoX) >= 0.01) {
              folha.el.style.setProperty(propX, nx.toFixed(3));
              folha.ultimoX = nx;
            }
          }
        }
      }
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
      limparProximidade();
      alvoAtual = null;
      pendente = null;
    }

    if (proximidade) {
      // Medição inicial (layout já commitado quando o efeito roda) + quando
      // as fontes assentarem (swap da Newsreader muda as métricas do H1).
      medir();
      if (typeof document !== "undefined" && document.fonts?.ready) {
        document.fonts.ready
          .then(() => {
            if (!cancelado) medir();
          })
          .catch(() => {
            /* FontFaceSet rejeitado: fica a medição do layout atual */
          });
      }
      window.addEventListener("resize", aoRedimensionar, { passive: true });
    }

    container.addEventListener("pointermove", aoMover, { passive: true });
    container.addEventListener("pointerleave", aoSair, { passive: true });
    // pointercancel (raro com mouse/caneta, possível em híbridos): mesmo
    // tratamento de saída — limpa e volta ao neutro via transition CSS.
    container.addEventListener("pointercancel", aoSair, { passive: true });

    return () => {
      cancelado = true;
      container.removeEventListener("pointermove", aoMover);
      container.removeEventListener("pointerleave", aoSair);
      container.removeEventListener("pointercancel", aoSair);
      if (proximidade) {
        window.removeEventListener("resize", aoRedimensionar);
        window.cancelAnimationFrame(idQuadroMedida);
      }
      // Cancela quadro pendente para nenhum `aplicar()` órfão escrever em nó
      // desmontado após o cleanup.
      window.cancelAnimationFrame(idQuadro);
      limpar(alvoAtual);
      // Reduce ligado AO VIVO cai aqui (deps): as folhas voltam ao estado
      // nominal sem resíduo de --palavra-prox/--palavra-x.
      limparProximidade();
    };
  }, [containerRef, seletorAlvo, escreverEm, proximidade, prefereReduzido]);
}
