import { type NextRequest } from "next/server";

import { redir } from "@/lib/auth/http";
import { validaSeguir } from "@/lib/auth/seguir";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

// Rota de "bounce" de refresh: páginas RSC NÃO escrevem cookie (o setAll é no-op
// nelas), então uma sessão vencida numa página server-rendered redireciona para
// cá. Aqui (route handler) o getClaims dispara o refresh E o cookie novo é escrito;
// depois seguimos para o destino (validado como path relativo — anti open-redirect).
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const next = validaSeguir(new URL(request.url).searchParams.get("next"), "/");
  try {
    const supabase = await criarClienteAuth();
    await supabase.auth.getClaims();
  } catch {
    // sem env/sessão: apenas segue (a página de destino trata o anônimo).
  }
  return redir(request, next);
}
