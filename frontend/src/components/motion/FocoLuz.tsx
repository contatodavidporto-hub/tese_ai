"use client";

import { useCallback, useMemo, useRef, type RefObject } from "react";

import { usePonteiro } from "@/components/motion/usePonteiro";

/**
 * Luminária dupla com massa (missão MATÉRIA VIVA, plano §3 crit.4 camada 1 —
 * Onda 1A): TRÊS camadas-sprite `aria-hidden` puramente decorativas,
 * irmãs dentro do container `.tem-foco`, estilizadas em `cinema/luz.css`:
 *
 *   `.foco-luz-penumbra` — anel EXTERNO ameixa (~310°), o corpo mais lento;
 *   `.foco-luz`          — o BLOOM (90vmax, stop 45%, ~700ms --ease-cena);
 *   `.foco-luz-nucleo`   — o NÚCLEO rápido (36vmax, chega em ~180ms).
 *
 * A física é a assinatura única da casa: núcleo rápido, corpo com atraso —
 * cada sprite persegue o MESMO par `--mx`/`--my` com transition própria
 * (180ms/700ms/900ms, todas `--ease-cena`); o lag escalonado é 100% CSS.
 *
 * Perf (gate 3.2 + MATÉRIA VIVA): `--mx`/`--my` são escritas EM CADA FOLHA
 * (`escreverEm` com lista) — nunca no container (custom property herdada
 * escrita no container invalida a subárvore inteira a cada quadro; ~-80% de
 * custo medido escrevendo na folha). UM listener/rAF alimenta as 3 folhas +
 * o `.glifo-fantasma` (contra-cursor −0.03×, hero.css): o glifo é montado
 * pela page.tsx como irmão dentro do MESMO `.tem-foco` e é descoberto aqui
 * via `querySelector` no mount — se não existir (outras superfícies
 * `.tem-foco`), é simplesmente ignorado.
 *
 * Uso: `<div className="tem-foco ..."><FocoLuz />{...conteúdo...}</div>`.
 * Os sprites precisam ser filhos DIRETOS do container `.tem-foco` (é dele
 * que o callback ref lê `parentElement` — a geometria/centro é do container).
 */
export function FocoLuz() {
  const containerRef = useRef<HTMLElement | null>(null);
  const nucleoRef = useRef<HTMLDivElement | null>(null);
  const bloomRef = useRef<HTMLDivElement | null>(null);
  const penumbraRef = useRef<HTMLDivElement | null>(null);
  const glifoRef = useRef<HTMLElement | null>(null);

  const refPenumbra = useCallback((el: HTMLDivElement | null) => {
    penumbraRef.current = el;
    const container = el?.parentElement ?? null;
    containerRef.current = container;
    // Glifo-fantasma (hero.css): folha IRMÃ dentro do mesmo .tem-foco,
    // server-rendered pela page.tsx — co-recebe --mx/--my para o
    // contra-cursor. Opcional por contrato (null fora do hero).
    glifoRef.current =
      container?.querySelector<HTMLElement>(".glifo-fantasma") ?? null;
  }, []);

  // Lista ESTÁVEL de folhas (dependência do efeito de usePonteiro): os refs
  // são caixas estáveis; folhas vazias (ex.: glifo ausente) são filtradas na
  // hora da escrita, dentro do hook.
  const folhas = useMemo<ReadonlyArray<RefObject<HTMLElement | null>>>(
    () => [nucleoRef, bloomRef, penumbraRef, glifoRef],
    [],
  );

  usePonteiro(containerRef, { escreverEm: folhas });

  // Ordem de pintura entre irmãos z-index:-1 = ordem do DOM (o último fica
  // por cima): penumbra (fundo) → bloom → núcleo (topo).
  return (
    <>
      <div ref={refPenumbra} aria-hidden className="foco-luz-penumbra" />
      <div ref={bloomRef} aria-hidden className="foco-luz" />
      <div ref={nucleoRef} aria-hidden className="foco-luz-nucleo" />
    </>
  );
}
