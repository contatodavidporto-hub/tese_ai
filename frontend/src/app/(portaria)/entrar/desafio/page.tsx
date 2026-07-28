import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";

import { Masthead } from "../../_ui";

// Passo de verificação em dois fatores (2FA TOTP). Na Onda 2 ninguém tem fator
// VERIFICADO, então o login nunca cai aqui — esta página nasce completa (formulário
// de código + códigos de recuperação) na Onda 3. Placeholder honesto até lá.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Verificação em dois fatores",
  description: "Confirme o código do seu app autenticador.",
};

export default function DesafioPage() {
  return (
    <section aria-labelledby="desafio-titulo">
      <Masthead
        tituloId="desafio-titulo"
        titulo="Verificação em dois fatores"
        sub="A verificação em dois fatores ainda está sendo habilitada. Se você chegou aqui, entre novamente."
      />
      <p className="mt-8 text-ui text-ink-2">
        <LinkCinema href="/entrar" className="sublinhado-brasa font-semibold text-brasa-texto">
          Voltar ao login
        </LinkCinema>
      </p>
    </section>
  );
}
