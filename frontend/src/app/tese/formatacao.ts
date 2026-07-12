// Funções puras compartilhadas pelos blocos novos do envelope ("Tese
// Profunda"): formatação pt-BR (números/datas) e a geometria dos gráficos
// SVG. Zero JSX aqui de propósito — mantém `GraficoLinha/Macd/Oscilador` e as
// seções novas magras, e deixa a matemática testável isoladamente.

import type { PontoFaixaGrafico, PontoGrafico } from "./types";

// ---------------------------------------------------------------------------
// Números e datas pt-BR
// ---------------------------------------------------------------------------

export type UnidadeValor = "BRL" | "pct" | "indice" | "razao" | "x";

// Uma casa a mais para valores pequenos (ex.: RSI/estocástico ~costumam ter
// 1-2 casas; preço de FII pode ser < 10) e menos para valores grandes (evita
// rótulo de eixo/tabela gigante, ex.: "1.234" em vez de "1.234,00").
function casasDecimais(valor: number): number {
  const abs = Math.abs(valor);
  if (abs === 0) return 2;
  if (abs < 10) return 2;
  if (abs < 1000) return 2;
  return 0;
}

// Formata um valor já numérico (o backend nunca manda string formatada —
// "Números viajam como number (JSON); o frontend formata pt-BR", contrato
// §0) segundo a unidade declarada pelo próprio bloco do envelope. `null`/
// não-finito devolve `null` — quem chama decide o fallback visual ("dado não
// encontrado"), nunca inventa um "0" ou um traço silencioso.
export function formatarValor(valor: number | null | undefined, unidade: UnidadeValor): string | null {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return null;
  switch (unidade) {
    case "BRL":
      return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: casasDecimais(valor),
      }).format(valor);
    case "pct":
      return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor)}%`;
    case "x":
      return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor)}x`;
    case "razao":
    case "indice":
    default:
      return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: casasDecimais(valor) }).format(valor);
  }
}

// Variante de `formatarValor` para os campos de Valuation cujo `unidade` é
// STRING LIVRE no contrato (`cenarios[].unidade`, `faixa.unidade` — não a
// união fechada `UnidadeValor`, porque o backend pode nomear a unidade de um
// modelo específico, ex.: "R$/cota"). Reconhece os alias mais comuns e cai
// para "número pt-BR + unidade literal" no resto — nunca formata errado por
// não reconhecer a string, só fica menos elegante.
export function formatarValorLivre(valor: number | null | undefined, unidadeLivre: string): string | null {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return null;
  const u = unidadeLivre.trim().toLowerCase();
  if (u === "brl" || u === "r$") return formatarValor(valor, "BRL");
  if (u === "pct" || u === "%") return formatarValor(valor, "pct");
  if (u === "x") return formatarValor(valor, "x");
  if (u === "indice" || u === "razao") return formatarValor(valor, u as UnidadeValor);
  const numero = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: casasDecimais(valor) }).format(valor);
  return unidadeLivre.trim() ? `${numero} ${unidadeLivre.trim()}` : numero;
}

// Rótulo de eixo/tick de gráfico: mais compacto que `formatarValor` (sem
// símbolo de moeda/percentual repetido a cada tick — o eixo já anuncia a
// unidade uma vez via `rotuloEixo`).
export function formatarTick(valor: number, eixoY: "BRL" | "indice" | "pct"): string {
  const casas = eixoY === "pct" ? 1 : casasDecimais(valor);
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: casas }).format(valor);
}

export function rotuloEixo(eixoY: "BRL" | "indice" | "pct"): string {
  return eixoY === "BRL" ? "R$" : eixoY === "pct" ? "%" : "pts";
}

// dd/mm/aaaa — mesmo padrão de `formatData` em TeseView.tsx (data ISO local,
// sem deslocamento de fuso: acrescenta T00:00:00 antes de `new Date`).
export function formatarData(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR");
}

