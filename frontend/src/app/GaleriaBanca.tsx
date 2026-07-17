"use client";

// Banca de Teses — 2º momento horizontal da landing (missão MATÉRIA VIVA,
// §3 critério 3, enxerto C; posse Onda 1E). Troca a GRADE teaser da galeria
// por um rail horizontal NATIVO (overflow-x + scroll-snap via utilitários
// Tailwind — ZERO listener de wheel, zero GSAP, custo de JS ~zero): o
// deslocamento lateral é 100% do navegador; o JS daqui só cuida de setas e
// dots acessíveis (padrão a11y do FilmstripDimensoes: role="list",
// aria-current="location", scrollIntoView SEM `behavior` — herda o
// scroll-behavior do CSS, que já vira `auto` sob prefers-reduced-motion).
//
// Reuso deliberado (contrato da Onda 0): GradeFoco (o <ul> com foco frio
// por delegação — `.banca-rail` entra via className; filhos <li> DIRETOS
// preservados: semântica de lista + seletor `.cartao-ticker` da delegação
// intocados) e CartaoTese (mesma anatomia de card-manchete; hairline e luz
// de card intactas — nenhuma segunda anatomia).
//
// Carimbo de entrada por card: CSS puro `view(inline)` em cinema/banca.css
// (classe `.banca-carimbo` no wrapper do card) — scrubbed, reversível, sob
// @supports; fallback = visível. NENHUM <Reveal> por card aqui: a varredura
// de segurança do motor Reveal ignora clipagem por ancestral com overflow e
// marcaria todos os cards como "alcançados" no 1º quadro (pegadinha
// documentada no recon; precedente FilmstripDimensoes).
//
// CONTRATO (Onda 2 — page.tsx): substituir o bloco <GradeFoco>…</GradeFoco>
// da galeria teaser por
//   <GaleriaBanca papeis={exemplos} dataCarteira={DATA_CARTEIRA_IBOV} />
// — a MESMA interface de dados que a grade atual consome (PapelB3[] +
// data ISO da carteira); sem `.stagger`/`.i-N`/<Reveal> por card.

// APOTEOSE (2026-07-13, onda BANCA — crit. 3/5): o rail ganha (a) palco 3D
// (usePalco + cinema/palco.css, autorização S1/S3), (b) arrasto de mouse com
// inércia snap-safe (useRailDrag + classe .banca-arrastando), (c) hairline de
// progresso substituta da scrollbar oculta (scroll-timeline sob @supports +
// fallback JS passivo D6 abaixo). Setas/dots/teclado/IO/view(inline) do rail
// permanecem EXATAMENTE como estavam.

// FRONTEND HORIZONTE (2026-07-14, raia 1B VITRINE — crit. 4): a faixa vira
// "vitrine giratória" — deriva contínua por scroll real (useVitrineDeriva,
// D21/E7/E8/E21/E24) + controle on-page (D22/E16-E18, 1º controle 2.2.2 do
// site) + pedestal por cartão (`.vitrine-pedestal`, cinema/vitrine.css).
// Palco 3D/drag/hairline/teclado/dots-IO seguem INTOCADOS (D24) — só a
// coalescência dos dots durante a deriva é nova (E24, ver `aoMudarEstado`).
//
// INTEGRAÇÃO (Onda 2, page.tsx): o wrapper `<section id="galeria">` ganha
// `className="vitrine-veludo veludo-escopo b-sangria"`; o `<div data-cena-el>`
// que hoje envolve `<GaleriaBanca>` deve DEIXAR de ter `data-cena-el` (E18 —
// ver relatório da raia 1B: o controle não pode desbotar a 0.55 na saída do
// CenaScrub).

