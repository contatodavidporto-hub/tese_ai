import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";

import { CLASSE_BOTAO, Masthead } from "../../_ui";

// Confirmação de e-mail. O link do e-mail aterrissa em /confirmar/pronto?token_hash=…
// (página INERTE): NÃO consome o token em GET; um botão POST → /api/auth/confirmar
// consome (scanner corporativo tipo Outlook SafeLinks queimaria o single-use em GET).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Confirmar e-mail",
  description: "Confirme seu e-mail para ativar sua conta do Tese AI.",
};

const TIPOS = new Set(["email", "signup", "email_change"]);

export default async function ConfirmarPage({
  params,
  searchParams,
}: {
  params: Promise<{ estado: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { estado } = await params;
  const sp = await searchParams;

  if (estado === "pronto") {
    const tokenHash = typeof sp.token_hash === "string" ? sp.token_hash : undefined;
    const tipo = typeof sp.type === "string" && TIPOS.has(sp.type) ? sp.type : "email";
    if (!tokenHash) {
      return (
        <Aviso
          titulo="Link inválido"
          sub="Este link de confirmação não é válido."
          acao={{ href: "/criar-conta", texto: "Criar conta" }}
        />
      );
    }
    return (
      <section aria-labelledby="confirmar-titulo">
        <Masthead
          tituloId="confirmar-titulo"
          titulo="Confirmar e-mail"
          sub="Clique no botão abaixo para ativar sua conta."
        />
        <form method="post" action="/api/auth/confirmar" className="mt-8 flex flex-col gap-6">
          <input type="hidden" name="token_hash" value={tokenHash} />
          <input type="hidden" name="type" value={tipo} />
          <button type="submit" className={CLASSE_BOTAO}>
            Confirmar e-mail
          </button>
        </form>
      </section>
    );
  }

  if (estado === "pendente") {
    return (
      <Aviso
        titulo="Confira seu e-mail"
        sub="Enviamos um link de confirmação. Abra-o para ativar sua conta e entrar. Não achou? Verifique o spam."
        acao={{ href: "/entrar", texto: "Ir para o login" }}
      />
    );
  }

  if (estado === "expirado") {
    return (
      <Aviso
        titulo="Link expirado"
        sub="Este link de confirmação expirou ou já foi usado. Crie a conta de novo ou entre para pedir um novo e-mail."
        acao={{ href: "/entrar", texto: "Entrar" }}
      />
    );
  }

  return (
    <Aviso
      titulo="Link inválido"
      sub="Este link de confirmação não é válido."
      acao={{ href: "/criar-conta", texto: "Criar conta" }}
    />
  );
}

function Aviso({
  titulo,
  sub,
  acao,
}: {
  titulo: string;
  sub: string;
  acao: { href: string; texto: string };
}) {
  return (
    <section aria-labelledby="confirmar-titulo">
      <Masthead tituloId="confirmar-titulo" titulo={titulo} sub={sub} />
      <p className="mt-8 text-ui text-ink-2">
        <LinkCinema href={acao.href} className="sublinhado-brasa font-semibold text-brasa-texto">
          {acao.texto}
        </LinkCinema>
      </p>
    </section>
  );
}
