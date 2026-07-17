"use client";

// MISSÃO OURIVESARIA — raia 2D (crit. 9 · §3-C9 · §7-E9/F6 · conceito B §8):
// HEMEROTECA DO ZERO — "Registro de bancada". As LOMBADAS verticais da
// Horizonte (writing-mode: vertical-rl) MORRERAM; a lista vira FICHAS
// horizontais agrupadas por dia, com cabeçalho de dia sticky sob a Tarja.
// Elemento novo NOMEADO: **"Ficha com carimbo de hora"** (+ Regenerar).
//
// CONTRATOS PRESERVADOS (nenhum mudou):
//   - `lib/historico.ts` INTOCADA (só consumo): localStorage
//     `teseai.historico.v1`, limite 50, `useSyncExternalStore` + evento
//     `storage` (outras abas), ordem mais-recente-primeiro.
//   - Abrir = <Link> GET `/tese?id&ticker` (bypass do LinkCinema — o véu
//     especializado mora em /tese): reabrir NUNCA dispara POST.
//   - REGENERAR (novo por ficha): <Link> GET `/tese?ticker=` SEM id — o
//     form chega preenchido e o humano confirma com 1 clique. A guarda
//     anti-custo do `autoIniciar` (tese/page.tsx: auto-POST só para
//     EXEMPLOS_PRONTOS, cache aquecido) fica INTACTA por construção: esta
//     página só navega, nunca inicia geração.
//   - Em ficha `falhou`, a ação primária é "Tentar de novo" (brasa);
//     "Regenerar" é secundária e só em ficha `pronta`; `processando` só
//     tem Abrir (a tese ainda está em voo — reabrir retoma o polling).
//
// COPY CONGELADA (.maestro/copy-ourivesaria.md §3 — transcrição byte-fiel,
// §7-E5; sr-only e aria-label CONTAM no gate, ruling 6.6): carimbo
// "registrada às {HH:MM}" (cobre gerada E aberta — honesto com a lib),
// cabeçalho de dia "{DD} {MMM} {AAAA} · {n} teses", rótulos de status
// BYTE-IDÊNTICOS (pronta/processando/falhou — hierarquia de cor da casa,
// NUNCA cor nova), aria-labels com o ticker (§7-F6).
//
// A11Y DA FICHA (§7-F6):
//   - scroll-margin-top nas fichas E nas ações = Tarja + cabeçalho de dia
//     sticky + folga (2.4.11 — foco nunca obscurecido; o cabeçalho de dia
//     mede ~62px, a classe reserva 4.5rem = 72px além da Tarja).
//   - Limpar em 2 TEMPOS: 1º clique arma ("Confirmar limpeza?" + nota do
//     que apaga/não apaga); NÃO reverte enquanto o botão tem foco — blur
//     ou 5s, o que vier DEPOIS; role=status anuncia armar e concluir.
//   - Regenerar/Tentar ficam DENTRO da ficha mas FORA do Link principal
//     (2 alvos irmãos — nunca link aninhado); todos ≥44px (min-h-11).
//
// MOVIMENTO (2.2.2 — nada contínuo; ZERO efeito novo, zero folha nova):
//   - entrada = Fila do Ticker (`reveal-ticker` + stagger .i-N teto 6 por
//     posição no dia) — one-shot do motor Reveal (reduce já coberto lá);
//   - talha de ouro (`talha-capitulo` + `reveal-regua`) abre cada dia —
//     one-shot, registro nominal na bancada.css (1A);
//   - `.ticker-luz` por ficha: specular movido pelo usePonteiro DELEGADO
//     abaixo (1 listener passivo, hook existente; reduce/touch inertes) —
//     o `[overflow-x:clip]` do wrapper é OBRIGATÓRIO (sprite 46vmax; clip
//     nunca hidden; este wrapper NÃO é ancestral de TermoTooltip — §7-F5);
//   - relevo = `.gema-chip__corpo` (bisel + lift 2px hover/focus, reuso
//     "sem o filho" D14); estado vazio = pedra bruta com `.pedra-404`
//     (dash-draw one-shot 900ms, dona: lapidacao.css; reduce = contorno
//     completo estático). O `d` do path é DUPLICADO de not-found.tsx de
//     propósito (pegadinha 3/D18: importar CenaNascimento aqui embarcaria
//     a cena inteira; a classe já é global via lapidacao.css — CSS pago).

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

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

