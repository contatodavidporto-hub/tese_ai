import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { validaSeguir } from "@/lib/auth/seguir";

import { Campo, CLASSE_BOTAO, CLASSE_BOTAO_SEC, Masthead, Mensagem } from "../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Entrar",
  description: "Acesse sua conta do Tese AI para gerar teses e ver seu histórico.",
};

const ERROS: Record<string, string> = {
  // Mensagem genérica (anti-enumeração) + lembrete de confirmação para TODOS — não
  // revela se o e-mail existe nem se está confirmado.
  credenciais: "E-mail ou senha incorretos. Se você acabou de criar a conta, confirme o e-mail que enviamos antes de entrar.",
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
      <Mensagem texto={erro} id="entrar-erro" />

      <form method="post" action="/api/auth/entrar" className="mt-4 flex flex-col gap-6">
        <input type="hidden" name="seguir" value={seguir} />
        <Campo
          id="email"
          name="email"
          label="E-mail"
          type="email"
          autoComplete="email"
          descrevePorId={erro ? "entrar-erro" : undefined}
          invalido={!!erro}
        />
        <Campo
          id="senha"
          name="senha"
          label="Senha"
          type="password"
          autoComplete="current-password"
          descrevePorId={erro ? "entrar-erro" : undefined}
          invalido={!!erro}
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
          supabase.co pela form-action). Navegação top-level é permitida pela CSP.
          Borda `border-field` (≥4.8:1) via CLASSE_BOTAO_SEC — passa SC 1.4.11. */}
      <a href={`/api/auth/oauth/google${seguirQS}`} className={`mt-6 block ${CLASSE_BOTAO_SEC}`}>
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
