// Compensação da "Leaked Password Protection" (recurso Pro do Supabase, DESLIGADO):
// checa a senha contra o HaveIBeenPwned por K-ANONIMATO — envia SÓ o prefixo de 5
// hex do SHA-1, NUNCA a senha nem o hash completo. Usada só em CADASTRO/TROCA/RESET
// (jamais no login — mandar o prefixo da senha correta a cada login não protege
// nada e abre canal de timing).
//
// Server-only: o fetch ao HIBP acontece no servidor Next (a CSP do navegador não o
// rege). FAIL-OPEN: indisponibilidade do HIBP NÃO trava o cadastro (decisão da ADR,
// a ratificar) — devolve `verificado:false` e quem chama segue.
import "server-only";

const HIBP_TIMEOUT_MS = 3000;

export type ResultadoHibp = { vazada: boolean; verificado: boolean };

export async function senhaVazada(senha: string): Promise<ResultadoHibp> {
  try {
    const hash = await sha1Hex(senha);
    const prefixo = hash.slice(0, 5);
    const sufixo = hash.slice(5); // NUNCA sai da máquina — só o prefixo vai ao HIBP
    const res = await fetch(`https://api.pwnedpasswords.com/range/${prefixo}`, {
      headers: { "Add-Padding": "true" }, // padding: o tamanho da resposta não vaza o hit
      cache: "no-store",
      signal: AbortSignal.timeout(HIBP_TIMEOUT_MS),
    });
    if (!res.ok) return { vazada: false, verificado: false };
    const alvo = `${sufixo}:`;
    const vazada = (await res.text())
      .split("\n")
      .some((linha) => linha.toUpperCase().startsWith(alvo));
    return { vazada, verificado: true };
  } catch {
    return { vazada: false, verificado: false }; // fail-open com telemetria no chamador
  }
}

async function sha1Hex(texto: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(texto));
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
}
