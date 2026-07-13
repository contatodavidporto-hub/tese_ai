import { LinkCinema } from "@/components/motion/LinkCinema";
import { Marca } from "@/components/site/Marca";

// Missão MATÉRIA VIVA, Onda 1D: toda a nav interna usa <LinkCinema> (véus de
// rota — virada de página do jornal). O LinkCinema é JS puro (classList +
// keyframes de cinema/rotas.css) e preserva o prefetch do next/link.
//
// R2 (LEI — DECISÃO documentada): este Header NÃO importa gsap nem
// useMagnetico em hipótese alguma — magnéticos são exclusivos das ilhas da
// landing (CTAs do hero/faixa final e setas/dots do filmstrip). O CTA
// "Gerar tese" daqui fica SEM física de cursor por padrão, em TODAS as
// rotas (a alternativa "delegação pela ilha da landing" foi descartada
// nesta onda: física parcial por rota custaria acoplamento Header↔ilha e o
// ganho é marginal — o CTA já tem hover de cor próprio). Gate de merge:
// delta ZERO de gsap em /tese; first-load de /tese ≤ +3KB (LinkCinema puro).
//
// Missão APOTEOSE (crit.1): a marca "O Um Lastreado" entra como SVG inline
// (Marca.tsx, Server Component — R2 segue intacta: zero JS novo no Header;
// todo o comportamento vivo é CSS puro em cinema/marca.css). ENTRADA ZERO:
// o selo nasce 100% visível; altura do header NÃO muda (CLS zero — o svg
// 28px cabe no line box de 32px do wordmark text-2xl, ver marca.css).

// Nav canônica (ARQUITETURA.md — mapa de telas): a mesma lista serve o menu
// desktop e o menu mobile abaixo. "/glossario" é contrato da Onda 0 da
// missão APOTEOSE (CHROME linka; a rota nasce na onda COPY).
const NAV = [
  { href: "/como-funciona", label: "Como funciona" },
  { href: "/teses", label: "Teses" },
  { href: "/cobertura", label: "Cobertura" },
  { href: "/glossario", label: "Glossário" },
  { href: "/sobre", label: "Sobre" },
  { href: "/historico", label: "Histórico" },
] as const;

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

// "EDIÇÃO DE 09 JUL 2026" — a data corrente do render server-side (a página
// já é `force-dynamic` pelo CSP com nonce por requisição; não é um dado
// factual do produto, é só o timbre editorial do masthead).
function edicaoDeHoje(): string {
  const agora = new Date();
  const dia = String(agora.getDate()).padStart(2, "0");
  const mes = MESES[agora.getMonth()];
  return `EDIÇÃO DE ${dia} ${mes} ${agora.getFullYear()}`;
}

// Cabeçalho do site: masthead editorial (marca serifada + data da edição em
// mono) + navegação. Sem lib no mobile: <details>/<summary> nativo, sempre
// navegável por teclado, alvo de toque ≥44px (min-h/min-w-11 = 2.75rem).
export function Header() {
  const edicao = edicaoDeHoje();

  return (
    <header className="border-b border-line bg-page">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-4 sm:px-6">
        <div className="flex items-baseline gap-3">
          {/* Lockup da marca (crit.1): selo + wordmark são INSEPARÁVEIS
              (cláusula M-c do guia de uso — "[1]" sozinho leria "nº 1").
              O selo entra INLINE (não flex): preserva a baseline do
              wordmark como referência do items-baseline deste masthead
              (divisor + timbre continuam alinhados como hoje) — detalhe
              documentado em cinema/marca.css. */}
          <LinkCinema
            href="/"
            className="marca-lockup font-display text-2xl font-semibold tracking-tight text-ink"
          >
            <Marca />
            Tese AI
          </LinkCinema>
          <span aria-hidden className="hidden h-4 w-px bg-line-strong sm:inline-block" />
          <span className="hidden font-mono text-meta tracking-wide text-ink-3 sm:inline">
            {edicao}
          </span>
        </div>

        {/* Nav desktop */}
        <nav aria-label="Principal" className="hidden items-center gap-6 md:flex">
          {/* A3 (alvo ≥24px, WCAG 2.5.8): piso py-1.5 + inline-block — a caixa
              clicável de um link de texto sem padding vertical media 19.6px. */}
          {NAV.map((item) => (
            <LinkCinema
              key={item.href}
              href={item.href}
              className="sublinhado-brasa inline-block py-1.5 font-sans text-ui text-ink-2 hover:text-ink"
            >
              {item.label}
            </LinkCinema>
          ))}
          {/* CTA sem física (R2, decisão documentada acima); destino /tese
              faz push direto no LinkCinema (sem véu — .virada-edicao é o véu
              especializado da rota). */}
          <LinkCinema
            href="/tese"
            className="bg-brasa px-4 py-2 font-sans text-ui font-semibold text-sobre-brasa transition-colors duration-[var(--dur-tick)] hover:bg-brasa-forte"
          >
            Gerar tese
          </LinkCinema>
        </nav>

        {/* Nav mobile: details/summary nativo (sem JS, sem lib) */}
        <details className="group md:hidden">
          {/* `.menu-mobile-resumo` (item 6, §6 M6 — propagação Onda 1): hairline
              que "imprime" sob o summary quando o menu abre (globals.css). */}
          <summary
            aria-label="Abrir menu de navegação"
            className="menu-mobile-resumo flex min-h-11 min-w-11 cursor-pointer list-none items-center justify-center gap-1 border border-line-strong px-3 py-2 font-sans text-ui text-ink [&::-webkit-details-marker]:hidden"
          >
            <span className="group-open:hidden">Menu</span>
            <span className="hidden group-open:inline">Fechar</span>
          </summary>
          <nav aria-label="Principal (mobile)" className="flex flex-col gap-1 border-t border-line pb-3 pt-2">
            {NAV.map((item) => (
              <LinkCinema
                key={item.href}
                href={item.href}
                className="flex min-h-11 items-center px-1 font-sans text-ui text-ink-2 hover:text-ink"
              >
                {item.label}
              </LinkCinema>
            ))}
            <LinkCinema
              href="/tese"
              className="mt-1 flex min-h-11 items-center justify-center bg-brasa px-4 font-sans text-ui font-semibold text-sobre-brasa"
            >
              Gerar tese
            </LinkCinema>
          </nav>
        </details>
      </div>
      <div className="h-px bg-line-strong" aria-hidden />
    </header>
  );
}
