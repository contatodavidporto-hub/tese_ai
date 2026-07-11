// Fixture de DESENVOLVIMENTO — dados sintéticos de uma `TeseOut` completa,
// cobrindo os 5 blocos novos do envelope ("Tese Profunda", contrato v3).
// NÃO é servida por rota nenhuma (sem `page.tsx`/`route.ts` que a importe) —
// existe só para o `tsc`/`next build` validar os 5 shapes contra `types.ts`
// no momento do build (o tsconfig inclui `**/*.ts` do projeto inteiro, então
// um erro de tipo aqui já quebra `npm run build` mesmo sem import nenhum).
// Ticker fictício "TESTE4" (nunca resolve de verdade — fora do catálogo de
// `lib/tickers.ts` e do formato usado em qualquer chamada real).

import type {
  Consenso,
  Grafico,
  MetricaSetor,
  Tecnica,
  TeseOut,
  Valuation,
} from "./types";

// 14 pregões sintéticos (não é uma série real — só formato).
const DATAS = [
  "2026-06-16",
  "2026-06-17",
  "2026-06-18",
  "2026-06-19",
  "2026-06-22",
  "2026-06-23",
  "2026-06-24",
  "2026-06-25",
  "2026-06-26",
  "2026-06-29",
  "2026-06-30",
  "2026-07-01",
  "2026-07-02",
  "2026-07-03",
];

// Objeto ligeiramente mais rico que `FonteRef` (tem `id` também) — assinável
// tanto a `FonteRef` (grafico/tecnica/metricas_setor) quanto a `Fonte`
// (`TeseOut.fontes`, que exige `id`): TS ignora o campo extra em atribuição
// por variável (só bloqueia excesso em literal direto).
const FONTE_B3 = {
  id: "fonte-cotahist-teste4",
  descricao: "B3 — Séries Históricas (COTAHIST)",
  url: "https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/series-historicas/",
  dt_referencia: "2026-07-03",
};

const GRAFICOS_FIXTURE: Grafico[] = [
  {
    id: "preco_bollinger",
    tipo: "linha_faixa",
    titulo: "Preço de fechamento e Bandas de Bollinger (20, 2)",
    ticker: "TESTE4",
    eixo_y: "BRL",
    nota: "Preços de fim de dia não ajustados por proventos (COTAHIST B3).",
    fonte: FONTE_B3,
    series: [
      { nome: "Preço de fechamento", pontos: DATAS.map((d, i) => ({ d, v: 32 + Math.sin(i / 2) * 1.5 })) },
      { nome: "Média móvel (50)", pontos: DATAS.map((d, i) => ({ d, v: 31.8 + i * 0.05 })) },
    ],
    faixa: {
      nome: "Bandas de Bollinger",
      pontos: DATAS.map((d, i) => ({ d, sup: 33.5 + Math.sin(i / 2) * 1.5, inf: 30.2 + Math.sin(i / 2) * 1.5 })),
    },
  },
  {
    id: "macd",
    tipo: "macd",
    titulo: "MACD (12, 26, 9)",
    ticker: "TESTE4",
    eixo_y: "indice",
    nota: "Calculado sobre preços de fechamento não ajustados por proventos.",
    fonte: FONTE_B3,
    series: [
      { nome: "MACD", pontos: DATAS.map((d, i) => ({ d, v: -0.3 + i * 0.04 })) },
      { nome: "Sinal", pontos: DATAS.map((d, i) => ({ d, v: -0.18 + i * 0.02 })) },
      { nome: "Histograma", pontos: DATAS.map((d, i) => ({ d, v: -0.12 + i * 0.02 })) },
    ],
  },
  {
    id: "rsi",
    tipo: "oscilador",
    titulo: "Índice de Força Relativa — RSI (14)",
    ticker: "TESTE4",
    eixo_y: "indice",
    nota: "Calculado sobre preços de fechamento não ajustados por proventos.",
    fonte: FONTE_B3,
    series: [{ nome: "RSI (14)", pontos: DATAS.map((d, i) => ({ d, v: 45 + Math.sin(i / 1.5) * 20 })) }],
    linhas_ref: [
      { nome: "Sobrevenda (30)", valor: 30 },
      { nome: "Sobrecompra (70)", valor: 70 },
    ],
  },
  {
    id: "estocastico",
    tipo: "oscilador",
    titulo: "Estocástico (14, 3, 3)",
    ticker: "TESTE4",
    eixo_y: "indice",
    nota: "Calculado sobre preços de fechamento não ajustados por proventos.",
    fonte: FONTE_B3,
    series: [
      { nome: "%K", pontos: DATAS.map((d, i) => ({ d, v: 50 + Math.cos(i / 1.5) * 30 })) },
      { nome: "%D", pontos: DATAS.map((d, i) => ({ d, v: 50 + Math.cos((i - 1) / 1.5) * 28 })) },
    ],
    linhas_ref: [
      { nome: "Sobrevenda (20)", valor: 20 },
      { nome: "Sobrecompra (80)", valor: 80 },
    ],
  },
  {
    id: "williams",
    tipo: "oscilador",
    titulo: "Williams %R (14)",
    ticker: "TESTE4",
    eixo_y: "indice",
    nota: "Calculado sobre preços de fechamento não ajustados por proventos.",
    fonte: FONTE_B3,
    series: [{ nome: "Williams %R (14)", pontos: DATAS.map((d, i) => ({ d, v: -50 + Math.sin(i / 1.5) * 30 })) }],
    linhas_ref: [
      { nome: "Sobrevenda (-80)", valor: -80 },
      { nome: "Sobrecompra (-20)", valor: -20 },
    ],
  },
  {
    id: "volume_ad",
    tipo: "linha",
    titulo: "Acumulação/Distribuição",
    ticker: "TESTE4",
    eixo_y: "indice",
    nota: "Calculado sobre preços de fechamento e volume não ajustados por proventos.",
    fonte: FONTE_B3,
    series: [{ nome: "Acumulação/Distribuição", pontos: DATAS.map((d, i) => ({ d, v: 1_000_000 + i * 42_000 })) }],
  },
];

