// Peças presentacionais compartilhadas pelas 4 seções novas do envelope
// ("Tese Profunda": Métricas do setor, Valuation, Análise técnica, Consenso)
// e pelos 3 componentes de gráfico. Mantidas num único módulo pequeno para
// as seções não duplicarem a mesma faixa de aviso/chip de fonte 4x.

import { formatarData } from "./formatacao";
import { BadgeLacuna } from "./SecaoChrome";
import type { FonteRef } from "./types";

// Só URLs http(s) viram link (javascript:, data:... -> texto) — mesma
// segunda linha de defesa de `urlHttp` em TeseView.tsx/Markdown.tsx; os
// blocos novos vêm de cálculo determinístico/consenso validado no backend,
// não do markdown livre do LLM, mas a regra é barata e universal o bastante
// para não abrir exceção aqui.
function urlHttp(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\//i.test(url);
}

// Fonte de um dado dos blocos novos (B3/CVM/BCB/ANEEL/ANBIMA...): descrição
// + link opcional + data de referência — mesmo papel visual de `FonteLink`
// em TeseView.tsx, só que para `FonteRef` (sem `id`).
export function FonteChip({ fonte }: { fonte: FonteRef }) {
  return (
    <p className="flex flex-wrap items-baseline gap-x-1.5 font-mono text-meta text-ink-3">
      {urlHttp(fonte.url) ? (
        <a
          href={fonte.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-ink-2 underline decoration-line-strong underline-offset-2 hover:text-ink hover:decoration-brasa-texto"
        >
          {fonte.descricao}
        </a>
      ) : (
        <span className="font-medium text-ink-2">{fonte.descricao}</span>
      )}
      {fonte.dt_referencia && <span>· {formatarData(fonte.dt_referencia)}</span>}
    </p>
  );
}

// Nota metodológica fixa (ex.: "preços não ajustados por proventos") — mais
// leve que `AvisoBanner` (que carrega o peso de compliance da tarja CVM):
// mesma família de cor (`aviso-*`), mas como uma tira fina de rodapé de
// gráfico/seção, sempre visível, nunca condicionada a hover/estado.
export function NotaFixa({ texto }: { texto: string }) {
  if (!texto.trim()) return null;
  return (
    <p className="border-l-2 border-aviso-borda bg-aviso-fundo/40 px-3 py-1.5 text-ui text-aviso-texto">{texto}</p>
  );
}

// Tag curta para rótulos de proveniência (ex.: "prudencial", "aprox.",
// "não ajustado") — mesma hierarquia visual do selo de classe do ativo no
// masthead (TeseView.tsx: `seloClasse`), reaproveitada aqui para os rótulos
// de métricas/premissas de valuation.
export function RotuloChip({ texto }: { texto: string }) {
  return (
    <span className="border border-line-strong px-1.5 py-0.5 font-sans text-label uppercase tracking-[0.08em] text-ink-3">
      {texto}
    </span>
  );
}

// Card de valor ausente para um gráfico sem pontos válidos suficientes
// (< 2 pontos finitos após o filtro anti-NaN) — nunca um <svg> quebrado ou
// um `path[d]` vazio: degrada para a MESMA linguagem de "dado não
// encontrado" do resto da tese, com nota+fonte ainda visíveis (o gráfico
// pode ter falhado, mas a proveniência do que FOI tentado continua auditável).
export function GraficoIndisponivel({
  titulo,
  nota,
  fonte,
}: {
  titulo: string;
  nota: string;
  fonte: FonteRef;
}) {
  return (
    <figure className="flex flex-col gap-3 border border-line bg-card p-5">
      <figcaption className="font-display text-lede font-semibold text-ink">{titulo}</figcaption>
      <div className="flex flex-wrap items-center gap-3">
        <BadgeLacuna texto="Dado não encontrado" />
        <p className="text-ui text-ink-2">Pontos insuficientes para desenhar este gráfico.</p>
      </div>
      <NotaFixa texto={nota} />
      <FonteChip fonte={fonte} />
    </figure>
  );
}
