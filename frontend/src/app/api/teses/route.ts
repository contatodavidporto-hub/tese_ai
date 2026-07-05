import { NextResponse, type NextRequest } from "next/server";

import { backendUrl } from "@/lib/backend";

// Proxy SERVER-SIDE para o backend FastAPI.
// O CSP do app (src/proxy.ts) tem `connect-src 'self'`, então o NAVEGADOR só pode
// chamar a MESMA origem. O cliente chama /api/teses; este handler repassa ao backend.
// Doc instalada: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/route.md

// GET de Route Handler é dinâmico por padrão no Next 16; explicitamos para o POST proxy.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const apiUrl = backendUrl();
  if (!apiUrl) {
    return NextResponse.json(
      { detail: "Backend não configurado (defina API_URL no ambiente do servidor)." },
      { status: 502 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "Corpo da requisição inválido (JSON esperado)." },
      { status: 400 },
    );
  }

  const ticker =
    typeof body === "object" && body !== null && "ticker" in body
      ? (body as { ticker?: unknown }).ticker
      : undefined;

  if (typeof ticker !== "string" || ticker.trim() === "") {
    return NextResponse.json(
      { detail: "Campo 'ticker' é obrigatório." },
      { status: 400 },
    );
  }

  // Repassa o IP real do cliente (a Vercel injeta x-forwarded-for): o backend
  // aplica o rate-limit POR USUÁRIO em vez de agrupar todos no IP de egress.
  const xff = request.headers.get("x-forwarded-for");

  try {
    const upstream = await fetch(`${apiUrl}/teses`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(xff ? { "x-forwarded-for": xff } : {}),
      },
      body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
      cache: "no-store",
      // Sem timeout a função serverless ficaria pendurada até o maxDuration.
      signal: AbortSignal.timeout(10_000),
    });

    const text = await upstream.text();
    const data = text ? safeParse(text) : null;

    return NextResponse.json(data ?? { detail: text }, {
      status: upstream.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Não foi possível contatar o backend de teses." },
      { status: 502 },
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
