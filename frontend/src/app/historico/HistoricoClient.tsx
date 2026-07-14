"use client";

// Lista das teses geradas NESTE navegador (localStorage — ver src/lib/historico.ts).
// Reabrir usa GET /api/teses/{id} direto (via /tese?id=...): nunca dispara POST,
// logo nunca regenera nem custa nada.
//
// Enxerto NORMA #4 (DESIGN-BRIEF.md §5): extrato de auditoria SEM cards — só
// linhas e réguas, agrupadas por dia com cabeçalho sticky. O CONTRATO de
// ItemHistorico (id, ticker, status, criadoEm) não muda aqui — só o visual.
//
// Missão APOTEOSE (crit.7 + crit.10 — onda CHROME):
// - Luz especular nos tickers: cada linha do extrato (o <Link> É a linha)
//   ganha `.ticker-luz` (primitiva da Onda 0, cinema/ticker-luz.css);
//   --mx/--my chegam por DELEGAÇÃO — um único usePonteiro no wrapper
//   estável abaixo (listener passivo + rAF, padrão GradeFoco), zero
//   mecanismo novo. Reduce/touch: hook e primitiva inertes por construção.
// - Reveals mais ricos: linhas entram como "Fila do Ticker"
//   (variant="reveal-ticker" + stagger .i-N por posição DENTRO do grupo do
//   dia, teto i-6 — grupos longos não acumulam atraso).
//
// Missão HORIZONTE (2026-07-14 — "A Hemeroteca", direcao-horizonte.md §9):
// ELEMENTO NOVO desta rota — os cabeçalhos de dia viram LOMBADAS de volume
// encadernado: no desktop (md+), sticky na LATERAL ESQUERDA de cada grupo
// (não mais uma faixa horizontal cobrindo a largura toda), texto mono em
// `writing-mode: vertical-rl` (lido de cima para baixo, como o dorso de um
// livro). No mobile, o sticky de TOPO atual é preservado tal qual (mesmas
// classes, sem `md:`). O offset agora usa o CONTRATO `--altura-tarja`
// (Onda 0/E4) em vez do `top-10` aproximado de antes — mais preciso em
// TODOS os breakpoints, sem precisar de outro número mágico.
//
// Zero cobertura de foco (E19/D33-doutrina): a lombada vive numa COLUNA
// própria (`md:self-start`), nunca sobre a coluna das entradas — e o
// `[id] { scroll-margin-top: 6rem }` global (globals.css) já cobre o caso
// em que o foco chega por âncora direta (`#registro-{id}`), nos dois modos.
//
// Relevo das entradas: cada linha ganha `.gema-chip__corpo` (cinema/gema.css,
// reuso "sem o filho" — D14 já documenta esse padrão para nós que já
// respondem a :hover/:focus-within sozinhos, como esta linha). Zero CSS
// novo: a classe já existe, só é aplicada aqui pela 1ª vez fora da Prova
// Viva/hero.

import Link from "next/link";
import { useMemo, useRef, useSyncExternalStore } from "react";

import { Reveal } from "@/components/motion/Reveal";
import { usePonteiro } from "@/components/motion/usePonteiro";
import {
  assinarHistorico,
  HISTORICO_VAZIO,
  lerHistoricoSnapshot,
  limparHistorico,
  type ItemHistorico,
} from "@/lib/historico";

const ROTULO_STATUS: Record<ItemHistorico["status"], string> = {
  ready: "pronta",
  processing: "processando",
  error: "falhou",
};

// Cor do status segue a hierarquia do design system: "pronta" usa a brasa
// (ação normal, tese pode ser aberta); "processando" usa o par aviso;
// "falhou" usa o par erro (falha técnica) — nunca o inverso.
const CLASSE_STATUS: Record<ItemHistorico["status"], string> = {
  ready: "text-brasa-texto",
  processing: "text-aviso-texto",
  error: "text-erro-texto",
};

const MESES = [
  "JAN",
  "FEV",
  "MAR",
  "ABR",
  "MAI",
  "JUN",
  "JUL",
  "AGO",
  "SET",
  "OUT",
  "NOV",
  "DEZ",
] as const;

function formatHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

