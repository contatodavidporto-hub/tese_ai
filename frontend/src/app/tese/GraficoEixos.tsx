// Moldura SVG compartilhada pelos 3 componentes de gráfico (GraficoLinha,
// GraficoMacd, GraficoOscilador): grade + eixos + `<title>/<desc>` + `role`
// de imagem. Geometria só via atributos de apresentação (`x`/`y`/`d`/
// `points`/viewBox) — cor/traço só via classes Tailwind ESTÁTICAS (nunca
// `style=`, CSP `style-src` sem `unsafe-inline` — ver src/proxy.ts). Zero
// interatividade: nenhum destes componentes precisa de `"use client"`.

import type { ReactNode } from "react";

export const LARGURA_GRAFICO = 640;
export const ALTURA_GRAFICO = 280;
export const MARGEM_GRAFICO = { top: 16, right: 16, bottom: 32, left: 56 } as const;

export type TickPosicionado = { pos: number; rotulo: string };

export function areaUtil() {
  return {
    x0: MARGEM_GRAFICO.left,
    x1: LARGURA_GRAFICO - MARGEM_GRAFICO.right,
    y0: MARGEM_GRAFICO.top,
    y1: ALTURA_GRAFICO - MARGEM_GRAFICO.bottom,
  };
}

export function MolduraGrafico({
  idBase,
  titulo,
  descricao,
  ticksY,
  ticksX,
  altura = ALTURA_GRAFICO,
  children,
}: {
  idBase: string;
  titulo: string;
  descricao: string;
  ticksY: TickPosicionado[];
  ticksX: TickPosicionado[];
  altura?: number;
  children: ReactNode;
}) {
  const { x0, x1 } = areaUtil();
  const y1Real = altura - MARGEM_GRAFICO.bottom;
  return (
    <svg
      viewBox={`0 0 ${LARGURA_GRAFICO} ${altura}`}
      role="img"
      aria-labelledby={`${idBase}-titulo ${idBase}-desc`}
      className="h-auto w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <title id={`${idBase}-titulo`}>{titulo}</title>
      <desc id={`${idBase}-desc`}>{descricao}</desc>

      {/* Grade horizontal — sutil, decorativa (mesma isenção de contraste de
          `border-line`, DESIGN-TOKENS.md §1: "isenta de AA, não comunica
          estado sozinha"; os RÓTULOS ao lado é que carregam a informação). */}
      {ticksY.map((t, i) => (
        <line key={`grid-${i}`} x1={x0} x2={x1} y1={t.pos} y2={t.pos} className="stroke-line" strokeWidth={1} />
      ))}

      {/* Eixo base (linha do zero/piso do gráfico) — mais forte que a grade. */}
      <line x1={x0} x2={x1} y1={y1Real} y2={y1Real} className="stroke-line-strong" strokeWidth={1} />

      {/* Rótulos do eixo Y — mono (número factual), alinhados à direita da
          margem esquerda. */}
      {ticksY.map((t, i) => (
        <text
          key={`ty-${i}`}
          x={x0 - 8}
          y={t.pos}
          textAnchor="end"
          dominantBaseline="middle"
          className="fill-ink-3 font-mono text-label"
        >
          {t.rotulo}
        </text>
      ))}

      {/* Rótulos do eixo X (datas curtas pt-BR) — abaixo do eixo base. */}
      {ticksX.map((t, i) => (
        <text key={`tx-${i}`} x={t.pos} y={y1Real + 18} textAnchor="middle" className="fill-ink-3 font-mono text-label">
          {t.rotulo}
        </text>
      ))}

      {children}
    </svg>
  );
}

// Legenda visível (não só sr-only): quadrado de cor + nome da série — o
// `<table className="sr-only">` ao lado cobre o leitor de tela; esta legenda
// cobre quem enxerga mas não consegue distinguir só pela cor (WCAG 1.4.1).
export function LegendaGrafico({ itens }: { itens: { nome: string; classeCor: string; tracejado?: boolean }[] }) {
  if (itens.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
      {itens.map((item, i) => (
        <li key={i} className="flex items-center gap-1.5 font-sans text-ui text-ink-2">
          <span
            aria-hidden
            className={`inline-block h-0.5 w-4 ${item.classeCor} ${item.tracejado ? "opacity-70" : ""}`}
          />
          {item.nome}
        </li>
      ))}
    </ul>
  );
}
