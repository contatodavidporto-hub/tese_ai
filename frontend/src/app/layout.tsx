import type { Metadata, Viewport } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { Tarja } from "@/components/site/Tarja";

// Fontes self-hosted pelo next/font (baixadas no build): nada de request externo
// em runtime — compatível com o CSP `font-src 'self'` (src/proxy.ts).
const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
});

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
    { media: "(prefers-color-scheme: light)", color: "#f6f4ee" },
    { media: "(prefers-color-scheme: dark)", color: "#101513" },
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
      className={`${fraunces.variable} ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-papel text-tinta">
        {/* Skip link (WCAG 2.4.1): primeiro item focável, visível só com foco. */}
        <a
          href="#conteudo"
          className="sr-only z-[60] rounded-lg bg-selo px-4 py-2 text-sm font-semibold text-sobre-selo focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
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
