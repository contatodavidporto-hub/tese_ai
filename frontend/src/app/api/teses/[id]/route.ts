import { NextResponse, type NextRequest } from "next/server";

// Proxy SERVER-SIDE para GET /teses/{id} do backend FastAPI.
// No Next 16, `params` do Route Handler é uma Promise — precisa de await.
// Doc instalada: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/dynamic-routes.md
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.API_URL ??
  "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ detail: "id ausente." }, { status: 400 });
  }

  try {
    const upstream = await fetch(
      `${API_URL}/teses/${encodeURIComponent(id)}`,
      { cache: "no-store" },
    );

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
