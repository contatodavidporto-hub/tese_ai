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
 * Perf (gate 3.2): `--mx`/`--my` são escritas NO PRÓPRIO sprite
 * (`escreverEm`), não no container — custom property herdada escrita no
 * container invalida o estilo da subárvore inteira a cada quadro de
 * pointermove (~6ms/frame medidos no hero, 28 elementos); escrita na folha
 * invalida 1 elemento. A geometria continua medida no container (é a
 * referência de centro do sprite). `@property inherits:false` foi REJEITADO:
 * quebraria a herança container→sprite dos cards (::after) — ver relatório
 * do gate de performance.
 *
 * Uso: `<div className="tem-foco ..."><FocoLuz />{...conteúdo...}</div>`.
 * `<FocoLuz/>` precisa ser filho DIRETO do container `.tem-foco` (é dele que
 * o callback ref lê `parentElement`).
 */
export function FocoLuz() {
  const containerRef = useRef<HTMLElement | null>(null);
  const spriteRef = useRef<HTMLDivElement | null>(null);

  const refSprite = useCallback((el: HTMLDivElement | null) => {
    spriteRef.current = el;
    containerRef.current = el?.parentElement ?? null;
  }, []);

  usePonteiro(containerRef, { escreverEm: spriteRef });

  return <div ref={refSprite} aria-hidden className="foco-luz" />;
}
