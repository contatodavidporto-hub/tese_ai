"use client";

// D2 (CORRECOES-RODADA-1.md): scrollspy do índice lateral de /como-funciona —
// marca a cláusula ativa com `aria-current="location"` + Sublinhado de Brasa
// permanente (globals.css: `.sublinhado-brasa[aria-current="location"]`).
// Único pedaço client desta página: a página em si (`page.tsx`) continua
// Server Component, e só passa `items` (dados já resolvidos) como prop —
// nada de estado/efeito sobe além do necessário para o scrollspy.

import { useSecaoAtiva } from "@/components/motion/useSecaoAtiva";

type ItemIndice = { href: string; label: string };

function idDoHref(href: string): string {
  return href.replace(/^#/, "");
}

export function IndiceNav({ items }: { items: readonly ItemIndice[] }) {
  const ids = items.map((item) => idDoHref(item.href));
  const ativo = useSecaoAtiva(ids);

  return (
    <nav aria-label="Sumário desta página" className="text-ui">
      <p className="mb-3 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3 [font-stretch:72%]">
        Sumário
      </p>
      <ol className="flex flex-col gap-1 border-l border-line">
        {items.map((item) => {
          const ehAtivo = ativo === idDoHref(item.href);
          return (
            <li key={item.href}>
              <a
                href={item.href}
                aria-current={ehAtivo ? "location" : undefined}
                className={`sublinhado-brasa block border-l-2 py-1 pl-3 font-sans text-ui leading-snug transition-colors duration-[var(--dur-tick)] hover:text-ink ${
                  ehAtivo ? "border-brasa-texto text-ink" : "border-transparent text-ink-2"
                }`}
              >
                {item.label}
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
