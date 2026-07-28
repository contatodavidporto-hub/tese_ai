import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { validaSeguir } from "@/lib/auth/seguir";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Entrar",
  description: "Acesse sua conta do Tese AI para gerar teses e ver seu histórico.",
};

const ERROS: Record<string, string> = {
  credenciais: "E-mail ou senha incorretos.",
  campos: "Preencha e-mail e senha.",
  oauth: "Não foi possível entrar com o Google. Tente novamente.",
};

export default async function EntrarPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const seguir = validaSeguir(typeof sp.seguir === "string" ? sp.seguir : undefined, "/historico");
  const erro = typeof sp.erro === "string" ? ERROS[sp.erro] : undefined;
  const seguirQS = `?seguir=${encodeURIComponent(seguir)}`;

  return (
    <section aria-labelledby="entrar-titulo">
      <Masthead
        tituloId="entrar-titulo"
        titulo="Entrar"
        sub="Acesse sua conta para gerar teses e acompanhar seu histórico."
      />
      <Mensagem texto={erro} />

      <form method="post" action="/api/auth/entrar" className="mt-4 flex flex-col gap-6">
        <input type="hidden" name="seguir" value={seguir} />
        <Campo id="email" name="email" label="E-mail" type="email" autoComplete="email" />
        <Campo
          id="senha"
          name="senha"
          label="Senha"
          type="password"
          autoComplete="current-password"
          extra={
            <LinkCinema href="/recuperar" className="sublinhado-brasa font-mono text-meta text-brasa-texto">
              Esqueci a senha
            </LinkCinema>
          }
        />
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Entrar
        </button>
      </form>

      <div className="mt-6 flex items-center gap-3" aria-hidden>
        <span className="h-px flex-1 bg-line" />
        <span className="font-mono text-meta text-ink-3">ou</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      {/* OAuth SEMPRE por <a> GET (nunca form POST — o Chrome bloquearia o 303 para
          supabase.co pela form-action). Navegação top-level é permitida pela CSP. */}
      <a
        href={`/api/auth/oauth/google${seguirQS}`}
        className="mt-6 flex items-center justify-center gap-2 border border-line-strong bg-card px-4 py-2.5 font-sans text-ui text-ink transition-colors hover:border-ink-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
      >
        Entrar com Google
      </a>

      <p className="mt-8 text-ui text-ink-2">
        Não tem conta?{" "}
        <LinkCinema href="/criar-conta" className="sublinhado-brasa font-semibold text-brasa-texto">
          Criar conta
        </LinkCinema>
      </p>
    </section>
  );
}
