// src/lib/glossario.ts — dicionário curado do glossário · DONA: onda COPY
// (missão APOTEOSE 2026-07-13, critério 11; plano §2 D7 e §3.11).
//
// CONTRATO (D7 do plano-apoteose.md): este arquivo é a fonte ÚNICA dos
// termos FIXOS do site — consumido pela rota /glossario e pelos
// `TermoTooltip` das páginas estáticas. Termos DINÂMICOS de métricas
// (nome/`o_que_mede` no payload da tese) NÃO passam por aqui: a onda TESE
// consome `o_que_mede` direto do backend. Slug desconhecido em
// `tooltipDe()` devolve `definicao: undefined` → o TermoTooltip cai no
// fallback SILENCIOSO (só o texto, sem popup) — zero definição inventada.
//
// HONESTIDADE DAS DEFINIÇÕES (gate anti-alucinação da copy): cada verbete é
// uma definição CONCEITUAL, não um dado — número, taxa e preço continuam
// vivendo nas teses, com fonte e data. `fonteDoConceito` registra de quem é
// o CONCEITO (ANBIMA, B3, BCB, ANEEL…), não valida nenhum número.

export type Verbete = {
  /** Âncora estável em /glossario (ex.: "p-vp" → /glossario#p-vp). */
  slug: string;
  /** Nome exibido do termo. */
  termo: string;
  /**
   * Definição curta (1–3 frases) — a MESMA usada pelo popup do
   * TermoTooltip e pelo corpo do verbete em /glossario.
   */
  definicao: string;
  /** Contexto adicional exibido SÓ na página /glossario. */
  detalhe?: string;
  /** Fonte do conceito (não de dado): "ANBIMA", "B3", "BCB (IF.data)"… */
  fonteDoConceito?: string;
  /** Slugs de verbetes relacionados ("ver também"). */
  verTambem?: readonly string[];
};

