// Gráfico "linha" (uma ou mais séries, ex.: SMA overlays) e "linha_faixa"
// (a mesma coisa + a faixa de Bollinger desenhada como uma área via <path>,
// contorno superior→inferior fechando o polígono — ver `caminhoFaixa` em
// formatacao.ts). SVG React inline; geometria só por atributos de
// apresentação; cor só pelas classes ESTÁTICAS `stroke-grafico-*`/
// `fill-grafico-*` (correção A16). Sem `"use client"`: nenhum estado/efeito,
// puro presentacional — só é renderizado dentro da árvore client de
// `/tese` (TeseClient.tsx) porque quem o importa (SecaoTecnica → TeseView)
// já está nela, não porque precise de interatividade própria.

import { FonteChip, GraficoIndisponivel, NotaFixa } from "./EnvelopeNovo";
import {
  areaUtil,
  LegendaGrafico,
  MolduraGrafico,
} from "./GraficoEixos";
import {
  caminhoFaixa,
  caminhoLinha,
  corFundo,
  corTraco,
  criarEscala,
  domCompadding,
  formatarData,
  formatarDataCurta,
  formatarTick,
  indicesEspacados,
  pontosFaixaValidos,
  pontosLinhaValidos,
  rotuloEixo,
  ticksLineares,
  type PontoLinhaValido,
} from "./formatacao";
import type { Grafico } from "./types";

const QTD_TICKS_Y = 5;
const QTD_TICKS_X = 6;

export function GraficoLinha({ grafico }: { grafico: Grafico }) {
  const series = grafico.series
    .map((s, i) => ({ nome: s.nome, indice: i, pontos: pontosLinhaValidos(s.pontos) }))
    .filter((s) => s.pontos.length >= 2);
  const faixaValida = grafico.faixa ? pontosFaixaValidos(grafico.faixa.pontos) : [];

  if (series.length === 0 && faixaValida.length === 0) {
    return <GraficoIndisponivel titulo={grafico.titulo} nota={grafico.nota} fonte={grafico.fonte} />;
  }

  const timestamps = [
    ...series.flatMap((s) => s.pontos.map((p) => p.t)),
    ...faixaValida.map((p) => p.t),
  ];
  const tMin = Math.min(...timestamps);
  const tMax = Math.max(...timestamps);

  const valores = [
    ...series.flatMap((s) => s.pontos.map((p) => p.v)),
    ...faixaValida.flatMap((p) => [p.sup, p.inf]),
  ];
  const [vMin, vMax] = domCompadding(Math.min(...valores), Math.max(...valores));

  const { x0, x1, y0, y1 } = areaUtil();
  const escalaX = criarEscala(tMin, tMax, x0, x1);
  const escalaY = criarEscala(vMin, vMax, y1, y0); // inverte: valor maior → y menor

  const caminhosSeries = series.map((s) => ({
    nome: s.nome,
    indice: s.indice,
    d: caminhoLinha(s.pontos.map((p) => ({ x: escalaX(p.t), y: escalaY(p.v) }))),
  }));

  const caminhoBanda =
    grafico.faixa && faixaValida.length > 0
      ? caminhoFaixa(
          faixaValida.map((p) => ({ x: escalaX(p.t), y: escalaY(p.sup) })),
          faixaValida.map((p) => ({ x: escalaX(p.t), y: escalaY(p.inf) })),
        )
      : "";

  const ticksY = ticksLineares(vMin, vMax, QTD_TICKS_Y).map((v) => ({
    pos: escalaY(v),
    rotulo: formatarTick(v, grafico.eixo_y),
  }));

  // Ticks X a partir da série mais longa (melhor amostragem de datas).
  const serieReferencia: { pontos: PontoLinhaValido[] } | undefined = [...series].sort(
    (a, b) => b.pontos.length - a.pontos.length,
  )[0];
  const ticksX = serieReferencia
    ? indicesEspacados(serieReferencia.pontos.length, QTD_TICKS_X).map((i) => {
        const p = serieReferencia.pontos[i];
        return { pos: escalaX(p.t), rotulo: formatarDataCurta(p.d) };
      })
    : [];

  const linhasRef = grafico.linhas_ref ?? [];

  const descricao = `${grafico.titulo}. Eixo Y em ${rotuloEixo(grafico.eixo_y)}. ${series
    .map((s) => s.nome)
    .join(", ")}${grafico.faixa ? `, faixa ${grafico.faixa.nome}` : ""}. Fonte: ${grafico.fonte.descricao}${
    grafico.fonte.dt_referencia ? `, ${formatarData(grafico.fonte.dt_referencia)}` : ""
  }. ${grafico.nota}`;

  return (
    <figure className="flex flex-col gap-3 border border-line bg-card p-5">
      <figcaption className="font-display text-lede font-semibold text-ink">{grafico.titulo}</figcaption>

      <MolduraGrafico
        idBase={grafico.id}
        titulo={grafico.titulo}
        descricao={descricao}
        ticksY={ticksY}
        ticksX={ticksX}
      >
        {/* Faixa de Bollinger — área entre `sup` e `inf`, ATRÁS das linhas. */}
        {caminhoBanda && <path d={caminhoBanda} className="fill-grafico-5/15 stroke-none" />}

        {/* Linhas de referência (se vierem num gráfico de linha — raro, mas
            o tipo permite; ex.: níveis de Fibonacci sobre o preço). */}
        {linhasRef.map((l, i) => {
          const y = escalaY(l.valor);
          if (!Number.isFinite(y)) return null;
          return (
            <line
              key={`ref-${i}`}
              x1={x0}
              x2={x1}
              y1={y}
              y2={y}
              className="stroke-grafico-6"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
          );
        })}

        {caminhosSeries.map((s) =>
          s.d ? (
            <path key={s.indice} d={s.d} fill="none" className={corTraco(s.indice)} strokeWidth={1.75} />
          ) : null,
        )}
      </MolduraGrafico>

      <LegendaGrafico
        itens={[
          ...caminhosSeries.map((s) => ({ nome: s.nome, classeCor: corFundo(s.indice) })),
          ...(grafico.faixa ? [{ nome: grafico.faixa.nome, classeCor: "bg-grafico-5", tracejado: true }] : []),
        ]}
      />

      <NotaFixa texto={grafico.nota} />
      <FonteChip fonte={grafico.fonte} />

      {/* Tabela oculta (WCAG): os mesmos dados desenhados acima, em texto.
          O wrapper <div className="sr-only"> é obrigatório: `sr-only` direto
          na <table> não contém a largura (table-layout auto ignora width:1px)
          e a caixa fantasma vaza para o scrollWidth do documento no mobile. */}
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
            {grafico.faixa && (
              <>
                <th scope="col">{grafico.faixa.nome} — superior</th>
                <th scope="col">{grafico.faixa.nome} — inferior</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {(serieReferencia?.pontos ?? []).map((p, i) => (
            <tr key={i}>
              <td>{formatarData(p.d)}</td>
              {series.map((s) => (
                <td key={s.indice}>{s.pontos.find((pp) => pp.d === p.d)?.v ?? "dado não encontrado"}</td>
              ))}
              {grafico.faixa && (
                <>
                  <td>{faixaValida.find((f) => f.d === p.d)?.sup ?? "dado não encontrado"}</td>
                  <td>{faixaValida.find((f) => f.d === p.d)?.inf ?? "dado não encontrado"}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </figure>
  );
}
