// Lista estática de papéis da B3 para autocomplete e galeria de exemplos.
//
// FONTE (zero alucinação): carteira teórica do Ibovespa em 2026-07-08, consultada
// em 2026-07-08 no endpoint público GetPortfolioDay (índice IBOV) do site da B3 —
// página humana: https://www.b3.com.br/pt_br/market-data-e-indices/indices/
// indices-amplos/ibovespa-composicao-da-carteira.htm. `nome` é o nome de pregão
// da B3; `participacaoPct` é a participação % na carteira teórica nessa data.
// É um RETRATO datado (a carteira rebalanceia a cada quadrimestre) — atualizar
// junto com o warm-cache do backend (app/scripts/warm_cache.py usa a mesma fonte).
//
// O autocomplete é conveniência, não autoridade: o backend resolve QUALQUER
// companhia aberta via cadastro CVM. Ticker fora desta lista segue permitido,
// desde que passe no formato B3 (mesma regex do backend, app/schemas/tese.py).

export type PapelB3 = {
  ticker: string;
  nome: string;
  participacaoPct: number;
};

export const DATA_CARTEIRA_IBOV = "2026-07-08";

export const CARTEIRA_IBOV: PapelB3[] = [
  { ticker: "VALE3", nome: "VALE", participacaoPct: 11.279 },
  { ticker: "ITUB4", nome: "ITAUUNIBANCO", participacaoPct: 8.97 },
  { ticker: "PETR4", nome: "PETROBRAS", participacaoPct: 7.098 },
  { ticker: "AXIA3", nome: "AXIA ENERGIA", participacaoPct: 4.82 },
  { ticker: "PETR3", nome: "PETROBRAS", participacaoPct: 4.025 },
  { ticker: "BBDC4", nome: "BRADESCO", participacaoPct: 3.805 },
  { ticker: "SBSP3", nome: "SABESP", participacaoPct: 3.542 },
  { ticker: "ITSA4", nome: "ITAUSA", participacaoPct: 3.372 },
  { ticker: "B3SA3", nome: "B3", participacaoPct: 3.04 },
  { ticker: "WEGE3", nome: "WEG", participacaoPct: 2.853 },
  { ticker: "ABEV3", nome: "AMBEV S/A", participacaoPct: 2.793 },
  { ticker: "BPAC11", nome: "BTGP BANCO", participacaoPct: 2.728 },
  { ticker: "EMBJ3", nome: "EMBRAER", participacaoPct: 2.542 },
  { ticker: "BBAS3", nome: "BRASIL", participacaoPct: 2.348 },
  { ticker: "ENEV3", nome: "ENEVA", participacaoPct: 2.056 },
  { ticker: "EQTL3", nome: "EQUATORIAL", participacaoPct: 2.044 },
  { ticker: "CPLE3", nome: "COPEL", participacaoPct: 1.853 },
  { ticker: "PRIO3", nome: "PRIO", participacaoPct: 1.782 },
  { ticker: "RENT3", nome: "LOCALIZA", participacaoPct: 1.601 },
  { ticker: "RDOR3", nome: "REDE D OR", participacaoPct: 1.591 },
  { ticker: "VBBR3", nome: "VIBRA", participacaoPct: 1.54 },
  { ticker: "UGPA3", nome: "ULTRAPAR", participacaoPct: 1.261 },
  { ticker: "GGBR4", nome: "GERDAU", participacaoPct: 1.151 },
  { ticker: "SUZB3", nome: "SUZANO S.A.", participacaoPct: 1.05 },
  { ticker: "VIVT3", nome: "TELEF BRASIL", participacaoPct: 1.015 },
  { ticker: "BBSE3", nome: "BBSEGURIDADE", participacaoPct: 0.995 },
  { ticker: "RADL3", nome: "RAIADROGASIL", participacaoPct: 0.968 },
  { ticker: "BBDC3", nome: "BRADESCO", participacaoPct: 0.954 },
  { ticker: "CSMG3", nome: "COPASA", participacaoPct: 0.948 },
  { ticker: "CMIG4", nome: "CEMIG", participacaoPct: 0.871 },
  { ticker: "TIMS3", nome: "TIM", participacaoPct: 0.732 },
  { ticker: "RAIL3", nome: "RUMO S.A.", participacaoPct: 0.69 },
  { ticker: "ENGI11", nome: "ENERGISA", participacaoPct: 0.662 },
  { ticker: "TOTS3", nome: "TOTVS", participacaoPct: 0.641 },
  { ticker: "MOTV3", nome: "MOTIVA SA", participacaoPct: 0.615 },
  { ticker: "KLBN11", nome: "KLABIN S/A", participacaoPct: 0.578 },
  { ticker: "LREN3", nome: "LOJAS RENNER", participacaoPct: 0.561 },
  { ticker: "ALOS3", nome: "ALLOS", participacaoPct: 0.544 },
  { ticker: "CXSE3", nome: "CAIXA SEGURI", participacaoPct: 0.525 },
  { ticker: "MBRF3", nome: "MARFRIG", participacaoPct: 0.501 },
  { ticker: "ISAE4", nome: "ISA ENERGIA", participacaoPct: 0.492 },
  { ticker: "EGIE3", nome: "ENGIE BRASIL", participacaoPct: 0.49 },
  { ticker: "ASAI3", nome: "ASSAI", participacaoPct: 0.478 },
  { ticker: "SMFT3", nome: "SMART FIT", participacaoPct: 0.46 },
  { ticker: "SANB11", nome: "SANTANDER BR", participacaoPct: 0.392 },
  { ticker: "PSSA3", nome: "PORTO SEGURO", participacaoPct: 0.386 },
  { ticker: "MULT3", nome: "MULTIPLAN", participacaoPct: 0.383 },
  { ticker: "TAEE11", nome: "TAESA", participacaoPct: 0.37 },
  { ticker: "BRAV3", nome: "BRAVA", participacaoPct: 0.366 },
  { ticker: "CSAN3", nome: "COSAN", participacaoPct: 0.361 },
  { ticker: "CPFE3", nome: "CPFL ENERGIA", participacaoPct: 0.357 },
  { ticker: "GOAU4", nome: "GERDAU MET", participacaoPct: 0.334 },
  { ticker: "CMIN3", nome: "CSNMINERACAO", participacaoPct: 0.314 },
  { ticker: "FLRY3", nome: "FLEURY", participacaoPct: 0.291 },
  { ticker: "NATU3", nome: "NATURA", participacaoPct: 0.283 },
  { ticker: "HYPE3", nome: "HYPERA", participacaoPct: 0.278 },
  { ticker: "CYRE3", nome: "CYRELA REALT", participacaoPct: 0.262 },
  { ticker: "BRAP4", nome: "BRADESPAR", participacaoPct: 0.229 },
  { ticker: "CURY3", nome: "CURY S/A", participacaoPct: 0.229 },
  { ticker: "IGTI11", nome: "IGUATEMI S.A", participacaoPct: 0.215 },
  { ticker: "DIRR3", nome: "DIRECIONAL", participacaoPct: 0.184 },
  { ticker: "USIM5", nome: "USIMINAS", participacaoPct: 0.183 },
  { ticker: "COGN3", nome: "COGNA ON", participacaoPct: 0.177 },
  { ticker: "POMO4", nome: "MARCOPOLO", participacaoPct: 0.173 },
  { ticker: "AURE3", nome: "AUREN", participacaoPct: 0.161 },
  { ticker: "CSNA3", nome: "SID NACIONAL", participacaoPct: 0.144 },
  { ticker: "SLCE3", nome: "SLC AGRICOLA", participacaoPct: 0.122 },
  { ticker: "VIVA3", nome: "VIVARA S.A.", participacaoPct: 0.117 },
  { ticker: "HAPV3", nome: "HAPVIDA", participacaoPct: 0.116 },
  { ticker: "RECV3", nome: "PETRORECSA", participacaoPct: 0.11 },
  { ticker: "YDUQ3", nome: "YDUQS PART", participacaoPct: 0.092 },
  { ticker: "CEAB3", nome: "CEA MODAS", participacaoPct: 0.088 },
  { ticker: "AZZA3", nome: "AZZAS 2154", participacaoPct: 0.083 },
  { ticker: "MRVE3", nome: "MRV", participacaoPct: 0.081 },
  { ticker: "MGLU3", nome: "MAGAZ LUIZA", participacaoPct: 0.069 },
  { ticker: "BRKM5", nome: "BRASKEM", participacaoPct: 0.066 },
  { ticker: "BEEF3", nome: "MINERVA", participacaoPct: 0.066 },
  { ticker: "VAMO3", nome: "VAMOS", participacaoPct: 0.054 },
];

