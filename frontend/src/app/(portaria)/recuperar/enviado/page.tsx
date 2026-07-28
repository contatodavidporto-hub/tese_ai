import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";

import { Masthead } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Link enviado",
  description: "Confira seu e-mail para redefinir a senha.",
};

export default function RecuperarEnviadoPage() {
  return (
    <section aria-labelledby="enviado-titulo">
      <Masthead
        tituloId="enviado-titulo"
        titulo="Confira seu e-mail"
        sub="Se houver uma conta com esse e-mail, enviamos um link para redefinir a senha. O link expira em breve — abra-o no mesmo dispositivo, se puder."
      />
      <p className="mt-8 text-ui text-ink-2">
        Não chegou?{" "}
        <LinkCinema href="/recuperar" className="sublinhado-brasa font-semibold text-brasa-texto">
          Pedir outro link
        </LinkCinema>
      </p>
    </section>
  );
}