// Ordem alfabética por `termo` (a mesma da página — manter ao editar).
export const GLOSSARIO: readonly Verbete[] = [
  {
    slug: "citations",
    termo: "Anthropic Citations",
    definicao:
      "Recurso da API da Anthropic que ancora cada afirmação do texto gerado ao trecho exato do documento de origem. É o mecanismo que faz cada fato da tese carregar a própria prova: link, hospedeiro e o trecho citado.",
    detalhe:
      "No Tese AI, afirmação factual sem citação não entra como fato — ou vira interpretação rotulada, ou sai do texto. É a regra que transforma a tese num documento auditável, não num texto persuasivo.",
    fonteDoConceito: "Anthropic (documentação da API)",
  },
  {
    slug: "brent",
    termo: "Brent",
    definicao:
      "Petróleo do Mar do Norte usado como referência internacional para o preço do barril. Nas teses, entra como série de contexto macro (dimensão 03), com rótulo e data de cada leitura.",
  },
  {
    slug: "bull-bear",
    termo: "Bull × bear",
    definicao:
      "Convenção de mercado para os dois lados de uma tese: “bull” é o cenário construtivo, “bear” é o adverso. Toda tese do motor fecha com os dois lados expostos — a síntese e a contra-tese.",
    verTambem: ["contra-tese"],
  },
  {
    slug: "carrego",
    termo: "Carrego (carry)",
    definicao:
      "Em renda fixa, o rendimento de simplesmente manter o título em carteira por um período — os juros que ele acumula —, separado do ganho ou da perda por variação de preço.",
    detalhe:
      "As teses de Tesouro Direto descrevem o carrego quando o dado da fonte permite, sempre separado de qualquer sugestão de montar, manter ou desfazer posição — a decisão é do leitor.",
    fonteDoConceito: "conceito usual de renda fixa (ANBIMA)",
    verTambem: ["marcacao-a-mercado", "data-base"],
  },
  {
    slug: "carteira-teorica",
    termo: "Carteira teórica do Ibovespa",
    definicao:
      "A composição oficial do índice Ibovespa publicada pela B3, com o peso de cada papel. É rebalanceada a cada quadrimestre — por isso todo peso citado no site carrega a data do retrato.",
    fonteDoConceito: "B3",
  },
  {
    slug: "contra-tese",
    termo: "Contra-tese",
    definicao:
      "Os argumentos mais fortes contra a síntese: riscos, premissas frágeis e leituras alternativas dos mesmos dados. O motor gera a contra-tese lado a lado com a tese — quem lê recebe os dois lados, não um discurso único.",
    verTambem: ["bull-bear"],
  },
  {
    slug: "data-base",
    termo: "Data Base",
    definicao:
      "A data de referência das taxas e dos preços divulgados para um título público no Tesouro Direto. Preço de título muda todo dia útil — sem a Data Base, o número solto não informa nada; por isso toda taxa citada nas teses a carrega.",
    fonteDoConceito: "Tesouro Direto / STN",
    verTambem: ["stn", "marcacao-a-mercado"],
  },
  {
    slug: "dy",
    termo: "Dividend yield (DY)",
    definicao:
      "Proventos distribuídos num período divididos pelo preço do papel ou da cota. Mede a renda distribuída em relação ao preço — um retrato do período observado, não uma promessa de rendimento futuro.",
    fonteDoConceito: "conceito usual de mercado",
    verTambem: ["p-vp"],
  },
  {
    slug: "elo-causal",
    termo: "Elo causal",
    definicao:
      "A ligação narrada entre evento, commodity, setor e empresa (dimensão 05). É interpretação — marcada como tal, em cenários condicionais —, mas nunca solta: cada ponta do elo carrega sua própria fonte e data.",
  },
  {
    slug: "basileia",
    termo: "Índice de Basileia",
    definicao:
      "Indicador de solvência dos bancos: compara o capital regulatório da instituição com seus ativos ponderados pelo risco. Quanto maior o índice, mais capital próprio sustenta a operação.",
    detalhe:
      "No Brasil, o BCB publica os dados prudenciais das instituições no painel público IF.data — é dessa fonte que as teses de bancos extraem o índice, sempre com a data da apuração.",
    fonteDoConceito: "BCB (IF.data)",
  },
  {
    slug: "inflacao-implicita",
    termo: "Inflação implícita",
    definicao:
      "A inflação embutida nos preços de mercado: a diferença entre a taxa de um título prefixado e a taxa real de um título indexado ao IPCA de prazo comparável (o “breakeven”). É leitura de mercado, não previsão oficial.",
    detalhe:
      "As curvas usadas nesse cálculo são divulgadas pela ANBIMA. Nas teses, a inflação implícita aparece como o que é: o consenso embutido nos preços em uma data — nunca como projeção da plataforma.",
    fonteDoConceito: "ANBIMA",
  },
  {
    slug: "informe-mensal-cvm",
    termo: "Informe mensal (FII)",
    definicao:
      "Documento periódico obrigatório que todo FII listado entrega à CVM: carteira, receitas, vacância, distribuições. É o eixo de fundamentos das teses de FII — dado primário do regulador, não estimativa de terceiros.",
    fonteDoConceito: "CVM",
  },
  {
    slug: "lacuna-declarada",
    termo: "Lacuna declarada",
    definicao:
      "Quando o dado não é encontrado na fonte pública, a tese registra “dado não encontrado” no lugar do número, em vez de estimar. A ausência fica visível no texto e no registro de fontes — abster é mais honesto que preencher com chute.",
    detalhe:
      "Cada tese abre com a contagem de lacunas ao lado da contagem de citações e de fontes: o que faltou é parte do documento, não uma omissão. É por isso que uma lacuna nunca vira número aproximado no meio do texto.",
    verTambem: ["citations"],
  },
  {
    slug: "marcacao-a-mercado",
    termo: "Marcação a mercado",
    definicao:
      "Avaliar um ativo pelo preço corrente de mercado, e não pelo preço pago ou pela curva do papel. É o que explica um título público valer hoje mais ou menos do que o investidor pagou — antes do vencimento, o preço flutua com os juros.",
    fonteDoConceito: "conceito ANBIMA / BCB",
    verTambem: ["carrego", "data-base"],
  },
  {
    slug: "p-vp",
    termo: "P/VP",
    definicao:
      "Preço dividido pelo valor patrimonial (por ação ou por cota): quanto o mercado paga por cada real de patrimônio contábil. A leitura depende do setor — as teses apresentam o número com fonte e contexto, nunca como gatilho de decisão.",
    fonteDoConceito: "conceito usual de mercado",
    verTambem: ["dy"],
  },
  {
    slug: "rap",
    termo: "RAP",
    definicao:
      "Receita Anual Permitida: a remuneração regulada que uma transmissora de energia tem direito de receber, definida pela ANEEL nos contratos de concessão. Para transmissoras, é a espinha da receita — por isso as teses do setor a acompanham na fonte.",
    fonteDoConceito: "ANEEL",
  },
  {
    slug: "focus",
    termo: "Relatório Focus",
    definicao:
      "Pesquisa semanal do Banco Central com expectativas de mercado para inflação, juros, câmbio e atividade. É expectativa declarada de analistas, não fato consumado — e as teses o citam exatamente assim.",
    fonteDoConceito: "BCB",
  },
  {
    slug: "rls",
    termo: "RLS (Row Level Security)",
    definicao:
      "Regra de segurança aplicada dentro do próprio banco de dados: cada linha só é visível para o seu dono. Na plataforma, o isolamento de dados por usuário é imposto nessa camada — a proteção não depende só do código da aplicação.",
    fonteDoConceito: "PostgreSQL",
  },
  {
    slug: "sec-edgar",
    termo: "SEC EDGAR",
    definicao:
      "O sistema público de arquivos da SEC, o regulador do mercado de capitais dos EUA. É de onde saem os comparáveis internacionais das teses (dimensão 02) — sempre com a ressalva de padrão contábil e moeda.",
    fonteDoConceito: "SEC (EUA)",
  },
  {
    slug: "stn",
    termo: "STN",
    definicao:
      "Secretaria do Tesouro Nacional: a fonte oficial das taxas e dos preços dos títulos públicos, publicados nos dados abertos do Tesouro Transparente. É a origem dos números das teses de Tesouro Direto.",
    fonteDoConceito: "Tesouro Nacional",
    verTambem: ["data-base"],
  },
  {
    slug: "ticker",
    termo: "Ticker",
    definicao:
      "O código de negociação de um ativo — PETR4, HGLG11 e afins na B3, ou o código do título no Tesouro Direto. É a chave de entrada do motor: dele se resolve a classe do ativo e as dimensões que a tese vai cruzar.",
  },
  {
    slug: "warm-cache",
    termo: "Warm-cache",
    definicao:
      "Termo técnico do motor: as teses da galeria são geradas antecipadamente e mantidas “quentes” em cache, renovadas em ciclo diário. Na interface, aparecem como teses prontas da galeria — abrem na hora, sem custo de geração, com a mesma trilha de citações.",
    verTambem: ["carteira-teorica"],
  },
] as const;

