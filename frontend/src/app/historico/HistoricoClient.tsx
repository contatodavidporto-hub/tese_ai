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
// MISSÃO ARREMATE — raia C (defeito 4 do dono: "que fique certo, bonito,
// harmônico e sem essa porra de iluminação ridícula"). Conceito vencedor
// do conselho (2/3): **FOLHA DE BANCADA** — a lista deixa de ser uma pilha
// de cartões ACESOS e vira uma folha PAUTADA. O que substitui a decoração
// é ALINHAMENTO, não outro efeito:
//   1. O HALO MORRE NA FICHA (R5 do plano-arremate). `.ticker-luz::after`
//      é um radial de 46vmax (cinema/ticker-luz.css:66-89) sempre aceso
//      sob `@media (hover:hover) and (pointer:fine)` — não depende de
//      `:hover`. A folha é BLINDADA e compartilhada com /banca, /tese e
//      TickerCombobox: proibido editá-la. Mata-se tirando a STRING
//      `ticker-luz` do <Link> da ficha (era :371) — e só. Em cascata saem
//      o `usePonteiro` (que alimentava --mx/--my) e o clip do wrapper, que
//      existia SÓ para conter o sprite.
//      ARREMATE/raia G (arbitragem do maestro, 2026-07-18) — CORREÇÃO DO
//      RULING R5: a raia C manteve a classe nos 13 links de "Teses de
//      exemplo" (page.tsx) porque o recon dizia que a parte G do gate
//      exigia um `a.ticker-luz` no documento. Duas medições derrubaram
//      isso: (a) no ESTADO VAZIO a rota ainda tinha 13 sprites de 46vmax
//      ACESOS (662px, opacity 1, a 1440x900, contexto normal) na zona
//      inferior da tela — ou seja, a tela que o dono fotografou continuou
//      acesa depois da raia C; (b) a parte G roda inteira sob
//      reduced_motion=reduce, onde o ::after é display:none para TODA
//      instância — ela media 0 sprite mesmo no baseline :3010, e a
//      dependência era ILUSÓRIA. Agora a rota tem ZERO `.ticker-luz`, o
//      clip gêmeo saiu com ele e o gate passou a provar isso pelo
//      POSITIVO, nos dois modos (gate_2d_hemeroteca.py, parte G).
//   2. COLUNAS EM `ch` sobre as spans mono: o carimbo começa no mesmo x em
//      TODAS as fichas, e a ação encerra a linha num prumo único. É isso
//      que responde ao "eu quero entender o que aconteceu??".
//   3. A BRASA SAI DO CASO NORMAL: status "pronta" desce para ink-3 (ver
//      CLASSE_STATUS) — 40 rótulos laranja numa lista de 50 linhas é o
//      ruído que lê como decoração.
//
// MOVIMENTO (2.2.2 — nada contínuo; ZERO efeito novo, zero folha nova):
//   - entrada = Fila do Ticker (`reveal-ticker` + stagger .i-N teto 6 por
//     posição no dia) — one-shot do motor Reveal (reduce já coberto lá);
//   - talha de ouro (`talha-capitulo` + `reveal-regua`) abre cada dia —
//     one-shot, registro nominal na bancada.css (1A);
//   - relevo = `.gema-chip__corpo` + `.gema-chip--recuo` (gema.css:142-153):
//     ficam as 4 keylines inset de 1px e o lift de 2px (regra separada,
//     gema.css:121-126); morrem `--gema-elevacao` e a sombra de hover
//     `0 18px 36px` — a ficha para de levitar como cartão. RESSALVA: a
//     classe está DOCUMENTADA em gema.css:142-144 como recuo binário S4 de
//     reprovação AA por pixel; aqui é reuso deliberado pelo EFEITO (sobriedade),
//     não sinal de que a AA falhou nesta rota. Registrado no relatório.
//   - estado vazio = contorno bruto com `.pedra-404` (dash-draw one-shot
//     900ms, dona: lapidacao.css; reduce = contorno completo estático). O
//     `d` do path é DUPLICADO de not-found.tsx de propósito (pegadinha
//     3/D18: importar CenaNascimento aqui embarcaria a cena inteira; a
//     classe já é global via lapidacao.css — CSS pago).
//
// O INVENTÁRIO DE EFEITOS DA ROTA ENCOLHE EM UM (o sprite `.ticker-luz`
// some da ficha) e não cresce em nenhum ⇒ ZERO registro nominal novo a
// fazer em bloco `prefers-reduced-motion` de folha nenhuma.

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { Reveal } from "@/components/motion/Reveal";
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

