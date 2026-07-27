# Fortaleza — Baseline de regressão + SAST + governança (Fase 1, sessão 2026-07-21b)

> Continuação da Fase 0 (`00-recon-e-scans.md`). Todas as saídas abaixo foram
> reproduzidas **nesta sessão** no worktree `C:/Users/conta/wt-fortaleza`
> (`feat/fortaleza` = `origin/master` @ `4790479`), com o venv
> `PROJETO/backend/.venv` (Python 3.13.14). Regra de honestidade: só "passou"
> com a saída anexada.

## 1. Baseline de regressão-zero (referência própria, não herdada)

- Comando: `pytest -q --junitxml` com `PYTHONPATH` fixado no worktree (derrota o
  editable `.pth` `_editable_impl_tese_ai_backend` que aponta para o checkout
  compartilhado sujo — confirmado que `import app` resolve para
  `wt-fortaleza/backend/app`).
- **Resultado (JUnit XML, à prova de supressão de tty):** `tests=1012
  failures=0 errors=0 skipped=0`, tempo 16,5 s. Exit 0.
- Artefato: `evidencias/baseline-junit.xml`. **Este é o baseline A imutável**;
  toda onda de refactor prova `≥1012` verdes.

## 2. SAST estático (código nosso, não o `.venv`)

| Scanner | Escopo | Resultado | Evidência |
|---|---|---|---|
| bandit `-r app -ll` | backend/app (14.704 LOC) | **0 medium+**; 1 LOW/High-conf (`B311` jitter do scheduler, já `# noqa`, não-cripto, benigno) | `sast-bandit.txt` |
| semgrep `p/security-audit p/secrets p/python p/javascript` | backend/app + frontend/src (163 arquivos, 323 regras) | **0 findings (0 blocking)** | `sast-semgrep.log` / `.json` |
| pip-audit `--skip-editable` | deps Python | 3 CVEs **só em `mcp` 1.23.3** (contaminação do venv de dev; **não** está em `pyproject`/`uv.lock` → não embarca no Railway); backend editable pulado | `pip-audit.txt` |

**Disposição honesta:** backend e frontend efetivamente limpos de SAST. A dívida
`mcp` é de higiene do venv de dev (recriar do lock), **não** exposição de produção.
Ressalva semgrep: rulesets community (login habilita mais regras) — não é prova de
ausência total, é o mesmo conjunto que o CI roda.

## 3. Gap de header confirmado (candidato à Onda 1, baixo risco)

`frontend/next.config.ts` → array `securityHeaders` NÃO inclui
`Cross-Origin-Opener-Policy` nem `Cross-Origin-Resource-Policy` (confirmado por
leitura + prod-probe da Fase 0). Recomendado `COOP: same-origin` + `CORP:
same-origin`. App não tem popup cross-origin nem CDN → seguro. Não interage com o
nonce do `proxy.ts`. Sem regressão visual (é header HTTP).

## 4. Governança: o hardening "Nível Bancário" (PR #30) está ÓRFÃO

`AGENTS.md` documenta como existentes: `PROJETO/docs/security/*`,
`PROJETO/SECURITY.md`, `.github/workflows/security-scheduled.yml`. **Em `master`
(`4790479`) nada disso existe.** Vivem só em `origin/feat/seguranca-nivel-bancario`
(`095ceba`, 2026-07-11), que está **stale**: `git diff origin/master..branch` =
`123 files, +2291 −18750` — as 18.750 deleções são **todo o sistema visual das 7
missões** (`cinema/*.css`, `components/motion/*`), porque a branch nasceu ANTES
delas. **Conclusão: a branch é IMPOSSÍVEL de mergear** (aniquilaria o visual
aprovado — violação de invariante).

**Payload de segurança salvável (adições puras, zero conflito com o visual):**

| Arquivo | Linhas | Natureza |
|---|---|---|
| `docs/security/threat-model.md` | 138 | STRIDE completo (DFD, trust boundaries, por componente) |
| `docs/security/compliance-asvs-owasp-nist.md` | 88 | OWASP Web/API/LLM 2025 + ASVS 5.0 L3 + NIST/CIS |
| `docs/security/plano-resposta-incidentes-lgpd.md` | 75 | IR (NIST SP 800-61) + trilho LGPD/ANPD |
| `docs/security/observabilidade-seguranca.md` | 77 | eventos→detecção→alerta; CSP-report ausente |
| `docs/security/relatorio-seguranca-2026-07-11.md` | — | relatório datado (artefato histórico) |
| `SECURITY.md` | 29 | política de divulgação responsável + safe harbor |
| `.github/workflows/security-scheduled.yml` | 169 | re-scan diário do master → abre issue `security` |

**Ação (Onda de recuperação):** restaurar os artefatos **duráveis** sobre o master
(`git checkout <branch> -- <path>`), **re-validar cada alegação contra o código
atual** (não confiar no estado de 11/07), e construir o scorecard Fortaleza em
cima — em vez de duplicar. Isso fecha o gap de governança (as promessas do
`AGENTS.md` viram verdade). As modificações `.py` da branch (config/ratelimit/
http_client/tese) são **base-stale** → NÃO cherry-pick; diff individual e só portar
o que faltar em master, com testes verdes.
