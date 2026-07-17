// "Chrome" editorial compartilhado pela tese legada (TeseView.tsx) E pelas 4
// seções novas do envelope (SecaoMetricasSetor/Valuation/Tecnica/Consenso) +
// os 3 componentes de gráfico. Extraído para módulo PRÓPRIO (em vez de viver
// dentro de TeseView.tsx e ser importado de lá) de propósito: TeseView.tsx
// importa `Secao*`/`Grafico*`, e esses importariam de volta `TeseView.tsx`
// se este chrome continuasse morando lá — um ciclo de módulos ES. Este
// arquivo não importa nada de `Secao*`/`Grafico*`/`TeseView`, então o grafo
// de import fica em árvore (aqui → sem volta).

import type { ReactNode } from "react";

import { classesReveal, Reveal, useReveal } from "@/components/motion/Reveal";

// Disclaimer regulatório de NÃO-recomendação. NUNCA pode sumir: se o backend
// não enviar o aviso, caímos numa constante fixa no front (conformidade).
// Reaproveitado também para o aviso fixo de Valuation ("NÃO é preço-alvo
// nem recomendação") e de Consenso ("a plataforma reporta, não endossa") —
// mesmo peso visual/semântico: aviso de compliance sempre visível.
export function AvisoBanner({ aviso }: { aviso: string }) {
  const texto =
    aviso?.trim() ||
    "Não é recomendação de investimento. Tese estruturada a partir de dados públicos; a decisão é do leitor.";
  return (
    <div role="note" className="flex items-start gap-3 border-l-4 border-aviso-borda bg-aviso-fundo px-5 py-4">
      <span className="mt-0.5 shrink-0 font-sans text-label font-semibold uppercase tracking-[0.16em] text-aviso-texto">
        Aviso
      </span>
      <p className="text-ui text-aviso-texto">{texto}</p>
    </div>
  );
}

// Badge "Dado não encontrado" (Lacuna Declarada, assinatura de motion):
// outline tracejado expande e dissolve 1x — mesma hierarquia de uma
// citação, nunca a de erro. Reaproveitado pelas 4 seções novas sempre que
// um `valor` do envelope vem `null`.
export function BadgeLacuna({ texto }: { texto: string }) {
  const { ref, armado, revelado } = useReveal<HTMLSpanElement>();
  return (
    <span
      ref={ref}
      className={classesReveal(
        "lacuna-declarada",
        armado,
        revelado,
        "inline-flex w-fit items-center bg-aviso-fundo px-2 py-1 font-mono text-meta font-semibold uppercase tracking-[0.1em] text-aviso-texto",
      )}
    >
      {texto}
    </span>
  );
}

// Impressão de Régua + cláusula numerada mono: abre cada seção do report
// (markdown legado E as 4 seções novas). `useReveal` único (em vez de dois
// <Reveal>) para a régua e o título dispararem exatamente juntos, com o
// título assentando 80ms depois (`.atraso-regua`) — ver DESIGN-TOKENS.md §3.
// As seções novas do envelope chamam com `numero={null}` (não fazem parte
// da numeração "1. Fundamentos"…"8. Lacunas" emitida pelo LLM) e
// `lacunas={false}` (a régua "de alerta" segue reservada à seção "Lacunas"
// de verdade; lacunas internas de um bloco novo viram um aviso pontual
// dentro do corpo, não recolorem o título inteiro).
export function CabecalhoSecao({
  tituloId,
  numero,
  texto,
  lacunas,
}: {
  tituloId: string;
  numero: string | null;
  texto: string;
  lacunas: boolean;
}) {
  const { ref, armado, revelado } = useReveal<HTMLDivElement>();
  // OURIVESARIA 1A (§3-C1): a régua h-1 (4px — a ÚNICA régua de 4px do
  // site, 4× o peso de todo o resto) harmoniza com a casa: vira a
  // `.talha-capitulo` (traço de ouro 2.5rem×2px, bancada.css §4), mesma
  // impressão `.reveal-regua`. A variante de ALERTA da seção "Lacunas"
  // mantém o papel (âmbar `--warn-border`) via `.talha-capitulo--aviso`.
  // gap-6 = pós-fio único 1.5rem (--ritmo-pos-fio; era 1rem).
  return (
    <div ref={ref} className="flex flex-col gap-6">
      <div
        className={classesReveal(
          "reveal-regua",
          armado,
          revelado,
          lacunas ? "talha-capitulo talha-capitulo--aviso" : "talha-capitulo",
        )}
      />
      <h3
        id={tituloId}
        className={classesReveal(
          undefined,
          armado,
          revelado,
          `atraso-regua flex flex-wrap items-baseline gap-x-3 font-display text-h2 font-semibold tracking-tight ${
            lacunas ? "text-aviso-texto" : "text-ink"
          }`,
        )}
      >
        {numero && (
          <span className={`font-mono text-ui font-semibold ${lacunas ? "text-aviso-texto" : "text-brasa-texto"}`}>
            {numero}.
          </span>
        )}
        {texto}
      </h3>
    </div>
  );
}

// Wrapper de seção completo (régua + título + conteúdo) para as 4 seções
// novas — mesma casca de `<section>` que as seções vindas do markdown usam
// em TeseView.tsx, sem repetir `aria-labelledby`/estrutura 4x.
export function SecaoEnvelope({
  id,
  titulo,
  children,
}: {
  id: string;
  titulo: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="flex flex-col gap-6">
      <CabecalhoSecao tituloId={`${id}-titulo`} numero={null} texto={titulo} lacunas={false} />
      <Reveal className="flex flex-col gap-6">{children}</Reveal>
    </section>
  );
}