const porSlug = new Map(GLOSSARIO.map((v) => [v.slug, v]));

export function verbetePorSlug(slug: string): Verbete | undefined {
  return porSlug.get(slug);
}

/**
 * Props prontas para `<TermoTooltip {...tooltipDe("p-vp")}>…</TermoTooltip>`.
 * Slug desconhecido → `definicao: undefined` → fallback silencioso do
 * componente (D7): renderiza só o texto, sem popup — nunca inventa definição.
 */
export function tooltipDe(slug: string): {
  termo: string;
  definicao?: string;
  slug?: string;
} {
  const v = porSlug.get(slug);
  if (!v) return { termo: slug };
  return { termo: v.termo, definicao: v.definicao, slug: v.slug };
}

/** Letra de agrupamento (sem diacrítico: "Índice…" agrupa em "I"). */
function letraDe(termo: string): string {
  return termo
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .charAt(0)
    .toUpperCase();
}

export type GrupoAlfabetico = { letra: string; verbetes: Verbete[] };

/**
 * Verbetes agrupados por letra inicial, na ordem do GLOSSARIO (que é
 * alfabética por convenção do arquivo) — alimenta a navegação alfabética
 * de /glossario (padrão IndiceNav).
 */
export function gruposAlfabeticos(): GrupoAlfabetico[] {
  const grupos: GrupoAlfabetico[] = [];
  for (const v of GLOSSARIO) {
    const letra = letraDe(v.termo);
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.letra === letra) ultimo.verbetes.push(v);
    else grupos.push({ letra, verbetes: [v] });
  }
  return grupos;
}
