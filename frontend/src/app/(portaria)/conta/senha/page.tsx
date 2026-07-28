import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { sessaoAtual } from "@/lib/auth/sessao";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Trocar senha", description: "Altere a senha da sua conta." };

const ERROS: Record<string, string> = {
  atual: "A senha atual está incorreta.",
  curta: "A nova senha precisa ter pelo menos 10 caracteres.",
  vazada: "Essa senha apareceu em vazamentos públicos. Escolha outra.",
  troca: "Não foi possível trocar a senha. Tente novamente.",
  "2fa": "Informe o código do seu app autenticador.",
  codigo: "Código de dois fatores incorreto.",
};

export default async function SenhaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (!(await sessaoAtual())) redirect("/entrar?seguir=/conta/senha");
  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const tem2fa = (fatores?.totp ?? []).some((f) => f.status === "verified");
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
        {tem2fa ? (
          <div className="flex flex-col gap-2">
            <label htmlFor="code" className="font-sans text-ui font-medium text-ink-2">
              Código do app autenticador (2FA)
            </label>
            <input
              id="code"
              name="code"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="one-time-code"
              required
              aria-describedby={codigo === "2fa" || codigo === "codigo" ? "senha-erro" : undefined}
              aria-invalid={codigo === "2fa" || codigo === "codigo" ? true : undefined}
              className="w-full border border-field bg-card px-3.5 py-2.5 text-body text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
            />
          </div>
        ) : null}
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
