import { NextResponse, type NextRequest } from "next/server";

// Proxy SERVER-SIDE para o backend FastAPI.
// O CSP do app (src/proxy.ts) tem `connect-src 'self'`, então o NAVEGADOR só pode
// chamar a MESMA origem. O cliente chama /api/teses; este handler repassa ao backend.
// Doc instalada: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/route.md
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.API_URL ??
  "http://localhost:8000";

// GET de Route Handler é dinâmico por padrão no Next 16; explicitamos para o POST proxy.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
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

  try {
    const upstream = await fetch(`${API_URL}/teses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
      cache: "no-store",
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
