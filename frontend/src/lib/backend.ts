// O import abaixo FALHA O BUILD se este módulo entrar num client component —
// garante em tempo de compilação que a URL do backend nunca vai ao bundle.
import "server-only";

// Resolução SERVER-ONLY da URL do backend (route handlers e server components).
// `API_URL` tem precedência: é server-only e não entra no bundle do cliente.
// `NEXT_PUBLIC_API_URL` segue aceita para dev local, mas nunca é obrigatória.
// Em produção sem env configurada NÃO caímos em localhost: devolvemos null e quem
// chama responde um erro claro (config ausente ≠ backend fora do ar).
export function backendUrl(): string | null {
  const url = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL;
  if (url) return url.replace(/\/+$/, "");
  return process.env.NODE_ENV === "production" ? null : "http://localhost:8000";
}

// Segredo de perímetro X-Portaria (Vercel↔Railway) — server-only, nunca no bundle.
// Ausente em dev/local: o middleware do backend é no-op (fail-closed só em produção).
export function segredoPortaria(): string | undefined {
  return process.env.PORTARIA_SECRET;
}

// Cabeçalhos para chamar o backend AUTENTICADO (missão "A Portaria"): repassa o
// access token do usuário (o backend RE-valida por JWKS) + o perímetro X-Portaria.
export function cabecalhosAutenticados(accessToken: string | null): Record<string, string> {
  const h: Record<string, string> = {};
  if (accessToken) h["Authorization"] = `Bearer ${accessToken}`;
  const seg = segredoPortaria();
  if (seg) h["X-Portaria"] = seg;
  return h;
}