// PERF — B2 (2026-07-14): A CASCA É CLIENT, OS CARTÕES SÃO DO SERVIDOR.
// Mesma lei do Salão (ver cabeçalho de SalaoDimensoes.tsx): o excedente de
// TBT da landing é custo de COMMIT DE HIDRATAÇÃO, proporcional ao tamanho da
// árvore que o cliente reconcilia. O que o servidor renderiza e passa como
// SLOT chega pronto no payload RSC. Por isso os 13 `<li>` (envelope
// `.banca-carimbo .vitrine-pedestal` + CartaoTese) deixaram de ser mapeados
// AQUI: page.tsx os monta e passa em `cartoes`.
// OURIVESARIA ONDA P — H1 (2026-07-17, §3-C10/§7-D7): a ressalva de
// honestidade da B2 ("CartaoTese continua client — a função dele ainda roda
// na hidratação ×13") FECHOU. CartaoTese agora é Server Component: o recheio
// dos 13 cartões saiu da tarefa de hidratação junto com o envelope. O clique
// do morph é DELEGADO — <ViradaDelegada containerRef={envelopeRef}> abaixo
// instala 1 listener de click no envelope e reusa o useViradaCartao original
// (uma instância nula por ticker — canal vooAtivo/vooFinished intacto para a
// deriva E21 e para o TeseClient C4).
// A deriva/palco/drag/hairline/teclado/dots continuam idênticos (D24).

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { GradeFoco } from "@/components/motion/GradeFoco";
import { usePalco } from "@/components/motion/usePalco";
import { usePrefereReduzido } from "@/components/motion/usePonteiro";
import { useRailDrag } from "@/components/motion/useRailDrag";
import { useVitrineDeriva } from "@/components/motion/useVitrineDeriva";
import { ViradaDelegada } from "@/components/motion/viradaDelegada";

export type GaleriaBancaProps = {
  /** Só os tickers: é o que a CASCA precisa (rótulo/aria-label dos dots).
   *  Os dados completos do papel (PapelB3) não cruzam mais a fronteira —
   *  quem os consome é o CartaoTese, renderizado no SERVIDOR (page.tsx). */
  tickers: readonly string[];
  /** SLOT SERVIDOR: os 13 `<li>` com o cartão dentro, já renderizados. */
  cartoes: ReactNode;
};

const CHAVE_VITRINE_PAUSADA = "tese-ai:vitrine-pausada";
const ROTULO_CONTROLE = "Movimento da vitrine"; // E16 — rótulo FIXO, nunca troca

// DEFEITO 1 (correção onda 5 — erro de hidratação React #418): o SSR e o 1º
// render do CLIENTE (a passada de hidratação) têm de produzir o MESMO HTML
// — nenhum dos dois pode ler `localStorage`. `useState(lerPausadoInicial)`
// como inicializador rodava a leitura DENTRO do próprio render; no cliente
// isso é uma passada de MONTAGEM (hidratação conta como mount), então o
// inicializador roda de novo e diverge do `false` do SSR sempre que o
// visitante já pausou a vitrine antes — mismatch determinístico em 100%
// dos carregamentos para esse visitante (Chromium/Firefox, 3/3).
// A leitura de localStorage SÓ acontece depois, em `useLayoutEffectIsomorfo`
// abaixo (client-only, roda ANTES do browser pintar E antes do 1º rAF do
// motor da deriva — useVitrineDeriva só agenda seu primeiro
// `requestAnimationFrame` num useEffect PASSIVO, que corre depois dos
// layout effects) — isto ainda satisfaz a E16 ("ler a flag antes do 1º
// rAF") sem jamais divergir do HTML do SSR.
function lerPausadoInicial(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(CHAVE_VITRINE_PAUSADA) === "true";
  } catch {
    // Storage indisponível (modo privado estrito): começa em movimento —
    // a escolha simplesmente não sobrevive à sessão.
    return false;
  }
}

// useLayoutEffect no cliente (aplica o valor persistido ANTES do primeiro
// paint pós-hidratação — zero flash do ícone/estado errado); useEffect no
// servidor só para silenciar o aviso de SSR do React (não roda de verdade
// lá) — mesmo padrão de src/app/template.tsx e src/app/tese/TeseClient.tsx.
const useLayoutEffectIsomorfo =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

