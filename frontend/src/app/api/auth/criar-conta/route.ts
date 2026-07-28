import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { senhaVazada } from "@/lib/auth/hibp";
import { origemDe, recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Cadastro. Política de força HONESTA (comprimento acima de tudo) + checagem HIBP
// por k-anonimato. ANTI-ENUMERAÇÃO: responde SEMPRE a mesma tela ("confira seu
// e-mail"), exista ou não a conta — nunca revela se o e-mail já existe.
export const dynamic = "force-dynamic";

const MIN_SENHA = 10;

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim();
  const senha = String(form.get("senha") ?? "");

  if (!email || !email.includes("@")) return redir(request, "/criar-conta?erro=email");
  if (senha.length < MIN_SENHA) return redir(request, "/criar-conta?erro=curta");

  const hibp = await senhaVazada(senha);
  if (hibp.verificado && hibp.vazada) return redir(request, "/criar-conta?erro=vazada");

  const supabase = await criarClienteAuth();
  // emailRedirectTo é o fallback do fluxo padrão; o template com {{ .TokenHash }}
  // (configurado no dashboard) aterrissa em /confirmar/pronto p/ um POST inerte.
  await supabase.auth.signUp({
    email,
    password: senha,
    options: { emailRedirectTo: `${origemDe(request)}/confirmar/pronto` },
  });
  // SEMPRE a mesma resposta (a conta pode já existir — o GoTrue reenvia/silencia).
  return redir(request, "/confirmar/pendente");
}
