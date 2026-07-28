import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Recuperar senha",
  description: "Receba um link para redefinir a senha da sua conta do Tese AI.",
};

const ERROS: Record<string, string> = {
  link: "Link inválido. Peça um novo abaixo.",
  expirado: "O link expirou. Peça um novo abaixo.",
  troca: "Não foi possível trocar a senha. Tente novamente.",
};

export default async function RecuperarPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const erro = typeof sp.erro === "string" ? ERROS[sp.erro] : undefined;

  return (
    <section aria-labelledby="recuperar-titulo">
      <Masthead
        tituloId="recuperar-titulo"
        titulo="Recuperar senha"
        sub="Informe seu e-mail. Se houver uma conta, enviaremos um link para redefinir a senha."
      />
      <Mensagem texto={erro} />

      <form method="post" action="/api/auth/recuperar" className="mt-4 flex flex-col gap-6">
        <Campo id="email" name="email" label="E-mail" type="email" autoComplete="email" />
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Enviar link
        </button>
      </form>

      <p className="mt-8 text-ui text-ink-2">
        Lembrou a senha?{" "}
        <LinkCinema href="/entrar" className="sublinhado-brasa font-semibold text-brasa-texto">
          Entrar
        </LinkCinema>
      </p>
    </section>
  );
}
