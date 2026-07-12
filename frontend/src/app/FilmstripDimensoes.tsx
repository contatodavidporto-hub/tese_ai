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

import { useCallback, useEffect, useRef, useState } from "react";

import { classesReveal, useReveal } from "@/components/motion/Reveal";

export type DimensaoFilmstrip = {
  numero: string;
  titulo: string;
  fonte: string;
  texto: string;
};

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
  const { ref, armado, revelado } = useReveal<HTMLDivElement>();
  const trilhoRef = useRef<HTMLDivElement | null>(null);
  const painelRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [ativo, setAtivo] = useState(0);

  // Detecta o painel mais visível DENTRO do trilho — `root` é o próprio
  // container que rola horizontalmente (nunca a viewport inteira, nunca um
  // listener de `scroll` cru). Mesmo espírito de useSecaoAtiva.ts (reduz por
  // interseção), aqui usando `intersectionRatio` em vez de posição vertical
  // — a métrica certa para um `root` horizontal.
  useEffect(() => {
    const container = trilhoRef.current;
    const paineis = painelRefs.current.filter((el): el is HTMLDivElement => el !== null);
    if (!container || paineis.length === 0) return;

    const observer = new IntersectionObserver(
      (entradas) => {
        setAtivo((atual) => {
          const maisVisivel = entradas.reduce((melhor, entrada) =>
            entrada.intersectionRatio > melhor.intersectionRatio ? entrada : melhor,
          );
          if (maisVisivel.intersectionRatio < 0.5) return atual;
          const indice = paineis.indexOf(maisVisivel.target as HTMLDivElement);
          return indice === -1 ? atual : indice;
        });
      },
      { root: container, threshold: [0, 0.25, 0.5, 0.75, 1] },
    );
    paineis.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [dimensoes.length]);

  // `scrollIntoView` SEM `behavior` explícito: herda `scroll-behavior` do
  // CSS (`smooth` global em `html`, `auto` sob `prefers-reduced-motion` —
  // globals.css) em vez de fixar "smooth" no JS, que sobrescreveria a
  // preferência do usuário independente do CSS.
  const irPara = useCallback((indice: number) => {
    const alvo = painelRefs.current[indice];
    alvo?.scrollIntoView({ inline: "start", block: "nearest" });
  }, []);

  function aoTeclado(ev: React.KeyboardEvent<HTMLDivElement>) {
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      irPara(Math.min(ativo + 1, dimensoes.length - 1));
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      irPara(Math.max(ativo - 1, 0));
    }
  }

  return (
    <div ref={ref} className="flex flex-col gap-4">
      {/* Trilho de progresso D1..D5 + setas — FORA do container que rola
          (nunca clipadas pelo `overflow-x` do trilho abaixo: guarda C2 do
          red-team, anel de foco precisa respirar sem ser cortado). */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {dimensoes.map((d, i) => (
          <button
            key={d.numero}
            type="button"
            onClick={() => irPara(i)}
            aria-current={i === ativo ? "location" : undefined}
            className={`sublinhado-brasa font-mono text-meta uppercase tracking-wide transition-colors duration-[var(--dur-tick)] ${
              i === ativo ? "text-brasa-texto" : "text-ink-3 hover:text-ink"
            }`}
          >
            {d.numero}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => irPara(Math.max(ativo - 1, 0))}
            disabled={ativo === 0}
            aria-label="Dimensão anterior"
            className="seta-filmstrip seta-filmstrip--prev flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
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
            className="seta-filmstrip seta-filmstrip--next flex h-10 w-10 items-center justify-center border border-field font-mono text-ui text-ink disabled:opacity-60"
          >
            <span aria-hidden className="seta-filmstrip__glifo">
              →
            </span>
          </button>
        </div>
      </div>

      {/* Trilho horizontal — snap nativo (Tailwind `snap-x snap-mandatory` +
          `snap-start` nos painéis), sem sequestro de scroll vertical (zero
          listener de `wheel`). Sem JS: lista rolável íntegra, cada painel já
          com seus 5 estratos (impressos/fantasma) estáticos e visíveis. */}
      <div
        ref={trilhoRef}
        tabIndex={0}
        role="group"
        aria-label="Cinco dimensões — role para o lado"
        onKeyDown={aoTeclado}
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-px-4 pb-2 sm:scroll-px-6"
      >
        {dimensoes.map((d, i) => {
          const ehD5 = i === dimensoes.length - 1;
          return (
            <div
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
                          <div key={camada.numero} className="flex items-center gap-2">
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
