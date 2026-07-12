// Gráfico "macd": linha MACD + linha de sinal + histograma (linha − sinal),
// no mesmo eixo Y (mesma escala) e mesmo eixo X (data). O contrato do
// envelope não separa um campo "histograma" — o backend manda as 3 séries em
// `series[]` (contrato: "MACD (12, 26, 9)" → linha/sinal/histograma, mesmo
// vocabulário do `detalhe` do indicador em `tecnica`); este componente
// reconhece a série de histograma pelo NOME (contém "hist", robusto a
// acentuação) e desenha como barras a partir do zero — as demais como linha.

import { FonteChip, GraficoIndisponivel, NotaFixa } from "./EnvelopeNovo";
import { areaUtil, LegendaGrafico, MolduraGrafico } from "./GraficoEixos";
import {
  caminhoLinha,
  classeEntradaSerie,
  corFundo,
  corTraco,
  criarEscala,
  domCompadding,
  formatarData,
  formatarDataCurta,
  formatarTick,
  indicesEspacados,
  pontosLinhaValidos,
  rotuloEixo,
  ticksLineares,
  type PontoLinhaValido,
} from "./formatacao";
import type { Grafico } from "./types";

const QTD_TICKS_Y = 5;
const QTD_TICKS_X = 6;
const LARGURA_BARRA = 2.4;

function ehSerieHistograma(nome: string): boolean {
  return /hist/i.test(nome);
}

export function GraficoMacd({ grafico }: { grafico: Grafico }) {
  const series = grafico.series
    .map((s, i) => ({ nome: s.nome, indice: i, histograma: ehSerieHistograma(s.nome), pontos: pontosLinhaValidos(s.pontos) }))
    .filter((s) => s.pontos.length >= 2);

  if (series.length === 0) {
    return <GraficoIndisponivel titulo={grafico.titulo} nota={grafico.nota} fonte={grafico.fonte} />;
  }

  const timestamps = series.flatMap((s) => s.pontos.map((p) => p.t));
  const tMin = Math.min(...timestamps);
  const tMax = Math.max(...timestamps);

  const valoresBrutos = series.flatMap((s) => s.pontos.map((p) => p.v));
  // O MACD oscila em torno de zero — força o zero a sempre aparecer no
  // domínio, mesmo quando toda a série ficou de um único lado no período.
  const minComZero = Math.min(0, ...valoresBrutos);
  const maxComZero = Math.max(0, ...valoresBrutos);
  const [vMin, vMax] = domCompadding(minComZero, maxComZero);

  const { x0, x1, y0, y1 } = areaUtil();
  const escalaX = criarEscala(tMin, tMax, x0, x1);
  const escalaY = criarEscala(vMin, vMax, y1, y0);
  const yZero = escalaY(0);

  const linhas = series.filter((s) => !s.histograma);
  const histograma = series.find((s) => s.histograma);

  const caminhosLinhas = linhas.map((s) => ({
    nome: s.nome,
    indice: s.indice,
    d: caminhoLinha(s.pontos.map((p) => ({ x: escalaX(p.t), y: escalaY(p.v) }))),
  }));

  const ticksY = ticksLineares(vMin, vMax, QTD_TICKS_Y).map((v) => ({
    pos: escalaY(v),
    rotulo: formatarTick(v, grafico.eixo_y),
  }));

  const serieReferencia: { pontos: PontoLinhaValido[] } | undefined =
    [...series].sort((a, b) => b.pontos.length - a.pontos.length)[0];
  const ticksX = serieReferencia
    ? indicesEspacados(serieReferencia.pontos.length, QTD_TICKS_X).map((i) => {
        const p = serieReferencia.pontos[i];
        return { pos: escalaX(p.t), rotulo: formatarDataCurta(p.d) };
      })
    : [];

  const descricao = `${grafico.titulo}. Eixo Y em ${rotuloEixo(grafico.eixo_y)}, linha do zero em destaque. ${series
    .map((s) => s.nome)
    .join(", ")}. Fonte: ${grafico.fonte.descricao}${
    grafico.fonte.dt_referencia ? `, ${formatarData(grafico.fonte.dt_referencia)}` : ""
  }. ${grafico.nota}`;

  return (
    <figure className="flex flex-col gap-3 border border-line bg-card p-5">
      <figcaption className="font-display text-lede font-semibold text-ink">{grafico.titulo}</figcaption>

      <MolduraGrafico idBase={grafico.id} titulo={grafico.titulo} descricao={descricao} ticksY={ticksY} ticksX={ticksX}>
        {/* Linha do zero — mais forte que a grade comum (é a referência do
            indicador: positivo acima, negativo abaixo). */}
        <line x1={x0} x2={x1} y1={yZero} y2={yZero} className="stroke-line-strong" strokeWidth={1} />

        {/* `.traco-grafico-barra`: fade-only (§5, MOLDE MACIO) — retângulo
            sólido sem stroke, `stroke-dashoffset` não se aplicaria; a altura/
            posição é assinada (positivo cresce para cima, negativo para
            baixo a partir do zero), então um `scaleY` compositor-safe
            precisaria de `transform-origin` distinto por sinal — a favor da
            fidelidade factual sobre o espetáculo, opacity simples evita
            qualquer risco de geometria errada num dado financeiro. */}
        {histograma?.pontos.map((p, i) => {
          const xCentro = escalaX(p.t);
          const yValor = escalaY(p.v);
          if (!Number.isFinite(xCentro) || !Number.isFinite(yValor)) return null;
          const positivo = p.v >= 0;
          const yTopo = Math.min(yValor, yZero);
          const altura = Math.abs(yValor - yZero);
          return (
            <rect
              key={i}
              x={xCentro - LARGURA_BARRA / 2}
              y={yTopo}
              width={LARGURA_BARRA}
              height={Math.max(altura, 0.5)}
              className={`${positivo ? "fill-grafico-3" : "fill-grafico-4"} traco-grafico-barra`}
            />
          );
        })}

        {caminhosLinhas.map((s, pos) =>
          s.d ? (
            <path
              key={s.indice}
              d={s.d}
              fill="none"
              pathLength={1}
              className={`${corTraco(s.indice)} ${classeEntradaSerie(pos)}`}
              strokeWidth={1.75}
            />
          ) : null,
        )}
      </MolduraGrafico>

      <LegendaGrafico
        itens={[
          ...caminhosLinhas.map((s) => ({ nome: s.nome, classeCor: corFundo(s.indice) })),
          ...(histograma
            ? [
                { nome: `${histograma.nome} (positivo)`, classeCor: "bg-grafico-3" },
                { nome: `${histograma.nome} (negativo)`, classeCor: "bg-grafico-4" },
              ]
            : []),
        ]}
      />

      <NotaFixa texto={grafico.nota} />
      <FonteChip fonte={grafico.fonte} />

      {/* Wrapper sr-only obrigatorio: `sr-only` direto na <table> nao contem
          a largura (table-layout auto ignora width:1px) e vaza para o
          scrollWidth do documento no mobile. */}
      <div className="sr-only">
        <table>
        <caption>{grafico.titulo} — dados por data</caption>
        <thead>
          <tr>
            <th scope="col">Data</th>
            {series.map((s) => (
              <th key={s.indice} scope="col">
                {s.nome}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(serieReferencia?.pontos ?? []).map((p, i) => (
            <tr key={i}>
              <td>{formatarData(p.d)}</td>
              {series.map((s) => (
                <td key={s.indice}>{s.pontos.find((pp) => pp.d === p.d)?.v ?? "dado não encontrado"}</td>
              ))}
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </figure>
  );
}