const TECNICA_FIXTURE: Tecnica = {
  nota: "Indicadores calculados sobre preços de fim de dia não ajustados por proventos (COTAHIST B3).",
  fonte: FONTE_B3,
  indicadores: [
    {
      nome: "RSI (14)",
      valor: 58.4,
      unidade: "indice",
      detalhe: null,
      o_que_mede: "Velocidade e magnitude das variações de preço recentes, numa escala de 0 a 100.",
      leitura: "RSI em 58,4 — faixa neutra, sem leitura de sobrecompra (>70) nem sobrevenda (<30) no período.",
    },
    {
      nome: "MACD (12, 26, 9)",
      valor: -0.02,
      unidade: "indice",
      detalhe: "linha −0,02 / sinal 0,00 / histograma −0,02",
      o_que_mede: "Convergência/divergência entre duas médias móveis exponenciais de prazos distintos.",
      leitura: "Linha do MACD ligeiramente abaixo do sinal — histograma negativo no fechamento do período.",
    },
    {
      nome: "Bandas de Bollinger (20, 2)",
      valor: 32.9,
      unidade: "BRL",
      detalhe: "banda superior R$ 34,10 / média R$ 32,90 / banda inferior R$ 31,70",
      o_que_mede: "Faixa de volatilidade de 2 desvios-padrão em torno da média móvel de 20 pregões.",
      leitura: "Preço de fechamento dentro da faixa, sem tocar a banda superior nem a inferior no período.",
    },
    {
      nome: "Média móvel (50)",
      valor: 32.15,
      unidade: "BRL",
      detalhe: null,
      o_que_mede: "Média aritmética do preço de fechamento nos últimos 50 pregões.",
      leitura: "Preço de fechamento negociando acima da média móvel de 50 pregões.",
    },
    {
      nome: "Estocástico (14, 3, 3)",
      valor: 62.1,
      unidade: "indice",
      detalhe: "%K 62,1 / %D 59,8",
      o_que_mede: "Posição do fechamento em relação à faixa de preços (máxima−mínima) do período.",
      leitura: "%K acima de %D, faixa neutra — sem leitura de sobrecompra (>80) nem sobrevenda (<20).",
    },
    {
      nome: "Williams %R (14)",
      valor: -38.2,
      unidade: "indice",
      detalhe: null,
      o_que_mede: "Posição do fechamento em relação à máxima do período, escala de 0 a −100.",
      leitura: "Williams %R em −38,2 — faixa neutra, fora das zonas de sobrecompra (−20) e sobrevenda (−80).",
    },
    {
      nome: "Acumulação/Distribuição",
      valor: null,
      unidade: "indice",
      detalhe: null,
      o_que_mede: "Indicador de volume que combina posição do fechamento na faixa do dia com o volume negociado.",
      leitura: "Tendência crescente ao longo do período — mais pregões de acumulação que de distribuição.",
    },
    {
      nome: "Retração de Fibonacci (252 pregões)",
      valor: null,
      unidade: "BRL",
      detalhe: "0%: R$ 28,40 · 38,2%: R$ 30,10 · 50%: R$ 31,20 · 61,8%: R$ 32,30 · 100%: R$ 34,90",
      o_que_mede: "Níveis de preço derivados da máxima e mínima dos últimos 252 pregões.",
      leitura: "Níveis calculados sobre a máxima e a mínima do período — sem implicação direcional própria.",
    },
  ],
  lacunas: [],
};

