import { NextResponse } from "next/server";

import { sessaoAtual } from "@/lib/auth/sessao";

// Estado da conta para a ILHA client-side do Header (menu Entrar/Conta). Same-origin
// (a CSP `connect-src 'self'` permite este fetch) e no-store: mantém as páginas
// públicas cookie-free no HTML server-rendered (o estado logado é resolvido no
// cliente, sem variar o cache do ISR nem envenenar CDN).
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const s = await sessaoAtual();
    return NextResponse.json(
      { logado: !!s, email: s?.email ?? null },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json(
      { logado: false, email: null },
      { headers: { "Cache-Control": "no-store" } },
    );
  }
}
