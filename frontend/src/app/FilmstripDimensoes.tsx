"use client";

// Filmstrip D1→D5 (§3, .maestro/direcao-de-arte-cinema.md) — "a tese se
// monta, camada por camada": troca o `<ol>` vertical das cinco Dimensões
// (page.tsx, versão anterior) por um carrossel horizontal com progressão
// real. Reusa 100% do vocabulário de motion já existente (nenhuma
// assinatura nova de reveal): `useReveal`/`classesReveal` (Reveal.tsx) armam
// o filmstrip inteiro UMA vez, `.reveal-regua` imprime cada estrato e
// `.traco-elo`/`.ponto-elo` (globals.css, seção 7 — o mesmo diagrama causal
// de TracoDoElo em como-funciona/page.tsx) conectam os 5 estratos no painel
// D5, girado para vertical.
//
// Por que UM `useReveal` para o filmstrip inteiro, e não um por painel: os
// painéis D2…D5 nascem CLIPADOS pelo `overflow-x:auto` do trilho enquanto o
// usuário não rola horizontalmente até eles. Um `IntersectionObserver` por
// painel nunca notificaria a entrada deles antes disso (comportamento
// correto — a clipagem por ancestral com overflow conta para a interseção),
// mas a VARREDURA de segurança do motor de Reveal (Reveal.tsx,
// `varreduraReveal`) usa só `getBoundingClientRect` SEM considerar clipagem
// de ancestral — ela marcaria os 5 painéis como "alcançados" já no primeiro
// quadro após o registro, atropelando o efeito "camada por camada"
// pretendido. Observar o FILMSTRIP INTEIRO (o bloco que envolve o trilho de
// progresso + o container que rola — nunca ele mesmo clipado, é um bloco
// normal do fluxo vertical da página) evita o problema por completo: a
// entrada em view acontece 1x, como qualquer outra seção da página, e a
// progressão D1→D5 continua vindo da ESTRUTURA (quantos estratos cada
// painel imprime), não de um gate de scroll horizontal por painel.
//
// ============================================================
// MODO PINADO (Onda 1C, missão MATÉRIA VIVA — plano §3 crit.3 + R1/R4/R9)
// ============================================================
// Travelling horizontal REAL: sob o gate `(hover:hover) + ≥1024px +
// pointer:fine + prefers-reduced-motion:no-preference` (gsap.matchMedia), o
// wrapper PRÓPRIO deste componente é pinado (ScrollTrigger pin — nunca um
// ancestral da Tarja z-50/régua z-55, trava C2) e o scroll VERTICAL nativo
// vira a manivela de um tween único `x: −(scrollWidth−clientWidth)` no
// trilho (`ease:'none'`, `scrub:1`, snap por painel). Zero listener de
// wheel, zero preventDefault — PageDown/espaço atravessam o pin
// naturalmente.
//
// - R5: gsap SÓ via `carregarGsap()` (import dinâmico, chunk da landing),
//   e SÓ quando o wrapper se APROXIMA do viewport (IntersectionObserver
//   one-shot com rootMargin 100%) — custo zero no load da página.
// - R4: enquanto o modo pinado existe, `html.rolagem-pinada` desliga o
//   `scroll-behavior:smooth` global (regra real em cinema/filmstrip.css):
//   smooth interceptaria CADA escrita de scrollTop do snap/ScrollToPlugin.
//   Teclado ←/→/Home/End e cliques em dots/setas viram tween do
//   ScrollToPlugin (nunca window.scrollTo nativo). Tudo restaurado no
//   revert.
// - R9: no modo pinado, `.filmstrip-pinado` desliga overflow-x/snap do
//   trilho (o translate assume) e o IO do painel ativo é DESLIGADO —
//   `ScrollTrigger.progress` é a ÚNICA fonte de aria-current/dots/contador
//   "0X / 05" e da hairline (`--prog` escrita via CSSOM na própria folha da
//   barra). `focusin` nos painéis → scrollTo(st.start + p*(st.end−st.start))
//   para foco por Tab nunca ficar fora da tela. `revert()` completo ao
//   cruzar <1024px ou ligar reduce (rail nativo + IO voltam, MESMO DOM).
// - Estratos internos por `containerAnimation` — RESTRIÇÕES (documentadas,
//   exigidas pelo mecanismo): o tween do container TEM de ser `ease:'none'`
//   (senão o mapeamento posição↔progresso mente) e os triggers internos NÃO
//   podem ter `pin` nem `snap` (não suportados/aninhados). Os tweens miram
//   SÓ as linhas `.filmstrip-camada` (transform/opacity SEM outro escritor —
//   as barras `.reveal-regua` DENTRO delas continuam do motor Reveal:
//   um escritor por propriedade, elementos distintos).
// - PEGADINHA herdada (decidida): o useReveal único do strip inteiro
//   CONTINUA valendo nos dois modos — no modo pinado o wrapper é o elemento
//   observado (a varredura o vê com top<vh assim que chega; nada aqui
//   depende de varredura DENTRO da área clipada pelo pin).
// - CSP: zero `style=`/`setAttribute('style')` — só `classList`, escritas
//   CSSOM do GSAP (carve-out DESIGN-TOKENS.md) e `setProperty('--prog')` na
//   folha consumidora. `markers:false` sempre.

