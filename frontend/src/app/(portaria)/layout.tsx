import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";

// Layout do grupo (portaria) — telas de conta (missão "A Portaria", Onda 2).
// Nascem DENTRO do sistema visual: mesmo Header/Footer/Tarja, tokens e ritmo. Forms
// nativos server-rendered (PRG POST→303→GET): funcionam com zero JS, sobrevivem a
// chunk falho, rede ruim e botão voltar. Coluna estreita e centrada (medida de
// formulário), ritmo --ritmo-* nos vãos. Zero conectoras, zero glow (regra de ferro).
export default function PortariaLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        <div className="mx-auto w-full max-w-md px-4 py-16 sm:px-6 sm:py-24">{children}</div>
      </main>
      <Footer
        saudeSlot={
          <Suspense fallback={<ChipSaude />}>
            <ChipSaudeAoVivo />
          </Suspense>
        }
      />
    </>
  );
}
