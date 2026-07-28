import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { sessaoAtual } from "@/lib/auth/sessao";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Trocar e-mail",
  description: "Altere o e-mail da sua conta.",
};

const ERROS: Record<string, string> = {
  email: "Informe um e-mail válido.",
  senha: "A senha está incorreta.",
  troca: "Não foi possível trocar o e-mail. Tente novamente.",
};

export default async function EmailPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sessao = await sessaoAtual();
  if (!sessao) redirect("/entrar?seguir=/conta/email");
  const sp = await searchParams;
  const codigo = typeof sp.erro === "string" ? sp.erro : undefined;
  const erro = codigo ? ERROS[codigo] : undefined;

  return (
    <section aria-labelledby="email-titulo">
      <Masthead
        tituloId="email-titulo"
        titulo="Trocar e-mail"
        sub={`E-mail atual: ${sessao.email ?? "—"}. Enviaremos uma confirmação para os DOIS endereços — a troca só vale quando ambos confirmarem.`}
      />
      <Mensagem texto={erro} id="email-erro" />
      <form method="post" action="/api/conta/email" className="mt-4 flex flex-col gap-6">
        <Campo
          id="novo"
          name="novo"
          label="Novo e-mail"
          type="email"
          autoComplete="email"
          descrevePorId={codigo === "email" ? "email-erro" : undefined}
          invalido={codigo === "email"}
        />
        <Campo
          id="senha"
          name="senha"
          label="Sua senha"
          type="password"
          autoComplete="current-password"
          descrevePorId={codigo === "senha" ? "email-erro" : undefined}
          invalido={codigo === "senha"}
        />
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Trocar e-mail
        </button>
      </form>
    </section>
  );
}
