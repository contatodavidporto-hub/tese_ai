import type { NextConfig } from "next";

// Headers de segurança ESTÁTICOS, aplicados a toda resposta ("/(.*)").
// O Content-Security-Policy (com nonce por requisição) é definido em src/proxy.ts,
// pois exige um valor único por request + renderização dinâmica.
// Refs (docs instaladas do Next 16):
//   node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/headers.md
//   node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md
const securityHeaders = [
  // Força HTTPS por ~2 anos, incl. subdomínios (fintech / CWE-319).
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  // Impede MIME sniffing (único valor válido: nosniff).
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Anti-clickjacking (reforçado por `frame-ancestors 'none'` no CSP).
  { key: "X-Frame-Options", value: "DENY" },
  // Vaza o mínimo de referrer ao navegar para outra origem.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Desliga APIs sensíveis do navegador que o app não usa.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
  },
  // Sem prefetch de DNS para terceiros.
  { key: "X-DNS-Prefetch-Control", value: "off" },
  // Isola o contexto de navegação (cross-origin isolation / defesa Spectre). O
  // app não abre popup cross-origin nem usa window.opener — same-origin é seguro.
  // (COEP fica de fora de propósito: pode quebrar carregamentos e não há ganho concreto.)
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // Impede que outras origens embutam nossos recursos (defesa de vazamento
  // cross-origin). Servimos tudo same-origin; nenhum terceiro embute nossos assets.
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  // Não revelar o framework no header `X-Powered-By`.
  poweredByHeader: false,
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