// dd/mm — rótulo curto para eixo X de gráfico (5-7 ticks; "dd/mm/aaaa"
// inteiro lotaria o eixo).
export function formatarDataCurta(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

// ---------------------------------------------------------------------------
// Paleta fixa de gráficos — classes ESTÁTICAS (ver nota em globals.css,
// correção A16). Os arrays abaixo são a ÚNICA fonte de seleção "dinâmica" de
// cor: o literal de cada classe aparece aqui por extenso, então o scanner do
// Tailwind sempre o encontra — só o ÍNDICE escolhido em runtime é dinâmico.
// ---------------------------------------------------------------------------

export const CLASSES_TRACO_GRAFICO = [
  "stroke-grafico-1",
  "stroke-grafico-2",
  "stroke-grafico-3",
  "stroke-grafico-4",
  "stroke-grafico-5",
  "stroke-grafico-6",
] as const;

export const CLASSES_PREENCHIMENTO_GRAFICO = [
  "fill-grafico-1",
  "fill-grafico-2",
  "fill-grafico-3",
  "fill-grafico-4",
  "fill-grafico-5",
  "fill-grafico-6",
] as const;

// `background-color` (não `fill`/`stroke`, que só se aplicam a SVG) — usada
// pelo quadrado de cor da legenda visível (`LegendaGrafico`, elemento
// `<span>` fora do <svg>).
export const CLASSES_FUNDO_GRAFICO = [
  "bg-grafico-1",
  "bg-grafico-2",
  "bg-grafico-3",
  "bg-grafico-4",
  "bg-grafico-5",
  "bg-grafico-6",
] as const;

export function corTraco(indiceSerie: number): string {
  return CLASSES_TRACO_GRAFICO[indiceSerie % CLASSES_TRACO_GRAFICO.length];
}

export function corPreenchimento(indiceSerie: number): string {
  return CLASSES_PREENCHIMENTO_GRAFICO[indiceSerie % CLASSES_PREENCHIMENTO_GRAFICO.length];
}

export function corFundo(indiceSerie: number): string {
  return CLASSES_FUNDO_GRAFICO[indiceSerie % CLASSES_FUNDO_GRAFICO.length];
}

// ---------------------------------------------------------------------------
// Entrada em cena dos gráficos ("a tinta desenhando no papel" — §5,
// .maestro/direcao-de-arte-cinema.md). Classe pura, zero JSX: monta o par
// `.traco-grafico`(+ posição) que `GraficoLinha/Macd/Oscilador` aplicam nos
// `<path>` de série — o hook mínimo autorizado pela missão (junto de
// `pathLength={1}`, aplicado direto no JSX). A escolha do delay/duração de
// cada posição vive só em CSS (globals.css, seletores `.i-2`…`.i-6`) — este
// helper só decide QUAL classe de posição cada série recebe, reaproveitando
// o MESMO vocabulário `.i-N` já usado no stagger de citações/cláusulas
// (TeseView.tsx, como-funciona/page.tsx) em vez de inventar um mecanismo novo.
// ---------------------------------------------------------------------------

// `posicaoRenderizada` é o índice (0-based) da série DEPOIS do filtro de
// pontos válidos (`pontosLinhaValidos`) — não o índice de cor original
// (`s.indice`/`corTraco`): a 1ª série que efetivamente desenha é sempre a
// "primária" da encenação, mesmo que sua cor não seja `grafico-1` (ex.: a
// série 0 ficou sem pontos válidos e foi filtrada). Teto `i-6`: mesmo
// tamanho de `CLASSES_TRACO_GRAFICO` — séries além da 6ª (raro) reaproveitam
// o delay da 6ª em vez de ficarem sem stagger.
export function classeEntradaSerie(posicaoRenderizada: number): string {
  if (posicaoRenderizada <= 0) return "traco-grafico";
  return `traco-grafico i-${Math.min(posicaoRenderizada + 1, 6)}`;
}

// ---------------------------------------------------------------------------
// Geometria SVG — escalas, ticks, filtro de pontos não-finitos (A16: "path[d]
// não-vazio e sem NaN"). Puramente numérico; nenhuma função aqui toca o DOM.
// ---------------------------------------------------------------------------

// timestamp (ms) de uma data ISO "YYYY-MM-DD", ou `null` se inválida — nunca
// deixa um `NaN` vazar para quem soma/compara domínio.
function timestamp(iso: string): number | null {
  const t = new Date(`${iso}T00:00:00`).getTime();
  return Number.isFinite(t) ? t : null;
}

export type PontoXY = { x: number; y: number };

// `d` original preservado ao lado do timestamp: formatar o rótulo do eixo X
// a partir do `d` ISO (não de `new Date(t).toISOString()`) evita um
// round-trip local→UTC que deslocaria a data em fusos horários negativos.
export type PontoLinhaValido = { d: string; t: number; v: number };
export type PontoFaixaValida = { d: string; t: number; sup: number; inf: number };

// Filtra pontos {d,v} com data inválida OU valor não-finito — nunca chega um
// NaN a um atributo `d`/`points` de <path>/<polyline>.
export function pontosLinhaValidos(pontos: PontoGrafico[]): PontoLinhaValido[] {
  const out: PontoLinhaValido[] = [];
  for (const p of pontos) {
    const t = timestamp(p.d);
    if (t === null || !Number.isFinite(p.v)) continue;
    out.push({ d: p.d, t, v: p.v });
  }
  return out;
}

export function pontosFaixaValidos(pontos: PontoFaixaGrafico[]): PontoFaixaValida[] {
  const out: PontoFaixaValida[] = [];
  for (const p of pontos) {
    const t = timestamp(p.d);
    if (t === null || !Number.isFinite(p.sup) || !Number.isFinite(p.inf)) continue;
    out.push({ d: p.d, t, sup: p.sup, inf: p.inf });
  }
  return out;
}

// Escala linear domínio→alcance (mesma forma de uma escala d3, sem a
// dependência): domínio degenerado (min===max) devolve o ponto médio do
// alcance para todo valor, em vez de dividir por zero.
export function criarEscala(domMin: number, domMax: number, alcMin: number, alcMax: number): (v: number) => number {
  const largura = domMax - domMin;
  if (largura === 0 || !Number.isFinite(largura)) {
    const meio = (alcMin + alcMax) / 2;
    return () => meio;
  }
  return (v: number) => alcMin + ((v - domMin) / largura) * (alcMax - alcMin);
}

// N ticks igualmente espaçados entre min e max (inclusive) — "4-6 ticks y".
// min>max ou não-finitos devolve [] (chamador simplesmente não desenha grid).
export function ticksLineares(min: number, max: number, quantidade: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || quantidade < 1) return [];
  if (min === max) return [min];
  const passo = (max - min) / (quantidade - 1);
  return Array.from({ length: quantidade }, (_, i) => min + passo * i);
}

