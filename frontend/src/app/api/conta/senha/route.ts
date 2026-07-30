import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { senhaVazada } from "@/lib/auth/hibp";
import { recusa, redir } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Troca de senha: REAUTENTICA a senha atual (signInWithPassword) antes de trocar +
// HIBP na nova. Operação sensível — a reautenticação é a trava.
export const dynamic = "force-dynamic";

const MIN_SENHA = 12; // ASVS V2.1.1 (piso de senha 12)

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const atual = String(form.get("atual") ?? "");
  const nova = String(form.get("nova") ?? "");
  if (nova.length < MIN_SENHA) return redir(request, "/conta/senha?erro=curta");
  const hibp = await senhaVazada(nova);
  if (hibp.verificado && hibp.vazada) return redir(request, "/conta/senha?erro=vazada");

  const supabase = await criarClienteAuth();
  const { data: u } = await supabase.auth.getUser();
  const email = u.user?.email;
  if (!email) return redir(request, "/entrar");
  const { error: eAuth } = await supabase.auth.signInWithPassword({ email, password: atual });
  if (eAuth) return redir(request, "/conta/senha?erro=atual");

  // Step-up 2FA (correção da revisão de segurança): se há fator verificado, exige o
  // código TOTP ANTES de trocar — senão quem tem só a senha (o exato cenário que o 2FA
  // deveria deter) trocaria a senha sozinho, derrubando a conta.
  const { data: fatores, error: eFatores } = await supabase.auth.mfa.listFactors();
  // MFA-01 (fail-CLOSED): nunca inferir "sem 2FA" de uma chamada que FALHOU — senão um
  // erro transitório de listFactors pularia o step-up e deixaria trocar a senha com aal1.
  if (eFatores) return redir(request, "/conta/senha?erro=2fa_indisponivel");
  const totp = (fatores?.totp ?? []).find((f) => f.status === "verified");
  if (totp) {
    const code = String(form.get("code") ?? "").trim();
    if (!code) return redir(request, "/conta/senha?erro=2fa");
    const { data: ch } = await supabase.auth.mfa.challenge({ factorId: totp.id });
    if (!ch) return redir(request, "/conta/senha?erro=2fa");
    const { error: eMfa } = await supabase.auth.mfa.verify({
      factorId: totp.id,
      challengeId: ch.id,
      code,
    });
    if (eMfa) return redir(request, "/conta/senha?erro=codigo");
  }

  const { error } = await supabase.auth.updateUser({ password: nova });
  if (error) return redir(request, "/conta/senha?erro=troca");
  return redir(request, "/conta?ok=senha");
}
