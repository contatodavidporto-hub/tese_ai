import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { validaSeguir } from "@/lib/auth/seguir";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Login por e-mail+senha (BFF: o navegador nunca fala com o GoTrue). Form nativo
// POST→303→GET. Mensagens GENÉRICAS (anti-enumeração): "credenciais" não distingue
// e-mail inexistente de senha errada.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim();
  const senha = String(form.get("senha") ?? "");
  const seguir = validaSeguir(form.get("seguir"), "/historico");
  if (!email || !senha) return redir(request, "/entrar?erro=campos");

  const supabase = await criarClienteAuth();
  const { error } = await supabase.auth.signInWithPassword({ email, password: senha });
  if (error) {
    // ANTI-ENUMERAÇÃO (correção do red-team): NÃO distinguir "e-mail não confirmado" de
    // "credenciais erradas" — o redirect distinto revelava que o e-mail existe. Sempre
    // genérico; a mensagem de /entrar traz um lembrete de confirmação para TODOS.
    return redir(request, "/entrar?erro=credenciais");
  }

  // Exige o desafio 2FA SÓ se houver fator TOTP VERIFICADO (correção do red-team:
  // decidir por listFactors, nunca por nextLevel — um fator só enrolado trancaria
  // o usuário). Na Onda 2 ninguém tem fator; o passo nasce completo na Onda 3.
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  const temVerificado = (fatores?.totp ?? []).some((f) => f.status === "verified");
  if (temVerificado) {
    return redir(request, `/entrar/desafio?seguir=${encodeURIComponent(seguir)}`);
  }

  return redir(request, seguir);
}
