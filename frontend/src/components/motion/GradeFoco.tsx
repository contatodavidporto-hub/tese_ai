"use client";

import { useRef, type ReactNode } from "react";

import { usePonteiro } from "@/components/motion/usePonteiro";

type GradeFocoProps = {
  children: ReactNode;
  className?: string;
  /**
   * Seletor CSS do card que recebe `--mx`/`--my` sob o ponteiro (ex.:
   * `.cartao-ticker`) — delegação: UM listener de `pointermove` para a
   * grade inteira, mais barato em listeners que um `usePonteiro` por card
   * (§4 da direção de arte deixa a escolha explícita a este critério).
   */
  seletorAlvo: string;
};

/**
 * Ilha client fina: envolve uma grade de `<CartaoTese>` (Server Component,
 * renderizada por `page.tsx`) num `<ul>` que liga o foco frio dos cards
 * (`.cartao-ticker.tem-foco::after`, globals.css) por delegação — mantém
 * `page.tsx` como Server Component; só esta borda vira client.
 */
export function GradeFoco({ children, className, seletorAlvo }: GradeFocoProps) {
  const ref = useRef<HTMLUListElement | null>(null);
  usePonteiro(ref, { seletorAlvo });

  return (
    <ul ref={ref} className={className}>
      {children}
    </ul>
  );
}
