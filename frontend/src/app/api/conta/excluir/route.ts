import { type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa, redir } from "@/lib/auth/http";
import { chamarBackend } from "@/lib/backend";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// LGPD (apagamento): exclui a conta. Travas: reautenticação da senha + confirmação
// digitada ("EXCLUIR") + step-up 2FA (se houver fator, sobe para aal2 com o código — o
// FastAPI exige aal2). Depois o FastAPI apaga o usuário (FK CASCADE limpa tudo).
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const form = await request.formData();
  const senha = String(form.get("senha") ?? "");
  const confirmacao = String(form.get("confirmacao") ?? "").trim();
  const code = String(form.get("code") ?? "").trim();
  if (confirmacao !== "EXCLUIR") return redir(request, "/conta/excluir?erro=confirmacao");

  const supabase = await criarClienteAuth();
  const { data: u } = await supabase.auth.getUser();
  const email = u.user?.email;
  if (!email) return redir(request, "/entrar");
  const { error: eAuth } = await supabase.auth.signInWithPassword({ email, password: senha });
  if (eAuth) return redir(request, "/conta/excluir?erro=senha");

  // Step-up 2FA (se houver fator verificado): o FastAPI exige aal2 para excluir.
  const { data: fatores, error: eFatores } = await supabase.auth.mfa.listFactors();
  // MFA-01 (fail-CLOSED): erro em listFactors não pode pular o step-up (o backstop aal2 do
  // FastAPI ainda pega, mas não confiamos numa camada só).
  if (eFatores) return redir(request, "/conta/excluir?erro=2fa_indisponivel");
  const totp = (fatores?.totp ?? []).find((f) => f.status === "verified");
  if (totp) {
    if (!code) return redir(request, "/conta/excluir?erro=2fa");
    const { data: ch } = await supabase.auth.mfa.challenge({ factorId: totp.id });
    if (!ch) return redir(request, "/conta/excluir?erro=2fa");
    const { error } = await supabase.auth.mfa.verify({
      factorId: totp.id,
      challengeId: ch.id,
      code,
    });
    if (error) return redir(request, "/conta/excluir?erro=codigo");
  }

  const { data: s } = await supabase.auth.getSession();
  try {
    const r = await chamarBackend("/conta/excluir", s.session?.access_token ?? null, {
      method: "POST",
    });
    if (!r.ok) return redir(request, "/conta/excluir?erro=falha");
  } catch {
    return redir(request, "/conta/excluir?erro=indisponivel");
  }
  await supabase.auth.signOut({ scope: "global" });
  return redir(request, "/?conta=excluida");
}
