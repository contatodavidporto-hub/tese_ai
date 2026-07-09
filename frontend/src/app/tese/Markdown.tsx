// Renderizador de markdown MÍNIMO e SEGURO (sem biblioteca — restrição do projeto).
// Não usa dangerouslySetInnerHTML: cada trecho vira um nó React, eliminando o risco
// de injeção de HTML vindo da saída do LLM (ver AGENTS.md: "saída do LLM ... sem sanitizar").
// Suporta: títulos #/##/###, listas (-, *, 1.), citações em bloco (>), tabelas de
// pipe, parágrafos; inline: **negrito**, *itálico*, `código` e [links](https://...)
// — só http(s) vira <a>; qualquer outro esquema permanece texto.

import { Fragment, type ReactNode } from "react";

import type { Citacao } from "./types";

export type Bloco =
  | { kind: "h1" | "h2" | "h3" | "p" | "quote"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "table"; header: string[]; rows: string[][] };

// ---------------------------------------------------------------------------
// Parse em blocos
// ---------------------------------------------------------------------------

function dividirLinhaTabela(linha: string): string[] {
  return linha
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function ehSeparadorTabela(linha: string): boolean {
  return /^\|?[\s:|-]+\|?$/.test(linha) && linha.includes("-");
}

export function parseBlocos(markdown: string): Bloco[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocos: Bloco[] = [];

  let paragraph: string[] = [];
  let list: { type: "ul" | "ol"; items: string[] } | null = null;
  let table: { header: string[]; rows: string[][] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocos.push({ kind: "p", text: paragraph.join(" ") });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocos.push({ kind: list.type, items: list.items });
      list = null;
    }
  };
  const flushTable = () => {
    if (table) {
      blocos.push({ kind: "table", header: table.header, rows: table.rows });
      table = null;
    }
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
    flushTable();
  };

  for (const raw of lines) {
    const trimmed = raw.trim();

    if (trimmed === "") {
      flushAll();
      continue;
    }

    // Tabela de pipes: linha começando com "|" abre/continua uma tabela.
    if (trimmed.startsWith("|")) {
      flushParagraph();
      flushList();
      if (ehSeparadorTabela(trimmed) && table && table.rows.length === 0) {
        continue; // linha |---|---| logo após o cabeçalho
      }
      const celulas = dividirLinhaTabela(trimmed);
      if (!table) {
        table = { header: celulas, rows: [] };
      } else {
        table.rows.push(celulas);
      }
      continue;
    }
    flushTable();

    // Níveis 4-6 são rebaixados para h3 (nunca viram "####" literal na tela).
    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (heading) {
      flushAll();
      const level = heading[1].length;
      blocos.push({
        kind: level === 1 ? "h1" : level === 2 ? "h2" : "h3",
        text: heading[2].trim(),
      });
      continue;
    }

    const quote = /^>\s?(.*)$/.exec(trimmed);
    if (quote) {
      flushAll();
      const anterior = blocos[blocos.length - 1];
      if (anterior && anterior.kind === "quote") {
        anterior.text += ` ${quote[1].trim()}`;
      } else {
        blocos.push({ kind: "quote", text: quote[1].trim() });
      }
      continue;
    }

    const unordered = /^[-*]\s+(.*)$/.exec(trimmed);
    if (unordered) {
      flushParagraph();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(unordered[1].trim());
      continue;
    }

    const ordered = /^\d+[.)]\s+(.*)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(ordered[1].trim());
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushAll();
  return blocos;
}

// ---------------------------------------------------------------------------
// Seções: o motor emite exatamente "## 1. Fundamentos" ... "## 8. Lacunas"
// (backend/app/services/tese.py). Dividimos nos h2 para sumário + âncoras.
// ---------------------------------------------------------------------------

export type Secao = {
  id: string;
  titulo: string;
  blocos: Bloco[];
};

export type DocumentoTese = {
  titulo: string | null;
  intro: Bloco[]; // blocos antes do primeiro h2 (ex.: o blockquote de aviso)
  secoes: Secao[];
};

