import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { origemDe, recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Pedido de recuperação de senha. ANTI-ENUMERAÇÃO: resposta idêntica exista ou não
// a conta. O link do e-mail (template com {{ .TokenHash }}) aterrissa em
// /recuperar/redefinir para um POST inerte (nunca consome o token em GET).
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim();
  if (email && email.includes("@")) {
    const supabase = await criarClienteAuth();
    await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${origemDe(request)}/recuperar/redefinir`,
    });
  }
  // SEMPRE a mesma tela — nunca revela se o e-mail existe.
  return redir(request, "/recuperar/enviado");
}
