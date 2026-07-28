import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { sessaoAtual } from "@/lib/auth/sessao";

import { Masthead, Mensagem } from "../_ui";

// Hub da conta (rota AUTENTICADA — não é público, então ler o cookie server-side é
// correto). Onda 2: e-mail + sair. As telas de segurança (2FA), troca de e-mail/senha
// e LGPD (exportar/excluir) nascem na Onda 3.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sua conta",
  description: "Gerencie sua conta do Tese AI.",
};

export default async function ContaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sessao = await sessaoAtual();
  if (!sessao) redirect("/entrar?seguir=/conta");
  const sp = await searchParams;
  const ok = sp.ok === "senha" ? "Senha atualizada com sucesso." : undefined;

  return (
    <section aria-labelledby="conta-titulo">
      <Masthead tituloId="conta-titulo" titulo="Sua conta" />
      <Mensagem texto={ok} tom="ok" />

      <dl className="mt-6 border-t border-line">
        <div className="flex items-baseline justify-between gap-4 border-b border-line py-3">
          <dt className="font-sans text-ui text-ink-3">E-mail</dt>
          <dd className="font-mono text-ui text-ink">{sessao.email ?? "—"}</dd>
        </div>
      </dl>

      <div className="mt-6 flex flex-col gap-3">
        <LinkCinema
          href="/historico"
          className="sublinhado-brasa font-sans text-ui font-semibold text-brasa-texto"
        >
          Ver meu histórico →
        </LinkCinema>
      </div>

      {/* Sair — POST-only (por GET, o prefetch do next/link deslogaria ao renderizar).
          Botão secundário (contorno), não a brasa primária. */}
      <form method="post" action="/api/auth/sair" className="mt-10">
        <button
          type="submit"
          className="w-full border border-line-strong bg-card px-4 py-2.5 text-center font-sans text-ui font-semibold text-ink transition-colors hover:border-ink-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
        >
          Sair desta conta
        </button>
      </form>

      <p className="mt-10 font-mono text-meta text-ink-3">
        Verificação em dois fatores, troca de e-mail e senha, e exportação/exclusão de dados
        (LGPD) chegam na próxima etapa.
      </p>
    </section>
  );
}
