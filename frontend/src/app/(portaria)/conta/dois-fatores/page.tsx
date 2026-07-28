import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DoisFatoresWizard } from "@/components/conta/DoisFatoresWizard";
import { sessaoAtual } from "@/lib/auth/sessao";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

import { CLASSE_BOTAO_SEC, Masthead, Mensagem } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Verificação em dois fatores",
  description: "Ative ou desative a verificação em dois fatores da sua conta.",
};

const ERROS: Record<string, string> = {
  codigo: "Código incorreto. Tente novamente.",
  desafio: "Não foi possível verificar. Tente novamente.",
};

export default async function DoisFatoresPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sessao = await sessaoAtual();
  if (!sessao) redirect("/entrar?seguir=/conta/dois-fatores");
  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const ativo = (fatores?.totp ?? []).some((f) => f.status === "verified");

  const sp = await searchParams;
  const ok = sp.ok === "desativado" ? "Verificação em dois fatores desativada." : undefined;
  const erro = typeof sp.erro === "string" ? ERROS[sp.erro] : undefined;

  return (
    <section aria-labelledby="dois-fatores-titulo">
      <Masthead tituloId="dois-fatores-titulo" titulo="Verificação em dois fatores" />
      <Mensagem texto={ok} tom="ok" />
      <Mensagem texto={erro} id="dois-fatores-erro" />

      {ativo ? (
        <div className="mt-4 flex flex-col gap-6">
          <p className="border border-line bg-card px-3 py-3 text-ui text-ink-2">
            A verificação em dois fatores está <span className="font-semibold text-ink">ativa</span>{" "}
            na sua conta.
          </p>
          <form method="post" action="/api/auth/2fa/unenroll" className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="code" className="font-sans text-ui font-medium text-ink-2">
                Código do app (para confirmar a desativação)
              </label>
              <input
                id="code"
                name="code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="one-time-code"
                required
                aria-describedby={erro ? "dois-fatores-erro" : undefined}
                className="w-full border border-field bg-card px-3.5 py-2.5 text-body text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
              />
            </div>
            <button type="submit" className={CLASSE_BOTAO_SEC}>
              Desativar 2FA
            </button>
          </form>
        </div>
      ) : (
        <div className="mt-4">
          <DoisFatoresWizard />
        </div>
      )}
    </section>
  );
}
