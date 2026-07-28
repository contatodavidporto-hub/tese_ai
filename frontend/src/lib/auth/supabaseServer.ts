// Cliente Supabase Auth SERVER-ONLY (missão "A Portaria", Onda 2).
// O import "server-only" FALHA O BUILD se este módulo vazar para um client
// component — garante em compilação que a chave e o cliente do GoTrue nunca vão
// ao bundle do navegador. É o mesmo padrão de src/lib/backend.ts.
//
// Por que server-only: a CSP `connect-src 'self'` (src/proxy.ts) PROÍBE o
// navegador de falar com *.supabase.co. Toda conversa com o GoTrue acontece aqui,
// no servidor Next; os cookies de sessão são httpOnly (o navegador nunca lê o
// token por JS). Isso mantém a CSP diff-zero por construção.
import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Env SEM prefixo NEXT_PUBLIC (server-only, nunca no bundle) — mesma convenção de
// API_URL. Aceita PUBLISHABLE ou ANON (chaves públicas do GoTrue; seguras server-side).
export function envAuth(): { url: string; key: string } | null {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY ?? process.env.SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return { url, key };
}

// ⚠ NUNCA instanciar o cliente em escopo de módulo: no Fluid compute da Vercel as
// instâncias são reusadas entre requisições e a sessão VAZARIA entre usuários
// (aviso literal da doc do @supabase/ssr). Sempre POR REQUISIÇÃO, dentro do handler.
export async function criarClienteAuth() {
  const env = envAuth();
  if (!env) throw new Error("SUPABASE_URL / chave ausentes no ambiente do servidor.");
  const jar = await cookies();
  return createServerClient(env.url, env.key, {
    cookies: {
      getAll: () => jar.getAll(),
      setAll: (paraSetar) => {
        // FORÇA httpOnly/secure/sameSite=lax/path — o default do @supabase/ssr
        // supõe um browser client (não é o nosso caso); sem httpOnly o token
        // ficaria legível por JS. SameSite=Lax deixa o callback OAuth e os links
        // de e-mail (GET top-level) cruzarem; a defesa CSRF mora no Origin-check.
        for (const { name, value, options } of paraSetar) {
          jar.set(name, value, {
            ...options,
            httpOnly: true,
            secure: true,
            sameSite: "lax",
            path: "/",
          });
        }
      },
    },
  });
}