// Cor do status segue a hierarquia do design system: "processando" usa o
// par aviso; "falhou" usa o par erro (falha técnica) — nunca o inverso.
const CLASSE_STATUS: Record<ItemHistorico["status"], string> = {
  // ARREMATE/raia C: "pronta" é o caso NORMAL da folha e desce de
  // `brasa-texto` para `ink-3` — quieto. Numa lista de até 50 linhas, 40
  // rótulos laranja gritando o caso normal é exatamente o ruído que o
  // dono lê como decoração, e fere o guard-rail "brasa em <5% da
  // superfície, sempre com significado". A brasa fica reservada ao que é
  // ACIONÁVEL ("Abrir →", "Tentar de novo"). ZERO token novo: ink-3 já é
  // o tom do carimbo de hora e do cabeçalho de dia.
  // RECUO PRÉ-REGISTRADO (conselho, ordem fixa): se "pronta" sumir demais
  // ao olho, sobe UM degrau para `text-ink-2` — NUNCA de volta à brasa.
  ready: "text-ink-3",
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

// ---- AS COLUNAS DA FOLHA (ARREMATE/raia C) ---------------------------
// O alinhamento é feito em `ch` NA PRÓPRIA span, nunca em trilhas de um
// wrapper: as 4 spans TÊM que continuar filhas DIRETAS do <Link> porque o
// gate lê `span:nth-child(1|2|3)` na parte A (gate_2d_hemeroteca.py:138-140)
// e na parte E (:525-529) — envolver qualquer par num nó de layout reprova
// as duas de uma vez. Como a fonte é MONO, `Nch` são N avanços exatos e o
// alinhamento entre fichas cai para 0px sem subgrid e sem folha nova.
//   · 13ch no papel: maior ticker aceito por TICKER_RE/TD_GRAMATICA
//     (lib/tickers.ts:166-167) é `TD-IPCAJ-2035` = 13 caracteres (a
//     gramática admite siglas de 5 letras: IPCAJ/IGPMJ/RENDA/EDUCA/SELIC).
//     Se a gramática crescer, RE-MEDIR esta constante.
//   · 19ch no carimbo: "registrada às HH:MM" tem sempre 19 caracteres.
//   · 12ch na situação: "processando" (11) + `tracking-wide` (0.025em)
//     cabe com folga em 12 avanços.
// Só a partir de `sm:`: abaixo de 640px a linha quebra e quem manda é o
// flex-wrap — coluna fixa em 375px seria mentira geométrica.
const COL_PAPEL = "sm:w-[13ch] sm:shrink-0";
const COL_CARIMBO = "sm:w-[19ch] sm:shrink-0";
const COL_SITUACAO = "sm:w-[12ch] sm:shrink-0";
// A 5a coluna (a ação) fecha a folha do lado direito: largura FIXA igual
// para "Regenerar" e "Tentar de novo" ⇒ como o <Link> irmão é `flex-1` e
// absorve a sobra, as bordas ESQUERDAS das duas ações caem no MESMO x em
// todas as fichas — não só as direitas. Ficha `processando` deixa a coluna
// vazia e alinhada, que é informação, não buraco.
const COL_ACAO = "sm:w-40 sm:justify-center";

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

  // ARREMATE/raia C: a delegação `usePonteiro` (1 listener passivo +
  // escrita de --mx/--my a cada quadro) morreu JUNTO com o sprite — ela
  // existia só para mover o halo de 46vmax sob o ponteiro. Sem
  // `.ticker-luz` na ficha não há o que mover: hook, ref e listener saem.

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
    // ARREMATE/raia C — acha o cabeçalho por PROPRIEDADE, não por POSIÇÃO.
    // Com `secao.firstElementChild`, qualquer nó inserido antes do
    // cabeçalho dentro da <section> fazia esta correção 2.4.11 morrer em
    // SILÊNCIO (early return sem erro e sem rastro) e só a parte D do gate,
    // a 375px, reprovaria. Buscar o primeiro filho com `position: sticky`
    // desarma a armadilha: a <section> tem 2 filhos, custo desprezível.
    // (O `div.sticky` CONTINUA sendo o primeiro filho — não insira nada
    // antes dele: `main section > div.sticky` é alvo do gate D.)
    const cabecalho = Array.from(secao?.children ?? []).find(
      (n) => n instanceof HTMLElement && getComputedStyle(n).position === "sticky",
    );
    if (!(cabecalho instanceof HTMLElement)) return;
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
    // ARREMATE/raia C: o `[OVERFLOW-X:CLIP]` que existia AQUI saiu junto
    // com o sprite. Ele foi posto (§7-F5) porque cada ficha era
    // `.ticker-luz` e o `::after` de 46vmax transbordava a caixa do link
    // mesmo em repouso, estourando o `scrollWidth` do documento em mobile.
    // Sem a classe na ficha não há o que clipar: `box-shadow` e o lift de
    // 2px não contribuem para `scrollWidth`.
    // ARREMATE/raia G (arbitragem do maestro, 2026-07-18): o clip GÊMEO da
    // lista de exemplos TAMBÉM caiu (page.tsx) — os 13 links perderam
    // `.ticker-luz` e a rota inteira ficou sem um único sprite. Prova de
    // que a remoção era segura: scrollWidth - clientWidth = 0 em
    // 320/375/390/768/1024/1440, nos dois estados, antes E depois
    // (.maestro/ferramentas/sonda_g_glow.py).
    // O NOME DA UTILITY VAI EM MAIÚSCULA de propósito: em minúscula, o
    // scanner do Tailwind lê ESTE COMENTÁRIO como uso e recompila
    // `.\[overflow-x\:clip\]` para dentro do CSS de produção — a regra que
    // acabamos de remover voltaria pela porta dos fundos. Conferido no
    // bundle depois do build: zero ocorrências do seletor.
    // RITMO: gap-12 = 3rem entre grupos de dia (--ritmo-bloco).
    <div onFocus={aoFocar} className="flex flex-col gap-12">
      {itens.length === 0 ? (
        // Estado vazio digno (conceito B §8.4): a pedra bruta com a
        // "Aresta que se desenha" (.pedra-404, one-shot 900ms; reduce =
        // contorno completo) + copy do anexo + CTA existente + âncora para
        // os exemplos prontos desta mesma página.
        // ARREMATE/raia C: o hairline cinza (`border border-line`) MORREU —
        // a diferença de MATERIAL (bg-card sobre bg-page) já é a fronteira,
        // e a keyline passa a ser a MESMA das fichas (`.gema-chip__corpo`
        // + `.gema-chip--recuo`: 4 insets de 1px, sem elevação). O vazio
        // deixa de ser uma caixa cinza estranha e entra na linguagem da
        // folha. `data-registro-vazio` é ÂNCORA DE CONTRATO para o gate:
        // hoje a parte A ancora por `.pedra-404.closest('div')` (acidente —
        // qualquer wrapper futuro faria cta/secundário/texto virarem null
        // EM SILÊNCIO). O atributo é aditivo: não quebra a âncora atual.
        // ARMADILHA: o <svg> tem que continuar FILHO DIRETO deste div.
        <div
          data-registro-vazio
          className="gema-chip__corpo gema-chip--recuo flex flex-col items-start gap-6 bg-card p-6"
        >
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
          {/* Medida de linha: 56ch é contenção editorial (o parágrafo não
              corre a largura inteira do palco). A copy é CONGELADA e não
              muda um byte — só a caixa que a contém. */}
          <p className="max-w-[56ch] font-sans text-ui leading-relaxed text-ink-2">
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
                {/* ARREMATE/raia C: `pl-4` casa com o `px-4` da ficha —
                    talha, data e a coluna do papel passam a nascer no
                    MESMO prumo. É a margem do caderno feita de
                    ALINHAMENTO, sem gastar um pixel de tinta (hairline
                    está banido de qualquer forma). Padding-left não muda
                    `offsetHeight`, então a reserva de 4.5rem do
                    SCROLL_FICHA continua válida sem re-medição. */}
                <div className="sticky top-[var(--altura-tarja)] z-10 flex flex-col gap-6 bg-page py-2 pl-4">
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
                        {/* A FICHA: banda horizontal fina .gema-chip__corpo
                            + .gema-chip--recuo (4 keylines inset de 1px,
                            SEM elevação — para de levitar; o lift de 2px
                            no hover sobrevive por ser regra separada,
                            gema.css:121-126) sobre bg-card. `group` para o
                            "Abrir →" acender no hover/focus DA FICHA
                            (anexo §3). A goteira sobe de 1rem para 1.5rem
                            (--ritmo-assento): a densidade vem da altura da
                            linha, o ar vem do vão horizontal. flex-wrap:
                            em 375px a ação quebra para a linha de baixo
                            sem estourar a viewport (E3). */}
                        <div className="gema-chip__corpo gema-chip--recuo group flex flex-wrap items-center gap-x-6 gap-y-1 bg-card px-4 py-2">
                          {/* VETO GRAVADO (não "limpe" este markup depois):
                              `display:contents` neste <a> zeraria a caixa
                              do link, mataria o anel de foco e faria o
                              getBoundingClientRect do activeElement voltar
                              0x0 — a parte D do gate passaria POR
                              VACUIDADE, com a acessibilidade quebrada. */}
                          <Link
                            id={`registro-${item.id}`}
                            href={`/tese?id=${encodeURIComponent(item.id)}&ticker=${encodeURIComponent(item.ticker)}`}
                            aria-label={`Abrir a tese de ${item.ticker} (${ROTULO_STATUS[item.status]})`}
                            className={`${SCROLL_FICHA} flex min-h-11 min-w-0 flex-1 flex-wrap items-center gap-x-6 gap-y-1`}
                          >
                            <span
                              className={`whitespace-nowrap font-mono text-ui font-semibold text-ink ${COL_PAPEL}`}
                            >
                              {item.ticker}
                            </span>
                            {/* O CARIMBO DE HORA (elemento novo nomeado):
                                "registrada" cobre gerada E aberta —
                                honesto com o criadoEm da lib. */}
                            <span
                              className={`whitespace-nowrap font-mono text-meta text-ink-3 ${COL_CARIMBO}`}
                            >
                              registrada às {formatHora(item.criadoEm)}
                            </span>
                            <span
                              className={`whitespace-nowrap font-mono text-meta uppercase tracking-wide ${COL_SITUACAO} ${CLASSE_STATUS[item.status]}`}
                            >
                              {ROTULO_STATUS[item.status]}
                            </span>
                            {/* `ml-auto` só ABAIXO de sm:. A partir de sm:
                                o "Abrir →" ancora logo após a coluna da
                                situação (`sm:ml-0`) — assim ele cai no
                                MESMO x em toda ficha, inclusive na
                                `processando` (que não tem ação irmã para
                                empurrá-lo). Só `opacity` transita: zero
                                deslocamento de layout, zero CLS. */}
                            <span className="sublinhado-brasa ml-auto font-sans text-ui font-semibold text-brasa-texto opacity-0 transition-opacity duration-[var(--dur-tick)] group-hover:opacity-100 group-focus-within:opacity-100 sm:ml-0">
                              Abrir →
                            </span>
                          </Link>
                          {item.status === "ready" && (
                            <Link
                              href={`/tese?ticker=${encodeURIComponent(item.ticker)}`}
                              aria-label={`Regenerar ${item.ticker}: abre o formulário preenchido — você confirma antes de gerar`}
                              className={`${SCROLL_FICHA} ${COL_ACAO} flex min-h-11 items-center gap-2 border border-field px-4 font-sans text-ui font-medium text-ink transition-colors duration-[var(--dur-tick)] hover:border-brasa-texto`}
                            >
                              <span aria-hidden>↻</span>
                              Regenerar
                            </Link>
                          )}
                          {item.status === "error" && (
                            <Link
                              href={`/tese?ticker=${encodeURIComponent(item.ticker)}`}
                              aria-label={`Tentar de novo com ${item.ticker}: abre o formulário preenchido — você confirma antes de gerar`}
                              className={`${SCROLL_FICHA} ${COL_ACAO} flex min-h-11 items-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte`}
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
          {/* Rodapé da folha: `pl-4` fecha a mesma margem de alinhamento
              do cabeçalho de dia e do `px-4` das fichas. */}
          <div className="flex flex-col items-start gap-2 pl-4">
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
          de tela só anunciam mudanças de um live region já montado).
          ARMADILHA GRAVADA: este <p> fica FORA do ternário vazio/lista. Se
          alguém o mover para dentro do ramo da lista, ele DESMONTA no
          instante em que o registro é limpo e a MSG_LIMPO nunca é
          anunciada — a parte C(c) do gate reprova. */}
      <p role="status" className="sr-only">
        {aviso}
      </p>
    </div>
  );
}
