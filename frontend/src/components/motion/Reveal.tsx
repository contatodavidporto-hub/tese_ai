"use client";

import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type HTMLAttributes,
  type ReactNode,
} from "react";

type OpcoesReveal = {
  /** Fração visível do elemento para disparar a revelação (0–1). Padrão 0.2. */
  threshold?: number;
};

type EstadoReveal<T extends HTMLElement> = {
  ref: React.RefObject<T | null>;
  /** true assim que o componente confirma JS ativo e arma a transição CSS. */
  armado: boolean;
  /** true quando a assinatura deve rodar (entrou em view, ou reduced-motion). */
  revelado: boolean;
};

const QUERY_REDUZIDO = "(prefers-reduced-motion: reduce)";

function inscreverReduzido(notificar: () => void): () => void {
  const mql = window.matchMedia(QUERY_REDUZIDO);
  mql.addEventListener("change", notificar);
  return () => mql.removeEventListener("change", notificar);
}

function instantaneoReduzido(): boolean {
  return window.matchMedia(QUERY_REDUZIDO).matches;
}

function instantaneoReduzidoServidor(): boolean {
  // SSR nunca sabe a preferência do usuário — assume "sem preferência" (o
  // valor real chega no client via useSyncExternalStore logo após montar,
  // sem causar hydration mismatch).
  return false;
}

/**
 * `prefers-reduced-motion: reduce`, lido via `useSyncExternalStore` (padrão
 * React para estado externo ao navegador) — evita tanto o mismatch de
 * hidratação (SSR sempre reporta `false`) quanto o anti-padrão de chamar
 * `setState` diretamente dentro de um efeito.
 */
function usePrefereReduzido(): boolean {
  return useSyncExternalStore(
    inscreverReduzido,
    instantaneoReduzido,
    instantaneoReduzidoServidor,
  );
}

/**
 * Hook de revelação do design system BRASA EDITORIAL — o motor por trás de
 * TODAS as assinaturas de entrada em CSS puro definidas em `globals.css`
 * (Impressão de Régua `.reveal-regua`, Assentamento de Tipo `.reveal`, Fila
 * do Ticker `.reveal-ticker`, Pin de Citação `.citacao-pin`, Lacuna
 * Declarada `.lacuna-declarada`).
 *
 * Contrato CSP: zero `style=` inline — só alterna classes (`is-armed`,
 * `is-revealed`); a animação real vive inteira em `globals.css`.
 *
 * Progressive enhancement: enquanto `armado` é false (SSR e o primeiro
 * paint, antes da hidratação), NENHUMA classe de estado inicial esconde o
 * conteúdo — todas as classes de assinatura só ganham `opacity`/`transform`
 * quando combinadas com `.is-armed`. Se o JS nunca carregar, o conteúdo
 * permanece visível: "sem JS no HTML, sem animação".
 *
 * Reduced motion: `matchMedia` decide ANTES de armar qualquer observer — se
 * o usuário pediu menos movimento, aplica `revelado=true` direto (a
 * assinatura nunca chega a rodar; ver também o `@media (prefers-reduced-
 * motion: reduce)` em globals.css como rede de segurança adicional).
 *
 * Roda 1x: ao revelar, desconecta o observer (guard-rail: reveals nunca
 * se repetem no scroll).
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>({
  threshold = 0.2,
}: OpcoesReveal = {}): EstadoReveal<T> {
  const ref = useRef<T | null>(null);
  const [armado, setArmado] = useState(false);
  const [revelado, setRevelado] = useState(false);
  const prefereReduzido = usePrefereReduzido();

  useEffect(() => {
    const elemento = ref.current;
    // Reduced motion: nunca arma a transição nem observa — a assinatura
    // simplesmente não roda (o booleano final vira `true` por derivação,
    // logo abaixo, sem passar por setState dentro do efeito).
    if (!elemento || prefereReduzido) return;

    setArmado(true);

    const observer = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (entrada.isIntersecting) {
            setRevelado(true);
            observer.unobserve(entrada.target);
          }
        }
      },
      { threshold },
    );
    observer.observe(elemento);
    return () => observer.disconnect();
  }, [threshold, prefereReduzido]);

  return { ref, armado, revelado: revelado || prefereReduzido };
}

/**
 * Monta a string de classes de uma assinatura de revelação — uso interno do
 * `<Reveal>` abaixo, e também exportado para quem usar `useReveal` direto
 * num elemento próprio (ex.: aplicar `.reveal-regua` numa `<hr>` de seção).
 *
 * `variante` é uma das classes de assinatura de `globals.css`
 * (`"reveal-regua"`, `"reveal-ticker"`, `"citacao-pin"`, `"lacuna-
 * declarada"`) — omitida, o padrão é Assentamento de Tipo (`.reveal` puro).
 */
export function classesReveal(
  variante: string | undefined,
  armado: boolean,
  revelado: boolean,
  extra?: string,
): string {
  const base = variante ?? "reveal";
  return [base, armado && "is-armed", revelado && "is-revealed", extra]
    .filter(Boolean)
    .join(" ");
}

type RevealProps = {
  children: ReactNode;
  className?: string;
  threshold?: number;
  /**
   * Classe de assinatura a usar no lugar do padrão `.reveal` (Assentamento
   * de Tipo) — ex.: `"reveal-regua"`, `"reveal-ticker"`, `"lacuna-
   * declarada"`. Ver tabela completa em `frontend/DESIGN-TOKENS.md`.
   */
  variant?: string;
} & Omit<HTMLAttributes<HTMLDivElement>, "className">;

/**
 * Wrapper de conveniência sobre `useReveal`: entra em view, uma vez, com a
 * assinatura escolhida. Renderiza sempre um `<div>` — para aplicar a
 * revelação a um elemento que já existe (um `<h2>`, uma `<section>`, uma
 * `<hr>` de régua) sem acrescentar um wrapper ao DOM, use `useReveal`
 * diretamente e monte a `className` com `classesReveal`.
 */
export function Reveal({ children, className, threshold, variant, ...resto }: RevealProps) {
  const { ref, armado, revelado } = useReveal<HTMLDivElement>({ threshold });

  return (
    <div ref={ref} className={classesReveal(variant, armado, revelado, className)} {...resto}>
      {children}
    </div>
  );
}
