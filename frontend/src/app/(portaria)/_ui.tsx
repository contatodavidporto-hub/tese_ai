// Primitivas server-rendered dos formulários da Portaria (arquivo privado `_ui`,
// não é rota). Consistência = AA + CLS por construção: foco visível (outline brasa),
// tokens do sistema, região de erro com altura RESERVADA (mostrar erro não desloca).
import type { ReactNode } from "react";

// Campo de texto/senha: borda de campo, foco visível AA, largura cheia.
export const CLASSE_CAMPO =
  "w-full border border-field bg-card px-3.5 py-2.5 text-body text-ink " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-brasa";

// Botão primário (brasa) com foco visível. py-3 (alvo de toque ~44px, meta da casa).
export const CLASSE_BOTAO =
  "w-full bg-brasa px-4 py-3 text-center font-sans text-ui font-semibold text-sobre-brasa " +
  "transition-colors hover:bg-brasa-forte focus-visible:outline focus-visible:outline-2 " +
  "focus-visible:outline-offset-2 focus-visible:outline-brasa";

// Botão SECUNDÁRIO (contorno): borda `border-field` (≥4.8:1 vs card/página, passa SC
// 1.4.11 — `border-line-strong` reprovava a 1.68:1) + foco visível.
export const CLASSE_BOTAO_SEC =
  "w-full border border-field bg-card px-4 py-3 text-center font-sans text-ui font-semibold " +
  "text-ink transition-colors hover:border-ink-3 focus-visible:outline focus-visible:outline-2 " +
  "focus-visible:outline-offset-2 focus-visible:outline-brasa";

export function Masthead({
  eyebrow = "Portaria",
  titulo,
  sub,
  tituloId,
}: {
  eyebrow?: string;
  titulo: string;
  sub?: ReactNode;
  tituloId: string;
}) {
  return (
    <header>
      <p className="font-mono text-meta uppercase tracking-[0.2em] text-ink-3">{eyebrow}</p>
      <h1
        id={tituloId}
        className="mt-3 font-display text-h1 font-semibold tracking-tight text-ink"
      >
        {titulo}
      </h1>
      {sub ? <p className="mt-3 text-body leading-relaxed text-ink-2">{sub}</p> : null}
    </header>
  );
}

// Região de mensagem: altura mínima RESERVADA (CLS zero). `id` permite ligar o campo
// que falhou (aria-describedby). No erro, recebe foco no load (tabIndex=-1 + autoFocus):
// como o fluxo é PRG sem JS, um role=alert já presente no DOM ao carregar nem sempre é
// anunciado — mover o foco garante o anúncio (CSP-safe, sem JS de submit).
export function Mensagem({
  texto,
  tom = "erro",
  id,
}: {
  texto?: string;
  tom?: "erro" | "ok";
  id?: string;
}) {
  const erro = tom === "erro";
  const estilo = erro
    ? "border border-aviso-borda bg-aviso-fundo text-ink"
    : "border border-line bg-card text-ink-2";
  return (
    <div className="mt-6 min-h-[1.75rem]">
      {texto ? (
        <p
          id={id}
          role={erro ? "alert" : "status"}
          tabIndex={erro ? -1 : undefined}
          autoFocus={erro || undefined}
          className={`${estilo} px-3 py-2 text-ui outline-none`}
        >
          {texto}
        </p>
      ) : null}
    </div>
  );
}

// Campo com rótulo associado (WCAG 3.3.2/1.3.1).
export function Campo({
  id,
  name,
  label,
  type = "text",
  autoComplete,
  required = true,
  defaultValue,
  extra,
  descrevePorId,
  invalido,
}: {
  id: string;
  name: string;
  label: string;
  type?: string;
  autoComplete?: string;
  required?: boolean;
  defaultValue?: string;
  extra?: ReactNode;
  // Liga o campo à mensagem de erro (aria-describedby) e o marca inválido, para o
  // leitor de tela anunciar a razão ao chegar no campo.
  descrevePorId?: string;
  invalido?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="font-sans text-ui font-medium text-ink-2">
          {label}
        </label>
        {extra}
      </div>
      <input
        id={id}
        name={name}
        type={type}
        autoComplete={autoComplete}
        required={required}
        defaultValue={defaultValue}
        aria-describedby={descrevePorId}
        aria-invalid={invalido || undefined}
        className={CLASSE_CAMPO}
      />
    </div>
  );
}
