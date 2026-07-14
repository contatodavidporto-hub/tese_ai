"use client";

// Navegação alfabética de /glossario · DONA: onda COPY (APOTEOSE, crit. 11).
// Mesmo padrão do IndiceNav de /como-funciona (contrato do stub
// cinema/glossario.css): scrollspy via useSecaoAtiva + Sublinhado de Brasa
// permanente no ativo (`.sublinhado-brasa[aria-current="location"]`,
// globals.css) — reaproveita o wayfinding da casa, não reinventa.
// Único pedaço client da rota: a página (`page.tsx`) segue Server Component
// e só passa os grupos (dados já resolvidos) como prop.

import { useSecaoAtiva } from "@/components/motion/useSecaoAtiva";
import type { GrupoAlfabetico } from "@/lib/glossario";

export function IndiceLetras({ grupos }: { grupos: readonly GrupoAlfabetico[] }) {
  const slugs = grupos.flatMap((g) => g.verbetes.map((v) => v.slug));
  const ativo = useSecaoAtiva(slugs);

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
                const ehAtivo = ativo === v.slug;
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