// Copy congelada do anexo §3 (role=status — anunciada, sr-only; conta no
// gate de copy do mesmo jeito, ruling 6.6).
const MSG_CONFIRMAR = "Clique de novo para confirmar a limpeza do registro.";
const MSG_LIMPO = "Registro limpo. Nenhuma tese guardada neste navegador.";

// 2.4.11 (§7-F6): margem de rolagem do foco = Tarja (var por breakpoint) +
// cabeçalho de dia sticky (~62px: py-2 + talha 2px + pós-fio 1.5rem +
// linha mono) + folga ≥0.5rem → 4.5rem reserva tudo. Aplicada ao Link da
// ficha E às ações irmãs (é o ELEMENTO FOCADO que o navegador rola).
const SCROLL_FICHA = "scroll-mt-[calc(var(--altura-tarja)_+_4.5rem)]";

export function HistoricoClient() {
  // localStorage é um sistema externo: useSyncExternalStore lê o snapshot no
  // cliente (o servidor rende a lista vazia) e reage a mudanças — inclusive
  // de outras abas, via evento `storage`.
  const itens = useSyncExternalStore(
    assinarHistorico,
    lerHistoricoSnapshot,
    () => HISTORICO_VAZIO,
  );

  const grupos = useMemo(() => agruparPorDia(itens), [itens]);

  // Delegação da luz especular: UM listener passivo no wrapper ESTÁVEL (o
  // mesmo nó nos dois estados — vazio/lista — para o efeito do usePonteiro,
  // que roda 1x, nunca apontar para um nó desmontado) escreve --mx/--my no
  // `.ticker-luz` sob o ponteiro.
  const raizRef = useRef<HTMLDivElement | null>(null);
  usePonteiro(raizRef, { seletorAlvo: ".ticker-luz" });

  // ---- Limpar em 2 tempos (§7-F6) ------------------------------------
  // Regra do recuo: NÃO reverte enquanto o botão tem foco — reverte no
  // blur ou aos 5s, O QUE VIER DEPOIS. Implementação: o timer de 5s marca
  // `expirou`; se ao disparar o botão não tem foco, desarma; se tem, quem
  // desarma é o blur (que só desarma se `expirou`). O 2º clique confirma.
  const [confirmando, setConfirmando] = useState(false);
  const [aviso, setAviso] = useState("");
  const botaoLimparRef = useRef<HTMLButtonElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const expirouRef = useRef(false);

  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  function desarmarLimpeza() {
    setConfirmando(false);
    setAviso("");
    expirouRef.current = false;
  }

  function aoClicarLimpar() {
    if (!confirmando) {
      setConfirmando(true);
      setAviso(MSG_CONFIRMAR);
      expirouRef.current = false;
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        expirouRef.current = true;
        if (document.activeElement !== botaoLimparRef.current) {
          desarmarLimpeza();
        }
      }, 5000);
      return;
    }
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    limparHistorico();
    setConfirmando(false);
    expirouRef.current = false;
    setAviso(MSG_LIMPO);
  }

  function aoDesfocarLimpar() {
    if (confirmando && expirouRef.current) desarmarLimpeza();
  }

  // ---- 2.4.11 — foco nunca obscurecido (§7-F6) -----------------------
  // O scroll-margin-top das fichas cobre o caso COM rolagem; mas quando o
  // alvo do Tab/Shift+Tab JÁ está dentro do viewport ATRÁS do cabeçalho
  // de dia sticky, o navegador não rola nada (oclusão por sticky não
  // conta como "fora de vista") e o foco nasceria coberto. Empurrão
  // mínimo: se o topo do elemento focado ficar acima da linha inferior do
  // cabeçalho sticky da PRÓPRIA seção (que já embute a Tarja — o sticky
  // ancora em --altura-tarja), rola exatamente a diferença. Instantâneo
  // (sem smooth): não é animação, é correção de viewport — nada a
  // registrar sob reduce.
  function aoFocar(e: React.FocusEvent<HTMLDivElement>) {
    const alvo = e.target;
    if (!(alvo instanceof HTMLElement)) return;
    const secao = alvo.closest("section");
    const cabecalho = secao?.firstElementChild;
    if (!(cabecalho instanceof HTMLElement)) return;
    if (getComputedStyle(cabecalho).position !== "sticky") return;
    // DOUBLE-rAF (medido na sonda da raia): a rolagem-reveal do próprio
    // navegador é ASSÍNCRONA (~2 quadros após o focus) — corrigir dentro
    // do evento seria clobberado por ela. Dois quadros depois, RECOMPUTA:
    // se o alvo ainda estiver sob a linha do cabeçalho, empurra só a
    // diferença.
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (document.activeElement !== alvo) return;
        // Posição ESTACIONÁRIA do sticky (computed top resolve a var da
        // Tarja em px), não o rect atual: na fase de push-out (seção
        // saindo pelo topo) o cabeçalho está espremido ACIMA dela e o
        // rect daria um limite curto — a ficha pousaria sob a Tarja.
        const estilo = getComputedStyle(cabecalho);
        const limite =
          (parseFloat(estilo.top) || 0) + cabecalho.offsetHeight + 8;
        const topo = alvo.getBoundingClientRect().top;
        if (topo < limite) window.scrollBy(0, topo - limite);
      });
    });
  }

  return (
    // `[overflow-x:clip]` (gate de geometria, §7-F5): cada ficha É
    // `.ticker-luz` — o sprite `::after` (46vmax) transborda a caixa do
    // link mesmo em posição neutra; sem um ancestral que clipe, o
    // `scrollWidth` do documento estoura em mobile. Clip, NUNCA hidden
    // (não vira scroll container — o sticky do cabeçalho de dia segue
    // funcionando) e este wrapper não é ancestral de TermoTooltip.
    // RITMO: gap-12 = 3rem entre grupos de dia (--ritmo-bloco).
    <div
      ref={raizRef}
      onFocus={aoFocar}
      className="flex flex-col gap-12 [overflow-x:clip]"
    >
      {itens.length === 0 ? (
        // Estado vazio digno (conceito B §8.4): a pedra bruta com a
        // "Aresta que se desenha" (.pedra-404, one-shot 900ms; reduce =
        // contorno completo) + copy do anexo + CTA existente + âncora para
        // os exemplos prontos desta mesma página.
        <div className="flex flex-col items-start gap-4 border border-line bg-card px-6 py-8">
          <svg
            viewBox="405 135 110 85"
            className="h-16 w-auto"
            aria-hidden="true"
            focusable="false"
          >
            <path
              d="M 420 150 L 470 143 L 508 168 L 497 208 L 438 212 L 413 183 Z"
              className="nascimento-pedra-bruta pedra-404"
            />
          </svg>
          <p className="font-sans text-ui text-ink-2">
            Nenhuma tese registrada neste navegador ainda. As que você gerar
            ou abrir aparecem aqui — e ficam só no seu aparelho.
          </p>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <Link
              href="/tese"
              className="flex min-h-11 items-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
            >
              Gerar a primeira tese
            </Link>
            <a
              href="#exemplos-titulo"
              className="sublinhado-brasa inline-block py-1.5 font-sans text-ui text-ink-2 hover:text-ink"
            >
              Ver os exemplos prontos
            </a>
          </div>
        </div>
      ) : (
        <>
          {grupos.map((grupo) => {
            const n = grupo.itens.length;
            return (
              <section
                key={grupo.chave}
                aria-labelledby={`dia-${grupo.chave}`}
                className="flex flex-col gap-3"
              >
                {/* Cabeçalho de dia: linha mono sticky SOB a Tarja
                    (contrato --altura-tarja), horizontal nos DOIS
                    breakpoints — a lombada vertical morreu. bg-page
                    oclui as fichas que rolam por baixo; a talha de ouro
                    (reveal-regua one-shot) abre o dia com o assento
                    pós-fio único de 1.5rem (gap-6). */}
                <div className="sticky top-[var(--altura-tarja)] z-10 flex flex-col gap-6 bg-page py-2">
                  <Reveal
                    variant="reveal-regua"
                    className="talha-capitulo"
                    aria-hidden
                  >
                    {null}
                  </Reveal>
                  <h2
                    id={`dia-${grupo.chave}`}
                    className="font-mono text-meta uppercase tracking-wide text-ink-3"
                  >
                    {`${grupo.rotulo} · ${n} ${n === 1 ? "tese" : "teses"}`}
                  </h2>
                </div>
                {/* RITMO: gap-3 = 0.75rem entre fichas (--ritmo-0). */}
                <ul className="flex flex-col gap-3">
                  {grupo.itens.map((item, indice) => (
                    <li key={item.id}>
                      {/* Fila do Ticker: stagger por posição no grupo do
                          dia, teto .i-6 — ficha 40 não espera 40 passos. */}
                      <Reveal
                        variant="reveal-ticker"
                        className={
                          indice > 0 ? `i-${Math.min(indice, 6)}` : undefined
                        }
                      >
                        {/* A FICHA: card horizontal fino .gema-chip__corpo
                            (bisel + lift, reuso "sem o filho" D14) sobre
                            bg-card. `group` para o "Abrir →" acender no
                            hover/focus DA FICHA (anexo §3). flex-wrap: em
                            375px a ação quebra para a linha de baixo sem
                            estourar a viewport (E3). */}
                        <div className="gema-chip__corpo group flex flex-wrap items-center gap-x-4 gap-y-1 bg-card px-4 py-2">
                          <Link
                            id={`registro-${item.id}`}
                            href={`/tese?id=${encodeURIComponent(item.id)}&ticker=${encodeURIComponent(item.ticker)}`}
                            aria-label={`Abrir a tese de ${item.ticker} (${ROTULO_STATUS[item.status]})`}
                            className={`ticker-luz ${SCROLL_FICHA} flex min-h-11 min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1`}
                          >
                            <span className="font-mono text-ui font-semibold text-ink">
                              {item.ticker}
                            </span>
                            {/* O CARIMBO DE HORA (elemento novo nomeado):
                                "registrada" cobre gerada E aberta —
                                honesto com o criadoEm da lib. */}
                            <span className="font-mono text-meta text-ink-3">
                              registrada às {formatHora(item.criadoEm)}
                            </span>
                            <span
                              className={`font-mono text-meta uppercase tracking-wide ${CLASSE_STATUS[item.status]}`}
                            >
                              {ROTULO_STATUS[item.status]}
                            </span>
                            <span className="sublinhado-brasa ml-auto font-sans text-ui font-semibold text-brasa-texto opacity-0 transition-opacity duration-[var(--dur-tick)] group-hover:opacity-100 group-focus-within:opacity-100">
                              Abrir →
                            </span>
                          </Link>
                          {item.status === "ready" && (
                            <Link
                              href={`/tese?ticker=${encodeURIComponent(item.ticker)}`}
                              aria-label={`Regenerar ${item.ticker}: abre o formulário preenchido — você confirma antes de gerar`}
                              className={`${SCROLL_FICHA} flex min-h-11 items-center gap-2 border border-field px-4 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto`}
                            >
                              <span aria-hidden>↻</span>
                              Regenerar
                            </Link>
                          )}
                          {item.status === "error" && (
                            <Link
                              href={`/tese?ticker=${encodeURIComponent(item.ticker)}`}
                              aria-label={`Tentar de novo com ${item.ticker}: abre o formulário preenchido — você confirma antes de gerar`}
                              className={`${SCROLL_FICHA} flex min-h-11 items-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte`}
                            >
                              Tentar de novo
                            </Link>
                          )}
                        </div>
                      </Reveal>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
          <div className="flex flex-col items-start gap-2">
            <button
              ref={botaoLimparRef}
              type="button"
              onClick={aoClicarLimpar}
              onBlur={aoDesfocarLimpar}
              className="flex min-h-11 w-fit items-center font-sans text-ui text-ink-3 underline underline-offset-4 hover:text-ink"
            >
              {confirmando
                ? "Confirmar limpeza?"
                : "Limpar o registro deste navegador"}
            </button>
            {confirmando && (
              <p className="font-sans text-meta text-ink-2">
                Apaga só a lista deste navegador. As teses prontas da galeria
                continuam onde estão.
              </p>
            )}
          </div>
        </>
      )}
      {/* Região viva PERSISTENTE (existe antes da 1ª mensagem — leitores
          de tela só anunciam mudanças de um live region já montado). */}
      <p role="status" className="sr-only">
        {aviso}
      </p>
    </div>
  );
}
