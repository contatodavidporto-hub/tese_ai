import { NextResponse, type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { recusa } from "@/lib/auth/http";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Inicia o enroll de um fator TOTP (GoTrue MFA, server-side). Devolve o QR (data-URI
// SVG) + o secret para o app autenticador. Limpa fatores TOTP NÃO-verificados antes
// (evita o teto de 10 fatores e conflito de friendlyName). Chamado pela ilha do wizard
// via fetch same-origin (a CSP `connect-src 'self'` permite).
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return recusa("origem inválida", 403);
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);

  const supabase = await criarClienteAuth();
  const { data: fatores } = await supabase.auth.mfa.listFactors();
  for (const f of fatores?.totp ?? []) {
    if (f.status !== "verified") await supabase.auth.mfa.unenroll({ factorId: f.id });
  }

  const { data, error } = await supabase.auth.mfa.enroll({
    factorType: "totp",
    friendlyName: `tese-ai-${Date.now()}`,
  });
  if (error || !data) return recusa("não foi possível iniciar o 2FA", 400);

  return NextResponse.json(
    { factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret },
    { headers: { "Cache-Control": "no-store" } },
  );
}
