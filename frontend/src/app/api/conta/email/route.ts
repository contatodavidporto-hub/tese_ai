import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Troca de e-mail: reautentica a senha e dispara a troca. "Secure email change" envia
// confirmação para os DOIS endereços (atual e novo) — a troca só vale quando ambos
// confirmam. O template do dashboard aterrissa em /confirmar/pronto (type=email_change).
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const novo = String(form.get("novo") ?? "").trim();
  const senha = String(form.get("senha") ?? "");
  if (!novo.includes("@")) return redir(request, "/conta/email?erro=email");

  const supabase = await criarClienteAuth();
  const { data: u } = await supabase.auth.getUser();
  const email = u.user?.email;
  if (!email) return redir(request, "/entrar");
  const { error: eAuth } = await supabase.auth.signInWithPassword({ email, password: senha });
  if (eAuth) return redir(request, "/conta/email?erro=senha");
  const { error } = await supabase.auth.updateUser({ email: novo });
  if (error) return redir(request, "/conta/email?erro=troca");
  return redir(request, "/conta?ok=email_pendente");
}