export function slugify(texto: string): string {
  return (
    texto
      .toLowerCase()
      .normalize("NFD")
      // remove diacríticos combinantes (U+0300–U+036F) após o NFD
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "secao"
  );
}

export function separarSecoes(markdown: string): DocumentoTese {
  const blocos = parseBlocos(markdown);
  let titulo: string | null = null;
  const intro: Bloco[] = [];
  const secoes: Secao[] = [];
  const idsUsados = new Set<string>();

  for (const bloco of blocos) {
    if (bloco.kind === "h1" && titulo === null && secoes.length === 0) {
      titulo = bloco.text;
      continue;
    }
    if (bloco.kind === "h2") {
      // Prefixo "secao-": um h2 do LLM não pode colidir com âncoras fixas da
      // página (#citacoes, #citacao-N, #registro-de-fontes, #conteudo).
      let id = `secao-${slugify(bloco.text)}`;
      let n = 2;
      while (idsUsados.has(id)) id = `secao-${slugify(bloco.text)}-${n++}`;
      idsUsados.add(id);
      secoes.push({ id, titulo: bloco.text, blocos: [] });
      continue;
    }
    (secoes.length === 0 ? intro : secoes[secoes.length - 1].blocos).push(bloco);
  }

  return { titulo, intro, secoes };
}

// ---------------------------------------------------------------------------
// Inline: links http(s), **negrito**, *itálico*, `código`
// ---------------------------------------------------------------------------

// Só URLs http(s) viram link (javascript:, data:... -> texto). O backend já
// valida; esta é a segunda linha de defesa no render.
// Quantificadores LIMITADOS ({1,400}/{1,2000}): entrada hostil do LLM com
// milhares de "[" sem fechamento não pode degenerar em varredura quadrática
// (classe ReDoS — achado M1 do auditor-mor). Flag `i`: HTTPS:// também vale.
const LINK_RE = /\[([^\]\n]{1,400})\]\((https?:\/\/[^\s)]{1,2000})\)/gi;

// Teto de tamanho por trecho antes de qualquer regex: acima disso, devolve
// texto puro (um bloco real de tese tem ~2 KB; 20 KB já é entrada hostil).
const LIMITE_TEXTO_INLINE = 20_000;

// Com `hostsOk` presente (render de tese), um link do markdown só vira <a> se o
// host está entre as FONTES da tese — um LLM comprometido não consegue apontar
// o leitor para domínio estranho com rótulo que mascara o destino (phishing).
function linkPermitido(url: string, hostsOk?: ReadonlySet<string>): boolean {
  if (!hostsOk) return true;
  try {
    return hostsOk.has(new URL(url).hostname);
  } catch {
    return false;
  }
}

