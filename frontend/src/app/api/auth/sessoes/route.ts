import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

// Encerrar TODAS as sessões (escopo global) — defesa contra token roubado. POST-only.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  try {
    const supabase = await criarClienteAuth();
    await supabase.auth.signOut({ scope: "global" });
  } catch {
    // segue para a home; o cookie inválido é inofensivo
  }
  return redir(request, "/entrar?ok=sessoes_encerradas");
}