export default function GaleriaBanca({ tickers, cartoes }: GaleriaBancaProps) {
  const envelopeRef = useRef<HTMLDivElement | null>(null);
  const barraRef = useRef<HTMLSpanElement | null>(null);
  const [ativo, setAtivo] = useState(0);
  const prefereReduzido = usePrefereReduzido();

  /** Os cartões VIVOS, lidos do DOM (são server-rendered — não há mais um ref
   *  por cartão). `:scope > li` do rail = ordem de documento = ordem de
   *  `tickers`. */
  const cartoesVivos = useCallback(
    () =>
      Array.from(
        envelopeRef.current?.querySelectorAll<HTMLLIElement>(".banca-rail > li") ?? [],
      ),
    [],
  );

  // Estado do CONTROLE (distinto dos pausas automáticas de hover/foco/
  // toque, que vivem só dentro do hook): só o clique do usuário move isto.
  // DEFEITO 1: o default aqui é SEMPRE o do servidor (`false` — em
  // movimento), idêntico ao que `lerPausadoInicial()` devolve durante SSR;
  // o valor persistido (se houver) é aplicado depois, no layout effect
  // abaixo — nunca no inicializador do useState.
  const [pausado, setPausado] = useState<boolean>(false);
  const [anuncio, setAnuncio] = useState("");

  // DEFEITO 1 — aplica o valor de `localStorage` (se houver) SÓ depois da
  // hidratação, síncrono e antes do 1º paint: HTML do SSR/1º render do
  // cliente nunca diverge (ambos `false`); se o valor guardado for `true`,
  // o re-render corrigido já commita antes do browser pintar (React
  // encadeia o setState de um layout effect antes do paint) — zero flash,
  // zero mismatch. Roda uma única vez (mount).
  useLayoutEffectIsomorfo(() => {
    const persistido = lerPausadoInicial();
    if (persistido) setPausado(true);
  }, []);

  // E24: enquanto a deriva está ativamente escrevendo, o efeito de IO
  // abaixo NÃO recalcula o dot ativo a cada limiar — só no assentamento
  // (aoMudarEstadoDeriva, quando `derivando` volta a `false`).
  const derivandoRef = useRef(false);

  // Palco 3D (mola do tilt) + drag do rail — ambos acham o `.banca-rail`
  // dentro do envelope (o <ul> vive no GradeFoco, que não expõe ref).
  usePalco(envelopeRef);
  useRailDrag(envelopeRef);

  const aoMudarEstadoDeriva = useCallback(({ derivando }: { derivando: boolean }) => {
    derivandoRef.current = derivando;
    if (derivando) return;
    // Assentou (E24): recomputa o dot ativo UMA vez a partir do scroll
    // atual — "o card mais centrado no rail" — em vez de esperar o
    // próximo limiar de IO (que só dispararia se um card cruzasse o
    // threshold DEPOIS deste ponto, o que pode nunca acontecer se a
    // deriva parou no meio de um respiro do pêndulo).
    const rail = envelopeRef.current?.querySelector<HTMLElement>(".banca-rail");
    const cards = cartoesVivos();
    if (!rail || cards.length === 0) return;
    const base = rail.getBoundingClientRect().left;
    const centroRail = rail.clientWidth / 2;
    let melhorIndice = 0;
    let melhorDist = Infinity;
    cards.forEach((li, i) => {
      const centroCard = li.getBoundingClientRect().left - base + li.offsetWidth / 2;
      const dist = Math.abs(centroCard - centroRail);
      if (dist < melhorDist) {
        melhorDist = dist;
        melhorIndice = i;
      }
    });
    setAtivo(melhorIndice);
  }, [cartoesVivos]);

  // Motor da vitrine giratória (D21/E7/E8/E21/E24) — nem monta sob reduce
  // (gate interno via usePrefereReduzido); o controle abaixo também não
  // renderiza sob reduce (D24: "reduce nem monta, controle não renderiza").
  useVitrineDeriva(envelopeRef, {
    pausadoPeloControle: pausado,
    aoMudarEstado: aoMudarEstadoDeriva,
  });

  // E17: role="status" anuncia SÓ mudança iniciada pelo usuário (clique/
  // tecla neste botão) — nunca as pausas automáticas de hover/foco/toque
  // do hook, que não tocam este estado.
  const aoAlternarPausa = useCallback(() => {
    setPausado((atual) => {
      const novo = !atual;
      try {
        window.localStorage.setItem(CHAVE_VITRINE_PAUSADA, novo ? "true" : "false");
      } catch {
        /* storage indisponível — a escolha funciona nesta sessão, só não persiste */
      }
      setAnuncio(novo ? "Vitrine pausada." : "Vitrine em movimento.");
      return novo;
    });
  }, []);

  // D6 — fallback da hairline (FF stable sem scroll-driven animations até
  // ~155): scroll passivo → rAF → --banca-prog NA PRÓPRIA barra (regra 5 do
  // DESIGN-TOKENS). Onde há suporte, a animação CSS dirige tudo e este
  // efeito nem liga (nunca dois escritores).
  useEffect(() => {
    if (typeof CSS !== "undefined" && CSS.supports("animation-timeline: --a")) return;
    const rail = envelopeRef.current?.querySelector<HTMLElement>(".banca-rail");
    const barra = barraRef.current;
    if (!rail || !barra) return;
    let quadro = 0;
    const pintar = () => {
      const max = rail.scrollWidth - rail.clientWidth;
      barra.style.setProperty("--banca-prog", max > 0 ? String(rail.scrollLeft / max) : "0");
    };
    const aoRolar = () => {
      window.cancelAnimationFrame(quadro);
      quadro = window.requestAnimationFrame(pintar);
    };
    pintar();
    rail.addEventListener("scroll", aoRolar, { passive: true });
    return () => {
      rail.removeEventListener("scroll", aoRolar);
      window.cancelAnimationFrame(quadro);
    };
  }, []);

  // Card ativo por IO com root = o próprio rail (nunca a viewport inteira,
  // nunca listener de `scroll` cru) — mesma métrica do FilmstripDimensoes
  // (`intersectionRatio`, a certa para um root horizontal). Reversível por
  // natureza: o estado segue o scroll nos dois sentidos.
  useEffect(() => {
    const cards = cartoesVivos();
    const rail = cards[0]?.parentElement;
    if (!rail || cards.length === 0) return;

    // Semântica de lista explícita no <ul> do GradeFoco (o preflight do
    // Tailwind zera list-style e o Safari/VoiceOver deixa de expor listas
    // sem marcador — mesma auditoria 1.3.1 do FilmstripDimensoes).
    // GradeFoco não aceita atributos extras e não é posse desta onda;
    // atributo ARIA setado 1x no mount — é ATRIBUTO, não estilo (nada de
    // setAttribute('style'): carve-out CSP intacto).
    rail.setAttribute("role", "list");
    rail.setAttribute("aria-label", "Banca de teses de exemplo — role para o lado");

    // DEFEITO 3 (onda 5): Tab até um cartão fora da vista precisa trazê-lo
    // INTEIRO para dentro do rail de forma explícita — o auto-scroll nativo
    // do foco, sob `scroll-snap-type: mandatory`, pode resolver para um
    // ponto de snap vizinho (não necessariamente o cartão focado); e,
    // enquanto a deriva (useVitrineDeriva) ainda está em fase ativa no
    // instante do foco, ela só entra em "freando" (rampa suave) — sem
    // ressincronizar sua posição interna a partir do `scrollLeft` real, o
    // próximo quadro reescreveria por cima do salto do foco. Mesmo cuidado
    // do Salão (SalaoDimensoes.tsx, `aoFocarDentro`/`rolarPara`): navegação
    // por foco é SOBERANA e explícita, nunca deixada para o default do
    // engine. `scrollIntoView` SEM `behavior`: herda o `scroll-behavior` do
    // CSS do rail (mesma decisão já documentada para `irPara`, acima).
    const aoFocarDentro = (ev: FocusEvent) => {
      if (!(ev.target instanceof Element)) return;
      // SÓ foco por teclado/programático (`:focus-visible`) — um
      // `pointerdown` que foca o link do cartão (início de um possível
      // drag, useRailDrag.ts) NÃO qualifica `:focus-visible` nos engines
      // atuais; sem este guarda, o próprio `mousedown` do agarrão da
      // deriva disparava este `scrollIntoView` e brigava com a parada
      // imediata do Defeito 2 (achado na prova local desta correção:
      // scrollLeft caindo a 0 logo após o pointerdown, mesmo depois do
      // cede duro — o causador era ESTE handler, não a deriva).
      if (!ev.target.matches(":focus-visible")) return;
      const li = ev.target.closest("li");
      if (!li || li.parentElement !== rail) return;
      li.scrollIntoView({ inline: "nearest", block: "nearest" });
    };
    rail.addEventListener("focusin", aoFocarDentro);

    const observer = new IntersectionObserver(
      (entradas) => {
        // E24 — coalescido: durante a deriva ativa, o limiar de IO cruza a
        // cada quadro; o "ativo" real só é recomputado no assentamento
        // (aoMudarEstadoDeriva acima), não aqui.
        if (derivandoRef.current) return;
        setAtivo((atual) => {
          const maisVisivel = entradas.reduce((melhor, entrada) =>
            entrada.intersectionRatio > melhor.intersectionRatio ? entrada : melhor,
          );
          if (maisVisivel.intersectionRatio < 0.5) return atual;
          const indice = cards.indexOf(maisVisivel.target as HTMLLIElement);
          return indice === -1 ? atual : indice;
        });
      },
      { root: rail, threshold: [0, 0.25, 0.5, 0.75, 1] },
    );
    cards.forEach((el) => observer.observe(el));
    return () => {
      observer.disconnect();
      rail.removeEventListener("focusin", aoFocarDentro);
    };
  }, [tickers.length, cartoesVivos]);

  // `scrollIntoView` SEM `behavior` explícito: herda o `scroll-behavior` do
  // CSS (`smooth` global no html; `auto` sob prefers-reduced-motion) — fixar
  // "smooth" no JS sobrescreveria a preferência do usuário (mesma decisão
  // documentada do FilmstripDimensoes).
  const irPara = useCallback(
    (indice: number) => {
      cartoesVivos()[indice]?.scrollIntoView({ inline: "start", block: "nearest" });
    },
    [cartoesVivos],
  );

  return (
    // `.banca-envelope` (banca.css): timeline-scope da hairline — a barra é
    // IRMÃ do rail e precisa do ancestral comum para enxergar --banca-rail.
    // Também é o ancestral comum de posse/gates do useVitrineDeriva
    // (pointerdown/focusin cobrem rail + dots + setas + controle).
    <div ref={envelopeRef} className="banca-envelope flex flex-col gap-4">
      {/* ONDA P H1 — morph por delegação (zero DOM): 1 listener de click no
          envelope + 13 registros nulos do useViradaCartao original. A
          supressão de clique-pós-drag do useRailDrag (captura no rail,
          stopPropagation) mata o evento antes desta bolha — nada a repetir
          aqui. */}
      <ViradaDelegada tickers={tickers} containerRef={envelopeRef} />
      {/* Controles FORA do container clipado (o anel de foco nunca é
          cortado pelo overflow do rail — guarda C2 do red-team, mesmo
          racional do FilmstripDimensoes). */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <ol role="list" aria-label="Ir direto a uma tese de exemplo" className="flex flex-wrap items-center gap-1">
          {tickers.map((ticker, i) => (
            <li key={ticker}>
              {/* Dot 8px dentro de alvo de toque 24px (WCAG 2.5.8). Estados
                  com contraste de UI provado: inativo `border-field`
                  (≥3.15:1 até no pico da luz), ativo `bg-brasa-texto`
                  (mesmo papel de "tab ativa" do design system).
                  `.banca-dot` (HORIZONTE): âncora do anel escopado ao
                  veludo (`.veludo-escopo .banca-dot:focus-visible`,
                  cinema/vitrine.css, E15). */}
              <button
                type="button"
                onClick={() => irPara(i)}
                aria-label={`Ir para ${ticker}`}
                aria-current={i === ativo ? "location" : undefined}
                className="banca-dot group flex h-6 w-6 items-center justify-center"
              >
                <span
                  aria-hidden
                  className={`h-2 w-2 rounded-full border transition-colors duration-[var(--dur-tick)] ${
                    i === ativo
                      ? "border-brasa-texto bg-brasa-texto"
                      : "border-field bg-transparent group-hover:border-ink-3"
                  }`}
                />
              </button>
            </li>
          ))}
        </ol>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => irPara(Math.max(ativo - 1, 0))}
            disabled={ativo === 0}
            aria-label="Tese anterior"
            className="seta-filmstrip seta-filmstrip--prev flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              ←
            </span>
          </button>
          <button
            type="button"
            onClick={() => irPara(Math.min(ativo + 1, tickers.length - 1))}
            disabled={ativo === tickers.length - 1}
            aria-label="Próxima tese"
            className="seta-filmstrip seta-filmstrip--next flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              →
            </span>
          </button>
          {/* Controle da vitrine (D22) — 1º controle on-page 2.2.2 do
              site. Sob reduce ele NÃO renderiza (D24: não há o que pausar
              — a deriva nem monta). Rótulo textual FIXO (E16): SÓ
              `aria-pressed` porta o estado — um rótulo que trocasse JUNTO
              com aria-pressed faria o leitor de tela anunciar
              "Girar vitrine, pressionado" (anti-padrão). `role="status"`
              sr-only separado (E17) anuncia só a mudança feita por
              clique/tecla AQUI — nunca as pausas automáticas de
              hover/foco/toque do hook (que não tocam `anuncio`). */}
          {!prefereReduzido && (
            <button
              type="button"
              onClick={aoAlternarPausa}
              aria-pressed={pausado}
              // `data-vitrine-nao-pausa` (useVitrineDeriva.ts): o foco que
              // o próprio <button> nativamente retém após o clique NÃO
              // conta para o gate de "foco-dentro" — senão o controle que
              // acabou de mandar "retomar" travaria, ele mesmo, a retomada.
              data-vitrine-nao-pausa=""
              className="vitrine-controle"
            >
              <span aria-hidden className="vitrine-controle__icone">
                {pausado ? "▶" : "⏸"}
              </span>
              <span>{ROTULO_CONTROLE}</span>
            </button>
          )}
        </div>
      </div>
      {!prefereReduzido && (
        <span role="status" className="sr-only">
          {anuncio}
        </span>
      )}

      {/* Rail nativo: snap-x mandatory, sem sequestro de wheel — o mesmo
          <ul> de foco frio por delegação da grade anterior, agora rolável.
          `overscroll-x-contain` evita o encadeamento do overscroll lateral
          (trackpad) virar navegação de histórico no meio do arrasto. */}
      <GradeFoco
        seletorAlvo=".cartao-ticker"
        className="banca-rail flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain scroll-px-4 pb-2 sm:scroll-px-6"
      >
        {/* OS 13 CARTÕES — slot SERVIDOR (perf/TBT, ver cabeçalho): o `<li>`
            estável para snap/IO e o wrapper `.banca-carimbo .vitrine-pedestal`
            (que anima no lugar do `<li>`, D19/D24) são montados em page.tsx e
            chegam prontos pelo payload RSC. A casca os acha por
            `.banca-rail > li`. */}
        {cartoes}
      </GradeFoco>

      {/* Hairline de progresso (crit. 5/D6) — affordance substituta da
          scrollbar oculta (padrão do filmstrip: 2px, brasa, transform-only;
          estilos em banca.css). Decorativa para leitor de tela: o
          wayfinding acessível segue nos dots aria-current + setas. */}
      <div className="banca-progresso" aria-hidden="true">
        <span ref={barraRef} className="banca-progresso__barra" />
      </div>
    </div>
  );
}
