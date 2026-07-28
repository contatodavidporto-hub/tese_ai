import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { sessaoAtual } from "@/lib/auth/sessao";

import { Masthead, Mensagem } from "../_ui";

// Hub da conta (rota AUTENTICADA). Onda 3: segurança (senha, 2FA, encerrar sessões) e
// LGPD (exportar/excluir). `no-store` forçado no next.config.ts (dado sensível: e-mail).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sua conta",
  description: "Gerencie sua conta, segurança e dados do Tese AI.",
};

const OKS: Record<string, string> = {
  senha: "Senha atualizada com sucesso.",
  email_pendente: "Troca de e-mail iniciada. Confirme nos DOIS endereços (o atual e o novo).",
};

function LinhaLink({ href, titulo, desc }: { href: string; titulo: string; desc: string }) {
  return (
    <LinkCinema
      href={href}
      className="group flex items-center justify-between gap-4 border-b border-line py-3 hover:bg-card"
    >
      <span className="flex flex-col gap-0.5">
        <span className="font-sans text-ui font-semibold text-ink">{titulo}</span>
        <span className="font-sans text-meta text-ink-3">{desc}</span>
      </span>
      <span aria-hidden className="font-mono text-ink-3 group-hover:text-brasa-texto">
        →
      </span>
    </LinkCinema>
  );
}

export default async function ContaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sessao = await sessaoAtual();
  if (!sessao) redirect("/entrar?seguir=/conta");
  const sp = await searchParams;
  const ok = typeof sp.ok === "string" ? OKS[sp.ok] : undefined;

  return (
    <section aria-labelledby="conta-titulo">
      <Masthead tituloId="conta-titulo" titulo="Sua conta" />
      <Mensagem texto={ok} tom="ok" />

      <dl className="mt-6 border-t border-line">
        <div className="flex items-baseline justify-between gap-4 border-b border-line py-3">
          <dt className="font-sans text-ui text-ink-3">E-mail</dt>
          <dd className="break-all font-mono text-ui text-ink">{sessao.email ?? "—"}</dd>
        </div>
      </dl>

      <h2 className="mt-10 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
        Segurança
      </h2>
      <nav className="mt-2 border-t border-line" aria-label="Segurança da conta">
        <LinhaLink href="/conta/senha" titulo="Trocar senha" desc="Requer a senha atual." />
        <LinhaLink
          href="/conta/dois-fatores"
          titulo="Verificação em dois fatores"
          desc="Ative o 2FA com um app autenticador."
        />
        <LinhaLink href="/conta/email" titulo="Trocar e-mail" desc="Confirmação nos dois endereços." />
      </nav>
      <form method="post" action="/api/auth/sessoes" className="mt-4">
        {/* inline-block + py-2 = alvo de toque ~35px (≥24px, SC 2.5.8). */}
        <button
          type="submit"
          className="sublinhado-brasa inline-block py-2 font-sans text-ui font-semibold text-brasa-texto"
        >
          Encerrar todas as sessões
        </button>
      </form>

      <h2 className="mt-10 font-sans text-label font-semibold uppercase tracking-[0.16em] text-ink-3">
        Seus dados
      </h2>
      <nav className="mt-2 border-t border-line" aria-label="Dados da conta">
        <LinhaLink
          href="/conta/dados"
          titulo="Exportar ou excluir meus dados"
          desc="Portabilidade e apagamento (LGPD)."
        />
        <LinhaLink href="/historico" titulo="Meu histórico" desc="Teses que você gerou." />
      </nav>

      <form method="post" action="/api/auth/sair" className="mt-10">
        <button
          type="submit"
          className="w-full border border-field bg-card px-4 py-3 text-center font-sans text-ui font-semibold text-ink transition-colors hover:border-ink-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
        >
          Sair desta conta
        </button>
      </form>
    </section>
  );
}
