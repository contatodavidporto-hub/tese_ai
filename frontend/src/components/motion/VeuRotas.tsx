"use client";

// VeuRotas — vigia do véu de SAÍDA de rota (#veu-rota-saida do layout.tsx).
// Missão MATÉRIA VIVA, Onda 1D (emenda R3 — véu de saída sem reset).
//
// O LinkCinema liga a classe .veu-rota-saindo no overlay e navega no
// animationend (com timeout de segurança). Este componente é o RESET: sem
// ele, o `animation-fill-mode: both` deixaria o véu parado em scaleY(1)
// cobrindo a rota nova para sempre. Duas redes, ambas via classList (CSP):
//
//   1. usePathname: a CADA troca de rota (inclusive popstate/voltar durante
//      a animação) a classe é removida — o overlay volta ao repouso
//      scaleY(0) e o guard de clique duplo do LinkCinema rearma.
//   2. animationcancel: se a animação de saída for abortada no meio (ex.:
//      preferências de motion mudando, classe removida por fora), desarma
//      também — nunca fica véu preso.
//
// Renderiza null (zero DOM próprio — o overlay é estático no layout.tsx,
// fora de qualquer stacking context novo). ZERO gsap (R2); custo de bundle
// ínfimo em todas as rotas (gate: first-load de /tese ≤ +3KB com LinkCinema).

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const CLASSE_SAIDA = "veu-rota-saindo";

export function VeuRotas() {
  const pathname = usePathname();

  // R3: troca de rota (push nosso, popstate, back/forward) desarma o véu.
  useEffect(() => {
    document.getElementById("veu-rota-saida")?.classList.remove(CLASSE_SAIDA);
  }, [pathname]);

  // animationcancel: aborto no meio da saída também desarma (idempotente —
  // remover classe já removida é no-op; remoção pós-fim natural não dispara
  // cancel, só a interrupção de animação em curso).
  useEffect(() => {
    const veu = document.getElementById("veu-rota-saida");
    if (!veu) return;
    const desarmar = () => veu.classList.remove(CLASSE_SAIDA);
    veu.addEventListener("animationcancel", desarmar);
    return () => veu.removeEventListener("animationcancel", desarmar);
  }, []);

  return null;
}
