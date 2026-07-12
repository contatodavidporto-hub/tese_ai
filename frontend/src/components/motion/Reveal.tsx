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

// ---------------------------------------------------------------------------
// Motor de observação compartilhado (fix rodada 2, CORRECOES-RODADA-1.md /
// achado do QA final): a versão anterior criava UM `new IntersectionObserver`
// POR elemento (`useReveal` chamado ~101x na página da tese com muitas
// citações). Sob volume alto + scroll rápido/contínuo, algumas dessas ~101
// instâncias simultâneas perdiam a notificação de interseção (3–42/101
// presos, medido em 4 métodos pelo QA — nunca é lógica quebrada: visitar o
// elemento via `scrollIntoView` sempre revela, confirmando que é perda de
// notificação sob volume, não um bug de `is-armed`/`is-revealed`).
//
// Correção: UM `IntersectionObserver` POR CONFIGURAÇÃO DE THRESHOLD (não por
// elemento) — mesmo padrão de registro central que `useSecaoAtiva.ts` já usa
// para o scrollspy. Um `Map<Element, registro>` guarda o callback de cada
// instância; o observer da config despacha para o registro certo e se
// desliga daquele elemento (`unobserve` + remoção do Map) assim que revela —
// "roda 1x" continua valendo por elemento, só o observer físico é
// compartilhado.
//
// Belt-and-suspenders: além do observer, uma VARREDURA de segurança roda (a)
// a CADA evento `scroll` (throttled a 1x/quadro via `requestAnimationFrame`
// — cobre inclusive a "cauda" de eventos que um jump grande/instantâneo
// dispara por até ~1,5s antes do navegador considerar o scroll encerrado),
// (b) em `scrollend` nativo onde existe, (c) num debounce `scroll` de
// ~150ms nos navegadores sem `scrollend`, e (d) uma vez ao registrar o
// primeiro elemento (cobre quem já nasce dentro da viewport, antes de
// qualquer scroll). Confere por `getBoundingClientRect` quem já foi
// "alcançado" pelo scroll e revela na marra qualquer um que o observer
// ainda não tenha notificado. Custo O(pendentes): cada revelação (via
// observer OU varredura) remove o elemento do Map, então a varredura
// encolhe com o tempo até não ter mais nada a conferir.
// ---------------------------------------------------------------------------

type RegistroReveal = {
  threshold: number;
  onEntra: () => void;
};

const registroReveal = new Map<Element, RegistroReveal>();
const observadoresPorThreshold = new Map<number, IntersectionObserver>();
let varreduraAgendada = false;
let varreduraGlobalLigada = false;

function obterObserverReveal(threshold: number): IntersectionObserver {
  let obs = observadoresPorThreshold.get(threshold);
  if (obs) return obs;
  obs = new IntersectionObserver(
    (entradas) => {
      for (const entrada of entradas) {
        if (!entrada.isIntersecting) continue;
        const reg = registroReveal.get(entrada.target);
        if (!reg) continue; // já revelado por outra via (ex.: a varredura) — ignora
        reg.onEntra();
        obs!.unobserve(entrada.target);
        registroReveal.delete(entrada.target);
      }
    },
    { threshold },
  );
  observadoresPorThreshold.set(threshold, obs);
  return obs;
}

function varreduraReveal() {
  if (registroReveal.size === 0) return;
  const vh = window.innerHeight;
  const vw = window.innerWidth;
  // Copia as entradas antes de iterar: `onEntra` pode disparar setState
  // síncrono o bastante para reentrar (não deveria, mas o Map não gosta de
  // ser mutado durante a própria iteração `for...of`).
  for (const [el, reg] of Array.from(registroReveal)) {
    const r = el.getBoundingClientRect();
    // "Já alcançado" (topo acima do fim da viewport), não "ainda visível"
    // (`bottom > 0` sozinho excluiria isso): um salto instantâneo (tecla
    // End, `scrollTo` direto) pula direto para o destino sem nunca renderizar
    // quadros intermediários — o IntersectionObserver real NUNCA vê os
    // elementos do meio do caminho "passarem" pela viewport, e eles ficam
    // ACIMA da viewport final, não afundo dela. Se a varredura exigisse
    // "ainda dentro da viewport" (`bottom > 0`), esses elementos ficariam
    // presos para sempre — exatamente o cenário medido pelo QA (73–91/101
    // presos no salto instantâneo). Manter só a checagem horizontal
    // (`left`/`right`) — a vertical usa a semântica "o scroll já passou por
    // aqui", que é a garantia real contra conteúdo que nunca reapareceu.
    const alcancado = r.top < vh && r.right > 0 && r.left < vw;
    if (!alcancado) continue;
    reg.onEntra();
    obterObserverReveal(reg.threshold).unobserve(el);
    registroReveal.delete(el);
  }
}

