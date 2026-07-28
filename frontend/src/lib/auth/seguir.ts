// Validação do destino pós-login `?seguir=` (anti open-redirect).
//
// Só aceita PATH RELATIVO da própria app: começa com uma barra e NÃO com duas
// (`//host` é URL absoluta protocol-relative — vetor clássico de open-redirect),
// sem barra invertida (que alguns browsers normalizam para `/`). O `next=` dos
// exemplos da doc do Supabase tem essa falha se copiado cru — por isso a guarda.

const SEGURO = /^\/(?!\/)[^\\]*$/;

export function validaSeguir(bruto: unknown, padrao = "/historico"): string {
  if (typeof bruto !== "string" || !SEGURO.test(bruto)) return padrao;
  return bruto;
}