import { useCallback, useEffect, useRef, useState } from "react";

import { classesReveal, useReveal } from "@/components/motion/Reveal";
import { carregarGsap, MQ_PIN_FILMSTRIP, type MotorGsap } from "@/lib/gsapSetup";

export type DimensaoFilmstrip = {
  numero: string;
  titulo: string;
  fonte: string;
  texto: string;
};

// Gate do modo pinado: a MQ canônica da Onda 0 (≥1024px + pointer:fine +
// no-preference) composta com `hover:hover` — o plano (§3 crit.3) exige os
// quatro termos; o `and` extra forma uma media query válida sem duplicar a
// string canônica.
const GATE_PINADO = `(hover: hover) and ${MQ_PIN_FILMSTRIP}`;

type ConectorProps = {
  armado: boolean;
  revelado: boolean;
};

// Diagrama causal vertical do painel D5 — mesma silhueta de TracoDoElo
// (como-funciona/page.tsx: 5 pontos, 4 segmentos, `pathLength={1}`
// normalizando o dash), só girado para vertical. Classes `.traco-elo`/
// `.ponto-elo(-N)` são as JÁ EXISTENTES em globals.css (seção 7) — nenhuma
// assinatura nova, só mais um lugar que as usa. Ilustrativo (viewBox
// esticado via `preserveAspectRatio="none"` para acompanhar a altura real da
// coluna de estratos ao lado) — mesmo espírito não-pixel-medido de
// TracoDoElo.
function ConectorEstratos({ armado, revelado }: ConectorProps) {
  const pontosY = [10, 60, 110, 160, 210] as const;
  return (
    <svg
      viewBox="0 0 20 220"
      preserveAspectRatio="none"
      role="img"
      aria-label="Os cinco estratos, conectados pelos elos causais"
      className={classesReveal("reveal-ticker", armado, revelado, "h-full w-full text-line-strong")}
    >
      {pontosY.slice(0, -1).map((y, idx) => (
        <path
          key={y}
          className="traco-elo"
          d={`M 10 ${y + 8} L 10 ${pontosY[idx + 1] - 8}`}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          pathLength={1}
        />
      ))}
      {pontosY.map((y, idx) => (
        <circle key={y} className={`ponto-elo ponto-elo-${idx + 1} fill-brasa`} cx={10} cy={y} r={4} />
      ))}
    </svg>
  );
}

