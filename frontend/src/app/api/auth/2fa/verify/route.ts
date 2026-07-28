import { NextResponse, type NextRequest } from "next/server";

import { mesmaOrigem } from "@/lib/auth/csrf";
import { chamarBackend } from "@/lib/backend";
import { sessaoAtual } from "@/lib/auth/sessao";
import { criarClienteAuth, envAuth } from "@/lib/auth/supabaseServer";

// Confirma o enroll do TOTP (challenge+verify na MESMA invocação → aal2) e, com o token
// FRESCO aal2, pede ao FastAPI os códigos de recuperação. Devolve-os UMA vez ao wizard.
export const dynamic = "force-dynamic";

function j(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: NextRequest) {
  if (!mesmaOrigem(request)) return j({ ok: false, erro: "origem" }, 403);
  if (!envAuth()) return j({ ok: false, erro: "indisponível" }, 503);
  if (!(await sessaoAtual())) return j({ ok: false, erro: "sessao" }, 401); // gate explícito
  const { factorId, code } = (await request.json().catch(() => ({}))) as {
    factorId?: string;
    code?: string;
  };
  if (!factorId || !code) return j({ ok: false, erro: "dados" }, 400);

  const supabase = await criarClienteAuth();
  const { data: ch, error: e1 } = await supabase.auth.mfa.challenge({ factorId });
  if (e1 || !ch) return j({ ok: false, erro: "desafio" }, 400);
  const { error: e2 } = await supabase.auth.mfa.verify({ factorId, challengeId: ch.id, code });
  if (e2) return j({ ok: false, erro: "codigo" }, 400);

  // Já aal2: gera os códigos de recuperação com o token FRESCO (mesmo client).
  let codigos: string[] = [];
  try {
    const { data: s } = await supabase.auth.getSession();
    const r = await chamarBackend("/conta/mfa/codigos", s.session?.access_token ?? null, {
      method: "POST",
    });
    if (r.ok) codigos = ((await r.json()) as { codigos?: string[] }).codigos ?? [];
  } catch {
    // Sem os códigos agora, o usuário pode gerar depois em /conta/dois-fatores.
  }
  return j({ ok: true, codigos });
}
