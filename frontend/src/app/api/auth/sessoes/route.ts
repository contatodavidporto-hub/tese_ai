import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth } from "@/lib/auth/supabaseServer";

// Encerrar TODAS as sessões (escopo global): revoga os REFRESH tokens no GoTrue de
// imediato. O access token já emitido é stateless e vale ATÉ o exp (TTL curto no dashboard)
// — o corte NÃO é instantâneo para leituras que usam getClaims; as operações de alto valor
// (senha/email/excluir/exportar) usam getUser (ciente de revogação) e cortam na hora. SESS-01.
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
