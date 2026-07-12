"use client";

import { useCallback, useRef } from "react";

import { usePonteiro } from "@/components/motion/usePonteiro";

/**
 * Camada-sprite da luminária de ponteiro (§2/§4,
 * .maestro/direcao-de-arte-cinema.md) — um `<div>` `aria-hidden` puramente
 * decorativo, posicionado e animado inteiramente por CSS (`.foco-luz`,
 * globals.css). Ilha client fina: liga o hook `usePonteiro` ao elemento PAI
 * deste componente na árvore (o container `.tem-foco` que o envolve) via
 * callback ref, para que a superfície que hospeda o foco (ex.: a `<section>`
 * do hero em page.tsx) continue sendo Server Component — só este componente
 * vira client.
 *
 * Uso: `<div className="tem-foco ..."><FocoLuz />{...conteúdo...}</div>`.
 * `<FocoLuz/>` precisa ser filho DIRETO do container `.tem-foco` (é dele que
 * o callback ref lê `parentElement`).
 */
export function FocoLuz() {
  const containerRef = useRef<HTMLElement | null>(null);

  const refSprite = useCallback((el: HTMLDivElement | null) => {
    containerRef.current = el?.parentElement ?? null;
  }, []);

  usePonteiro(containerRef);

  return <div ref={refSprite} aria-hidden className="foco-luz" />;
}
