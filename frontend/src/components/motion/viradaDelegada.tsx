"use client";

/**
 * viradaDelegada — H1 da ONDA P (perf; LEI §3-C10 + §7-D7, achados 52/66).
 *
 * O QUE É: a Virada de Edição (morph cartão→página) por DELEGAÇÃO — UMA
 * ilha client por container de cartões, com UM listener de `click` no
 * container, no lugar de 13 `CartaoTese` client cuja ÚNICA razão de
 * "use client" era o `onClick` do `useViradaCartao` (R8 §6-H1). Com isto o
 * CartaoTese vira Server Component e as 13 subárvores (~12 nós cada) saem
 * INTEIRAS do commit de hidratação (lei das ilhas de page.tsx — a mesma
 * prova do `#nascimento` ≈ 0ms).
 *
 * POR QUE REUSAR `useViradaCartao` (e não reimplementar): o estado de
 * módulo dele (`vooAtivo`/`vooFinished`/`resolverPintura`) é CONTRATO de
 * dois consumidores — `useVitrineDeriva` cede a posse do scrollLeft quando
 * `esperaViradaEmVoo() !== null` (E21) e o TeseClient segura o swap
 * skeleton→conteúdo durante o voo (C4). Reimplementar o disparo aqui
 * quebraria os dois canais em silêncio; e `useViradaCartao.ts` NÃO pode ser
 * editado (está no first-load de /tese via `esperaViradaEmVoo` — gate D7:
 * Δ de bytes == 0). Por isso a ilha instancia o HOOK ORIGINAL uma vez por
 * ticker em componentes NULOS (zero DOM, zero subárvore reconciliada;
 * regra dos hooks respeitada: um componente por instância) e o listener
 * delegado apenas ROTEIA o clique para o handler do cartão certo — morph,
 * view-transition-name via CSSOM só no clique + limpeza no finally (D4),
 * sessionStorage de chegada e navegação programática ficam bit-a-bit os
 * mesmos por construção.
 *
 * SEMÂNTICA DO CLIQUE (idêntica à do onClick de antes):
 *  - passthrough de ctrl/cmd/shift/alt+clique: o handler original devolve
 *    SEM preventDefault → o clique segue subindo até o onClick interno do
 *    <Link> (synthetic no React root, ACIMA deste container na bolha), que
 *    também não o consome (isModifiedEvent) → o browser abre a aba.
 *    Botão-do-meio dispara `auxclick` (não `click`) — nem chega aqui.
 *  - supressão de clique-pós-drag: useRailDrag suprime o clique fantasma em
 *    FASE DE CAPTURA no `.banca-rail` (preventDefault + stopPropagation) —
 *    o evento morre antes de qualquer bolha, logo este listener nunca o vê.
 *    Ativação por TECLADO (Enter/Space → click com detail === 0) não é
 *    consumida lá (achado 66) e chega aqui normalmente.
 *
 * ONDE: landing — GaleriaBanca (já client) abriga
 * `<ViradaDelegada containerRef={envelopeRef}>`; /teses — ilha mínima irmã
 * da grade, descobrindo o container por seletor no mount (precedente
 * FocoLuz → `.glifo-fantasma`).
 */

import {
  useEffect,
  useState,
  type MouseEvent as MouseEventReact,
  type RefObject,
} from "react";

import { useViradaCartao } from "@/components/motion/useViradaCartao";

const SELETOR_CARTAO = "a.cartao-ticker";

type AoClicarVirada = (ev: MouseEventReact<HTMLAnchorElement>) => void;
type MapaViradas = Map<string, AoClicarVirada>;

/** Extrai o ticker do href REAL do cartão (`/tese?ticker=X`) — fonte única:
 * o mesmo atributo que o browser usaria na navegação nativa. */
function tickerDoCartao(cartao: HTMLAnchorElement): string | null {
  const href = cartao.getAttribute("href") ?? "";
  const par = /[?&]ticker=([^&#]+)/.exec(href);
  return par ? decodeURIComponent(par[1]) : null;
}

/** Adapta o MouseEvent NATIVO do listener delegado para a assinatura React
 * do handler do hook. O hook lê tudo de forma SÍNCRONA no disparo
 * (defaultPrevented/button/modificadores/currentTarget) e a única escrita é
 * `preventDefault()` — repassada ao evento nativo, então o onClick interno
 * do <Link> (que respeita `defaultPrevented`) não navega em dobro. */
function comoEventoReact(
  ev: MouseEvent,
  cartao: HTMLAnchorElement,
): MouseEventReact<HTMLAnchorElement> {
  return {
    defaultPrevented: ev.defaultPrevented,
    button: ev.button,
    metaKey: ev.metaKey,
    ctrlKey: ev.ctrlKey,
    shiftKey: ev.shiftKey,
    altKey: ev.altKey,
    currentTarget: cartao,
    preventDefault: () => ev.preventDefault(),
    nativeEvent: ev,
  } as unknown as MouseEventReact<HTMLAnchorElement>;
}

/** Uma instância NULA do hook original por ticker: registra o handler no
 * mapa da ilha. Também carrega, por tabela, o layout-effect de unmount do
 * hook — o resolvedor da pintura da View Transition roda no commit que
 * desmonta a página de origem, semântica idêntica à dos 13 CartaoTese
 * client de antes. */
function RegistroVirada({ ticker, mapa }: { ticker: string; mapa: MapaViradas }) {
  const href = `/tese?ticker=${encodeURIComponent(ticker)}`;
  const aoClicar = useViradaCartao(ticker, href);
  useEffect(() => {
    mapa.set(ticker, aoClicar);
    return () => {
      mapa.delete(ticker);
    };
  }, [ticker, aoClicar, mapa]);
  return null;
}

export type ViradaDelegadaProps = {
  /** Tickers dos cartões do container (o roteamento do clique é pelo href
   * do cartão clicado, nunca por índice — ordem irrelevante). */
  tickers: readonly string[];
  /** Container com ref (pai client que já o possui — GaleriaBanca). */
  containerRef?: RefObject<HTMLElement | null>;
  /** OU seletor do container (ilha mínima em página server — /teses). */
  seletorContainer?: string;
};

export function ViradaDelegada({
  tickers,
  containerRef,
  seletorContainer,
}: ViradaDelegadaProps) {
  // Mapa estável (lazy init) — nunca recriado entre renders.
  const [mapa] = useState<MapaViradas>(() => new Map());

  useEffect(() => {
    const container =
      containerRef?.current ??
      (seletorContainer
        ? document.querySelector<HTMLElement>(seletorContainer)
        : null);
    if (!container) return;

    const aoClicarDelegado = (ev: MouseEvent) => {
      if (!(ev.target instanceof Element)) return;
      const cartao = ev.target.closest<HTMLAnchorElement>(SELETOR_CARTAO);
      if (!cartao || !container.contains(cartao)) return;
      const ticker = tickerDoCartao(cartao);
      const manejador = ticker !== null ? mapa.get(ticker) : undefined;
      if (!manejador) return; // cartão fora do conjunto registrado: fluxo nativo
      manejador(comoEventoReact(ev, cartao));
    };

    container.addEventListener("click", aoClicarDelegado);
    return () => container.removeEventListener("click", aoClicarDelegado);
  }, [containerRef, seletorContainer, mapa]);

  return (
    <>
      {tickers.map((ticker) => (
        <RegistroVirada key={ticker} ticker={ticker} mapa={mapa} />
      ))}
    </>
  );
}
