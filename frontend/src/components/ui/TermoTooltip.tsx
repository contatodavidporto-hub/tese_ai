"use client";

/**
 * TermoTooltip — tooltip de termo/métrica (Onda 0, missão "APOTEOSE",
 * critério 11). WCAG 1.4.13 (Content on Hover or Focus): DISMISSIBLE (Esc
 * fecha sem mover o ponteiro), HOVERABLE (o ponteiro pode entrar no popup
 * sem que ele feche) e PERSISTENT (não some sozinho por timeout — só
 * quando o foco/hover deixa o componente inteiro, ou por Esc).
 *
 * Folha irmã (dona única: cinema/tooltip.css) resolve posicionamento/
 * entrada; este arquivo nunca escreve `style=` — só classList (via ref,
 * medição única ao abrir) e className condicional (atributo `class`, fora
 * do escopo de `style-src`).
 *
 * D7 (plano-apoteose.md §2): termos de métricas do backend consomem
 * `o_que_mede` do payload (prop `definicao` vinda de onde a página chamar
 * este componente); termos fixos do site vêm de `lib/glossario.ts` (dono:
 * COPY). Termo SEM definição -> fallback SILENCIOSO (renderiza só
 * `children`, sem botão/popup) — gate anti-alucinação visual: zero
 * definição inventada.
 */

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

type TermoTooltipProps = {
  /** Nome do termo, exibido no cabeçalho do popup (herda a tipografia do
   * contexto — sem font-family própria). */
  termo: string;
  /** Texto âncora: o trecho sublinhado que dispara o tooltip. */
  children: ReactNode;
  /**
   * Definição do termo. AUSENTE -> fallback silencioso (só `children`,
   * sem tooltip). Nunca inventar uma definição no lugar de uma ausente.
   */
  definicao?: string;
  /** Slug em `/glossario` (ex.: "p-vp") — habilita o link "ver glossário →". */
  slug?: string;
};

/** Espaço mínimo acima do gatilho (px) para o popup abrir para cima; abaixo
 * disso, abre para baixo (`.tt-abaixo`). Medido uma vez por abertura. */
const ESPACO_MINIMO_ACIMA_PX = 180;

export function TermoTooltip({ termo, children, definicao, slug }: TermoTooltipProps) {
  const id = useId();
  const [aberto, setAberto] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const popupRef = useRef<HTMLSpanElement | null>(null);
  const timeoutFechar = useRef<number | null>(null);

  // useCallback (deps vazias — só tocam refs/setState, identidade estável):
  // permite declarar `fecharAgora` na dependência do listener de Esc abaixo
  // sem reexecutar o efeito a cada render.
  const cancelarFechamento = useCallback(() => {
    if (timeoutFechar.current !== null) {
      window.clearTimeout(timeoutFechar.current);
      timeoutFechar.current = null;
    }
  }, []);

  const abrir = useCallback(() => {
    cancelarFechamento();
    setAberto(true);
  }, [cancelarFechamento]);

  // Hoverable/persistent: sair do gatilho ou perder foco AGENDA o
  // fechamento com uma folga curta — se o ponteiro/foco reentrar em
  // QUALQUER descendente do wrapper (o próprio popup incluso) antes disso,
  // `abrir()` cancela o timeout. Nunca fecha por timeout enquanto o
  // usuário ainda está sobre/dentro do componente.
  const agendarFechamento = useCallback(() => {
    cancelarFechamento();
    timeoutFechar.current = window.setTimeout(() => setAberto(false), 140);
  }, [cancelarFechamento]);

  const fecharAgora = useCallback(() => {
    cancelarFechamento();
    setAberto(false);
  }, [cancelarFechamento]);

  // Mede o espaço UMA vez por abertura (não a cada frame) e alterna o lado
  // só via classList — zero style inline (CSP; regra da casa).
  useEffect(() => {
    if (!aberto) return;
    const gatilho = wrapperRef.current;
    const popup = popupRef.current;
    if (!gatilho || !popup) return;
    const r = gatilho.getBoundingClientRect();
    popup.classList.toggle("tt-abaixo", r.top < ESPACO_MINIMO_ACIMA_PX);
  }, [aberto]);

  // Dismissible: Esc fecha sem mover o ponteiro.
  useEffect(() => {
    if (!aberto) return;
    function aoTeclado(ev: KeyboardEvent) {
      if (ev.key === "Escape") fecharAgora();
    }
    document.addEventListener("keydown", aoTeclado);
    return () => document.removeEventListener("keydown", aoTeclado);
  }, [aberto, fecharAgora]);

  useEffect(() => cancelarFechamento, [cancelarFechamento]);

  // Fallback silencioso (D7): termo sem definição não vira tooltip.
  if (!definicao) {
    return <>{children}</>;
  }

  return (
    <span
      ref={wrapperRef}
      className="tt-wrapper"
      onMouseEnter={abrir}
      onMouseLeave={agendarFechamento}
      onFocus={abrir}
      onBlur={agendarFechamento}
    >
      <button
        type="button"
        className="border-b border-dashed border-ink-3 text-inherit transition-colors duration-[var(--dur-tick)] ease-ink hover:border-brasa-texto hover:text-brasa-texto focus-visible:border-brasa-texto focus-visible:text-brasa-texto"
        aria-describedby={aberto ? id : undefined}
        aria-expanded={aberto}
        onClick={() => (aberto ? fecharAgora() : abrir())}
      >
        {children}
      </button>
      {aberto && (
        <span
          ref={popupRef}
          role="tooltip"
          id={id}
          className="tt-popup sombra-elevada max-w-[min(22rem,80vw)] rounded-md border border-line-strong bg-elevated p-3 text-left text-ui text-ink"
        >
          <span className="mb-1 block font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
            {termo}
          </span>
          <span className="block">{definicao}</span>
          {slug && (
            <a
              href={`/glossario#${slug}`}
              className="sublinhado-brasa mt-2 inline-block font-sans text-label font-semibold text-brasa-texto"
            >
              ver glossário →
            </a>
          )}
        </span>
      )}
    </span>
  );
}
