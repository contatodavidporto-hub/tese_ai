"use client";

// Wizard de ativação do 2FA (ilha client em /conta/dois-fatores). Precisa de
// interação: o QR/secret só existem na resposta do enroll, então não dá para navegar
// entre passos por PRG — este componente faz enroll → QR → verify → códigos numa só
// tela. Fetch same-origin (CSP `connect-src 'self'` permite); o QR é data-URI SVG
// (`img-src data:` no proxy.ts). Sem style inline (CSP), só classes.

import { useEffect, useRef, useState } from "react";

// classes de campo/botão importadas como STRINGS (não componentes) — ok em client.
import { CLASSE_BOTAO } from "@/app/(portaria)/_ui";

type Passo = "inicio" | "qr" | "codigos";
type Enroll = { factorId: string; qr: string; secret: string };

const CAMPO =
  "w-full border border-field bg-card px-3.5 py-2.5 text-body text-ink focus-visible:outline " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brasa";

export function DoisFatoresWizard() {
  const [passo, setPasso] = useState<Passo>("inicio");
  const [dados, setDados] = useState<Enroll | null>(null);
  const [codigos, setCodigos] = useState<string[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const codeRef = useRef<HTMLInputElement>(null);
  const sucessoRef = useRef<HTMLDivElement>(null);

  // A11y: ao ATIVAR (troca para "codigos"), leva o foco ao bloco de sucesso — senão o
  // leitor de tela não anuncia que o 2FA foi ligado nem que os códigos estão na tela.
  useEffect(() => {
    if (passo === "codigos") sucessoRef.current?.focus();
  }, [passo]);

  async function iniciar() {
    setErro(null);
    setOcupado(true);
    try {
      const r = await fetch("/api/auth/2fa/enroll", { method: "POST", cache: "no-store" });
      if (!r.ok) throw new Error();
      setDados((await r.json()) as Enroll);
      setPasso("qr");
    } catch {
      setErro("Não foi possível iniciar. Tente novamente.");
    } finally {
      setOcupado(false);
    }
  }

  async function verificar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!dados || ocupado) return;
    setErro(null);
    setOcupado(true);
    try {
      const code = codeRef.current?.value ?? "";
      const r = await fetch("/api/auth/2fa/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ factorId: dados.factorId, code }),
        cache: "no-store",
      });
      const d = (await r.json()) as { ok: boolean; codigos?: string[] };
      if (!d.ok) {
        setErro("Código incorreto. Confira o horário do celular e tente de novo.");
        return;
      }
      setCodigos(d.codigos ?? []);
      setPasso("codigos");
    } catch {
      setErro("Falha ao verificar. Tente novamente.");
    } finally {
      setOcupado(false);
    }
  }

  if (passo === "inicio") {
    return (
      <div className="flex flex-col gap-6">
        {erro ? (
          <p role="alert" className="border border-aviso-borda bg-aviso-fundo px-3 py-2 text-ui text-ink">
            {erro}
          </p>
        ) : null}
        <p className="text-body leading-relaxed text-ink-2">
          Ative a verificação em dois fatores com um app autenticador (Google Authenticator,
          Authy, 1Password). A cada login você confirmará um código de 6 dígitos.
        </p>
        <button type="button" onClick={iniciar} disabled={ocupado} className={CLASSE_BOTAO}>
          {ocupado ? "Iniciando…" : "Ativar verificação em dois fatores"}
        </button>
      </div>
    );
  }

  if (passo === "qr" && dados) {
    return (
      <form onSubmit={verificar} className="flex flex-col gap-6">
        <ol className="flex flex-col gap-2 text-body text-ink-2">
          <li>1. Abra seu app autenticador e escaneie o QR abaixo.</li>
          <li>2. Não consegue escanear? Digite o código manual.</li>
          <li>3. Informe o código de 6 dígitos que o app mostrar.</li>
        </ol>
        {/* QR = data-URI SVG (img-src data: permitido). Fundo branco p/ contraste do QR.
            next/image é inaplicável: data-URI não é otimizável e a CSP proíbe a API de
            imagem do Next (a otimização precisaria de connect a um loader). */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={dados.qr}
          alt="QR code para configurar a verificação em dois fatores"
          className="mx-auto h-48 w-48 bg-white p-2"
        />
        <div className="flex flex-col gap-1">
          <span className="font-sans text-meta text-ink-3">Código manual</span>
          <code className="select-all break-all border border-line bg-card px-3 py-2 font-mono text-ui text-ink">
            {dados.secret}
          </code>
        </div>
        {erro ? (
          <p
            id="qr-erro"
            role="alert"
            className="border border-aviso-borda bg-aviso-fundo px-3 py-2 text-ui text-ink"
          >
            {erro}
          </p>
        ) : null}
        <div className="flex flex-col gap-2">
          <label htmlFor="code2fa" className="font-sans text-ui font-medium text-ink-2">
            Código do app
          </label>
          <input
            id="code2fa"
            ref={codeRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            autoComplete="one-time-code"
            required
            aria-describedby={erro ? "qr-erro" : undefined}
            aria-invalid={erro ? true : undefined}
            className={CAMPO}
          />
        </div>
        <button type="submit" disabled={ocupado} className={CLASSE_BOTAO}>
          {ocupado ? "Verificando…" : "Ativar"}
        </button>
      </form>
    );
  }

  // passo === "codigos"
  return (
    <div ref={sucessoRef} tabIndex={-1} role="status" className="flex flex-col gap-6 outline-none">
      <p className="border border-aviso-borda bg-aviso-fundo px-3 py-2 text-ui text-ink">
        Verificação em dois fatores ATIVADA. Guarde os códigos de recuperação abaixo em local
        seguro — cada um serve UMA vez, e são a única forma de entrar se você perder o app.
        Eles não serão mostrados de novo.
      </p>
      <pre className="grid grid-cols-2 gap-x-6 gap-y-1 overflow-x-auto border border-line bg-card px-4 py-4 font-mono text-ui text-ink">
        {codigos.join("\n")}
      </pre>
      <a href="/conta" className={CLASSE_BOTAO}>
        Concluir
      </a>
    </div>
  );
}
