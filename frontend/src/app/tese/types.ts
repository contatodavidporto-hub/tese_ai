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
};

export type CriarTeseResposta = {
  id: string;
  ticker: string;
  status: TeseStatus;
};
