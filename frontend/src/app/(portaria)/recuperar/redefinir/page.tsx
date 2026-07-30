import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";

import { Campo, CLASSE_BOTAO, Masthead, Mensagem } from "../../_ui";

// Página INERTE do link de e-mail: NÃO consome o token em GET (scanner corporativo
// queimaria o single-use). Coleta a senha nova + o token_hash (hidden) e POSTa —
// o handler consome o token (verifyOtp type=recovery) e troca a senha no mesmo passo.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Redefinir senha",
  description: "Escolha uma nova senha para sua conta do Tese AI.",
};

const ERROS: Record<string, string> = {
  curta: "A senha precisa ter pelo menos 12 caracteres.",
  vazada: "Essa senha apareceu em vazamentos públicos. Escolha outra.",
};

export default async function RedefinirPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const tokenHash =
    typeof sp.token_hash === "string" ? sp.token_hash : undefined;
  const erro = typeof sp.erro === "string" ? ERROS[sp.erro] : undefined;

  if (!tokenHash) {
    return (
      <section aria-labelledby="redefinir-titulo">
        <Masthead
          tituloId="redefinir-titulo"
          titulo="Link inválido"
          sub="Este link de redefinição não é válido ou já foi usado."
        />
        <p className="mt-8 text-ui text-ink-2">
          <LinkCinema href="/recuperar" className="sublinhado-brasa font-semibold text-brasa-texto">
            Pedir um novo link
          </LinkCinema>
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="redefinir-titulo">
      <Masthead
        tituloId="redefinir-titulo"
        titulo="Nova senha"
        sub="Escolha uma senha que você não use em outro lugar."
      />
      <Mensagem texto={erro} id="redefinir-erro" />

      <form
        method="post"
        action="/api/auth/recuperar/redefinir"
        className="mt-4 flex flex-col gap-6"
      >
        <input type="hidden" name="token_hash" value={tokenHash} />
        {/* campo username oculto p/ o gerenciador de senhas associar a credencial */}
        <input type="text" name="username" autoComplete="username" hidden readOnly value="" />
        <Campo
          id="senha"
          name="senha"
          label="Nova senha"
          type="password"
          autoComplete="new-password"
          descrevePorId={erro ? "redefinir-erro" : undefined}
          invalido={!!erro}
        />
        <p className="-mt-2 font-mono text-meta text-ink-3">Mínimo de 12 caracteres.</p>
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Redefinir senha
        </button>
      </form>
    </section>
  );
}
