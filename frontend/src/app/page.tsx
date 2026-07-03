import Link from "next/link";

// Renderização dinâmica: necessária para o CSP com nonce por requisição (src/proxy.ts)
// ser aplicado em cada resposta. O fetch no-store abaixo já tornaria a rota dinâmica;
// deixamos explícito para garantir o nonce.
export const dynamic = "force-dynamic";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Health = { ok: boolean; detail: string };

async function getHealth(): Promise<Health> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false, detail: `HTTP ${res.status}` };
    const data = (await res.json()) as { status?: string };
    return { ok: data.status === "ok", detail: data.status ?? "sem status" };
  } catch {
    return { ok: false, detail: "offline" };
  }
}

export default async function Home() {
  const health = await getHealth();
  const label = health.ok ? "ok" : health.detail;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-neutral-50 p-8 dark:bg-neutral-950">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
          Tese AI
        </h1>
        <p className="max-w-md text-sm text-neutral-500 dark:text-neutral-400">
          Teses de investimento estruturadas e auditáveis — fundamentos + macro +
          geopolítica, com cada afirmação rastreável.
        </p>
      </div>

      <Link
        href="/tese"
        className="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-neutral-400/50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
      >
        Gerar tese
      </Link>

      <div className="flex items-center gap-3 rounded-xl border border-neutral-200 bg-white px-5 py-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
        <span
          className={`inline-block h-3 w-3 rounded-full ${health.ok ? "bg-emerald-500" : "bg-red-500"}`}
          aria-hidden
        />
        <span className="font-mono text-sm text-neutral-700 dark:text-neutral-300">
          backend: {label}
        </span>
      </div>

      <p className="font-mono text-xs text-neutral-400">{API_URL}/health</p>
    </main>
  );
}
