// Sessão do usuário (server-only). Authz SEMPRE por `getClaims()` (valida a
// assinatura do JWT localmente via JWKS) ou `getUser()` (server-confirmed, ciente
// de revogação) — NUNCA `getSession()` sozinho, que só lê o cookie e confia.
import "server-only";

import { criarClienteAuth } from "@/lib/auth/supabaseServer";

export type Sessao = {
  userId: string;
  email: string | null;
  aal: string | null;
  accessToken: string | null;
};

// Sessão validada ou null. `getClaims()` valida a assinatura (chave assimétrica do
// projeto); o access token vem do cookie (o backend RE-valida por JWKS na Onda 1,
// então repassar o token lido é seguro — a fonte de verdade é o backend).
export async function sessaoAtual(): Promise<Sessao | null> {
  const supabase = await criarClienteAuth();
  const { data, error } = await supabase.auth.getClaims();
  const claims = data?.claims as Record<string, unknown> | undefined;
  if (error || !claims?.sub) return null;
  const { data: s } = await supabase.auth.getSession();
  return {
    userId: String(claims.sub),
    email: typeof claims.email === "string" ? claims.email : null,
    aal: typeof claims.aal === "string" ? claims.aal : null,
    accessToken: s.session?.access_token ?? null,
  };
}

// Confirmação FORTE para operações sensíveis (troca de e-mail/senha, exclusão):
// `getUser()` bate no GoTrue e enxerga revogação (um access token revogado ainda
// valeria até o exp na validação local). Usada nas rotas da Onda 3.
export async function usuarioConfirmado(): Promise<{ id: string; email: string | null } | null> {
  const supabase = await criarClienteAuth();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) return null;
  return { id: data.user.id, email: data.user.email ?? null };
}

// Sessão CONFIRMADA pelo GoTrue (`getUser` — CIENTE DE REVOGAÇÃO) + o access token para
// repassar ao backend. Para operações de ALTO VALOR (exportar LGPD — SESS-01): `getClaims`
// valida a assinatura mas NÃO enxerga revogação até o exp; `getUser` bate no GoTrue e vê o
// "encerrar todas as sessões" na hora.
export async function sessaoConfirmada(): Promise<Sessao | null> {
  const supabase = await criarClienteAuth();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) return null;
  const { data: s } = await supabase.auth.getSession();
  return {
    userId: data.user.id,
    email: data.user.email ?? null,
    aal: null, // não usado aqui — o backstop aal2 é imposto pelo FastAPI no /conta/exportar
    accessToken: s.session?.access_token ?? null,
  };
}
