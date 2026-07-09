import type { Metadata, Viewport } from "next";
import { Archivo, IBM_Plex_Mono, Newsreader } from "next/font/google";
import "./globals.css";

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
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  style: ["normal", "italic"],
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
      </body>
    </html>
  );
}
