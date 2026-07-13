import type { Metadata, Viewport } from "next";
import { Archivo, IBM_Plex_Mono, Newsreader } from "next/font/google";
import "./globals.css";

import { VeuRotas } from "@/components/motion/VeuRotas";
import { Tarja } from "@/components/site/Tarja";

// Fontes self-hosted pelo next/font (baixadas no build): nada de request
// externo em runtime — compatível com o CSP `font-src 'self'` (src/proxy.ts).
//
// Newsreader e Archivo são fontes variáveis: carregamos o eixo `wght` inteiro
// (sem restringir `weight`) + o eixo extra próprio de cada família via `axes`
// — `opsz` (optical size) no Newsreader, `wdth` (largura) no Archivo. Isso
// também habilita o "opsz alto no título / opsz 16 no corpo" do brief de
// graça: `font-optical-sizing: auto` é o padrão do navegador e liga o opsz
// ao tamanho de fonte usado, sem CSS extra. IBM Plex Mono não é variável —
// pesos discretos (400/500/600), sempre com `font-variant-numeric:
// tabular-nums` (ver globals.css, regra `.font-mono`).
//
// P1 (CORRECOES-RODADA-1.md): só o estilo "normal" aqui — o itálico (147 kB)
// virou uma segunda instância (src/lib/fontes.ts), preloadada só nas rotas
// que renderizam itálico de verdade (/tese, /como-funciona), não em toda
// página via este layout raiz.
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  style: ["normal"],
  axes: ["opsz"],
  display: "swap",
});

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Tese AI — Teses de investimento auditáveis",
    template: "%s — Tese AI",
  },
  description:
    "Teses de investimento estruturadas e rastreáveis: fundamentos + macro + pares globais + geopolítica, com cada afirmação ligada à sua fonte. Não é recomendação de investimento.",
  applicationName: "Tese AI",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f6f3" },
    { media: "(prefers-color-scheme: dark)", color: "#101216" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${newsreader.variable} ${archivo.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-page text-ink">
        {/* Skip link (WCAG 2.4.1): primeiro item focável, visível só com foco. */}
        <a
          href="#conteudo"
          className="sr-only z-[60] bg-brasa px-4 py-2 text-sm font-semibold text-sobre-brasa focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
        >
          Pular para o conteúdo
        </a>
        {/* Tarja regulatória SEMPRE visível (postura CVM) — fixa em toda página. */}
        <Tarja />
        {children}
        {/* Véu de SAÍDA de rota (missão MATÉRIA VIVA, Onda 1D — R3): overlay
            decorativo fixo z-40, SEMPRE abaixo da Tarja (z-50) e da régua
            (z-55). Irmão direto do body (nunca wrapper — trava C2). Quem o
            liga é o LinkCinema (classList + keyframe em cinema/rotas.css);
            quem o desarma a cada troca de rota é o <VeuRotas /> abaixo.
            ZERO gsap neste arquivo (R2 — delta zero de gsap em /tese). */}
        <div id="veu-rota-saida" aria-hidden="true" />
        <VeuRotas />
      </body>
    </html>
  );
}
