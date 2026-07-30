// Compensação da "Leaked Password Protection" (recurso Pro do Supabase, DESLIGADO):
// checa a senha contra o HaveIBeenPwned por K-ANONIMATO — envia SÓ o prefixo de 5
// hex do SHA-1, NUNCA a senha nem o hash completo. Usada só em CADASTRO/TROCA/RESET
// (jamais no login — mandar o prefixo da senha correta a cada login não protege
// nada e abre canal de timing).
//
// Server-only: o fetch ao HIBP acontece no servidor Next (a CSP do navegador não o rege).
// FAIL-OPEN RATIFICADO (Onda 4): o HIBP é DEFESA-EM-PROFUNDIDADE, não o controle primário
// (esse é o piso de 12 caracteres + anti-enumeração). Travar TODO cadastro quando um
// terceiro (HIBP) cai é pior que o risco marginal de uma senha vazada — logo uma
// indisponibilidade SUSTENTADA devolve `verificado:false` e o cadastro segue (com 1 retry
// curto p/ blips transitórios). Trade-off aceito com justificativa (ver ADR de segurança).
import "server-only";

const HIBP_TIMEOUT_MS = 3000;

export type ResultadoHibp = { vazada: boolean; verificado: boolean };

export async function senhaVazada(senha: string): Promise<ResultadoHibp> {
  const hash = await sha1Hex(senha);
  const prefixo = hash.slice(0, 5);
  const sufixo = hash.slice(5); // NUNCA sai da máquina — só o prefixo vai ao HIBP
  const alvo = `${sufixo}:`;
  // 2 tentativas (1 retry curto): reduz o fail-open por blip transitório sem travar o
  // cadastro numa indisponibilidade sustentada (fail-open ratificado — ver topo).
  for (let tentativa = 0; tentativa < 2; tentativa++) {
    try {
      const res = await fetch(`https://api.pwnedpasswords.com/range/${prefixo}`, {
        headers: { "Add-Padding": "true" }, // padding: o tamanho da resposta não vaza o hit
        cache: "no-store",
        signal: AbortSignal.timeout(HIBP_TIMEOUT_MS),
      });
      if (!res.ok) continue; // resposta ruim — tenta de novo, senão cai no fail-open
      const vazada = (await res.text())
        .split("\n")
        .some((linha) => linha.toUpperCase().startsWith(alvo));
      return { vazada, verificado: true };
    } catch {
      // timeout/rede — nova tentativa; a última volta cai no fail-open abaixo
    }
  }
  return { vazada: false, verificado: false }; // FAIL-OPEN ratificado (telemetria no chamador)
}

async function sha1Hex(texto: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(texto));
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
}
