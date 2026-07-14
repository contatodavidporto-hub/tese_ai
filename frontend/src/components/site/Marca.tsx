// Marca "O Um Lastreado" — o selo de citação da Tese AI.
// Missão APOTEOSE (2026-07-13), critério 1 · dona: onda CHROME.
// SPEC: .maestro/marca/veredito-marca.md §4 (SVG canônico + enxertos
// MANDATÓRIOS) + plano-apoteose.md §2 D1 / §3 crit.1.
//
// Anatomia (forma = produto): colchetes editoriais serifados (o aparato de
// citação, flare de cunha nas pontas) + índice "1" em brasa (a evidência,
// mesma família do pin do hero) + fio hairline (a trilha de auditoria)
// descendo à régua da fonte (o lastro). Nenhuma afirmação flutua.
//
// REGRAS DE USO (guia de marca — veredito §5.8):
//   (a) o símbolo é INSEPARÁVEL do wordmark "Tese AI" (M-c: sozinho, "[1]"
//       poderia ler como "somos o nº 1" — sempre com a palavra ao lado);
//   (b) ouro/sheen só ≥24px (variante joia); (c) safira plena só no
//       hover/focus (dosagem C3 — repouso = 2 materiais, tinta + brasa);
//   (d) o "1" nunca muda de cor por estado de sistema nem pulsa em loop.
//
// CONTRATO TÉCNICO:
// - Server Component FOLHA: zero import, zero hook, zero "use client" — é
//   deliberadamente importável também por client boundaries (error.tsx a
//   usa DENTRO da fronteira de erro; NUNCA adicionar aqui import de árvore
//   server ou dependência que possa falhar em runtime — D9/à prova de
//   re-erro).
// - SVG inline, SÓ atributos de apresentação e classes (zero `style=`,
//   zero <style> interno — CSP diff-zero; SVG inline é markup).
// - ENTRADA ZERO (enxerto mandatório C1 do veredito): nada aqui anima no
//   load — o selo nasce 100% visível; todo comportamento vivo mora em
//   src/styles/cinema/marca.css (hover/focus/scroll, CSS puro, zero JS no
//   Header — R2 intacta).
// - Cores da variante joia vêm das classes .marca-* (marca.css → tokens
//   semânticos --ink-primary/--accent-action/--accent-confianca/
//   --valor-brilho): trocam de tema sozinhas. A variante carimbo é
//   monocromática (currentColor) — rodapé/fronteira de erro são assinatura,
//   não palco (sem fio de repouso translúcido, sem sheen).

type MarcaProps = {
  /**
   * "joia" (padrão, ≥24px — header): paths com classes `.marca-*`, vivos
   * via cinema/marca.css. "carimbo" (≤20px — footer/error): monocromático
   * `currentColor`, estático, sem sheen.
   */
  variante?: "joia" | "carimbo";
  /** Lado do quadrado em px (default: 28 joia / 20 carimbo). */
  tamanho?: number;
  className?: string;
};

export function Marca({ variante = "joia", tamanho, className }: MarcaProps) {
  const lado = tamanho ?? (variante === "joia" ? 28 : 20);

  if (variante === "carimbo") {
    // Variante monocromática (veredito §4.3) — já dominada por fills;
    // estática por contrato (rodapé é assinatura, não palco).
    return (
      <svg
        viewBox="0 0 32 32"
        width={lado}
        height={lado}
        aria-hidden="true"
        focusable="false"
        fill="none"
        className={className}
      >
        <path d="M10.7 5H5v22h5.7v-2.5l-3.6.35V7.15l3.6.35z" fill="currentColor" />
        <path d="M21.3 5H27v22h-5.7v-2.5l3.6.35V7.15l-3.6.35z" fill="currentColor" />
        <path
          d="M18 6.8V19.2H15.6V10.2C14.8 10.7 13.9 11.05 12.8 11.2V9.6C14 9.3 15 8.6 15.8 7.6C16 7.35 16.2 7.05 16.35 6.8Z"
          fill="currentColor"
        />
        <path d="M16.8 19.2v4" stroke="currentColor" strokeWidth="1" />
        <path d="M11.8 24h8.4" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  }

  // Variante joia (veredito §4.4) — o comportamento vivo (repouso 2
  // materiais, safira no hover, sheen one-shot, :active no índice,
  // recolhimento do fio por scroll) é 100% de cinema/marca.css.
  return (
    <svg
      viewBox="0 0 32 32"
      width={lado}
      height={lado}
      aria-hidden="true"
      focusable="false"
      fill="none"
      className={className ? `marca-svg ${className}` : "marca-svg"}
    >
      <path className="marca-colchete" d="M10.7 5H5v22h5.7v-2.5l-3.6.35V7.15l3.6.35z" />
      <path className="marca-colchete" d="M21.3 5H27v22h-5.7v-2.5l3.6.35V7.15l-3.6.35z" />
      <path
        className="marca-um"
        d="M18 6.8V19.2H15.6V10.2C14.8 10.7 13.9 11.05 12.8 11.2V9.6C14 9.3 15 8.6 15.8 7.6C16 7.35 16.2 7.05 16.35 6.8Z"
      />
      <path className="marca-fio" d="M16.8 19.2v4" strokeWidth="1" />
      <path className="marca-regra" d="M11.8 24h8.4" strokeWidth="2" />
      <path className="marca-brilho" d="M12.5 24h3" strokeWidth="2" />
    </svg>
  );
}
