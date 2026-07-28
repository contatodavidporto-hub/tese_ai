import { type NextRequest } from "next/server";

import { redir } from "@/lib/auth/http";
import { validaSeguir } from "@/lib/auth/seguir";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Callback do OAuth (Google): troca o `code` PKCE por sessão (cookies httpOnly) e
// segue para o destino validado.
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const seguir = validaSeguir(url.searchParams.get("seguir"), "/historico");
  if (!code || !envAuth()) return redir(request, "/entrar?erro=oauth");

  const supabase = await criarClienteAuth();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) return redir(request, "/entrar?erro=oauth");
  return redir(request, seguir);
}
