# Fortaleza — Reconhecimento & Evidências de Scan (Fase 0)

> Base imutável: `origin/master` @ `4790479` (PR #43 "Arremate" = produção viva).
> Worktree de trabalho: `C:/Users/conta/wt-fortaleza` (branch `feat/fortaleza`, criado de `origin/master`).
> Data da coleta: 2026-07-21. Todas as saídas abaixo são reais (regra de honestidade: só "passou" com a saída anexada).

## 1. Verdade do estado de git (crítico — diverge do que os docs assumem)

| Fato | Realidade medida |
|---|---|
| `origin/master` | `4790479` = PR #43 Arremate = **produção**. Correto e alcançável. |
| Checkout local `PROJETO/` | branch `feat/warm-cache-scheduler` @ `8119603`, **122 commits atrás** de origin/master; upstream **sumiu**. |
| Working tree `PROJETO/` | **sujo com WIP multiativo alheio** (1686 inserções não-commitadas) + stash `"não é meu — preservado"`. |
| Regra aplicada | **NÃO** tocar/checkout/stash na árvore compartilhada `PROJETO/` (ver [[projeto-raias-paralelas-worktree]]). Trabalho isolado em `wt-fortaleza`. |

**Consequência:** o baseline A/B confiável é `origin/master`, não o checkout local. Toda medição e teste rodou no worktree limpo.

## 2. Baseline de testes (regressão-zero de referência)

- Comando: `python -m pytest -q` no `wt-fortaleza/backend` (venv Python 3.13.14).
- Resultado: **1012 testes, todos verdes** (exit 0, zero FAILED/ERROR; contagem por dots de progresso = 1012).
- Observação: a linha-resumo final do pytest fica suprimida neste ambiente não-tty; a prova é o exit code 0 + contagem determinística de dots + 0 marcadores de falha.

## 3. Sondagem NÃO-DESTRUTIVA de produção (`https://tese-ai.vercel.app`)

Regras de engajamento respeitadas: só GET read-only, nosso domínio, sem exfiltração, gentileza entre requests. Script: `evidencias/prod_probe.py`.

### TLS
- `TLSv1.3`, cipher `TLS_AES_128_GCM_SHA256`.
- Cert: Google Trust Services, `*.vercel.app`, válido até `Sep 26 2026`. (Gerido pela Vercel.)

### Headers de segurança (6 rotas: `/`, `/como-funciona`, `/historico`, `/glossario`, `/sobre`, `/cobertura` — todas consistentes)
| Header | Valor | Veredito |
|---|---|---|
| Content-Security-Policy | `default-src 'self'; script-src 'self' 'nonce-…' 'strict-dynamic'; style-src 'self' 'nonce-…'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests` | **Forte.** Nonce **por-requisição** (confirmado: nonce diferente em cada rota), `strict-dynamic`, sem `unsafe-inline`/`eval`. |
| Strict-Transport-Security | `max-age=63072000; includeSubDomains; preload` | **Forte** (2 anos + preload). |
| X-Frame-Options | `DENY` | OK (reforça `frame-ancestors 'none'`). |
| X-Content-Type-Options | `nosniff` | OK. |
| Referrer-Policy | `strict-origin-when-cross-origin` | OK. |
| Permissions-Policy | `camera=(), microphone=(), geolocation=(), browsing-topics=()` | OK. |
| X-Powered-By | ausente (`poweredByHeader:false`) | OK (não vaza framework). |

**Gaps reais (severidade BAIXA):**
- `Cross-Origin-Opener-Policy` (COOP) — **ausente**. Recomendado `same-origin` (isolamento de contexto / defesa Spectre). Fonte: `next.config.ts` `securityHeaders`.
- `Cross-Origin-Resource-Policy` (CORP) — **ausente**. Recomendado `same-origin`.
- COEP fica **opcional** (pode quebrar carregamentos; só com necessidade concreta).
- `X-XSS-Protection` ausente é **CORRETO** pela orientação moderna (header depreciado) — **não** é gap.

**Onde corrigir (verificado):** `frontend/next.config.ts` → array `securityHeaders` (headers estáticos em `/(.*)`). Não interage com o nonce do `proxy.ts`; o app não tem popup cross-origin nem CDN, então `same-origin` é seguro. Candidato a onda de endurecimento (sem regressão visual).

## 4. Scanners estáticos (saída real anexada)

### `bandit -r app` (SAST backend, 14.704 LOC)
- **1 achado LOW / High-confidence**: `B311` em `services/scheduler.py:400` — `random.uniform(0, tick*0.1)` (jitter de tick do scheduler). **Já anotado** `# noqa: S311 (não-cripto)`. Não-cripto, benigno. **Backend efetivamente limpo de SAST.**

### `pip-audit` (env instalado)
- 3 CVEs em `mcp` 1.23.3 (CVE-2026-52870/52869/59950).
- **Disposição honesta:** `mcp` **não** está em `pyproject.toml` **nem em `uv.lock`** → é contaminação do venv de dev, **não embarca** no Railway. Backend não roda servidor MCP. **Não é exposição de produção.** Ação: higienizar o venv (recriar a partir do lock) — dívida de dev, não de prod.

### `npm audit --package-lock-only --omit=dev` (frontend, 75 deps de prod)
- 2 moderadas: `postcss <8.5.10` XSS via `</style>` não-escapado no CSS Stringify — **transitivo via `next`**.
- **Disposição honesta:** pré-existente e **conhecido** (registrado desde a missão Cinema). É dep de **build-time**, não runtime do cliente; o "fix" do audit rebaixaria `next` para 9.x (**breaking, inaceitável**). Ação correta: aguardar bump do `postcss` pelo `next`, ou `overrides` no lock quando houver versão compatível. Risco real baixo.

## 5. Discrepância documentação × produção (achado de governança)

`AGENTS.md` referencia como existentes: `PROJETO/docs/security/` (threat model, ASVS/OWASP, IR/LGPD), `PROJETO/SECURITY.md`, e `.github/workflows/security-scheduled.yml`.
**Em `origin/master` nada disso existe** (`docs/` vazio; CI só tem `ci.yml`). O hardening "Segurança Nível Bancário" (PR #30) **nunca foi mergeado em produção** — vive só na branch `feat/seguranca-nivel-bancario`. Material para o scorecard Fortaleza (documentação promete o que produção não tem).
