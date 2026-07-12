// UUID v4-ish (formato canônico 8-4-4-4-12) usado como `id` de tese —
// fonte única, reusada tanto por src/app/tese/page.tsx (server component,
// valida o searchParam antes de repassar ao client) quanto pelo route
// handler src/app/api/teses/[id]/route.ts (valida antes de repassar ao
// backend — evita amplificar tráfego lixo/DoS barato contra o FastAPI).
export const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