const VALUATION_FIXTURE: Valuation = {
  aviso: "Exercício de sensibilidade sob premissas explícitas — NÃO é preço-alvo nem recomendação.",
  modelos: [
    {
      nome: "Gordon (dividendos)",
      descricao: "Modelo de crescimento constante de dividendos (DDM), sob banda de taxa de crescimento e custo de capital.",
      premissas: [
        { nome: "Dividendo esperado (D1)", valor: "R$ 1,85", origem: "DFP + proventos B3 12m", rotulo: "fato" },
        { nome: "Custo de capital próprio (Ke)", valor: "11,2%", origem: "CAPM-lite: Rf Treasury 10y + β×ERP", rotulo: "aproximação" },
        { nome: "ERP (prêmio de risco)", valor: "5,0%", origem: "Premissa fixa documentada — banda, não previsão", rotulo: "premissa" },
      ],
      cenarios: [
        { nome: "conservador", parametros: "g = 0%", valor: 16.5, unidade: "BRL", omitido: null },
        { nome: "base", parametros: "g = meta de inflação (IPCA 3%)", valor: 22.6, unidade: "BRL", omitido: null },
        { nome: "otimista", parametros: "g = banda superior (5%)", valor: 29.8, unidade: "BRL", omitido: null },
      ],
      faixa: { min: 16.5, max: 29.8, unidade: "BRL" },
      sensibilidade: {
        eixo_linhas: "Ke",
        eixo_colunas: "g",
        linhas: ["10,2%", "11,2%", "12,2%"],
        colunas: ["0%", "3%", "5%"],
        celulas: [
          [18.1, 25.4, 34.2],
          [16.5, 22.6, 29.8],
          [15.2, 20.3, 26.1],
        ],
      },
      omitido: null,
    },
    {
      nome: "Múltiplos vs pares",
      descricao: "Comparação de múltiplos correntes (P/L, EV/EBITDA) contra uma cesta de pares do mesmo setor.",
      premissas: [],
      cenarios: [],
      faixa: null,
      sensibilidade: null,
      omitido: "Cesta de pares do setor sem EBITDA comparável reportado no período — dado não encontrado.",
    },
  ],
  lacunas: ["DCF projetivo multi-estágio fora de escopo (projeção de fluxo é previsão, não recuperação de fato)."],
};

const CONSENSO_FIXTURE: Consenso = {
  aviso: "Opiniões de terceiros reportadas com atribuição — a plataforma reporta, não endossa.",
  itens: [
    {
      casa: "XP Investimentos",
      metrica: "preco_alvo",
      valor: 38.0,
      moeda: "BRL",
      veiculo: "InfoMoney",
      url: "https://www.infomoney.com.br/mercados/exemplo-teste4-preco-alvo/",
      titulo: "XP eleva preço-alvo de TESTE4 para R$ 38,00",
      data_materia: "2026-06-20",
      data_busca: "2026-07-09",
    },
    {
      casa: null,
      metrica: "preco_alvo",
      valor: 35.5,
      moeda: "BRL",
      veiculo: "Money Times",
      url: "https://www.moneytimes.com.br/exemplo-teste4-consenso/",
      titulo: "Consenso de mercado projeta upside moderado para TESTE4",
      data_materia: null,
      data_busca: "2026-07-09",
    },
  ],
  lacunas: ["Consenso agregado (LSEG/Bloomberg) é dado licenciado — indisponível publicamente."],
};

const METRICAS_SETOR_FIXTURE: MetricaSetor[] = [
  {
    nome: "P/L",
    valor: 12.4,
    unidade: "x",
    formula: "Preço / Lucro por ação (12m)",
    o_que_mede: "Quantos anos de lucro atual o mercado está pagando pela ação, ao preço corrente.",
    implicacao: "Múltiplo dentro da faixa histórica de 3 anos da própria companhia, sem prêmio nem desconto evidente.",
    fontes: [FONTE_B3, { descricao: "CVM — DFP", url: "https://dados.cvm.gov.br/", dt_referencia: "2026-03-31" }],
    rotulos: [],
    lacuna: null,
  },
  {
    nome: "Dívida líquida / EBITDA",
    valor: null,
    unidade: "x",
    formula: "Dívida líquida / EBITDA (12m)",
    o_que_mede: "Quantos anos de geração de caixa operacional seriam necessários para quitar a dívida líquida.",
    implicacao: "Sem leitura possível no período.",
    fontes: [],
    rotulos: [],
    lacuna: "EBITDA não segregado no DFP do período mais recente — dado não encontrado.",
  },
];

export const TESE_TESTE4_FIXTURE: TeseOut = {
  id: "00000000-0000-4000-8000-000000000000",
  ticker: "TESTE4",
  status: "ready",
  classe_ativo: "acao",
  criado_em: "2026-07-09T13:45:00Z",
  aviso: "Não é recomendação de investimento. Tese estruturada a partir de dados públicos; a decisão é do leitor.",
  markdown:
    "# TESTE4\n\n## 1. Fundamentos\n\nTexto de exemplo.\n\n## 5. Lacunas\n\n- Nenhuma lacuna relevante neste exemplo.\n",
  citacoes: [],
  fontes: [FONTE_B3],
  lacunas: [],
  uso: { modelo: "claude-opus-4.8", input_tokens: 28_000, output_tokens: 12_000, custo_estimado_usd: 0.42 },
  erro: null,
  graficos: GRAFICOS_FIXTURE,
  tecnica: TECNICA_FIXTURE,
  valuation: VALUATION_FIXTURE,
  consenso: CONSENSO_FIXTURE,
  metricas_setor: METRICAS_SETOR_FIXTURE,
};
