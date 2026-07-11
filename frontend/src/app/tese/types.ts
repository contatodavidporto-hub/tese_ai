// Tipos do contrato da API de teses (FastAPI). Mantidos próximos da UI que os consome.

import type { ClasseAtivo } from "@/lib/tickers";

export type TeseStatus = "processing" | "ready" | "error";

export type Fonte = {
  id: string | null;
  url: string | null;
  descricao: string;
  dt_referencia: string | null;
};

export type Citacao = {
  texto_citado: string;
  document_index: number | null;
  titulo_documento: string | null;
  fonte: Fonte | null;
};

export type Uso = {
  modelo?: string;
  input_tokens?: number;
  output_tokens?: number;
  custo_estimado_usd?: number;
  [key: string]: unknown;
};

// ---------------------------------------------------------------------------
// Blocos novos do envelope ("Tese Profunda") — espelho EXATO do contrato
// pinado pelo maestro: `.maestro/contrato-envelope-v3.md`. Divergência do
// shape aí definido é erro de integração, não decisão de estilo. Todos os 5
// campos abaixo são ADITIVOS e opcionais em `TeseOut` (default_factory no
// backend) — ausência = tese legada válida, a UI trata cada bloco ausente
// como "seção não aparece" (nunca inventa/preenche default visível).
// ---------------------------------------------------------------------------

// Referência de fonte comum aos 5 blocos — mais enxuta que `Fonte` (sem
// `id`): os blocos novos citam a origem do DADO (B3/CVM/BCB/ANEEL/ANBIMA),
// não uma linha do registro de fontes da tese.
export type FonteRef = {
  descricao: string;
  url: string | null;
  dt_referencia: string | null;
};

// 1. Gráficos ----------------------------------------------------------------

export type PontoGrafico = { d: string; v: number }; // data ISO (YYYY-MM-DD), valor
export type PontoFaixaGrafico = { d: string; sup: number; inf: number };

export type SerieGrafico = { nome: string; pontos: PontoGrafico[] };

export type TipoGrafico = "linha" | "linha_faixa" | "macd" | "oscilador";

// slugs estáveis emitidos pelo backend (ordem canônica do contrato):
// "preco_bollinger" | "macd" | "rsi" | "estocastico" | "williams" | "volume_ad"
export type Grafico = {
  id: string;
  tipo: TipoGrafico;
  titulo: string;
  ticker: string;
  eixo_y: "BRL" | "indice" | "pct";
  // SEMPRE inclui "preços de fim de dia não ajustados por proventos".
  nota: string;
  fonte: FonteRef;
  series: SerieGrafico[]; // ≤252 pontos por série (downsample no backend)
  faixa?: { nome: string; pontos: PontoFaixaGrafico[] }; // Bollinger
  linhas_ref?: { nome: string; valor: number }[]; // ex.: RSI 30/70, %R -20/-80
};

// Ordem canônica de exibição dos gráficos (contrato §1) — usada para
// ordenar `graficos[]` do envelope antes de renderizar em SecaoTecnica.
export const ORDEM_CANONICA_GRAFICOS = [
  "preco_bollinger",
  "macd",
  "rsi",
  "estocastico",
  "williams",
  "volume_ad",
] as const;

// 2. Técnica -------------------------------------------------------------

export type IndicadorTecnico = {
  nome: string;
  valor: number | null; // null para conjuntos (ex.: Fibonacci)
  unidade: "indice" | "BRL" | "pct";
  detalhe: string | null;
  o_que_mede: string;
  leitura: string; // template determinístico NEUTRO (já passou pelo gate)
};

export type Tecnica = {
  nota: string; // rótulo não-ajustado + fonte
  fonte: FonteRef;
  indicadores: IndicadorTecnico[];
  lacunas: string[];
};

// 3. Valuation -------------------------------------------------------------

export type RotuloPremissa = "fato" | "premissa" | "aproximação";

export type PremissaValuation = {
  nome: string;
  valor: string;
  origem: string;
  rotulo: RotuloPremissa;
};

export type CenarioValuation = {
  nome: "conservador" | "base" | "otimista";
  parametros: string;
  valor: number | null;
  unidade: string;
  omitido: string | null;
};

export type FaixaValuation = { min: number; max: number; unidade: string };

export type SensibilidadeValuation = {
  eixo_linhas: string;
  eixo_colunas: string;
  linhas: string[];
  colunas: string[];
  celulas: (number | null)[][];
};

export type ModeloValuation = {
  nome: string;
  descricao: string;
  premissas: PremissaValuation[];
  cenarios: CenarioValuation[];
  faixa: FaixaValuation | null;
  sensibilidade: SensibilidadeValuation | null;
  omitido: string | null; // motivo quando o modelo inteiro não computou
};

export type Valuation = {
  // fixo: "Exercício de sensibilidade sob premissas explícitas — NÃO é
  // preço-alvo nem recomendação."
  aviso: string;
  modelos: ModeloValuation[];
  lacunas: string[];
};

// 4. Consenso ----------------------------------------------------------------

export type ItemConsenso = {
  casa: string | null; // null se a matéria só fala "consenso"
  metrica: "preco_alvo";
  valor: number;
  moeda: string; // "BRL"
  veiculo: string; // ex.: "InfoMoney"
  url: string;
  titulo: string;
  data_materia: string | null;
  data_busca: string;
};

export type Consenso = {
  // fixo: "Opiniões de terceiros reportadas com atribuição — a plataforma
  // reporta, não endossa."
  aviso: string;
  itens: ItemConsenso[];
  lacunas: string[];
};

// 5. Métricas do setor -------------------------------------------------------

export type MetricaSetor = {
  nome: string;
  valor: number | null;
  unidade: "pct" | "BRL" | "razao" | "x";
  formula: string;
  o_que_mede: string;
  implicacao: string; // NEUTRA (já passou pelo gate)
  fontes: FonteRef[]; // pode ter 2 (ex.: P/VP = COTAHIST + DFP)
  rotulos: string[]; // ex.: ["prudencial"], ["aprox."]
  lacuna: string | null; // motivo quando valor=null
};

export type TeseOut = {
  id: string;
  ticker: string;
  status: TeseStatus;
  // 'acao' | 'fii' | 'renda_fixa'; `null`/ausente = ação (legado — NULL no
  // banco antes da Fase 2 multiativo, ver backend/app/schemas/tese.py). Campo
  // aditivo: teses antigas seguem válidas sem ele.
  classe_ativo?: ClasseAtivo | null;
  criado_em: string | null;
  aviso: string;
  markdown: string | null;
  citacoes: Citacao[];
  fontes: Fonte[];
  lacunas: string[];
  uso: Uso | null;
  erro: string | null;
  // Blocos novos ("Tese Profunda") — aditivos/opcionais; ausência (tese
  // legada, ou fail-closed em status=error/gate bloqueado — o router NÃO
  // serve nenhum bloco novo nesse caso) = seção correspondente não renderiza.
  graficos?: Grafico[];
  tecnica?: Tecnica | null;
  valuation?: Valuation | null;
  consenso?: Consenso | null;
  metricas_setor?: MetricaSetor[];
};

export type CriarTeseResposta = {
  id: string;
  ticker: string;
  status: TeseStatus;
};