export function FilmstripDimensoes({ dimensoes }: { dimensoes: readonly DimensaoFilmstrip[] }) {
  // UM `useReveal` para o filmstrip inteiro (ver nota de topo) — arma/revela
  // todos os estratos + o conector do D5 juntos, como qualquer outra seção.
  // O MESMO ref (RefObject) é o wrapper do modo pinado.
  const { ref, armado, revelado } = useReveal<HTMLDivElement>();
  const trilhoRef = useRef<HTMLOListElement | null>(null);
  const painelRefs = useRef<Array<HTMLLIElement | null>>([]);
  const [ativo, setAtivo] = useState(0);

  // Modo pinado (Onda 1C): estado + pontes para o mundo GSAP. `pinado`
  // desliga o IO do painel ativo (R9); `rolarPinadoRef` é a rota de
  // navegação por índice via ScrollToPlugin (R4) enquanto o modo existe;
  // `ativoPinadoRef` espelha o índice do ST para o restore do rail no
  // revert; `barraRef` é a folha que consome `--prog` (hairline).
  const [pinado, setPinado] = useState(false);
  const barraRef = useRef<HTMLDivElement | null>(null);
  const rolarPinadoRef = useRef<((indice: number) => void) | null>(null);
  const ativoPinadoRef = useRef(0);
  const refreshAposFontes = useRef(false);

  // Detecta o painel mais visível DENTRO do trilho — `root` é o próprio
  // container que rola horizontalmente (nunca a viewport inteira, nunca um
  // listener de `scroll` cru). Mesmo espírito de useSecaoAtiva.ts (reduz por
  // interseção), aqui usando `intersectionRatio` em vez de posição vertical
  // — a métrica certa para um `root` horizontal.
  // R9: DESLIGADO no modo pinado (o trilho nem é mais scroll container; o
  // `ScrollTrigger.progress` vira a única fonte do painel ativo) e religado
  // no revert (o efeito re-roda quando `pinado` volta a false).
  useEffect(() => {
    if (pinado) return;
    const container = trilhoRef.current;
    const paineis = painelRefs.current.filter((el): el is HTMLLIElement => el !== null);
    if (!container || paineis.length === 0) return;

    const observer = new IntersectionObserver(
      (entradas) => {
        setAtivo((atual) => {
          const maisVisivel = entradas.reduce((melhor, entrada) =>
            entrada.intersectionRatio > melhor.intersectionRatio ? entrada : melhor,
          );
          if (maisVisivel.intersectionRatio < 0.5) return atual;
          const indice = paineis.indexOf(maisVisivel.target as HTMLLIElement);
          return indice === -1 ? atual : indice;
        });
      },
      { root: container, threshold: [0, 0.25, 0.5, 0.75, 1] },
    );
    paineis.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [dimensoes.length, pinado]);

  // Boot do modo pinado — SÓ quando o strip se aproxima do viewport (IO
  // one-shot, rootMargin 100%: um viewport de antecedência) E o gate de
  // media query casa. `carregarGsap()` é import dinâmico memoizado (R5);
  // em falha de rede o rail nativo segue e um cruzamento futuro da MQ
  // tenta de novo (a memoização limpa a promise em falha).
  useEffect(() => {
    const involucro = ref.current;
    const trilho = trilhoRef.current;
    if (!involucro || !trilho) return;

    let cancelado = false;
    let bootIniciado = false;
    let mmGsap: { revert: () => void } | null = null;
    const mq = window.matchMedia(GATE_PINADO);

    const configurar = (motor: MotorGsap) => {
      const { gsap, ScrollTrigger } = motor;
      const mm = gsap.matchMedia();

      // gsap.matchMedia cuida do ciclo de vida: ativa quando o gate casa,
      // chama o cleanup retornado + reverte tweens/triggers/estilos inline
      // ao cruzar <1024px, perder hover/pointer fine ou ligar reduce (R9).
      mm.add(GATE_PINADO, () => {
        const paineis = painelRefs.current.filter((el): el is HTMLLIElement => el !== null);
        const total = paineis.length;
        if (total < 2) return;

        // Resquício de scroll nativo do rail zera ANTES de desligar o
        // overflow (depois da classe o trilho deixa de ser scroll container
        // e o translate é o único dono da posição horizontal).
        trilho.scrollLeft = 0;
        involucro.classList.add("filmstrip-pinado");
        // R4: desliga o scroll-behavior:smooth global enquanto o modo
        // existe — regra real em cinema/filmstrip.css (html.rolagem-pinada).
        document.documentElement.classList.add("rolagem-pinada");
        setPinado(true);

        const desligarBase = () => {
          involucro.classList.remove("filmstrip-pinado");
          document.documentElement.classList.remove("rolagem-pinada");
          barraRef.current?.style.removeProperty("--prog");
          // O tween do ScrollToPlugin nasce em handler (fora do mm.add
          // síncrono) e escaparia do revert(): mata aqui (auditoria final
          // 2026-07-13, achado 7) — a página não pode continuar rolando
          // sozinha após desmontar/cruzar o gate do modo pinado.
          gsap.killTweensOf(window);
          setPinado(false);
        };

        const distancia = () => Math.max(0, trilho.scrollWidth - trilho.clientWidth);

        // QA 2026-07-12: os pontos de snap são os OFFSETS REAIS dos painéis
        // (não k/4 da distância — os painéis não são equidistantes em relação
        // à distância total quando a janela ≠ viewport). O último ponto
        // clampa em 1 (o trilho encosta no fim e o painel 5 repousa
        // right-aligned, integral na janela — comportamento de fim de rail).
        // Recalculado a cada refresh (fontes/resize mudam offsetLeft).
        let pontosSnap: number[] = [];
        const recalcularPontos = () => {
          const base = paineis[0]?.offsetLeft ?? 0;
          const d = distancia();
          pontosSnap = paineis.map((p) =>
            d > 0 ? Math.min(1, (p.offsetLeft - base) / d) : 0,
          );
        };
        recalcularPontos();
        const pontoMaisProximo = (v: number) =>
          pontosSnap.reduce(
            (m, q) => (Math.abs(q - v) < Math.abs(m - v) ? q : m),
            pontosSnap[0] ?? 0,
          );
        const indiceMaisProximo = (v: number) =>
          pontosSnap.reduce(
            (mi, q, j) =>
              Math.abs(q - v) < Math.abs((pontosSnap[mi] ?? 0) - v) ? j : mi,
            0,
          );

        // Tween ÚNICO do travelling: 1px de scroll vertical = 1px de
        // travelling (ease:none — também OBRIGATÓRIO para o
        // containerAnimation dos estratos mapear posição corretamente).
        const tween = gsap.to(trilho, {
          x: () => -distancia(),
          ease: "none",
          scrollTrigger: {
            trigger: involucro,
            pin: true, // pina o wrapper PRÓPRIO — nunca ancestral de Tarja/régua (R1/C2)
            // Início logo abaixo da Tarja CVM sticky (z-50): o strip pinado
            // nunca nasce coberto pelo aviso regulatório (QA: Tarja visível
            // e legível DURANTE o pin). Função = re-medida a cada refresh.
            start: () => {
              const tarja = document.querySelector<HTMLElement>(
                '[role="note"][aria-label="Aviso regulatório"]',
              );
              return `top top+=${tarja?.offsetHeight ?? 0}`;
            },
            end: () => `+=${distancia()}`, // end dinâmico (re-medido no refresh)
            // O pai do invólucro é flex (container da seção): o ScrollTrigger
            // desliga pinSpacing sozinho em pai flex/grid, o documento não
            // cresce e a página ACABA no meio do travelling (bug pego na
            // sonda 2026-07-12: docH 3844, scroll preso em 2944). Forçar.
            pinSpacing: true,
            scrub: 1,
            snap: {
              // A11y 2026-07-12: função NEAREST idempotente (pouso exato não
              // re-salta — `directional:true` tratava o resíduo sub-pixel do
              // ScrollToPlugin como avanço e pulava +1 painel em setas/dots/
              // focusin, quebrando R9). Pontos = offsets reais dos painéis.
              // O `v` chega PROJETADO por velocidade: o salto nativo de foco
              // (focusin) injeta velocidade e projetava o snap até o FIM do
              // trilho — por isso o snap nunca vai além do ponto vizinho do
              // progresso REAL (self.progress), preservando o flick de wheel
              // (≤1 painel por gesto, mesma física do snap nativo).
              snapTo: (v: number, self?: ScrollTrigger) => {
                const alvoProjetado = pontoMaisProximo(Math.min(1, Math.max(0, v)));
                if (!self) return alvoProjetado;
                const vizinho = pontoMaisProximo(self.progress);
                const meioPasso = 0.5 / (total - 1);
                return Math.abs(alvoProjetado - self.progress) >
                  Math.abs(vizinho - self.progress) + meioPasso
                  ? vizinho
                  : alvoProjetado;
              },
              duration: { min: 0.15, max: 0.4 },
            },
            anticipatePin: 1,
            invalidateOnRefresh: true,
            onRefresh: () => recalcularPontos(),
            markers: false, // LEI: nunca true em produção (injetaria style inline)
            onUpdate: (st) => {
              // R9: ÚNICA fonte do painel ativo (aria-current/dots/contador)
              // e da hairline — `--prog` escrita via CSSOM na PRÓPRIA folha
              // da barra (nunca no container; nunca @property).
              barraRef.current?.style.setProperty("--prog", st.progress.toFixed(4));
              const indice = indiceMaisProximo(st.progress);
              ativoPinadoRef.current = indice;
              setAtivo(indice);
            },
          },
        });

        const st = tween.scrollTrigger;
        if (!st) {
          // Inalcançável na prática (vars.scrollTrigger sempre cria o
          // trigger) — rollback defensivo para nunca deixar classe órfã.
          tween.kill();
          desligarBase();
          return;
        }
        ativoPinadoRef.current = indiceMaisProximo(st.progress);

        // Estratos internos por containerAnimation: as linhas de camada de
        // cada painel (menos o D1, já em cena no início do pin) assentam
        // conforme o painel atravessa o quadro. SEM pin/snap aninhado
        // (restrição do mecanismo); alvos são SÓ `.filmstrip-camada`
        // (nenhum outro escritor de transform/opacity nelas — as barras
        // `.reveal-regua` ficam nos FILHOS, com o motor Reveal).
        for (const painel of paineis.slice(1)) {
          const camadas = painel.querySelectorAll<HTMLElement>(".filmstrip-camada");
          if (camadas.length === 0) continue;
          gsap.fromTo(
            camadas,
            { x: 28, opacity: 0.35 },
            {
              x: 0,
              opacity: 1,
              ease: "none",
              stagger: 0.08,
              scrollTrigger: {
                trigger: painel,
                containerAnimation: tween,
                start: "left right",
                end: "left 40%",
                scrub: true,
                markers: false,
              },
            },
          );
        }

        // R4/R9: navegação por índice = tween de scroll do ScrollToPlugin
        // (nunca window.scrollTo nativo). Progresso do painel i = ponto de
        // snap REAL (offset do painel / distância) — mesmos pontos do snap.
        const rolarPara = (indice: number) => {
          const alvo = Math.round(
            st.start + (pontosSnap[indice] ?? 0) * (st.end - st.start),
          );
          gsap.to(window, {
            scrollTo: alvo,
            duration: 0.45,
            ease: "power2.out",
            overwrite: "auto",
          });
        };
        rolarPinadoRef.current = rolarPara;

        // R9: foco por Tab dentro de um painel fora de cena → traz o painel
        // para a cena (scrollTo no progresso dele) — foco nunca fica
        // invisível atrás da clipagem do pin.
        const aoFocarDentro = (ev: FocusEvent) => {
          if (!(ev.target instanceof Element) || ev.target === trilho) return;
          const painel = ev.target.closest("li");
          const indice = painel ? paineis.indexOf(painel) : -1;
          if (indice >= 0) rolarPara(indice);
        };
        trilho.addEventListener("focusin", aoFocarDentro);

        // Refresh ÚNICO pós-fontes (CLS≈0): as fontes self-hosted mudam a
        // altura dos painéis; um único refresh global re-mede start/end.
        // Flag no componente — re-ativações do matchMedia não re-agendam.
        if (!refreshAposFontes.current) {
          refreshAposFontes.current = true;
          document.fonts.ready.then(
            () => {
              if (!cancelado) ScrollTrigger.refresh();
            },
            () => undefined,
          );
        }

        // Cleanup do modo (rodado pelo gsap.matchMedia no revert): rail
        // nativo + IO voltam, posicionados no painel que estava ativo
        // (scrollLeft direto = instantâneo; o <ol> não tem scroll-behavior
        // próprio — a preferência de smooth segue com o html).
        return () => {
          trilho.removeEventListener("focusin", aoFocarDentro);
          rolarPinadoRef.current = null;
          desligarBase();
          const alvo = paineis[ativoPinadoRef.current];
          const primeiro = paineis[0];
          if (alvo && primeiro) trilho.scrollLeft = alvo.offsetLeft - primeiro.offsetLeft;
        };
      });

      return mm;
    };

    const iniciar = () => {
      if (cancelado || bootIniciado) return;
      bootIniciado = true;
      carregarGsap()
        .then((motor) => {
          if (cancelado) return;
          mmGsap = configurar(motor);
        })
        .catch(() => {
          // Falha de rede: rail nativo segue intacto; libera retry no
          // próximo cruzamento da media query.
          bootIniciado = false;
        });
    };

    const aoMudarMq = (ev: MediaQueryListEvent) => {
      if (ev.matches) iniciar();
    };

    const io = new IntersectionObserver(
      (entradas) => {
        if (!entradas.some((entrada) => entrada.isIntersecting)) return;
        io.disconnect();
        // O listener fica como canal de boot tardio (ex.: janela redimensionada
        // para desktop depois do load); após o boot, o gsap.matchMedia é quem
        // liga/desliga o modo — `iniciar` vira no-op.
        mq.addEventListener("change", aoMudarMq);
        if (mq.matches) iniciar();
      },
      { rootMargin: "100% 0px 100% 0px" },
    );
    io.observe(involucro);

    return () => {
      cancelado = true;
      io.disconnect();
      mq.removeEventListener("change", aoMudarMq);
      mmGsap?.revert();
      rolarPinadoRef.current = null;
    };
  }, [dimensoes.length, ref]);

  // `scrollIntoView` SEM `behavior` explícito: herda `scroll-behavior` do
  // CSS (`smooth` global em `html`, `auto` sob `prefers-reduced-motion` —
  // globals.css) em vez de fixar "smooth" no JS, que sobrescreveria a
  // preferência do usuário independente do CSS.
  // No modo pinado a rota é outra (R4): tween do ScrollToPlugin no scroll
  // VERTICAL da página (o trilho não é mais scroll container).
  const irPara = useCallback((indice: number) => {
    const rolarPinado = rolarPinadoRef.current;
    if (rolarPinado) {
      rolarPinado(indice);
      return;
    }
    const alvo = painelRefs.current[indice];
    alvo?.scrollIntoView({ inline: "start", block: "nearest" });
  }, []);

  function aoTeclado(ev: React.KeyboardEvent<HTMLOListElement>) {
    const modoPinado = rolarPinadoRef.current !== null;
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      irPara(Math.min(ativo + 1, dimensoes.length - 1));
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      irPara(Math.max(ativo - 1, 0));
    } else if (modoPinado && ev.key === "Home") {
      // Home/End SÓ no modo pinado (R4) — o rail nativo aprovado não os
      // tratava e segue intacto como fallback.
      ev.preventDefault();
      irPara(0);
    } else if (modoPinado && ev.key === "End") {
      ev.preventDefault();
      irPara(dimensoes.length - 1);
    }
  }

  return (
    <div ref={ref} className="flex flex-col gap-4">
      {/* Trilho de progresso D1..D5 + setas — FORA do container que rola
          (nunca clipadas pelo `overflow-x` do trilho abaixo: guarda C2 do
          red-team, anel de foco precisa respirar sem ser cortado).
          `.magnetico` (contrato 1B/R2): dots e setas são das poucas ilhas
          da landing com física de cursor — a classe é só o marcador; quem
          liga é a ilha da landing (Onda 2), inerte sem JS/gsap. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {dimensoes.map((d, i) => (
          <button
            key={d.numero}
            type="button"
            onClick={() => irPara(i)}
            aria-current={i === ativo ? "location" : undefined}
            className={`magnetico magnetico-fino sublinhado-brasa font-mono text-meta uppercase tracking-wide transition-colors duration-[var(--dur-tick)] ${
              i === ativo ? "text-brasa-texto" : "text-ink-3 hover:text-ink"
            }`}
          >
            {d.numero}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {/* Contador do travelling ("02 / 05") — só existe visualmente no
              modo pinado (CSS); decorativo (aria-hidden: os dots com
              aria-current já contam a posição para leitores de tela).
              Alimentado pelo MESMO `ativo` — que no modo pinado tem o
              ScrollTrigger.progress como única fonte (R9). */}
          <span aria-hidden className="filmstrip-contador font-mono text-meta text-ink-3">
            {`${String(ativo + 1).padStart(2, "0")} / ${String(dimensoes.length).padStart(2, "0")}`}
          </span>
          <button
            type="button"
            onClick={() => irPara(Math.max(ativo - 1, 0))}
            disabled={ativo === 0}
            aria-label="Dimensão anterior"
            className="magnetico magnetico-fino seta-filmstrip seta-filmstrip--prev flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              ←
            </span>
          </button>
          <button
            type="button"
            onClick={() => irPara(Math.min(ativo + 1, dimensoes.length - 1))}
            disabled={ativo === dimensoes.length - 1}
            aria-label="Próxima dimensão"
            className="magnetico magnetico-fino seta-filmstrip seta-filmstrip--next flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              →
            </span>
          </button>
        </div>
      </div>

      {/* Hairline de progresso do travelling (contrato
          .filmstrip-trilho-progresso): transform scaleX(var(--prog)); a var
          é escrita via CSSOM na PRÓPRIA folha da barra pelo onUpdate do
          ScrollTrigger (R9). display:none fora do modo pinado — o fallback
          nativo fica pixel-idêntico ao aprovado. */}
      <div ref={barraRef} aria-hidden className="filmstrip-trilho-progresso" />

      {/* Trilho horizontal — snap nativo (Tailwind `snap-x snap-mandatory` +
          `snap-start` nos painéis), sem sequestro de scroll vertical (zero
          listener de `wheel`). Sem JS: lista rolável íntegra, cada painel já
          com seus 5 estratos (impressos/fantasma) estáticos e visíveis.
          `.filmstrip-trilho`: alvo do modo pinado (cinema/filmstrip.css
          desliga overflow/snap sob .filmstrip-pinado; o tween x assume). */}
      {/* `<ol role="list">` restaura a semântica de lista ordenada que o
          `<ol>` original da seção tinha (auditoria 1.3.1: leitor de tela
          anuncia "lista, 5 itens, item N de 5") — `role="list"` explícito
          porque o preflight do Tailwind zera list-style e o Safari/VoiceOver
          deixa de expor listas sem marcador. Um único papel por nó: NÃO usar
          role="group" aqui (sobrescreveria a lista); o rótulo + tabindex +
          setas de teclado convivem com role="list" sem conflito. */}
      <ol
        ref={trilhoRef}
        tabIndex={0}
        role="list"
        aria-label="Cinco dimensões — role para o lado"
        onKeyDown={aoTeclado}
        className="filmstrip-trilho flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-px-4 pb-2 sm:scroll-px-6"
      >
        {dimensoes.map((d, i) => {
          const ehD5 = i === dimensoes.length - 1;
          return (
            <li
              key={d.numero}
              ref={(el) => {
                painelRefs.current[i] = el;
              }}
              className="flex w-[88vw] shrink-0 snap-start flex-col gap-6 border border-line bg-card p-6 sm:w-[80vw] sm:p-8"
            >
              <div className="grid gap-6 sm:grid-cols-[1fr_15rem]">
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="font-mono text-h1 font-semibold text-line-strong">{d.numero}</span>
                    <span className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink">
                      {d.titulo}
                    </span>
                    <span aria-hidden className="text-ink-3">
                      ·
                    </span>
                    <span className="font-mono text-meta text-brasa-texto">{d.fonte}</span>
                  </div>
                  <p className="max-w-prose text-body leading-relaxed text-ink-2">{d.texto}</p>
                </div>

                <div className="flex flex-col gap-2 sm:border-l sm:border-line sm:pl-6">
                  <span className="font-sans text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
                    Camadas até aqui
                  </span>
                  <div className="flex gap-2">
                    {ehD5 ? (
                      <div className="w-5 shrink-0">
                        <ConectorEstratos armado={armado} revelado={revelado} />
                      </div>
                    ) : (
                      <div aria-hidden className="w-5 shrink-0" />
                    )}
                    <div className="flex flex-1 flex-col gap-2">
                      {dimensoes.map((camada, j) => {
                        const impresso = j <= i;
                        return (
                          // `.filmstrip-camada`: alvo dos estratos por
                          // containerAnimation no modo pinado (transform/
                          // opacity do GSAP SÓ nesta div — a barra
                          // `.reveal-regua` filha segue do motor Reveal:
                          // um escritor por propriedade).
                          <div key={camada.numero} className="filmstrip-camada flex items-center gap-2">
                            <span className="w-6 shrink-0 font-mono text-meta text-ink-3">
                              {camada.numero}
                            </span>
                            <span
                              className={
                                impresso
                                  ? classesReveal(
                                      "reveal-regua",
                                      armado,
                                      revelado,
                                      `i-${j + 1} h-1.5 flex-1 bg-line-strong`,
                                    )
                                  : "h-1.5 flex-1 bg-line"
                              }
                            />
                            {impresso && (
                              <span className="hidden max-w-[6rem] truncate font-mono text-meta text-ink-3 sm:inline">
                                {camada.fonte}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
