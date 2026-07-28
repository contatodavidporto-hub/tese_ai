import type { Metadata } from "next";

import { LinkCinema } from "@/components/motion/LinkCinema";
import { validaSeguir } from "@/lib/auth/seguir";

import { CLASSE_BOTAO, Masthead, Mensagem } from "../../_ui";

// Passo de verificação em dois fatores no login (aal1 → aal2). Form nativo PRG.
// Alterna para o modo "código de recuperação" (break-glass) por `?modo=recuperacao`.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Verificação em dois fatores",
  description: "Confirme o código do seu app autenticador.",
};

const CAMPO_OTP =
  "w-full border border-field bg-card px-3.5 py-2.5 text-center font-mono text-h2 tracking-[0.3em] " +
  "text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-brasa";

export default async function DesafioPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const seguir = validaSeguir(typeof sp.seguir === "string" ? sp.seguir : undefined, "/historico");
  const modo = sp.modo === "recuperacao" ? "recuperacao" : "codigo";
  const erro =
    sp.erro === "codigo"
      ? "Código incorreto. Tente novamente."
      : sp.erro === "desafio"
        ? "Não foi possível iniciar a verificação. Tente novamente."
        : sp.erro === "indisponivel"
          ? "Serviço indisponível. Tente novamente em instantes."
          : undefined;
  const qs = `?seguir=${encodeURIComponent(seguir)}`;

  if (modo === "recuperacao") {
    return (
      <section aria-labelledby="desafio-titulo">
        <Masthead
          tituloId="desafio-titulo"
          titulo="Código de recuperação"
          sub="Perdeu o acesso ao app autenticador? Use um dos códigos de recuperação que você guardou. Ele desativa o 2FA — você poderá reconfigurá-lo depois."
        />
        <Mensagem texto={erro} id="desafio-erro" />
        <form method="post" action="/api/auth/recuperacao" className="mt-4 flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <label htmlFor="codigo" className="font-sans text-ui font-medium text-ink-2">
              Código de recuperação
            </label>
            <input
              id="codigo"
              name="codigo"
              type="text"
              autoComplete="off"
              required
              aria-describedby={erro ? "desafio-erro" : undefined}
              aria-invalid={erro ? true : undefined}
              className="w-full border border-field bg-card px-3.5 py-2.5 font-mono text-body tracking-wide text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa"
            />
          </div>
          <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
            Usar código
          </button>
        </form>
        <p className="mt-8 text-ui text-ink-2">
          <LinkCinema
            href={`/entrar/desafio${qs}`}
            className="sublinhado-brasa font-semibold text-brasa-texto"
          >
            Voltar ao código do app
          </LinkCinema>
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="desafio-titulo">
      <Masthead
        tituloId="desafio-titulo"
        titulo="Verificação em dois fatores"
        sub="Digite o código de 6 dígitos do seu app autenticador (Google Authenticator, Authy, etc.)."
      />
      <Mensagem texto={erro} id="desafio-erro" />
      <form method="post" action="/api/auth/desafio" className="mt-4 flex flex-col gap-6">
        <input type="hidden" name="seguir" value={seguir} />
        <input type="text" name="username" autoComplete="username" hidden readOnly value="" />
        <div className="flex flex-col gap-2">
          <label htmlFor="code" className="font-sans text-ui font-medium text-ink-2">
            Código
          </label>
          {/* type=text + inputmode=numeric: type=number quebra no iOS (pegadinha conhecida). */}
          <input
            id="code"
            name="code"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            autoComplete="one-time-code"
            required
            aria-describedby={erro ? "desafio-erro" : undefined}
            aria-invalid={erro ? true : undefined}
            className={CAMPO_OTP}
          />
        </div>
        <button type="submit" className={`mt-2 ${CLASSE_BOTAO}`}>
          Verificar
        </button>
      </form>
      <p className="mt-8 text-ui text-ink-2">
        <LinkCinema
          href={`/entrar/desafio${qs}&modo=recuperacao`}
          className="sublinhado-brasa font-semibold text-brasa-texto"
        >
          Perdi meu dispositivo
        </LinkCinema>
      </p>
    </section>
  );
}
