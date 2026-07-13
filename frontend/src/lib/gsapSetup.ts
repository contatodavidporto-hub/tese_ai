/**
 * gsapSetup — loader assíncrono MEMOIZADO do motor GSAP.
 * Missão MATÉRIA VIVA (Onda 0) · plano: .maestro/plano-imersivo.md §5/§12.
 *
 * R5 (LEI): o gsap NUNCA entra no caminho crítico da hidratação — só chega
 * via import() dinâmico (chunk próprio da landing), chamado pelos
 * consumidores pós-idle/primeiro scroll-intent. JAMAIS importar "gsap"
 * estaticamente em componente/rota — em especial layout.tsx, Header e /tese
 * (R2: delta ZERO de gsap em /tese é gate de merge; bundle por rota medido
 * no QA da Onda 3).
 *
 * COMENTÁRIO-LEI (não negociável):
 * - CSP intacta: o GSAP escreve estilo via CSSOM (`element.style`) — é o
 *   carve-out aprovado (DESIGN-TOKENS.md §1, emenda MATÉRIA VIVA). Seguem
 *   PROIBIDOS: prop `style={}` em JSX, `setAttribute('style')`, tag
 *   `<style>` injetada, styled-jsx.
 * - Plugin Flip PROIBIDO: usa `setAttribute('style')` — único caminho do
 *   GSAP que violaria a CSP com nonce. Nunca importar/registrar.
 * - `markers: true` PROIBIDO em produção: o ScrollTrigger injeta nós com
 *   estilo inline para os marcadores — debug local apenas, nunca commitado.
 * - LICENÇA (registrada 2026-07-12; citar no PR): gsap@3.15.0 é distribuído
 *   sob a licença Webflow "Standard no-charge" — gratuita inclusive para uso
 *   comercial, porém NÃO-MIT (termos próprios; sem redistribuir o GSAP como
 *   ferramenta concorrente). Pin exato no package.json.
 * - useGSAP (@gsap/react) NÃO é usado (decisão 1B): o hook exigiria import
 *   estático de gsap no chunk da rota, violando R5 (import dinâmico
 *   pós-idle). Dependência removida na auditoria final 2026-07-13; o
 *   cleanup é manual via gsap.matchMedia().revert() nos componentes.
 * - Reduced motion: quem cria tween/trigger DEVE fazê-lo dentro de
 *   gsap.matchMedia() com MQ_SEM_REDUCE (sob reduce, NENHUM trigger nasce e
 *   nenhum estado inicial é escrito — SSR nunca emite conteúdo oculto).
 *   ehReduce() é o gate síncrono para decisões fora do gsap (ex.: nem baixar
 *   o chunk do shader).
 */

export type MotorGsap = {
  gsap: typeof import("gsap").gsap;
  ScrollTrigger: typeof import("gsap/ScrollTrigger").ScrollTrigger;
  ScrollToPlugin: typeof import("gsap/ScrollToPlugin").ScrollToPlugin;
};

/** Media queries canônicas da missão (usar nos gsap.matchMedia das ondas). */
export const MQ_REDUCE = "(prefers-reduced-motion: reduce)";
export const MQ_SEM_REDUCE = "(prefers-reduced-motion: no-preference)";
/** Gate do modo pinado do filmstrip (R4/R9): desktop + ponteiro fino + sem reduce. */
export const MQ_PIN_FILMSTRIP =
  "(min-width: 1024px) and (pointer: fine) and (prefers-reduced-motion: no-preference)";

/** true se o usuário pediu movimento reduzido (SSR-safe: false no servidor). */
export function ehReduce(): boolean {
  return typeof window !== "undefined" && window.matchMedia(MQ_REDUCE).matches;
}

let promessa: Promise<MotorGsap> | null = null;

/**
 * Carrega gsap + ScrollTrigger + ScrollToPlugin UMA única vez (memoizado):
 * toda chamada subsequente devolve a MESMA promise (um único registerPlugin,
 * um único ticker). Em falha (rede), a memoização é limpa para permitir
 * retry no próximo scroll-intent.
 */
export async function carregarGsap(): Promise<MotorGsap> {
  if (!promessa) {
    promessa = (async () => {
      const [nucleo, moduloST, moduloSTP] = await Promise.all([
        import("gsap"),
        import("gsap/ScrollTrigger"),
        import("gsap/ScrollToPlugin"),
      ]);
      const gsap = nucleo.gsap;
      const ScrollTrigger = moduloST.ScrollTrigger;
      const ScrollToPlugin = moduloSTP.ScrollToPlugin;
      // ScrollToPlugin registrado junto de propósito (R4: teclado do
      // filmstrip via tween de scroll). useGSAP NÃO entra: é hook, não plugin.
      gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
      // Assinatura física única da casa (plano §3 crit.8).
      gsap.defaults({ ease: "power2.out" });
      return { gsap, ScrollTrigger, ScrollToPlugin };
    })().catch((erro: unknown) => {
      promessa = null;
      throw erro;
    });
  }
  return promessa;
}
