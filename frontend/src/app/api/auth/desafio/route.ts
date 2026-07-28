import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { validaSeguir } from "@/lib/auth/seguir";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Desafio de login em 2 fatores: challenge+verify do TOTP verificado (mesma invocação →
// aal2) e segue para o destino. Form nativo PRG.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const code = String(form.get("code") ?? "").trim();
  const seguir = validaSeguir(form.get("seguir"), "/historico");
  const qs = `?seguir=${encodeURIComponent(seguir)}`;

  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const fator = (fatores?.totp ?? []).find((f) => f.status === "verified");
  if (!fator) return redir(request, seguir); // nada a desafiar

  const { data: ch, error: e1 } = await supabase.auth.mfa.challenge({ factorId: fator.id });
  if (e1 || !ch) return redir(request, `/entrar/desafio${qs}&erro=desafio`);
  const { error: e2 } = await supabase.auth.mfa.verify({
    factorId: fator.id,
    challengeId: ch.id,
    code,
  });
  if (e2) return redir(request, `/entrar/desafio${qs}&erro=codigo`);
  return redir(request, seguir); // aal2
}
