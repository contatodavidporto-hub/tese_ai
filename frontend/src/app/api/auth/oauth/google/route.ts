import { NextResponse, type NextRequest } from "next/server";

import { origemDe, recusa, redir } from "@/lib/auth/http";
import { validaSeguir } from "@/lib/auth/seguir";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Início do OAuth Google. Disparado por um <a href> (GET, navegação top-level) —
// NUNCA por form POST: o Chrome aplica `form-action 'self'` à cadeia de redirect da
// submissão e o 303 para supabase.co→Google seria bloqueado. Navegação top-level
// para supabase.co é PERMITIDA pela CSP (ela rege fetch/XHR, não navegação).
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);
  const seguir = validaSeguir(new URL(request.url).searchParams.get("seguir"), "/historico");

  const supabase = await criarClienteAuth();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${origemDe(request)}/api/auth/callback?seguir=${encodeURIComponent(seguir)}`,
      skipBrowserRedirect: true,
    },
  });
  if (error || !data?.url) return redir(request, "/entrar?erro=oauth");

  // 303 para o Google (via Supabase). O cookie do code-verifier PKCE é escrito
  // NESTA resposta — sem ele o exchangeCodeForSession do callback falharia.
  const res = NextResponse.redirect(data.url, 303);
  res.headers.set("Cache-Control", "no-store");
  return res;
}
