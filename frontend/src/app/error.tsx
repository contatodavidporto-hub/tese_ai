"use client";

// Fronteira de erro global: microcopy sóbria e tipográfica (nenhuma
// ilustração), par --erro-* (falha técnica — nunca o par de aviso, reservado
// à lacuna declarada). Mensagem amigável sem detalhes internos (stack/URLs
// ficam no console do servidor, não na tela do usuário).
//
// D9 (CORRECOES-RODADA-1.md): SEM Header nem Footer aqui, de propósito —
// este arquivo é uma fronteira de erro `"use client"` (contrato do Next para
// `error.tsx`), e o Footer compõe `ChipSaudeAoVivo` (Server Component
// assíncrono); misturar os dois é o tipo de composição frágil que pode
// disparar OUTRO erro dentro do próprio boundary de erro. `not-found.tsx`
// não tem essa restrição (é uma página normal, Server Component) e mantém o
// Header. O link abaixo é a única forma de navegação garantida daqui.
//
// Missão APOTEOSE (crit.10 — onda CHROME): intensidade CLIENT-ONLY e
// AUTOSSUFICIENTE, à prova de re-erro por construção:
// - Marca em variante carimbo (sem Header, a página precisa de assinatura):
//   Marca.tsx é FOLHA pura — zero import, zero hook, zero árvore server
//   (contrato documentado no próprio arquivo; nunca deixar de ser folha).
// - Entrada 100% CSS via `.entrada-hero` + stagger `.i-N` (globals.css):
//   animação INCONDICIONAL transform-only, nada nasce oculto (LCP-safe),
//   ZERO observer/JS — se o JS da página está quebrado, a entrada ainda
//   roda; reduced-motion já é tratado nominalmente no bloco de redução do
//   globals.css (transform zerado). Nenhum Reveal/LinkCinema aqui: <Link>
//   puro é a navegação mais garantida dentro de um boundary de erro.
//
// Missão HORIZONTE (2026-07-14 — "A Pedra Bruta", direcao-horizonte.md §9):
// - Migração D3/D5: `mx-auto max-w-xl` -> `.bancada` (mesma lei prosa
//   ≤68ch — bloco só texto+CTAs, E30 preservado); zero mudança na regra
//   "SEM Header/Footer" (D9-Apoteose, boundary de erro).
// - Mesma pedra bruta do not-found.tsx (SVG inline, `d` DUPLICADO — zero
//   import novo, mesmo raciocínio da pegadinha 3): aqui, CSS-only via
//   `.entrada-hero`/`.i-N` (NUNCA `<Reveal>` — este arquivo continua
//   autossuficiente, sem observer/hook que possa re-errar).
import Link from "next/link";

import { Marca } from "@/components/site/Marca";

export default function ErroGlobal({ reset }: { error: Error; reset: () => void }) {
  return (
    <main id="conteudo" className="bancada flex-1 items-start gap-5 py-24">
      {/* Selo sempre com o wordmark (cláusula M-c do guia de marca). */}
      <span className="entrada-hero flex items-center gap-2 text-ink">
        <Marca variante="carimbo" />
        <span className="font-display text-h3 font-semibold">Tese AI</span>
      </span>
      <svg
        viewBox="405 135 110 85"
        className="entrada-hero i-1 h-16 w-auto"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M 420 150 L 470 143 L 508 168 L 497 208 L 438 212 L 413 183 Z"
          className="nascimento-pedra-bruta"
        />
      </svg>
      <span className="entrada-hero i-2 border border-erro-borda bg-erro-fundo px-2 py-1 font-sans text-label font-semibold uppercase tracking-[0.16em] text-erro-texto">
        Falha técnica
      </span>
      <h1 className="entrada-hero i-3 font-display text-h1 font-semibold tracking-tight text-ink">
        Esta edição não fechou.
      </h1>
      <p className="entrada-hero i-4 text-body leading-relaxed text-ink-2">
        Um erro inesperado interrompeu o carregamento. Nenhum dado foi
        perdido — as teses já geradas continuam no Histórico deste
        navegador, com as mesmas citações e fontes.
      </p>
      <div className="entrada-hero i-5 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={reset}
          className="bg-brasa px-5 py-2.5 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
        >
          Tentar novamente
        </button>
        <Link
          href="/"
          className="border border-field px-5 py-2.5 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto"
        >
          Voltar ao início
        </Link>
      </div>
    </main>
  );
}
