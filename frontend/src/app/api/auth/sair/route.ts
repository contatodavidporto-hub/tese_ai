import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

// Logout — POST-only (por GET, o prefetch do next/link deslogaria o usuário ao
// renderizar o Header). Escopo EXPLÍCITO: `local` só derruba ESTA sessão (o default
// do signOut é GLOBAL — encerrar todas as sessões é ação própria da Onda 3).
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  try {
    const supabase = await criarClienteAuth();
    await supabase.auth.signOut({ scope: "local" });
  } catch {
    // Mesmo sem env/erro, prossegue para a home — o cookie inválido é inofensivo.
  }
  return redir(request, "/");
}
