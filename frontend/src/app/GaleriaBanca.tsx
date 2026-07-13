"use client";

// Banca de Teses — 2º momento horizontal da landing (missão MATÉRIA VIVA,
// §3 critério 3, enxerto C; posse Onda 1E). Troca a GRADE teaser da galeria
// por um rail horizontal NATIVO (overflow-x + scroll-snap via utilitários
// Tailwind — ZERO listener de wheel, zero GSAP, custo de JS ~zero): o
// deslocamento lateral é 100% do navegador; o JS daqui só cuida de setas e
// dots acessíveis (padrão a11y do FilmstripDimensoes: role="list",
// aria-current="location", scrollIntoView SEM `behavior` — herda o
// scroll-behavior do CSS, que já vira `auto` sob prefers-reduced-motion).
//
// Reuso deliberado (contrato da Onda 0): GradeFoco (o <ul> com foco frio
// por delegação — `.banca-rail` entra via className; filhos <li> DIRETOS
// preservados: semântica de lista + seletor `.cartao-ticker` da delegação
// intocados) e CartaoTese (mesma anatomia de card-manchete; hairline e luz
// de card intactas — nenhuma segunda anatomia).
//
// Carimbo de entrada por card: CSS puro `view(inline)` em cinema/banca.css
// (classe `.banca-carimbo` no wrapper do card) — scrubbed, reversível, sob
// @supports; fallback = visível. NENHUM <Reveal> por card aqui: a varredura
// de segurança do motor Reveal ignora clipagem por ancestral com overflow e
// marcaria todos os cards como "alcançados" no 1º quadro (pegadinha
// documentada no recon; precedente FilmstripDimensoes).
//
// CONTRATO (Onda 2 — page.tsx): substituir o bloco <GradeFoco>…</GradeFoco>
// da galeria teaser por
//   <GaleriaBanca papeis={exemplos} dataCarteira={DATA_CARTEIRA_IBOV} />
// — a MESMA interface de dados que a grade atual consome (PapelB3[] +
// data ISO da carteira); sem `.stagger`/`.i-N`/<Reveal> por card.

// APOTEOSE (2026-07-13, onda BANCA — crit. 3/5): o rail ganha (a) palco 3D
// (usePalco + cinema/palco.css, autorização S1/S3), (b) arrasto de mouse com
// inércia snap-safe (useRailDrag + classe .banca-arrastando), (c) hairline de
// progresso substituta da scrollbar oculta (scroll-timeline sob @supports +
// fallback JS passivo D6 abaixo). Setas/dots/teclado/IO/view(inline) do rail
// permanecem EXATAMENTE como estavam.

import { useCallback, useEffect, useRef, useState } from "react";

import { GradeFoco } from "@/components/motion/GradeFoco";
import { usePalco } from "@/components/motion/usePalco";
import { useRailDrag } from "@/components/motion/useRailDrag";
import { CartaoTese } from "@/components/teses/CartaoTese";
import type { PapelB3 } from "@/lib/tickers";

export type GaleriaBancaProps = {
  papeis: readonly PapelB3[];
  dataCarteira: string;
};