// Índices igualmente espaçados dentro de [0, total) — "5-7 ticks x": usado
// para escolher QUAIS pontos de uma série (já ordenada por data) recebem
// rótulo no eixo X, sem lotar o eixo com todo pregão.
export function indicesEspacados(total: number, quantidade: number): number[] {
  if (total <= 0 || quantidade < 1) return [];
  if (total <= quantidade) return Array.from({ length: total }, (_, i) => i);
  const passo = (total - 1) / (quantidade - 1);
  const idx = new Set<number>();
  for (let i = 0; i < quantidade; i++) idx.add(Math.round(passo * i));
  return [...idx].sort((a, b) => a - b);
}

// Amplia levemente o domínio de valores (padding visual — sem isso, o ponto
// máximo encosta no topo do SVG e a linha corta a moldura).
export function domCompadding(min: number, max: number, fracao = 0.08): [number, number] {
  if (min === max) return [min - 1, max + 1];
  const folga = (max - min) * fracao;
  return [min - folga, max + folga];
}

// Constrói o atributo `d` de um <path> de linha poligonal a partir de pontos
// XY já escalados para pixels — filtra qualquer NaN/Infinity residual (defesa
// em profundidade: mesmo que `pontosLinhaValidos` já tenha limpado a entrada,
// uma escala degenerada não deveria produzir NaN, mas o path NUNCA deve
// carregar um se algo escapar).
export function caminhoLinha(pontos: PontoXY[]): string {
  const validos = pontos.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  if (validos.length === 0) return "";
  return validos.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
}

// Constrói o atributo `d` de uma área (faixa de Bollinger): contorno superior
// da esquerda para a direita, depois o inferior da direita para a esquerda,
// fechando o polígono — um <path> só, sem <polygon> (mais fácil de manter
// NaN fora, um ponto por vez).
export function caminhoFaixa(superior: PontoXY[], inferior: PontoXY[]): string {
  const sup = superior.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  const inf = inferior.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  if (sup.length === 0 || inf.length === 0) return "";
  const topo = sup.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
  const base = [...inf].reverse().map((p) => `L${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
  return `${topo} ${base} Z`;
}
