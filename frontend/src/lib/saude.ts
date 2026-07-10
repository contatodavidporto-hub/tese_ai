import "server-only";

import { backendUrl } from "./backend";

// Health-check do backend (server-only). Timeout curto: o chip é informativo,
// nunca pode segurar a página (o chamador deve envolver em <Suspense>).
export async function backendSaudavel(): Promise<boolean> {
  const apiUrl = backendUrl();
  if (!apiUrl) return false;
  try {
    const res = await fetch(`${apiUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { status?: string };
    return data.status === "ok";
  } catch {
    return false;
  }
}
