"use client";

import {
  useCallback,
  useEffect,
  useRef,
  type ReactElement,
  type RefObject,
} from "react";

import {
  QUERY_HOVER_FINO,
  usePonteiro,
  usePrefereReduzido,
} from "@/components/motion/usePonteiro";

/**
 * H1-organismo (missão APOTEOSE 2026-07-13, LEI §3.2 — dona: onda HERO).
 *
 * (Extensão .tsx, não .ts: a ilha de conveniência `OrganismoH1` abaixo usa
 * JSX — mesmo idioma de FocoLuz.tsx; a alternativa createElement em .ts
 * reprova no lint react-hooks/refs, e o repositório não tem nenhum
 * eslint-disable como precedente. O especificador de import do contrato é
 * o MESMO: `@/components/motion/useOrganismoH1`.)
 *
 * Dá ao H1 do hero reatividade CONTÍNUA ao cursor, palavra a palavra: cada
 * `span.palavra-hero` recebe `--palavra-prox` (0..1, proximidade smoothstep
 * do ponteiro ao retângulo da palavra) e a palavra "fonte"
 * (`.palavra-hero-fonte`) recebe também `--palavra-x` (posição X normalizada
 * 0..1 do cursor dentro dela). O CSS de `cinema/hero.css` (§5) consome:
 * profundidade por `translate`/`scale` INDIVIDUAIS (o keyframe
 * `palavra-compoe` segue dono único do `transform`), luz por `color-mix`
 * com o par ouro em alfa contido, e — só após `animationend` da varredura —
 * o sheen de "fonte" atado ao cursor via `.sheen-vivo` (troca de dono por
 * classList; range [5%,95%] garantido por construção no calc da folha).
 *
 * Contratos honrados:
 * - CSP estrita: só `classList` + `style.setProperty` (CSSOM) — zero style
 *   inline/injetado (a escrita por quadro vive em usePonteiro).
 * - WCAG 2.2.2: TODO movimento é dirigido por input do usuário (pointermove
 *   → rAF; sem loop autônomo). Reduce = hook inteiro inerte (usePonteiro
 *   nem arma listener; o efeito do sheen abaixo idem) + bloco nominal em
 *   hero.css com estado assentado digno.
 * - Gate de dispositivo: `(hover:hover) and (pointer:fine)` — touch nunca
 *   liga (mesma QUERY dos hooks-irmãos).
 * - LCP/CLS: nada nasce oculto; translate/scale/color/background-position
 *   não participam de layout — zero mudança de layout por construção.
 *
 * Uso pela INTEGRAÇÃO (page.tsx): preferir a ilha `<OrganismoH1 />` abaixo
 * (padrão FocoLuz: sonda oculta descobre o container por `parentElement`) —
 * a page é Server Component e não pode chamar hook. Alternativa: um client
 * wrapper próprio com `useRef` + `useOrganismoH1(ref)` no wrapper do h1.
 */
const PROXIMIDADE_H1 = {
  seletor: ".palavra-hero",
  alcance: 220,
  propriedade: "--palavra-prox",
  seletorX: ".palavra-hero-fonte",
  propriedadeX: "--palavra-x",
} satisfies NonNullable<Parameters<typeof usePonteiro>[1]>["proximidade"];

// Opções ESTÁVEIS entre renders (dependência do efeito de usePonteiro):
// module const — nunca literal por render.
const OPCOES_H1 = { proximidade: PROXIMIDADE_H1 } as const;

/** Classe LITERAL que troca o dono do background-position do sheen (do
    keyframe `sheen-fonte`, fill both, para a regra viva de hero.css §5). */
const CLASSE_SHEEN_VIVO = "sheen-vivo";
const NOME_ANIMACAO_SHEEN = "sheen-fonte";

