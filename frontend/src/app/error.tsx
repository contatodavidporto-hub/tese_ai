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
import Link from "next/link";

import { Marca } from "@/components/site/Marca";

export default function ErroGlobal({ reset }: { error: Error; reset: () => void }) {
  return (
    <main
      id="conteudo"
      className="mx-auto flex w-full max-w-xl flex-1 flex-col items-start gap-5 px-4 py-24 sm:px-6"
    >
      {/* Selo sempre com o wordmark (cláusula M-c do guia de marca). */}
      <span className="entrada-hero flex items-center gap-2 text-ink">
        <Marca variante="carimbo" />
        <span className="font-display text-h3 font-semibold">Tese AI</span>
      </span>
      <span className="entrada-hero i-1 border border-erro-borda bg-erro-fundo px-2 py-1 font-sans text-label font-semibold uppercase tracking-[0.16em] text-erro-texto">
        Falha técnica
      </span>
      <h1 className="entrada-hero i-2 font-display text-h1 font-semibold tracking-tight text-ink">
        Esta edição não fechou.
      </h1>
      <p className="entrada-hero i-3 max-w-md text-body leading-relaxed text-ink-2">
        Um erro inesperado interrompeu o carregamento desta página. Nenhum
        dado foi perdido — as teses já geradas continuam disponíveis no
        Histórico deste navegador.
      </p>
      <div className="entrada-hero i-4 flex flex-wrap gap-3">
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
