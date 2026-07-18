import Link from "next/link";

import { Reveal } from "@/components/motion/Reveal";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { exemplosProntos } from "@/lib/tickers";
import { HistoricoClient } from "./HistoricoClient";

// Dinâmica pelo CSP com nonce por requisição (src/proxy.ts).
export const dynamic = "force-dynamic";

// Copy CONGELADA (missão OURIVESARIA, .maestro/copy-ourivesaria.md §3 —
// transcrição byte-fiel, §7-E5): o `title` é o do anexo; a description
// REUSA a linha-fina do masthead (zero redação nova — a string é a mesma
// do anexo, nenhuma palavra fora dele).
export const metadata = {
  title: "Seu registro de teses",
  description:
    "As teses que você gerou ou abriu neste navegador — ficam só aqui, no seu aparelho. Nada sobe para servidor.",
};

// MISSÃO OURIVESARIA — raia 2D (crit. 9 · §3-C9 · §7-E9/F6 · conceito B §8):
// a Hemeroteca vira "REGISTRO DE BANCADA" — página reconstruída do zero
// (as lombadas verticais da Horizonte morreram em HistoricoClient.tsx).
// Este arquivo é só o masthead + moldura da rota:
//   - masthead autoexplicativo em 5s: eyebrow mono "Registro de bancada" +
//     talha de ouro (mastheads padronizados da 1A) + H1 + linha-fina que
//     DIZ a função ("ficam só aqui, no seu aparelho");
//   - a lista inteira (fichas por dia, ações, vazio, limpeza em 2 tempos)
//     vive em HistoricoClient.tsx (client — localStorage);
//   - seção "Teses de exemplo": BYTE-IDÊNTICA à da 1A (fora do redesenho;
//     é o destino do link "Ver os exemplos prontos" do estado vazio, via
//     âncora #exemplos-titulo — [id]{scroll-margin-top} global cobre o
//     salto sob a Tarja).
// RITMO (escala congelada 0.5): py-14 = 3.5rem contra Header/Footer
// (--ritmo-capitulo), gap-y-12 = 3rem entre blocos (--ritmo-bloco),
// gap-6 = assento/pós-fio único 1.5rem no masthead. ZERO folha CSS nova
// nesta raia — Tailwind + primitivas existentes (talha-capitulo,
// gema-chip, reveal-ticker, pedra-404).
//
// MISSÃO ARREMATE — raia G (arbitragem do maestro, 2026-07-18): a
// primitiva TICKER-LUZ saiu desta lista (era o último `.ticker-luz` da
// rota — ver o bloco dos exemplos, abaixo). O inventário de efeitos de
// /historico encolheu de novo e não cresceu em nada ⇒ ZERO registro
// nominal novo a fazer em bloco `prefers-reduced-motion` de folha
// nenhuma; a folha `cinema/ticker-luz.css` fica BYTE-IDÊNTICA (é
// blindada e compartilhada com /banca, /tese e TickerCombobox).
export default function HistoricoPage() {
  const exemplos = exemplosProntos();

  return (
    <>
      <Header />
      <main id="conteudo" className="bancada flex-1 gap-y-12 py-14">
        <div className="flex flex-col gap-6">
          <Reveal>
            <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
              Registro de bancada
            </p>
          </Reveal>
          <Reveal variant="reveal-regua" className="talha-capitulo" aria-hidden>
            {null}
          </Reveal>
          <Reveal className="i-1">
            <h1 className="font-display text-h1 font-semibold tracking-tight text-ink">
              Seu registro de teses
            </h1>
          </Reveal>
          <Reveal className="i-2">
            <p className="font-sans text-ui leading-relaxed text-ink-2">
              As teses que você gerou ou abriu neste navegador — ficam só
              aqui, no seu aparelho. Nada sobe para servidor.
            </p>
          </Reveal>
          {/* ARREMATE/raia C — CARIMBO DA FOLHA. Copy NOVA (não estava no
              anexo da OURIVESARIA): diz em registro mono os dois fatos que
              a página nunca contou e que respondem ao "eu quero entender o
              que aconteceu??" — que a retenção é PARCIAL (só as mais
              recentes) e que é REVERSÍVEL. Mesmo registro tipográfico do
              eyebrow acima e dos cabeçalhos de dia: o propósito se resolve
              por REPETIÇÃO DE REGISTRO, não por caixa/ícone novos.

              ARREMATE/raia G (arbitragem do maestro, 2026-07-18) — O NÚMERO
              SAIU. A linha nasceu como "Guarda as 50 mais recentes · você
              pode apagar tudo". O "50" é a constante `LIMITE`
              (lib/historico.ts:15), que a lib NÃO exporta e que este arquivo
              não tem como ler: era um número TRANSCRITO À MÃO. No dia em que
              alguém mexer no `LIMITE`, esta linha passa a MENTIR em
              produção, sem teste, sem tipo e sem gate que perceba — e o 1º
              princípio do projeto é "nunca inventar dado; todo número com
              fonte". A intenção fica inteira sem o algarismo: "as mais
              recentes" continua verdadeiro para QUALQUER valor de `LIMITE`
              (a lib prepende e corta a cauda), e "você pode apagar tudo"
              continua sendo o botão de limpeza do rodapé da folha. As 12
              strings CONGELADAS do anexo não foram tocadas — esta não é uma
              delas (nasceu na raia C, ARREMATE). */}
          <Reveal className="i-3">
            <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">
              Guarda as mais recentes · você pode apagar tudo
            </p>
          </Reveal>
        </div>

        {/* E30 (correção-mãe): o registro é LISTA (fichas por dia), não
            prosa — `.b-palco` (as duas trilhas) mantém a paridade de
            largura com a produção (nunca mais estreito). O H1 acima já
            nomeia a região; os cabeçalhos de dia (h2 nas fichas) fazem a
            hierarquia — a seção não precisa de heading próprio. */}
        <section className="b-palco">
          <HistoricoClient />
        </section>

        {/* COSTURA 1A (intocada pela 2D): talha de ouro + respiro no lugar
            do border-t; gap-6 = pós-fio único 1.5rem. */}
        <section
          aria-labelledby="exemplos-titulo"
          className="b-palco flex flex-col gap-6"
        >
          <Reveal variant="reveal-regua" className="talha-capitulo" aria-hidden>
            {null}
          </Reveal>
          <Reveal className="i-1">
            <h2
              id="exemplos-titulo"
              className="font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3"
            >
              Teses de exemplo
            </h2>
          </Reveal>
          <Reveal className="i-2">
            <p className="max-w-2xl font-sans text-ui text-ink-2">
              Pré-geradas para os maiores pesos do Ibovespa e para os exemplos
              multiativo — um FII e um título do Tesouro Direto. Abrem na
              hora, sem entrar no seu histórico.
            </p>
          </Reveal>
          {/* A3 (alvo ≥24px, WCAG 2.5.8): piso PY-1.5 + INLINE-BLOCK.
              Destino /tese = bypass do LinkCinema de qualquer forma (véu
              especializado mora lá) — <Link> puro.

              ARREMATE/raia G (arbitragem do maestro, 2026-07-18) — O GLOW
              QUE SOBROU MORRE AQUI. A raia anterior tirou `ticker-luz` das
              FICHAS (o <Link> de HistoricoClient.tsx:487) mas MANTEVE nestes
              13 links, por dois motivos que a medição derrubou:
                (a) o ::after de `.ticker-luz` (cinema/ticker-luz.css:66-89)
                    é um radial de 46VMAX sempre ACESO sob
                    @media (hover:hover) and (pointer:fine) — não depende de
                    :hover. Medido em contexto NORMAL a 1440x900, ESTADO
                    VAZIO: 13 pseudo-elementos de 662px, opacity 1, na zona
                    inferior da tela. É EXATAMENTE o brilho quente que o
                    dono fotografou e mandou matar — a tela dele continuava
                    acesa depois da raia anterior;
                (b) supunha-se que a parte G do gate exigia um `a.ticker-luz`
                    no documento. Ela roda INTEIRA sob reduced_motion=reduce,
                    onde a folha faz `display:none !important` para TODA
                    instância: medido 0 sprites sob reduce, inclusive no
                    baseline :3010. A dependência era ILUSÓRIA. O gate foi
                    trocado por prova POSITIVA que roda nos DOIS modos
                    (gate_2d_hemeroteca.py, parte G).
              A folha continua PROIBIDA de ser editada (blindada, dividida
              com /banca, /tese e TickerCombobox): só a CLASSE sai.

              CASCATA 1 — o `[OVERFLOW-X:CLIP]` deste <ul> saiu junto. Ele
              existia SÓ para conter o sprite de 46VMAX, que transbordava a
              caixa do <a> mesmo em repouso e estourava o `scrollWidth` do
              documento em mobile. Sem NENHUM `.ticker-luz` na rota ele fica
              órfão. PROVADO antes de remover: scrollWidth - clientWidth = 0
              em 320/375/390/768/1024/1440, nos DOIS estados (vazio e com
              fichas), ANTES e DEPOIS (sonda_g_glow.py). O nome da utility
              vai em MAIÚSCULA neste comentário de propósito: em minúscula o
              scanner do Tailwind o recompilaria para o CSS a partir do
              próprio comentário, e a regra órfã sobreviveria à remoção.

              CASCATA 2 — o <ul> era um `GradeFoco` (ilha client que delega
              --mx/--my ao alvo sob o ponteiro). Com `seletorAlvo=
              ".ticker-luz"` sem nenhum alvo no documento, sobrava um
              componente client e 3 listeners de ponteiro fazendo `closest()`
              a cada movimento para achar sempre null. Vira <ul> puro: DOM
              byte-idêntico (GradeFoco.tsx:30 renderiza `<ul ref className>`),
              a página inteira volta a ser server-rendered e some uma ilha.
              GradeFoco.tsx NÃO foi tocado — /teses e GaleriaBanca seguem
              donos dele. */}
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            {exemplos.map((papel) => (
              <li key={papel.ticker}>
                <Link
                  href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
                  className="sublinhado-brasa inline-block py-1.5 font-mono text-ui text-ink-2 hover:text-ink"
                >
                  {papel.ticker}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <Footer />
    </>
  );
}
