// Despacha um `Grafico` do envelope para o componente certo pelo campo
// `tipo` (contrato do envelope v3, §1) — único ponto que conhece o mapa
// tipo→componente; `SecaoTecnica` só itera a lista e chama este componente.

import { GraficoLinha } from "./GraficoLinha";
import { GraficoMacd } from "./GraficoMacd";
import { GraficoOscilador } from "./GraficoOscilador";
import type { Grafico } from "./types";

export function GraficoTese({ grafico }: { grafico: Grafico }) {
  switch (grafico.tipo) {
    case "linha":
    case "linha_faixa":
      return <GraficoLinha grafico={grafico} />;
    case "macd":
      return <GraficoMacd grafico={grafico} />;
    case "oscilador":
      return <GraficoOscilador grafico={grafico} />;
    default:
      // Tipo futuro desconhecido do backend: string mais nova que o front —
      // omite (fail-closed) em vez de arriscar um <svg> com geometria que
      // este componente não sabe interpretar.
      return null;
  }
}