export function useOrganismoH1(
  containerRef: RefObject<HTMLElement | null>,
): void {
  // Camada 1 — proximidade por palavra (rects cacheados em resize +
  // fonts.ready; escrita rAF-coalescida por folha; gates reduce/hover
  // dentro do hook; em modo proximidade puro NÃO escreve --mx/--my).
  usePonteiro(containerRef, OPCOES_H1);

  // Camada 2 — troca de dono do sheen da palavra "fonte" após a varredura
  // única terminar (LEI §3.2: "sheen vira responsivo SÓ após animationend").
  const prefereReduzido = usePrefereReduzido();
  useEffect(() => {
    const container = containerRef.current;
    if (!container || prefereReduzido) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia(QUERY_HOVER_FINO).matches) return;

    const fonte = container.querySelector<HTMLElement>(".palavra-hero-fonte");
    if (!fonte || fonte.classList.contains(CLASSE_SHEEN_VIVO)) return;

    let cancelado = false;
    const entregar = () => {
      if (!cancelado) fonte.classList.add(CLASSE_SHEEN_VIVO);
    };

    // Caminho 1 (preciso, WAAPI): a varredura aparece em getAnimations()
    // desde a fase de delay e — por fill:both — segue lá depois de
    // terminada, então `finished` resolve NA HORA se já acabou (hidratação
    // tardia coberta). `catch`: animação cancelada (ex.: reduce ligado ao
    // vivo → animation:none) — o bloco nominal do CSS cobre o estado.
    const animacoes =
      typeof fonte.getAnimations === "function" ? fonte.getAnimations() : [];
    const sheen = animacoes.find(
      (a) => (a as CSSAnimation).animationName === NOME_ANIMACAO_SHEEN,
    );
    if (sheen) {
      sheen.finished.then(entregar).catch(() => {
        /* cancelada — estado nominal via CSS */
      });
      return () => {
        cancelado = true;
      };
    }

    // Caminho 2 (fallback sem WAAPI, ou @supports background-clip:text
    // reprovado — aí não existe varredura e a classe seria inerte de todo
    // modo, a regra .sheen-vivo vive DENTRO do mesmo @supports): escuta o
    // animationend. Se a varredura já tiver acabado antes deste efeito em
    // navegador sem getAnimations (borda raríssima), o keyframe fill:both
    // apenas segura o highlight em repouso — estado digno, sem quebra.
    const aoTerminar = (ev: AnimationEvent) => {
      if (ev.animationName === NOME_ANIMACAO_SHEEN) entregar();
    };
    fonte.addEventListener("animationend", aoTerminar);
    return () => {
      cancelado = true;
      fonte.removeEventListener("animationend", aoTerminar);
    };
    // Nota: a classe NÃO é removida no cleanup — se o reduce for ligado e
    // desligado ao vivo, o CSS nominal governa durante o reduce e, ao
    // voltar, o sheen já-entregue segue responsivo (sem replay da
    // varredura, que é deliberadamente única).
  }, [containerRef, prefereReduzido]);
}

/**
 * Ilha de conveniência para a INTEGRAÇÃO (page.tsx é Server Component):
 * renderiza uma SONDA oculta (`<span hidden aria-hidden>` — display:none,
 * zero layout/flex-item, zero LCP/CLS) e descobre o container por
 * `parentElement` no callback ref — mesmo idioma de FocoLuz.tsx.
 *
 * Onde plugar (recomendação, decisão final da INTEGRAÇÃO):
 * - como filha DIRETA da section#hero `.tem-foco` (irmã de <FocoLuz/>):
 *   superfície de eventos = o hero inteiro, coerente com luz/shader; OU
 * - como filha do `div[data-mascara-brasa]` (coluna de conteúdo): reação
 *   restrita à coluna. Os spans `.palavra-hero` são descobertos por
 *   querySelector DENTRO do container escolhido — ambos funcionam.
 */
export function OrganismoH1(): ReactElement {
  const containerRef = useRef<HTMLElement | null>(null);
  const refSonda = useCallback((el: HTMLSpanElement | null) => {
    containerRef.current = el?.parentElement ?? null;
  }, []);
  useOrganismoH1(containerRef);
  return <span ref={refSonda} hidden aria-hidden data-organismo-h1="" />;
}