function renderEnfase(text: string, keyBase: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    const key = `${keyBase}-${i}`;
    const bold = /^\*\*([^*]+)\*\*$/.exec(part);
    if (bold) return <strong key={key}>{bold[1]}</strong>;
    const italic = /^\*([^*]+)\*$/.exec(part);
    if (italic) return <em key={key}>{italic[1]}</em>;
    const code = /^`([^`]+)`$/.exec(part);
    if (code) {
      return (
        <code key={key} className="bg-line px-1 py-0.5 font-mono text-ink">
          {code[1]}
        </code>
      );
    }
    return <Fragment key={key}>{realcarNumeros(part, key)}</Fragment>;
  });
}

// ---------------------------------------------------------------------------
// Realce presentacional de números factuais — "se está em mono, tem fonte"
// (design system BRASA EDITORIAL, DESIGN-BRIEF.md §3). Puramente visual:
// reaproveita os MESMOS limites de quantificador das regexes de citação
// abaixo (RE_MONETARIO/RE_DECIMAL, já auditadas contra ReDoS — achado M1) e
// NÃO participa da lógica de ancoragem de citação/sanitização.
// ---------------------------------------------------------------------------

let RE_NUMERO_VISUAL: RegExp | null = null;

function realcarNumeros(text: string, keyBase: string): ReactNode[] {
  // Construída sob demanda (não no top level do módulo): RE_MONETARIO/
  // RE_DECIMAL só existem mais abaixo neste arquivo; adiar para a primeira
  // chamada evita depender de ordem de inicialização entre `const`s do módulo.
  RE_NUMERO_VISUAL ??= new RegExp(`${RE_MONETARIO.source}|${RE_DECIMAL.source}`, "g");
  const re = RE_NUMERO_VISUAL;
  re.lastIndex = 0;
  const nodes: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    nodes.push(
      <span key={`${keyBase}-n${i}`} className="font-mono text-brasa-texto">
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes.length > 0 ? nodes : [text];
}

export function renderInline(
  text: string,
  hostsOk?: ReadonlySet<string>,
): ReactNode {
  if (text.length > LIMITE_TEXTO_INLINE) return text; // hostil: sem regex
  const nodes: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  LINK_RE.lastIndex = 0;
  let i = 0;
  while ((m = LINK_RE.exec(text)) !== null) {
    if (m.index > last) nodes.push(...renderEnfase(text.slice(last, m.index), `t${i}`));
    if (linkPermitido(m[2], hostsOk)) {
      nodes.push(
        <a
          key={`l${i}`}
          href={m[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brasa-texto underline decoration-line-strong underline-offset-2 hover:decoration-brasa-texto"
        >
          {renderEnfase(m[1], `lr${i}`)}
        </a>,
      );
    } else {
      // host fora do registro de fontes: mostra rótulo e destino como TEXTO
      nodes.push(<Fragment key={`l${i}`}>{`${m[1]} (${m[2]})`}</Fragment>);
    }
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) nodes.push(...renderEnfase(text.slice(last), `t${i}`));
  return nodes;
}

// ---------------------------------------------------------------------------
// Citações: âncora [n] com preview da fonte ao hover/foco.
// O `texto_citado` (Anthropic Citations) cita o DOCUMENTO-FONTE (entrada do
// modelo), não o markdown gerado — substring direta nunca casa. A ancoragem é
// por VALOR: extraímos os números fortes da citação (R$ e decimais pt-BR) e
// marcamos os blocos que repetem o mesmo valor — exatamente a promessa "cada
// número com fonte". Medido com teses reais (VALE3/PETR4): 100% das citações
// com valor numérico ancoram. Citações qualitativas (sem número) continuam
// visíveis na lista "Citações" ao fim da tese.
// ---------------------------------------------------------------------------

export type CitacaoRef = { indice: number; citacao: Citacao; tokens: string[] };

// Grupos de milhar LIMITADOS ({0,6} cobre até casa de quatrilhão): repetição
// aberta degenerava em backtracking quadrático sob entrada hostil (M1).
const RE_MONETARIO = /R\$\s{0,4}-?\d{1,3}(?:\.\d{3}){0,6}(?:,\d{1,10})?/g;
const RE_DECIMAL = /-?\d{1,3}(?:\.\d{3}){0,6},\d{1,10}/g;

function tokensFortes(texto: string): string[] {
  // texto_citado real tem ~100-200 chars; o corte é só anti-abuso.
  const alvo = texto.length > 4_000 ? texto.slice(0, 4_000) : texto;
  const toks = new Set<string>();
  for (const m of alvo.match(RE_MONETARIO) ?? []) {
    toks.add(m.replace(/\s+/g, ""));
  }
  for (const m of alvo.match(RE_DECIMAL) ?? []) {
    const t = m.replace(/\s+/g, "");
    // >= 4 dígitos: um decimal curto ("3,25") coincide fácil com número de
    // OUTRO significado no corpo — marcador com fonte errada é pior que nenhum.
    if ((t.match(/\d/g) ?? []).length >= 4) toks.add(t);
  }
  return [...toks];
}

export function construirRefs(citacoes: Citacao[]): CitacaoRef[] {
  return citacoes.map((citacao, i) => ({
    indice: i + 1,
    citacao,
    tokens: tokensFortes(citacao.texto_citado),
  }));
}

// Ocorrência com FRONTEIRA numérica: "14,25" não pode casar dentro de
// "3.114,25" nem de "14,255" (marcador com fonte errada seria pior que nenhum).
function contemTokenComFronteira(alvo: string, token: string): boolean {
  const digito = (c: string | undefined) => !!c && c >= "0" && c <= "9";
  let idx = alvo.indexOf(token);
  while (idx !== -1) {
    const antes = alvo[idx - 1];
    const depois = alvo[idx + token.length];
    const okAntes =
      !digito(antes) && !((antes === "." || antes === ",") && digito(alvo[idx - 2]));
    const okDepois =
      !digito(depois) &&
      !((depois === "." || depois === ",") && digito(alvo[idx + token.length + 1]));
    if (okAntes && okDepois) return true;
    idx = alvo.indexOf(token, idx + 1);
  }
  return false;
}

export function citacoesDoTexto(texto: string, refs: CitacaoRef[]): CitacaoRef[] {
  if (refs.length === 0) return [];
  const alvo = texto.replace(/\s+/g, "");
  if (!alvo) return [];
  return refs.filter(
    (r) =>
      r.tokens.length > 0 &&
      r.tokens.some((t) => contemTokenComFronteira(alvo, t)),
  );
}

function formatDataCurta(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR");
}

function dominioDe(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

// Obs.: a prop NÃO pode se chamar `ref` (reservada pelo React).
export function MarcadorCitacao({ refCitacao }: { refCitacao: CitacaoRef }) {
  const { indice, citacao } = refCitacao;
  const fonte = citacao.fonte;
  const dominio = dominioDe(fonte?.url);
  return (
    <span className="group relative inline-block align-super">
      <a
        href={`#citacao-${indice}`}
        aria-label={`Citação ${indice}${fonte ? ` — fonte: ${fonte.descricao}` : ""}`}
        className="bg-realce px-1 py-0.5 font-mono text-label font-semibold text-brasa-texto no-underline hover:bg-brasa hover:text-sobre-brasa"
      >
        [{indice}]
      </a>
      {/* Sem margem entre âncora e balão e sem pointer-events-none: o ponteiro
          pode ENTRAR no balão sem que ele feche (WCAG 1.4.13 — hoverable). O
          clique na âncora leva à citação completa (alternativa sempre acessível). */}
      <span
        role="tooltip"
        className="sombra-elevada invisible absolute bottom-full left-1/2 z-40 w-64 -translate-x-1/2 border border-line-strong bg-elevated p-3 text-left text-ui leading-snug text-ink opacity-0 transition-opacity duration-[var(--dur-tick)] group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
      >
        <span className="mb-1 block font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
          Fonte da citação {indice}
        </span>
        <span className="block font-medium text-ink">
          {fonte?.descricao || citacao.titulo_documento || "Documento-fonte"}
        </span>
        {fonte?.dt_referencia && (
          <span className="mt-0.5 block font-mono text-meta text-ink-3">
            Referência: {formatDataCurta(fonte.dt_referencia)}
          </span>
        )}
        {dominio && <span className="mt-0.5 block font-mono text-meta text-ink-3">{dominio}</span>}
      </span>
    </span>
  );
}

