import { NextResponse, type NextRequest } from "next/server";

// CSP com nonce POR REQUISIÇÃO — padrão do Next 16 (arquivo `proxy.ts`, que
// substitui o antigo `middleware.ts`). O Next injeta automaticamente o nonce
// nos seus próprios scripts/estilos inline e nos bundles da página.
// Doc instalada: node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md
//
// Em desenvolvimento o React usa `eval` para debug → exige 'unsafe-eval' (e
// estilos inline). Em produção nada disso é necessário: política estrita.
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";

  const csp = `
    default-src 'self';
    script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""};
    style-src 'self' 'nonce-${nonce}'${isDev ? " 'unsafe-inline'" : ""};
    img-src 'self' blob: data:;
    font-src 'self';
    connect-src 'self';
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
    upgrade-insecure-requests;
  `
    .replace(/\s{2,}/g, " ")
    .trim();

  // Disponibiliza o nonce ao SSR (via header da requisição) e fixa o CSP na resposta.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    // Roda em tudo, exceto rotas de API, assets estáticos e prefetches do next/link.
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
