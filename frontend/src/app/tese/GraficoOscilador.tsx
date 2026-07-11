// Gráfico "oscilador": RSI, Estocástico (%K/%D) ou Williams %R — uma ou
// duas séries oscilando numa faixa limitada, com `linhas_ref` tracejadas
// marcando os níveis de leitura convencionais (RSI 30/70, %R −20/−80). As
// linhas de referência ENTRAM no domínio Y mesmo que nenhum ponto da série
// as alcance no período — senão uma tese "sempre neutra" nunca mostraria
// onde fica o limiar de sobrecompra/sobrevenda.

import { FonteChip, GraficoIndisponivel, NotaFixa } from "./EnvelopeNovo";
import { areaUtil, LegendaGrafico, MolduraGrafico } from "./GraficoEixos";
import {
  caminhoLinha,
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

export function GraficoOscilador({ grafico }: { grafico: Grafico }) {
  const series = grafico.series
    .map((s, i) => ({ nome: s.nome, indice: i, pontos: pontosLinhaValidos(s.pontos) }))
    .filter((s) => s.pontos.length >= 2);
  const linhasRef = grafico.linhas_ref ?? [];

  if (series.length === 0) {
    return <GraficoIndisponivel titulo={grafico.titulo} nota={grafico.nota} fonte={grafico.fonte} />;
  }

  const timestamps = series.flatMap((s) => s.pontos.map((p) => p.t));
  const tMin = Math.min(...timestamps);
  const tMax = Math.max(...timestamps);

  const valores = [...series.flatMap((s) => s.pontos.map((p) => p.v)), ...linhasRef.map((l) => l.valor)];
  const [vMin, vMax] = domCompadding(Math.min(...valores), Math.max(...valores));

  const { x0, x1, y0, y1 } = areaUtil();
  const escalaX = criarEscala(tMin, tMax, x0, x1);
  const escalaY = criarEscala(vMin, vMax, y1, y0);

  const caminhosSeries = series.map((s) => ({
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

  const descricao = `${grafico.titulo}. Eixo Y em ${rotuloEixo(grafico.eixo_y)}. ${series
    .map((s) => s.nome)
    .join(", ")}${
    linhasRef.length > 0
      ? `. Linhas de referência: ${linhasRef.map((l) => `${l.nome} em ${formatarTick(l.valor, grafico.eixo_y)}`).join(", ")}`
      : ""
  }. Fonte: ${grafico.fonte.descricao}${
    grafico.fonte.dt_referencia ? `, ${formatarData(grafico.fonte.dt_referencia)}` : ""
  }. ${grafico.nota}`;

  return (
    <figure className="flex flex-col gap-3 border border-line bg-card p-5">
      <figcaption className="font-display text-lede font-semibold text-ink">{grafico.titulo}</figcaption>

      <MolduraGrafico idBase={grafico.id} titulo={grafico.titulo} descricao={descricao} ticksY={ticksY} ticksX={ticksX}>
        {linhasRef.map((l, i) => {
          const y = escalaY(l.valor);
          if (!Number.isFinite(y)) return null;
          return (
            <g key={`ref-${i}`}>
              <line
                x1={x0}
                x2={x1}
                y1={y}
                y2={y}
                className="stroke-grafico-6"
                strokeWidth={1}
                strokeDasharray="4 4"
              />
              <text x={x1} y={y - 4} textAnchor="end" className="fill-ink-3 font-mono text-label">
                {l.nome}
              </text>
            </g>
          );
        })}

        {caminhosSeries.map((s) =>
          s.d ? <path key={s.indice} d={s.d} fill="none" className={corTraco(s.indice)} strokeWidth={1.75} /> : null,
        )}
      </MolduraGrafico>

      <LegendaGrafico
        itens={[
          ...caminhosSeries.map((s) => ({ nome: s.nome, classeCor: corFundo(s.indice) })),
          ...linhasRef.map((l) => ({
            nome: `${l.nome} (${formatarTick(l.valor, grafico.eixo_y)})`,
            classeCor: "bg-grafico-6",
            tracejado: true,
          })),
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
        {linhasRef.length > 0 && (
          <tfoot>
            <tr>
              <td colSpan={series.length + 1}>
                Linhas de referência: {linhasRef.map((l) => `${l.nome} = ${l.valor}`).join("; ")}
              </td>
            </tr>
          </tfoot>
        )}
        </table>
      </div>
    </figure>
  );
}
