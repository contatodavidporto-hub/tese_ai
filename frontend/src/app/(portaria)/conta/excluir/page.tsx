import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { sessaoAtual } from "@/lib/auth/sessao";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Excluir conta",
  description: "Exclua sua conta e todos os seus dados em definitivo.",
};

const ERROS: Record<string, string> = {
  senha: "A senha está incorreta.",
  confirmacao: 'Digite "EXCLUIR" (em maiúsculas) para confirmar.',
  "2fa": "Informe o código do seu app autenticador.",
  codigo: "Código de dois fatores incorreto.",
  falha: "Não foi possível excluir a conta. Tente novamente.",
  indisponivel: "Serviço indisponível. Tente novamente em instantes.",
};

export default async function ExcluirPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (!(await sessaoAtual())) redirect("/entrar?seguir=/conta/excluir");
  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const tem2fa = (fatores?.totp ?? []).some((f) => f.status === "verified");
  const sp = await searchParams;
  const codigo = typeof sp.erro === "string" ? sp.erro : undefined;
  const erro = codigo ? ERROS[codigo] : undefined;

  return (
    <section aria-labelledby="excluir-titulo">
      <Masthead
        tituloId="excluir-titulo"
        titulo="Excluir conta"
        sub="Esta ação apaga sua conta, suas teses e seu histórico em DEFINITIVO. Não pode ser desfeita."
      />
      <Mensagem texto={erro} id="excluir-erro" />
      <form method="post" action="/api/conta/excluir" className="mt-4 flex flex-col gap-6">
        <Campo
          id="senha"
          name="senha"
          label="Sua senha"
          type="password"
          autoComplete="current-password"
          descrevePorId={codigo === "senha" ? "excluir-erro" : undefined}
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
              aria-describedby={
                codigo === "2fa" || codigo === "codigo" ? "excluir-erro" : undefined
              }
              aria-invalid={codigo === "2fa" || codigo === "codigo" ? true : undefined}
              className="w-full border border-field bg-card px-3.5 py-2.5 text-body text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
            />
          </div>
        ) : null}
        <Campo
          id="confirmacao"
          name="confirmacao"
          label='Digite "EXCLUIR" para confirmar'
          type="text"
          autoComplete="off"
          descrevePorId={codigo === "confirmacao" ? "excluir-erro" : undefined}
          invalido={codigo === "confirmacao"}
        />
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Excluir minha conta em definitivo
        </button>
      </form>
      <p className="mt-8 text-ui text-ink-2">
        <LinkCinema href="/conta" className="sublinhado-brasa font-semibold text-brasa-texto">
          Cancelar
        </LinkCinema>
      </p>
    </section>
  );
}
