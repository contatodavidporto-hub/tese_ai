import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Desativa o 2FA. Step-up imediato: exige um código TOTP FRESCO (challenge+verify → aal2)
// antes de remover — desativar 2FA é operação sensível. Depois refreshSession (o
// downgrade aal2→aal1 só ocorre no refresh).
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const code = String(form.get("code") ?? "").trim();
  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const totp = (fatores?.totp ?? []).filter((f) => f.status === "verified");
  if (totp.length === 0) return redir(request, "/conta/dois-fatores");

  // Step-up: prova posse do fator antes de remover.
  const { data: ch } = await supabase.auth.mfa.challenge({ factorId: totp[0].id });
  if (!ch) return redir(request, "/conta/dois-fatores?erro=desafio");
  const { error } = await supabase.auth.mfa.verify({
    factorId: totp[0].id,
    challengeId: ch.id,
    code,
  });
  if (error) return redir(request, "/conta/dois-fatores?erro=codigo");

  for (const f of totp) await supabase.auth.mfa.unenroll({ factorId: f.id });
  await supabase.auth.refreshSession();
  return redir(request, "/conta/dois-fatores?ok=desativado");
}
