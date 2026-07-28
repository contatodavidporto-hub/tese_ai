import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { sessaoAtual } from "@/lib/auth/sessao";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

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
  "2fa": "Informe o código do seu app autenticador.",
  codigo: "Código de dois fatores incorreto.",
};

export default async function EmailPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sessao = await sessaoAtual();
  if (!sessao) redirect("/entrar?seguir=/conta/email");
  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const tem2fa = (fatores?.totp ?? []).some((f) => f.status === "verified");
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
              aria-describedby={codigo === "2fa" || codigo === "codigo" ? "email-erro" : undefined}
              aria-invalid={codigo === "2fa" || codigo === "codigo" ? true : undefined}
              className="w-full border border-field bg-card px-3.5 py-2.5 text-body text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
            />
          </div>
        ) : null}
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Trocar e-mail
        </button>
      </form>
    </section>
  );
}
