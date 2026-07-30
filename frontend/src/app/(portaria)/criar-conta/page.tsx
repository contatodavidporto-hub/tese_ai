import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Criar conta",
  description: "Crie sua conta do Tese AI para gerar teses estruturadas e auditáveis.",
};

const ERROS: Record<string, string> = {
  email: "Informe um e-mail válido.",
  curta: "A senha precisa ter pelo menos 12 caracteres.",
  vazada: "Essa senha apareceu em vazamentos públicos. Escolha outra que você não use em outro lugar.",
};

export default async function CriarContaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const codigo = typeof sp.erro === "string" ? sp.erro : undefined;
  const erro = codigo ? ERROS[codigo] : undefined;
  const emailInvalido = codigo === "email";
  const senhaInvalida = codigo === "curta" || codigo === "vazada";

  return (
    <section aria-labelledby="criar-titulo">
      <Masthead
        tituloId="criar-titulo"
        titulo="Criar conta"
        sub="Leva um minuto. Você confirma o e-mail e já pode gerar sua primeira tese."
      />
      <Mensagem texto={erro} id="criar-erro" />

      <form method="post" action="/api/auth/criar-conta" className="mt-4 flex flex-col gap-6">
        <Campo
          id="email"
          name="email"
          label="E-mail"
          type="email"
          autoComplete="email"
          descrevePorId={emailInvalido ? "criar-erro" : undefined}
          invalido={emailInvalido}
        />
        <Campo
          id="senha"
          name="senha"
          label="Senha"
          type="password"
          autoComplete="new-password"
          descrevePorId={senhaInvalida ? "criar-erro" : undefined}
          invalido={senhaInvalida}
        />
        {/* Política honesta: comprimento acima de tudo (verificação contra vazamentos
            no envio). Sem teatro de "1 maiúscula e 1 símbolo". */}
        <p className="-mt-2 font-mono text-meta text-ink-3">
          Mínimo de 12 caracteres. Prefira uma frase longa que só você saiba.
        </p>
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Criar conta
        </button>
      </form>

      <p className="mt-8 text-ui text-ink-2">
        Já tem conta?{" "}
        <LinkCinema href="/entrar" className="sublinhado-brasa font-semibold text-brasa-texto">
          Entrar
        </LinkCinema>
      </p>
    </section>
  );
}
