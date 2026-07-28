// Helpers dos route handlers de auth (server-only).
import "server-only";

import { NextResponse, type NextRequest } from "next/server";

// Redirect PRG (POST→303→GET) SEMPRE com no-store: toda resposta que escreve
// cookie de sessão precisa disso, senão um CDN/proxy poderia cachear o Set-Cookie
// de um usuário e servir para outro. `path` é relativo à origem da requisição.
export function redir(request: NextRequest, path: string): NextResponse {
  const res = NextResponse.redirect(new URL(path, request.url), 303);
  res.headers.set("Cache-Control", "no-store");
  return res;
}

export function recusa(mensagem = "requisição inválida", status = 400): NextResponse {
  return NextResponse.json(
    { detail: mensagem },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

// Origem absoluta (https://host) da requisição — para os redirects de e-mail/OAuth.
export function origemDe(request: NextRequest): string {
  return new URL(request.url).origin;
}