// Agenda uma varredura no PRÓXIMO QUADRO (`requestAnimationFrame`) — não
// `requestIdleCallback`: medido que esperar o navegador considerar "ocioso"
// (mesmo com `timeout` baixo) atrasa o settle bem além do que um quadro
// custaria, especialmente em jumps grandes/instantâneos numa página pesada
// (ver o comentário sobre a "cauda" de eventos de scroll em
// `ligarVarreduraGlobal` abaixo). `rAF` roda garantido no próximo quadro
// (~16ms), já depois do navegador ter recomputado layout — exatamente o
// momento certo para `getBoundingClientRect` ler geometria atualizada.
// Deduplicado por `varreduraAgendada`: várias chamadas antes do quadro
// rodar viram uma varredura só.
function agendarVarreduraReveal() {
  if (varreduraAgendada || typeof window === "undefined") return;
  varreduraAgendada = true;
  window.requestAnimationFrame(() => {
    varreduraAgendada = false;
    varreduraReveal();
  });
}

// Liga os listeners globais (módulo inteiro, não por instância) só na
// primeira vez que algo é observado — evitam custo em rotas sem `.reveal`.
function ligarVarreduraGlobal() {
  if (varreduraGlobalLigada || typeof window === "undefined") return;
  varreduraGlobalLigada = true;

  // Checagem via variável (não `"onscrollend" in window` direto no `if`):
  // narrowing do TS em cima de `window` por uma propriedade que a lib.dom
  // não declara em todo alvo de compilação produz `never` no ramo `else`.
  const suportaScrollend = "onscrollend" in window;
  if (suportaScrollend) {
    window.addEventListener("scrollend", agendarVarreduraReveal, { passive: true });
  }

  // Varredura POR QUADRO durante o próprio scroll (não só depois dele
  // "parar"): medido que um jump grande/instantâneo (scrollTo/tecla End numa
  // página de ~40 mil px, como a tese com 101 citações) faz o navegador
  // disparar uma "cauda" de eventos `scroll` por até ~1,5s ANTES de
  // considerar o scroll encerrado — se a varredura só rodasse ao final
  // (`scrollend`/debounce), o usuário veria conteúdo preso por esse 1,5s
  // inteiro. Disparando a cada evento `scroll` (throttled a 1x/quadro pelo
  // `agendarVarreduraReveal` acima), o elemento já revela no PRIMEIRO quadro
  // em que foi "alcançado" — o resto da cauda de eventos só reconfirma um
  // registro que já encolheu. Custo por quadro é O(registro pendente), que
  // esvazia rápido (cada acerto remove o elemento do Map).
  window.addEventListener("scroll", agendarVarreduraReveal, { passive: true });

  if (!suportaScrollend) {
    // Fallback extra (Safari mais antigo sem `scrollend`): debounce de
    // ~150ms por cima do `scroll` — rede de segurança adicional para quando
    // nem `scrollend` nem a varredura por quadro acima (que já cobre a
    // maioria dos casos) bastarem.
    let timer: number | undefined;
    window.addEventListener(
      "scroll",
      () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(agendarVarreduraReveal, 150);
      },
      { passive: true },
    );
  }

  // Varredura inicial numa folga ociosa: cobre elementos já dentro da
  // viewport no load, antes de qualquer scroll — rede de segurança extra,
  // não substitui o observer (que continua sendo o disparo primário).
  agendarVarreduraReveal();
}

// Registra um elemento no observer compartilhado da config de `threshold`
// informada; devolve a função de limpeza (chamada no cleanup do efeito do
// hook, igual à API antiga de `observer.disconnect()`).
function observarElementoReveal(el: Element, threshold: number, onEntra: () => void): () => void {
  ligarVarreduraGlobal();
  registroReveal.set(el, { threshold, onEntra });
  obterObserverReveal(threshold).observe(el);
  return () => {
    obterObserverReveal(threshold).unobserve(el);
    registroReveal.delete(el);
  };
}

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
 * Roda 1x: ao revelar, sai do registro do observer compartilhado
 * (guard-rail: reveals nunca se repetem no scroll).
 *
 * Observer compartilhado + varredura de segurança (fix rodada 2): não cria
 * mais `new IntersectionObserver` por elemento — registra no motor de
 * `observarElementoReveal` (topo deste arquivo), que usa UM observer por
 * config de `threshold` para a página inteira, mais uma varredura de
 * `getBoundingClientRect` em `scrollend`/idle inicial como rede de segurança
 * contra notificação perdida sob volume alto. Ver comentário do motor acima
 * para o diagnóstico completo.
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
    // QA 2026-07-12: além de não armar, DESARMA um `armado` que tenha
    // "grudado" na corrida de hidratação — o snapshot SSR-safe do
    // useSyncExternalStore devolve `false` no 1º render mesmo com
    // reduced-motion ativo; o efeito roda e arma, e quando reroda com o
    // valor real precisa reverter (senão a garantia "reduced-motion nunca
    // tem .is-armed" fica dependendo só da rede de segurança do CSS).
    if (!elemento || prefereReduzido) {
      setArmado(false);
      return;
    }

    setArmado(true);

    // `onEntra` só roda de forma assíncrona (callback do IntersectionObserver
    // compartilhado OU da varredura de scrollend/idle) — nunca síncrono
    // dentro do corpo deste efeito, então não corre o risco que a regra
    // react-hooks/set-state-in-effect cobre (setState síncrono na montagem
    // do efeito). `setArmado(true)` acima é o único setState síncrono aqui,
    // e já é o padrão intencional documentado na doc do hook (progressive
    // enhancement: SSR sem `.is-armed`, JS arma no commit do efeito).
    return observarElementoReveal(elemento, threshold, () => setRevelado(true));
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