// Chave estável de agrupamento (data local, não UTC — evita que um registro
// das 23h vire "dia seguinte" só por causa do fuso).
function chaveDia(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "indefinido";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function rotuloDia(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "DATA INDEFINIDA";
  const dia = String(d.getDate()).padStart(2, "0");
  const mes = MESES[d.getMonth()];
  return `${dia} ${mes} ${d.getFullYear()}`;
}

type Grupo = { chave: string; rotulo: string; itens: ItemHistorico[] };

// Os itens já chegam ordenados do mais recente para o mais antigo
// (registrarNoHistorico prepende) — o agrupamento preserva essa ordem.
function agruparPorDia(itens: ItemHistorico[]): Grupo[] {
  const grupos: Grupo[] = [];
  const porChave = new Map<string, Grupo>();
  for (const item of itens) {
    const chave = chaveDia(item.criadoEm);
    let grupo = porChave.get(chave);
    if (!grupo) {
      grupo = { chave, rotulo: rotuloDia(item.criadoEm), itens: [] };
      porChave.set(chave, grupo);
      grupos.push(grupo);
    }
    grupo.itens.push(item);
  }
  return grupos;
}

export function HistoricoClient() {
  // localStorage é um sistema externo: useSyncExternalStore lê o snapshot no
  // cliente (o servidor rende a lista vazia) e reage a mudanças — inclusive de
  // outras abas, via evento `storage`.
  const itens = useSyncExternalStore(
    assinarHistorico,
    lerHistoricoSnapshot,
    () => HISTORICO_VAZIO,
  );

  const grupos = useMemo(() => agruparPorDia(itens), [itens]);

  // Delegação da luz especular (crit.7): UM listener passivo no wrapper
  // ESTÁVEL (o mesmo nó nos dois estados — vazio/lista — para o efeito do
  // usePonteiro, que roda 1x, nunca apontar para um nó desmontado) escreve
  // --mx/--my no `.ticker-luz` sob o ponteiro.
  const raizRef = useRef<HTMLDivElement | null>(null);
  usePonteiro(raizRef, { seletorAlvo: ".ticker-luz" });

  return (
    // `[overflow-x:clip]` (defeito 3, gate de geometria, wt-horizonte
    // 2026-07-14): cada entrada É `.ticker-luz` (cinema/ticker-luz.css) — o
    // sprite `::after` (46vmax) transborda a caixa do link mesmo sem
    // hover/toque algum (posição neutra `--mx:0/--my:0` de globals.css já
    // extrapola a largura da coluna). Sem um ancestral que clipe, o
    // `scrollWidth` do documento estoura em mobile (mesmo padrão de
    // `.salao-pinado`: clip, nunca hidden — não é ancestral da régua/Tarja).
    <div ref={raizRef} className="flex flex-col gap-8 [overflow-x:clip]">
      {itens.length === 0 ? (
        <div className="flex flex-col items-start gap-3 border border-line bg-card px-6 py-8">
          {/* Copy HORIZONTE (copy-horizonte-spec.md §8, verbatim). */}
          <p className="font-sans text-ui text-ink-2">
            Nenhuma tese gerada neste navegador ainda. Comece por uma pronta
            da galeria — ou gere a primeira agora.
          </p>
          <Link
            href="/tese"
            className="flex min-h-11 items-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
          >
            Gerar a primeira tese
          </Link>
        </div>
      ) : (
        <>
          {grupos.map((grupo) => (
            <section
              key={grupo.chave}
              aria-labelledby={`dia-${grupo.chave}`}
              className="md:flex md:items-start md:gap-6"
            >
              {/* A LOMBADA (D)ia: mobile preserva o sticky de topo atual
                  (offset agora pelo contrato --altura-tarja, E4 — mais
                  preciso que o top-10 aproximado de antes). Desktop (md+):
                  sticky NA COLUNA ESQUERDA do próprio grupo (não mais uma
                  faixa horizontal), mono vertical (writing-mode: vertical-rl)
                  — a lombada de um volume encadernado. `md:self-start`
                  ancora no topo da linha flex; o sticky natural a mantém
                  visível enquanto o grupo (mais alto que ela) rola por
                  baixo — nunca sobre a coluna das entradas (zero cobertura
                  de foco, E19). */}
              <h2
                id={`dia-${grupo.chave}`}
                className="sticky top-[var(--altura-tarja)] z-10 border-b border-line-strong bg-page py-2 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3 md:top-[calc(var(--altura-tarja)_+_1.5rem)] md:w-9 md:shrink-0 md:self-start md:border-b-0 md:border-r md:border-line-strong md:bg-transparent md:py-4 md:pr-3 md:text-left md:[writing-mode:vertical-rl]"
              >
                {grupo.rotulo}
              </h2>
              <ul className="flex flex-1 flex-col md:pl-2">
                {grupo.itens.map((item, indice) => (
                  <li key={item.id} className="border-b border-line">
                    {/* Fila do Ticker (crit.10): stagger por posição no grupo
                        do dia, teto .i-6 — linha 40 não espera 40 passos. */}
                    <Reveal
                      variant="reveal-ticker"
                      className={indice > 0 ? `i-${Math.min(indice, 6)}` : undefined}
                    >
                      {/* A1 (foco não obscurecido, 2.4.11): id estável herda
                          `[id] { scroll-margin-top: 6rem }` (globals.css) — sem
                          isso, focar este link por teclado e rolar até ele o
                          deixava colado sob o cabeçalho de dia sticky.
                          Relevo (Hemeroteca): `.gema-chip__corpo`
                          (cinema/gema.css — reuso "sem o filho", D14) dá o
                          bisel/keyline + lift 2px no hover/focus a cada
                          entrada. A linha É o ticker: `.ticker-luz` aqui
                          (crit.7), sprite z:-1 contido pelo isolation da
                          própria primitiva. */}
                      <Link
                        id={`registro-${item.id}`}
                        href={`/tese?id=${encodeURIComponent(item.id)}&ticker=${encodeURIComponent(item.ticker)}`}
                        className="ticker-luz gema-chip__corpo grid min-h-11 grid-cols-[4.5rem_1fr] items-center gap-4 px-3 py-3 transition-colors duration-[var(--dur-tick)] hover:bg-card sm:grid-cols-[5.5rem_1fr]"
                      >
                        <span className="font-mono text-meta text-ink-3">
                          {formatHora(item.criadoEm)}
                        </span>
                        <span className="flex min-w-0 items-baseline gap-3">
                          <span className="truncate font-mono text-ui font-semibold text-ink">
                            {item.ticker}
                          </span>
                          <span
                            className={`font-mono text-meta uppercase tracking-wide ${CLASSE_STATUS[item.status]}`}
                          >
                            {ROTULO_STATUS[item.status]}
                          </span>
                        </span>
                      </Link>
                    </Reveal>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          <button
            type="button"
            onClick={() => limparHistorico()}
            className="flex min-h-11 w-fit items-center font-sans text-ui text-ink-3 underline underline-offset-4 hover:text-ink"
          >
            Limpar histórico deste navegador
          </button>
        </>
      )}
    </div>
  );
}