export default function GaleriaBanca({ papeis, dataCarteira }: GaleriaBancaProps) {
  const cardRefs = useRef<Array<HTMLLIElement | null>>([]);
  const envelopeRef = useRef<HTMLDivElement | null>(null);
  const barraRef = useRef<HTMLSpanElement | null>(null);
  const [ativo, setAtivo] = useState(0);

  // Palco 3D (mola do tilt) + drag do rail — ambos acham o `.banca-rail`
  // dentro do envelope (o <ul> vive no GradeFoco, que não expõe ref).
  usePalco(envelopeRef);
  useRailDrag(envelopeRef);

  // D6 — fallback da hairline (FF stable sem scroll-driven animations até
  // ~155): scroll passivo → rAF → --banca-prog NA PRÓPRIA barra (regra 5 do
  // DESIGN-TOKENS). Onde há suporte, a animação CSS dirige tudo e este
  // efeito nem liga (nunca dois escritores).
  useEffect(() => {
    if (typeof CSS !== "undefined" && CSS.supports("animation-timeline: --a")) return;
    const rail = envelopeRef.current?.querySelector<HTMLElement>(".banca-rail");
    const barra = barraRef.current;
    if (!rail || !barra) return;
    let quadro = 0;
    const pintar = () => {
      const max = rail.scrollWidth - rail.clientWidth;
      barra.style.setProperty("--banca-prog", max > 0 ? String(rail.scrollLeft / max) : "0");
    };
    const aoRolar = () => {
      window.cancelAnimationFrame(quadro);
      quadro = window.requestAnimationFrame(pintar);
    };
    pintar();
    rail.addEventListener("scroll", aoRolar, { passive: true });
    return () => {
      rail.removeEventListener("scroll", aoRolar);
      window.cancelAnimationFrame(quadro);
    };
  }, []);

  // Card ativo por IO com root = o próprio rail (nunca a viewport inteira,
  // nunca listener de `scroll` cru) — mesma métrica do FilmstripDimensoes
  // (`intersectionRatio`, a certa para um root horizontal). Reversível por
  // natureza: o estado segue o scroll nos dois sentidos.
  useEffect(() => {
    const cards = cardRefs.current.filter((el): el is HTMLLIElement => el !== null);
    const rail = cards[0]?.parentElement;
    if (!rail || cards.length === 0) return;

    // Semântica de lista explícita no <ul> do GradeFoco (o preflight do
    // Tailwind zera list-style e o Safari/VoiceOver deixa de expor listas
    // sem marcador — mesma auditoria 1.3.1 do FilmstripDimensoes).
    // GradeFoco não aceita atributos extras e não é posse desta onda;
    // atributo ARIA setado 1x no mount — é ATRIBUTO, não estilo (nada de
    // setAttribute('style'): carve-out CSP intacto).
    rail.setAttribute("role", "list");
    rail.setAttribute("aria-label", "Banca de teses de exemplo — role para o lado");

    const observer = new IntersectionObserver(
      (entradas) => {
        setAtivo((atual) => {
          const maisVisivel = entradas.reduce((melhor, entrada) =>
            entrada.intersectionRatio > melhor.intersectionRatio ? entrada : melhor,
          );
          if (maisVisivel.intersectionRatio < 0.5) return atual;
          const indice = cards.indexOf(maisVisivel.target as HTMLLIElement);
          return indice === -1 ? atual : indice;
        });
      },
      { root: rail, threshold: [0, 0.25, 0.5, 0.75, 1] },
    );
    cards.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [papeis.length]);

  // `scrollIntoView` SEM `behavior` explícito: herda o `scroll-behavior` do
  // CSS (`smooth` global no html; `auto` sob prefers-reduced-motion) — fixar
  // "smooth" no JS sobrescreveria a preferência do usuário (mesma decisão
  // documentada do FilmstripDimensoes).
  const irPara = useCallback((indice: number) => {
    cardRefs.current[indice]?.scrollIntoView({ inline: "start", block: "nearest" });
  }, []);

  return (
    // `.banca-envelope` (banca.css): timeline-scope da hairline — a barra é
    // IRMÃ do rail e precisa do ancestral comum para enxergar --banca-rail.
    <div ref={envelopeRef} className="banca-envelope flex flex-col gap-4">
      {/* Controles FORA do container clipado (o anel de foco nunca é
          cortado pelo overflow do rail — guarda C2 do red-team, mesmo
          racional do FilmstripDimensoes). */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <ol role="list" aria-label="Ir direto a uma tese de exemplo" className="flex flex-wrap items-center gap-1">
          {papeis.map((papel, i) => (
            <li key={papel.ticker}>
              {/* Dot 8px dentro de alvo de toque 24px (WCAG 2.5.8). Estados
                  com contraste de UI provado: inativo `border-field`
                  (≥3.15:1 até no pico da luz), ativo `bg-brasa-texto`
                  (mesmo papel de "tab ativa" do design system). */}
              <button
                type="button"
                onClick={() => irPara(i)}
                aria-label={`Ir para ${papel.ticker}`}
                aria-current={i === ativo ? "location" : undefined}
                className="group flex h-6 w-6 items-center justify-center"
              >
                <span
                  aria-hidden
                  className={`h-2 w-2 rounded-full border transition-colors duration-[var(--dur-tick)] ${
                    i === ativo
                      ? "border-brasa-texto bg-brasa-texto"
                      : "border-field bg-transparent group-hover:border-ink-3"
                  }`}
                />
              </button>
            </li>
          ))}
        </ol>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => irPara(Math.max(ativo - 1, 0))}
            disabled={ativo === 0}
            aria-label="Tese anterior"
            className="seta-filmstrip seta-filmstrip--prev flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              ←
            </span>
          </button>
          <button
            type="button"
            onClick={() => irPara(Math.min(ativo + 1, papeis.length - 1))}
            disabled={ativo === papeis.length - 1}
            aria-label="Próxima tese"
            className="seta-filmstrip seta-filmstrip--next flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              →
            </span>
          </button>
        </div>
      </div>

      {/* Rail nativo: snap-x mandatory, sem sequestro de wheel — o mesmo
          <ul> de foco frio por delegação da grade anterior, agora rolável.
          `overscroll-x-contain` evita o encadeamento do overscroll lateral
          (trackpad) virar navegação de histórico no meio do arrasto. */}
      <GradeFoco
        seletorAlvo=".cartao-ticker"
        className="banca-rail flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain scroll-px-4 pb-2 sm:scroll-px-6"
      >
        {papeis.map((papel, i) => (
          <li
            key={papel.ticker}
            ref={(el) => {
              cardRefs.current[i] = el;
            }}
            className="w-64 shrink-0 snap-start"
          >
            {/* `.banca-carimbo` no wrapper, NUNCA no <li>: transform animado
                no próprio alvo de snap deslocaria a snap area (a spec usa a
                bounding box transformada) — o wrapper anima, o <li> fica
                estável para o snap e para o IO. */}
            <div className="banca-carimbo h-full">
              <CartaoTese papel={papel} dataCarteira={dataCarteira} />
            </div>
          </li>
        ))}
      </GradeFoco>

      {/* Hairline de progresso (crit. 5/D6) — affordance substituta da
          scrollbar oculta (padrão do filmstrip: 2px, brasa, transform-only;
          estilos em banca.css). Decorativa para leitor de tela: o
          wayfinding acessível segue nos dots aria-current + setas. */}
      <div className="banca-progresso" aria-hidden="true">
        <span ref={barraRef} className="banca-progresso__barra" />
      </div>
    </div>
  );
}
