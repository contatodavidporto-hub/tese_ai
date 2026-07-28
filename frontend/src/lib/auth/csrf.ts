// Defesa CSRF dos route handlers mutantes (server-only).
//
// O matcher do proxy.ts EXCLUI /api, então NENHUMA proteção do proxy (CSP,
// headers) cobre estes handlers — e `form-action 'self'` não impede um POST
// cross-site (a CSP do atacante é dele). A defesa mora AQUI: exige que a origem
// da requisição seja a nossa. `SameSite=Lax` nos cookies é a segunda camada.
import "server-only";

import type { NextRequest } from "next/server";

// true se a requisição veio da MESMA origem. Checa `Sec-Fetch-Site` (enviado pelos
// browsers modernos) E o `Origin` contra o host da própria requisição. Aceita
// `same-origin`/`none` (navegação direta); recusa `cross-site`/`same-site` de
// subdomínio e Origin divergente.
export function mesmaOrigem(request: NextRequest): boolean {
  const site = request.headers.get("sec-fetch-site");
  if (site && !["same-origin", "none"].includes(site)) return false;

  const origem = request.headers.get("origin");
  if (!origem) {
    // FAIL-CLOSED (correção do red-team): sem Origin, só aceita se o Sec-Fetch-Site
    // CONFIRMAR same-origin/none. Ambos ausentes (proxy/extensão que estripa headers)
    // => recusa, nunca aceita por omissão.
    return site === "none" || site === "same-origin";
  }
  try {
    const o = new URL(origem);
    const host = request.headers.get("host");
    return !!host && o.host === host;
  } catch {
    return false;
  }
}
