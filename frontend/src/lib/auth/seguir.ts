// Validação do destino pós-login `?seguir=` (anti open-redirect).
//
// Um regex de proibição não basta: o parser WHATWG (`new URL()`) REMOVE tab/LF/CR
// antes de parsear, então `/\t/evil.com` escaparia de uma blocklist e viraria
// `//evil.com` (absoluta protocol-relative). A técnica robusta (OWASP): RESOLVER
// contra uma âncora neutra e aceitar só se a origem NÃO mudou — deixa o próprio
// parser normalizar e barra tudo que virou absoluto/protocol-relative/com controle.
export function validaSeguir(bruto: unknown, padrao = "/historico"): string {
  if (typeof bruto !== "string") return padrao;
  try {
    const base = "https://x.invalid";
    const resolvido = new URL(bruto, base);
    if (resolvido.origin !== base) return padrao; // virou absoluto/protocol-relative → recusa
    return resolvido.pathname + resolvido.search + resolvido.hash;
  } catch {
    return padrao;
  }
}
