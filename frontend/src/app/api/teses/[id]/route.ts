import { NextResponse, type NextRequest } from "next/server";

import { cabecalhosAutenticados, backendUrl } from "@/lib/backend";
import { sessaoAtual } from "@/lib/auth/sessao";

// Proxy SERVER-SIDE para GET /teses/{id} do backend FastAPI.
// No Next 16, `params` do Route Handler é uma Promise — precisa de await.
// Doc instalada: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/dynamic-routes.md

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const apiUrl = backendUrl();
  if (!apiUrl) {
    console.error("api/teses/[id]: API_URL ausente no ambiente do servidor");
    return NextResponse.json(
      { detail: "Serviço temporariamente indisponível — tente novamente em instantes." },
      { status: 502 },
    );
  }

  const { id } = await params;

  if (!id) {
    return NextResponse.json({ detail: "id ausente." }, { status: 400 });
  }

  // Repassa o x-forwarded-for para log/auditoria no backend (a chave do
  // rate-limit usa o hop confiável — ver app/core/ratelimit.py).
  const xff = request.headers.get("x-forwarded-for");
  // Leitura público-ou-do-dono: se logado, repassa o Bearer (o backend deixa o dono
  // ler a PRÓPRIA tese privada); anônimo lê só o acervo público. X-Portaria sempre.
  const sessao = await sessaoAtual().catch(() => null);

  try {
    const upstream = await fetch(
      `${apiUrl}/teses/${encodeURIComponent(id)}`,
      {
        headers: {
          ...(xff ? { "x-forwarded-for": xff } : {}),
          ...cabecalhosAutenticados(sessao?.accessToken ?? null),
        },
        cache: "no-store",
        // Sem timeout a função serverless ficaria pendurada até o maxDuration.
        signal: AbortSignal.timeout(10_000),
      },
    );

    const text = await upstream.text();
    const data = text ? safeParse(text) : null;

    // no-store: esta rota pode devolver a tese PRIVADA do dono (leitura
    // público-ou-do-dono, ver comentário acima) — sem o header, a resposta é
    // elegível a heurística de cache do navegador/CDN (sem Cache-Control nem
    // Expires) e ao disk cache/bfcache, o que vazaria o conteúdo da tese para
    // quem usar o mesmo navegador depois (computador compartilhado). Mesma
    // defesa já aplicada em estado/exportar/2fa/* — faltava aqui.
    return NextResponse.json(data ?? { detail: text }, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Não foi possível contatar o backend de teses." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
