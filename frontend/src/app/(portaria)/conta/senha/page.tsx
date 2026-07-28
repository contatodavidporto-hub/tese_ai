import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { sessaoAtual } from "@/lib/auth/sessao";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Trocar senha", description: "Altere a senha da sua conta." };

const ERROS: Record<string, string> = {
  atual: "A senha atual está incorreta.",
  curta: "A nova senha precisa ter pelo menos 10 caracteres.",
  vazada: "Essa senha apareceu em vazamentos públicos. Escolha outra.",
  troca: "Não foi possível trocar a senha. Tente novamente.",
};

export default async function SenhaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (!(await sessaoAtual())) redirect("/entrar?seguir=/conta/senha");
  const sp = await searchParams;
  const codigo = typeof sp.erro === "string" ? sp.erro : undefined;
  const erro = codigo ? ERROS[codigo] : undefined;

  return (
    <section aria-labelledby="senha-titulo">
      <Masthead
        tituloId="senha-titulo"
        titulo="Trocar senha"
        sub="Confirme a senha atual e escolha uma nova."
      />
      <Mensagem texto={erro} id="senha-erro" />
      <form method="post" action="/api/conta/senha" className="mt-4 flex flex-col gap-6">
        <input type="text" name="username" autoComplete="username" hidden readOnly value="" />
        <Campo
          id="atual"
          name="atual"
          label="Senha atual"
          type="password"
          autoComplete="current-password"
          descrevePorId={codigo === "atual" ? "senha-erro" : undefined}
          invalido={codigo === "atual"}
        />
        <Campo
          id="nova"
          name="nova"
          label="Nova senha"
          type="password"
          autoComplete="new-password"
          descrevePorId={codigo === "curta" || codigo === "vazada" ? "senha-erro" : undefined}
          invalido={codigo === "curta" || codigo === "vazada"}
        />
        <p className="-mt-2 font-mono text-meta text-ink-3">Mínimo de 10 caracteres.</p>
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Salvar nova senha
        </button>
      </form>
    </section>
  );
}
