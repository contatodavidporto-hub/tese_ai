import { NextResponse, type NextRequest } from "next/server";

import { backendUrl } from "@/lib/backend";
import { TICKER_RE } from "@/lib/tickers";

// Resposta carrega o resultado (ou erro) de UMA submissão específica —
// nunca deve ser guardada por cache de navegador/CDN.
const SEM_CACHE: Record<string, string> = { "Cache-Control": "no-store" };

// Proxy SERVER-SIDE para o backend FastAPI.
// O CSP do app (src/proxy.ts) tem `connect-src 'self'`, então o NAVEGADOR só pode
// chamar a MESMA origem. O cliente chama /api/teses; este handler repassa ao backend.
// Doc instalada: node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/route.md

// GET de Route Handler é dinâmico por padrão no Next 16; explicitamos para o POST proxy.
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const apiUrl = backendUrl();
  if (!apiUrl) {
    console.error("api/teses: API_URL ausente no ambiente do servidor");
    return NextResponse.json(
      { detail: "Serviço temporariamente indisponível — tente novamente em instantes." },
      { status: 502, headers: SEM_CACHE },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "Corpo da requisição inválido (JSON esperado)." },
      { status: 400, headers: SEM_CACHE },
    );
  }

  const ticker =
    typeof body === "object" && body !== null && "ticker" in body
      ? (body as { ticker?: unknown }).ticker
      : undefined;

  if (typeof ticker !== "string" || ticker.trim() === "") {
    return NextResponse.json(
      { detail: "Campo 'ticker' é obrigatório." },
      { status: 400, headers: SEM_CACHE },
    );
  }

  // Espelho da validação do backend (app/schemas/tese.py): corta lixo aqui e
  // não amplifica abuso até o FastAPI (defesa em profundidade, mesma união
  // B3 ∪ Tesouro Direto — TICKER_RE de lib/tickers.ts, fonte única do front).
  // min_length=4/max_length=16 espelham o `Field` do Pydantic no backend.
  const normalizado = ticker.trim().toUpperCase();
  if (
    normalizado.length < 4 ||
    normalizado.length > 16 ||
    !TICKER_RE.test(normalizado)
  ) {
    return NextResponse.json(
      {
        detail:
          "Ticker fora do formato aceito (ex.: PETR4, HGLG11, ou código do Tesouro Direto como TD-IPCA-2035).",
      },
      { status: 400, headers: SEM_CACHE },
    );
  }

  // Repassa o x-forwarded-for (a Vercel injeta o IP real do cliente) para fins
  // de log/auditoria no backend. A CHAVE do rate-limit usa o hop confiável (IP
  // de egress deste proxy) até existir login — ver app/core/ratelimit.py.
  const xff = request.headers.get("x-forwarded-for");

  try {
    const upstream = await fetch(`${apiUrl}/teses`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(xff ? { "x-forwarded-for": xff } : {}),
      },
      body: JSON.stringify({ ticker: normalizado }),
      cache: "no-store",
      // Sem timeout a função serverless ficaria pendurada até o maxDuration.
      signal: AbortSignal.timeout(10_000),
    });

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
