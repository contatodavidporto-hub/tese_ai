import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Consome o token de e-mail (confirmação de cadastro OU troca de e-mail). SÓ POR
// POST: um scanner corporativo (Outlook SafeLinks) faz GET no link e queimaria o
// token single-use — por isso o link aterrissa numa página inerte com um botão que
// dispara este POST. `verifyOtp` cria a sessão (cookies httpOnly).
export const dynamic = "force-dynamic";

const TIPOS = new Set(["email", "signup", "email_change"]);

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const tokenHash = String(form.get("token_hash") ?? "");
  const tipo = String(form.get("type") ?? "email");
  if (!tokenHash || !TIPOS.has(tipo)) return redir(request, "/confirmar/invalido");

  const supabase = await criarClienteAuth();
  const { error } = await supabase.auth.verifyOtp({
    token_hash: tokenHash,
    type: tipo as "email" | "signup" | "email_change",
  });
  if (error) return redir(request, "/confirmar/expirado");
  return redir(request, "/conta");
}
