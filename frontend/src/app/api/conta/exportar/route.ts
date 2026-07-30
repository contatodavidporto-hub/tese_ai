import { NextResponse, type NextRequest } from "next/server";

import { recusa, redir } from "@/lib/auth/http";
import { chamarBackend } from "@/lib/backend";
import { sessaoConfirmada } from "@/lib/auth/sessao";
import { envAuth } from "@/lib/auth/supabaseServer";

// LGPD (portabilidade): baixa TODOS os dados do usuário em JSON. GET (leitura, sem
// efeito colateral) via <a download>. Sem sessão → login. O FastAPI exige aal2 (para
// quem tem 2FA) e monta o JSON.
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  if (!envAuth()) return recusa("serviço de contas indisponível", 503);
  // SESS-01: exportar é dado LGPD (ALTO VALOR) — confirma por getUser (CIENTE DE
  // REVOGAÇÃO), não só getClaims (que valida a assinatura mas não vê "encerrar todas as
  // sessões" até o exp). sessaoConfirmada() bate no GoTrue e traz o token p/ o backend.
  const sessao = await sessaoConfirmada();
  if (!sessao) return redir(request, "/entrar?seguir=/conta/dados");
  try {
    const r = await chamarBackend("/conta/exportar", sessao.accessToken, {});
    if (!r.ok) {
      if (r.status === 403) return redir(request, "/conta/dados?erro=aal2");
      return recusa("não foi possível exportar seus dados", 502);
    }
    return new NextResponse(await r.text(), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": 'attachment; filename="tese-ai-meus-dados.json"',
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return recusa("serviço indisponível", 502);
  }
}
