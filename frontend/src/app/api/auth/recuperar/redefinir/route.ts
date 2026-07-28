import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { senhaVazada } from "@/lib/auth/hibp";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Redefinição de senha: um passo. A página inerte /recuperar/redefinir coleta a
// senha NOVA + o token_hash (hidden) do link e POSTa aqui. Consumimos o token
// (verifyOtp type=recovery → sessão) e então trocamos a senha (com HIBP). Nunca
// consumir o token em GET (scanner queima o single-use).
export const dynamic = "force-dynamic";

const MIN_SENHA = 10;

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const tokenHash = String(form.get("token_hash") ?? "");
  const senha = String(form.get("senha") ?? "");
  if (!tokenHash) return redir(request, "/recuperar?erro=link");
  if (senha.length < MIN_SENHA) {
    return redir(request, `/recuperar/redefinir?token_hash=${encodeURIComponent(tokenHash)}&erro=curta`);
  }

  const hibp = await senhaVazada(senha);
  if (hibp.verificado && hibp.vazada) {
    return redir(request, `/recuperar/redefinir?token_hash=${encodeURIComponent(tokenHash)}&erro=vazada`);
  }

  const supabase = await criarClienteAuth();
  const { error: erroToken } = await supabase.auth.verifyOtp({
    token_hash: tokenHash,
    type: "recovery",
  });
  if (erroToken) return redir(request, "/recuperar?erro=expirado");

  const { error: erroSenha } = await supabase.auth.updateUser({ password: senha });
  if (erroSenha) return redir(request, "/recuperar?erro=troca");
  return redir(request, "/conta?ok=senha");
}
