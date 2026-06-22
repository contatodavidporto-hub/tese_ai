// Tipos do contrato da API de teses (FastAPI). Mantidos próximos da UI que os consome.

export type TeseStatus = "processing" | "ready" | "error";

export type Fonte = {
  id: string;
  url: string;
  descricao: string;
  dt_referencia: string;
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
