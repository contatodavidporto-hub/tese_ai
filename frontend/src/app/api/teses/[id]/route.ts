import { NextResponse, type NextRequest } from "next/server";

import { backendUrl } from "@/lib/backend";
import { UUID_RE } from "@/lib/ids";

// Resposta é sempre sensível a instante-a-instante (status da tese em
// processamento) e pode conter dado individualizado por requisição —
// nunca deve ser guardada por cache de navegador/CDN.
const SEM_CACHE: Record<string, string> = { "Cache-Control": "no-store" };

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
      { status: 502, headers: SEM_CACHE },
    );
  }

  const { id } = await params;

  if (!id) {
    return NextResponse.json(
      { detail: "id ausente." },
      { status: 400, headers: SEM_CACHE },
    );
  }

  // Defesa em profundidade: só repassa ao backend algo com formato de UUID —
  // corta aqui tráfego lixo/varredura antes de amplificar contra o FastAPI.
  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { detail: "id fora do formato esperado (UUID)." },
      { status: 400, headers: SEM_CACHE },
    );
  }

  // Repassa o x-forwarded-for para log/auditoria no backend (a chave do
  // rate-limit usa o hop confiável — ver app/core/ratelimit.py).
  const xff = request.headers.get("x-forwarded-for");

  try {
    const upstream = await fetch(
      `${apiUrl}/teses/${encodeURIComponent(id)}`,
      {
        headers: { ...(xff ? { "x-forwarded-for": xff } : {}) },
        cache: "no-store",
        // Sem timeout a função serverless ficaria pendurada até o maxDuration.
        signal: AbortSignal.timeout(10_000),
      },
    );

    const text = await upstream.text();
    const data = text ? safeParse(text) : null;

    return NextResponse.json(data ?? { detail: text }, {
      status: upstream.status,
      headers: SEM_CACHE,
    });
  } catch {
    return NextResponse.json(
      { detail: "Não foi possível contatar o backend de teses." },
      { status: 502, headers: SEM_CACHE },
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
