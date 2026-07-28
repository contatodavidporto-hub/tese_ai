import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { sessaoAtual } from "@/lib/auth/sessao";

import { CLASSE_BOTAO_SEC, Masthead, Mensagem } from "../../_ui";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Seus dados",
  description: "Exporte ou exclua seus dados (LGPD).",
};

export default async function DadosPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (!(await sessaoAtual())) redirect("/entrar?seguir=/conta/dados");
  const sp = await searchParams;
  const erro =
    sp.erro === "aal2"
      ? "Confirme a verificação em dois fatores antes de exportar seus dados."
      : undefined;

  return (
    <section aria-labelledby="dados-titulo">
      <Masthead
        tituloId="dados-titulo"
        titulo="Seus dados"
        sub="Você pode baixar tudo o que guardamos sobre você, ou apagar sua conta em definitivo."
      />
      <Mensagem texto={erro} id="dados-erro" />

      <div className="mt-6 flex flex-col gap-8">
        <div className="flex flex-col gap-3">
          <h2 className="font-display text-h2 font-semibold text-ink">Exportar (portabilidade)</h2>
          <p className="text-body leading-relaxed text-ink-2">
            Baixa um arquivo JSON com seu perfil, suas teses e seu histórico.
          </p>
          {/* <a> comum (não LinkCinema): GET de download, sem prefetch. */}
          <a href="/api/conta/exportar" download="tese-ai-meus-dados.json" className={CLASSE_BOTAO_SEC}>
            Baixar meus dados
          </a>
        </div>

        <div className="flex flex-col gap-3 border-t border-line pt-8">
          <h2 className="font-display text-h2 font-semibold text-ink">Excluir conta</h2>
          <p className="text-body leading-relaxed text-ink-2">
            Apaga sua conta e todos os seus dados em definitivo. Esta ação não pode ser desfeita.
          </p>
          <LinkCinema
            href="/conta/excluir"
            className="sublinhado-brasa w-fit font-sans text-ui font-semibold text-brasa-texto"
          >
            Quero excluir minha conta →
          </LinkCinema>
        </div>
      </div>
    </section>
  );
}
