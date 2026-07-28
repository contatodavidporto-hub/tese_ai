import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { chamarBackend } from "@/lib/backend";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Break-glass: o usuário perdeu o 2º fator e usa um código de recuperação. Proxy puro
// para o FastAPI (que valida o código, remove os fatores TOTP via Admin API e apaga os
// códigos). O código NUNCA minta aal2 — depois o usuário re-loga sem 2FA e re-enrola.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const codigo = String(form.get("codigo") ?? "").trim();
  const supabase = await criarClienteAuth();
  const { data: s } = await supabase.auth.getSession();
  try {
    const r = await chamarBackend("/conta/mfa/recuperacao", s.session?.access_token ?? null, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo }),
    });
    if (!r.ok) return redir(request, "/entrar/desafio?modo=recuperacao&erro=codigo");
  } catch {
    return redir(request, "/entrar/desafio?modo=recuperacao&erro=indisponivel");
  }
  // Fatores removidos: encerra a sessão local e manda re-logar (agora sem 2FA).
  await supabase.auth.signOut({ scope: "local" });
  return redir(request, "/entrar?ok=2fa_removido");
}
