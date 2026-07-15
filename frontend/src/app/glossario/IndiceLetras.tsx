"use client";

// Navegação alfabética de /glossario · DONA: raia 3C (FRONTEND HORIZONTE,
// missão 2026-07-14 — direção §9 "O Lapidário A–Z").
//
// HORIZONTE: o índice deixa de ser uma lista aninhada (letra > cada verbete)
// e vira a RÉGUA DE TALHA — full-height, fixa à borda esquerda no desktop,
// UMA marca por letra (o gesto do polegar num dicionário físico: leva à
// letra, não ao verbete exato — os verbetes individuais já estão todos
// visíveis nas 2 colunas do corpo, com Ctrl+F/scroll normal cobrindo a busca
// fina). `useSecaoAtiva` (INTOCADO — mesmo hook de IndiceNav) passa a
// observar as SEÇÕES de letra (`letra-a`, `letra-b`…) em vez dos slugs de
// verbete: mesmo mecanismo de scrollspy, alvo diferente.
//
// Mobile (sem espaço para uma régua fixa): mantém a lista completa dobrável
// de hoje (letra + todos os verbetes), renderizada por `<IndiceLetras
// variante="lista" />` dentro do `<details>` de page.tsx.

import { useSecaoAtiva } from "@/components/motion/useSecaoAtiva";
import type { GrupoAlfabetico } from "@/lib/glossario";

type Props = {
  grupos: readonly GrupoAlfabetico[];
  /** "regua" (default, desktop fixo) | "lista" (mobile, dentro do <details>). */
  variante?: "regua" | "lista";
};

export function IndiceLetras({ grupos, variante = "regua" }: Props) {
  const idsLetra = grupos.map((g) => `letra-${g.letra.toLowerCase()}`);
  const slugsVerbete = grupos.flatMap((g) => g.verbetes.map((v) => v.slug));
  const ativoPorLetra = useSecaoAtiva(idsLetra);
  const ativoPorVerbete = useSecaoAtiva(slugsVerbete);

  if (variante === "lista") {
    return (
      <nav aria-label="Índice alfabético do glossário" className="text-ui">
        <p className="mb-3 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3 [font-stretch:72%]">
          A–Z
        </p>
        <ol className="flex flex-col gap-4">
          {grupos.map((grupo) => (
            <li key={grupo.letra}>
              <p
                aria-hidden
                className="mb-1 font-mono text-meta font-semibold uppercase text-ink-3"
              >
                {grupo.letra}
              </p>
              <ol className="flex flex-col gap-1 border-l border-line">
                {grupo.verbetes.map((v) => {
                  const ehAtivo = ativoPorVerbete === v.slug;
                  return (
                    <li key={v.slug}>
                      <a
                        href={`#${v.slug}`}
                        aria-current={ehAtivo ? "location" : undefined}
                        className={`sublinhado-brasa block border-l-2 py-1 pl-3 font-sans text-ui leading-snug transition-colors duration-[var(--dur-tick)] hover:text-ink ${
                          ehAtivo
                            ? "border-brasa-texto text-ink"
                            : "border-transparent text-ink-2"
                        }`}
                      >
                        {v.termo}
                      </a>
                    </li>
                  );
                })}
              </ol>
            </li>
          ))}
        </ol>
      </nav>
    );
  }

  // Régua de talha: STICKY (não `fixed`) dentro da própria coluna do layout
  // de /glossario (page.tsx: `.b-palco lg:flex`) — correção do defeito 2
  // (gate de geometria, wt-horizonte 2026-07-14): uma régua `fixed` ignora a
  // posição do documento e cobre o que estiver por baixo dela o tempo todo
  // (inclusive o masthead, bem acima na página); como coluna real do flex
  // row, ela só existe (e só "gruda") dentro do próprio corpo de verbetes,
  // nunca sobrepõe nada. `top`/altura usam o mesmo contrato `--altura-tarja`
  // de antes; `shrink-0` trava a largura no flex row. Mono, uma marca por
  // letra distribuída pela altura inteira (`justify-between`). z-index
  // abaixo dos véus de rota (z-40 < Tarja z-50): é navegação de conteúdo,
  // nunca disputa a pilha do chrome regulatório.
  return (
    <nav
      aria-label="Índice alfabético do glossário"
      className="talha-regua sticky top-[var(--altura-tarja)] z-10 hidden h-[calc(100svh-var(--altura-tarja))] w-16 shrink-0 flex-col overflow-y-auto border-r border-line bg-page py-6 lg:flex"
    >
      <ol className="flex h-full flex-col justify-between">
        {grupos.map((grupo) => {
          const id = `letra-${grupo.letra.toLowerCase()}`;
          const ehAtivo = ativoPorLetra === id;
          return (
            <li key={grupo.letra}>
              <a
                href={`#${id}`}
                aria-current={ehAtivo ? "location" : undefined}
                aria-label={`Ir para os termos com ${grupo.letra}`}
                className={`talha-marca flex min-h-6 w-full flex-col items-center gap-1 px-2 py-1 font-mono text-meta uppercase transition-colors duration-[var(--dur-tick)] ${
                  ehAtivo ? "text-brasa-texto" : "text-ink-3 hover:text-ink"
                }`}
              >
                <span
                  aria-hidden
                  className={`h-px w-4 transition-colors duration-[var(--dur-tick)] ${
                    ehAtivo ? "bg-valor-brilho" : "bg-line-strong"
                  }`}
                />
                {grupo.letra}
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