// Tickers pré-gerados pelo warm-cache do backend (top 10 pesos do IBOV) — teses
// `ready` no banco; o POST /teses devolve cache hit (custo US$ 0, abre na hora).
// Manter em sincronia com backend/app/scripts/warm_cache.py (TICKERS_IBOV_TOP).
export const EXEMPLOS_PRONTOS = [
  "VALE3",
  "ITUB4",
  "PETR4",
  "AXIA3",
  "PETR3",
  "BBDC4",
  "SBSP3",
  "ITSA4",
  "B3SA3",
  "WEGE3",
] as const;

// Formato de código de negociação B3 — espelho da validação do backend
// (app/schemas/tese.py): raiz de 4 alfanuméricos iniciada por letra + 1-2
// dígitos + sufixo "B" opcional (balcão organizado).
export const TICKER_B3_RE = /^[A-Z][A-Z0-9]{3}[0-9]{1,2}B?$/;

const porTicker = new Map(CARTEIRA_IBOV.map((p) => [p.ticker, p]));

export function papelPorTicker(ticker: string): PapelB3 | undefined {
  return porTicker.get(ticker.trim().toUpperCase());
}

export function exemplosProntos(): PapelB3[] {
  return EXEMPLOS_PRONTOS.map(
    (t) => porTicker.get(t) ?? { ticker: t, nome: t, participacaoPct: 0 },
  );
}