function Marcadores({ refs }: { refs: CitacaoRef[] }) {
  if (refs.length === 0) return null;
  return (
    <>
      {" "}
      {refs.map((r) => (
        <MarcadorCitacao key={r.indice} refCitacao={r} />
      ))}
    </>
  );
}

// Célula de tabela sem dado: heurística de MATCH EXATO (não substring) para
// não confundir um valor real com o placeholder — puramente presentacional,
// não participa do parseBlocos acima. Espelha os rótulos de abstenção do
// motor ("dado não encontrado", AGENTS.md: abster > inventar).
const RE_CELULA_LACUNA = /^(dado não encontrado|não encontrado|indispon[íi]vel|n\/d|n\.d\.|n\/a|—|-)$/i;

function ehCelulaLacuna(texto: string): boolean {
  return RE_CELULA_LACUNA.test(texto.trim());
}

// ---------------------------------------------------------------------------
// Render dos blocos
// ---------------------------------------------------------------------------

export function Blocos({
  blocos,
  refs = [],
  hostsOk,
  narrada = false,
}: {
  blocos: Bloco[];
  refs?: CitacaoRef[];
  // hosts permitidos para links do markdown (derivados das fontes da tese)
  hostsOk?: ReadonlySet<string>;
  // Voz narrada da D5 (seção "Camada geopolítica e correlações"): itálico
  // Newsreader 500 — a ÚNICA seção que recebe esse tratamento (DESIGN-
  // BRIEF.md §3: "itálico 500 = voz exclusiva da D5 narrada"). Afeta só
  // parágrafos de prosa corrida, não títulos/listas/tabelas.
  narrada?: boolean;
}) {
  return (
    <div className="flex flex-col gap-5 font-display text-body text-ink">
      {blocos.map((bloco, i) => {
        switch (bloco.kind) {
          case "h1":
            return (
              <h2 key={i} className="font-display text-h2 font-semibold tracking-tight text-ink">
                {renderInline(bloco.text, hostsOk)}
              </h2>
            );
          case "h2":
            return (
              <h3 key={i} className="mt-2 font-display text-h3 font-semibold tracking-tight text-ink">
                {renderInline(bloco.text, hostsOk)}
              </h3>
            );
          case "h3":
            return (
              <h4 key={i} className="mt-1 font-display text-lede font-semibold text-ink">
                {renderInline(bloco.text, hostsOk)}
              </h4>
            );
          case "quote":
            // Blockquote do markdown = a voz de aviso do próprio motor (ex.: o
            // aviso de não-recomendação embutido na introdução da tese) — par
            // aviso-*, nunca quote-wash (exclusivo de evidência/citação).
            return (
              <blockquote
                key={i}
                className="border-l-2 border-aviso-borda bg-aviso-fundo/40 py-2 pl-4 font-sans text-ui text-aviso-texto"
              >
                {renderInline(bloco.text, hostsOk)}
              </blockquote>
            );
          case "table":
            return (
              <div key={i} className="overflow-x-auto">
                <table className="w-full border-collapse font-sans text-ui text-ink">
                  <thead>
                    <tr className="border-b-2 border-line-strong text-left">
                      {bloco.header.map((c, j) => (
                        <th
                          key={j}
                          scope="col"
                          className="px-3 py-2 font-sans text-label font-semibold uppercase tracking-[0.1em] text-ink-2"
                        >
                          {renderInline(c, hostsOk)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {bloco.rows.map((row, j) => (
                      <tr key={j} className="border-b border-line">
                        {row.map((c, k) => {
                          if (ehCelulaLacuna(c)) {
                            return (
                              <td
                                key={k}
                                className="hachura-lacuna px-3 py-2 text-center align-middle font-mono text-meta text-aviso-texto"
                              >
                                {c}
                              </td>
                            );
                          }
                          return (
                            <td key={k} className="px-3 py-2 align-top">
                              {renderInline(c, hostsOk)}
                              <Marcadores refs={citacoesDoTexto(c, refs)} />
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "ul":
            return (
              <ul key={i} className="list-disc space-y-2 pl-5 text-body marker:text-ink-3">
                {bloco.items.map((item, j) => (
                  <li key={j}>
                    {renderInline(item, hostsOk)}
                    <Marcadores refs={citacoesDoTexto(item, refs)} />
                  </li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={i} className="list-decimal space-y-2 pl-5 text-body marker:text-ink-3">
                {bloco.items.map((item, j) => (
                  <li key={j}>
                    {renderInline(item, hostsOk)}
                    <Marcadores refs={citacoesDoTexto(item, refs)} />
                  </li>
                ))}
              </ol>
            );
          case "p":
          default:
            return (
              <p key={i} className={narrada ? "text-body font-display italic font-medium" : "text-body"}>
                {renderInline(bloco.text, hostsOk)}
                <Marcadores refs={citacoesDoTexto(bloco.text, refs)} />
              </p>
            );
        }
      })}
    </div>
  );
}

// Compatibilidade: render simples do markdown inteiro (sem seções/citações).
export function Markdown({ source }: { source: string }) {
  return <Blocos blocos={parseBlocos(source)} />;
}