// Slot 1..10 fixo pela ordem de EXEMPLOS_PRONTOS — usado SÓ para o nome do
// shared element CSS da assinatura "Virada de Edição" (motion; ver
// `.vt-tese-N` em globals.css e DESIGN-BRIEF.md §4.6). Conjunto finito e
// estático: as classes `.vt-tese-1`…`.vt-tese-10` já existem pré-declaradas
// no CSS — isto só escolhe qual delas usar, nunca gera CSS em runtime nem
// `style=` inline. Ticker fora da lista (gerado sob demanda) devolve `null`
// e não recebe shared element — cai só no véu geral da página.
export function slotVirada(ticker: string): number | null {
  const i = (EXEMPLOS_PRONTOS as readonly string[]).indexOf(ticker);
  return i === -1 ? null : i + 1;
}

// Normaliza para busca: caixa alta e sem diacríticos (digitar "ITAÚ" ou "SÃO"
// precisa achar os nomes de pregão da B3, que vêm sem acento).
function chaveBusca(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase();
}

// Busca para o autocomplete: prefixo de ticker primeiro, depois nome de pregão;
// dentro de cada grupo, maior participação primeiro (ordem da carteira).
export function buscarPapeis(consulta: string, limite = 8): PapelB3[] {
  const q = chaveBusca(consulta.trim());
  if (!q) return [];
  const porPrefixo: PapelB3[] = [];
  const porNome: PapelB3[] = [];
  for (const papel of CARTEIRA_IBOV) {
    if (papel.ticker.startsWith(q)) porPrefixo.push(papel);
    else if (chaveBusca(papel.nome).includes(q)) porNome.push(papel);
  }
  return [...porPrefixo, ...porNome].slice(0, limite);
}
