# Relatório de Segurança — Tese AI (Nível Bancário)

> **Missão:** SUPER PROMPT-MÃE "Segurança Nível Bancário" (2026-07-11). **Baseline:** `origin/master @ 1fbcdc2`.
> **Escopo:** só o NOSSO sistema; testes não-destrutivos; nada em produção derrubado; nada irreversível sem OK.
> **Metodologia:** 5 agentes de assessment read-only (backend, frontend, scanners reais, RLS/DB, cluster de
> segurança do Vault) + advisors da produção Supabase (`rjpqaaymwhcwxtinppvc`) + threat model STRIDE + remediação
> com regressão + verificação. **Zero alucinação:** todo achado tem âncora `arquivo:linha` e toda métrica é de
> execução real. Documentos irmãos: `threat-model.md`, `compliance-asvs-owasp-nist.md`,
> `plano-resposta-incidentes-lgpd.md`, `observabilidade-seguranca.md`, `../SECURITY.md`.

## 1. Sumário executivo

O baseline **já estava fortemente endurecido** — **nenhum CRÍTICO, nenhuma injeção, nenhum vazamento de segredo,
nenhum SQL injection**. Os scanners rodam limpos e a RLS está provada na produção. O trabalho desta missão foi:
(1) **formalizar** a postura (threat model, conformidade, IR/LGPD, observabilidade); (2) **fechar os gaps residuais**
que dava para fechar sem quebrar o produto (7 correções com regressão); (3) **instalar o processo contínuo** (scan
agendado + red/blue-team); e (4) **escalar honestamente** o que exige decisão de produto ou plano pago.

**Não declaramos "inviolável" nem "ASVS L3 certificado".** O maior gap é **arquitetural** (ausência de modelo de
autorização — decisão de produto antes do login), não um bug. Ver §6.

**Verificação final (execução real, worktree `feat/seguranca-nivel-bancario`):**
- `ruff check app tests` → **All checks passed**
- `black --check app tests` → **115 arquivos OK**
- `bandit -r app -ll` (gate do CI) → **exit 0, "No issues identified"** (único achado no repo = 1 B311 Low/já `noqa`)
- `pytest` (suíte completa) → **1038 passed, 0 failed** (baseline era ~1012; +26 de regressão de segurança)
- Scanners de supply-chain no baseline: **pip-audit 0 CVE · npm-audit-high 0 · semgrep-security 0**

## 2. O que já estava forte (verificado — não regredir)

| Área | Controle | Evidência |
|---|---|---|
| SSRF | Allowlist deny-by-default + bloqueio de IP interno + revalidação de redirect + esquema | `http_client.py:36-105,126-129,171` |
| Injeção | Zero SQL raw (único `text()` parametrizado); ORM; sem `eval/exec/subprocess/shell` | `scheduler.py:349`; varredura limpa |
| Segredos | Redação no structlog (URIs Postgres, `sb_secret_`, `sk-`, JWT); env-only; service_role backend-only | `logging.py:15-64`; `config.py:31-58` |
| LLM | Separação instrução/dado (XML); **gate determinístico fail-closed**; consenso valida número-na-citação | `tese.py:79-120`; `avaliacao.py`; `consenso.py:316-395` |
| Headers/CSP | CSP nonce+strict-dynamic; HSTS; frame-ancestors none; CORS estrito; docs off em prod | `proxy.ts`; `next.config.ts`; `main.py:32-46,142-171` |
| Capacidade | Rate-limit anti-spoof + teto custo/dia + concorrência + body-size (incl. chunked) | `ratelimit.py`; `limits.py`; `main.py:49-121` |
| RLS | 23/23 tabelas RLS ON; policies owner-only hardened; anon default-deny; `fonte_id NOT NULL` | migrações `0001-0006`; advisors prod |
| CI | bandit/semgrep/trivy/pip-audit/npm-audit/gitleaks/syft, falha em HIGH/CRÍTICO, actions SHA-pinned | `.github/workflows/ci.yml` |

## 3. Achados e disposição

| ID | Sev | Achado | Disposição | Regressão |
|---|---|---|---|---|
| **H1** | ALTO (latente) | Backend usa papel owner que **bypassa RLS**; `GET /teses/{id}` sem authz. Hoje LOW (sem login, galeria pública, UUID inguessável). | **🔒 ESCALADO** (decisão de produto antes do login) + documentado em threat model/AGENTS.md | teste "user A não lê tese de B" a criar junto do login |
| **M1** | MÉDIO | Evasão de rate-limit por spoof de X-Forwarded-For se alcançado sem edge confiável. | ✅ **CORRIGIDO** — hop confiável configurável (`RATE_LIMIT_TRUSTED_PROXY_HOPS`), fail-closed | `test_ratelimit_trusted_hops.py` (14 testes) |
| **M3** | MÉDIO → def. profundidade | Markdown do LLM servido sem remover imagem embutida (LLM02). **Risco vivo BAIXO**: o renderer `Markdown.tsx` nunca emite `<img>` e a CSP (`img-src`) bloqueia GET externo — o backend é que não tinha defesa própria. | ✅ **CORRIGIDO** — `_remover_imagens_markdown` antes de persistir/servir (links intactos) | 7 testes de função + 1 e2e no pipeline |
| **FE1** | MÉDIO | Headers COOP/CORP ausentes (tab-napping). | ✅ **CORRIGIDO** — COOP+CORP same-origin (COEP como follow-up) | verificação por header em preview |
| **FE2** | MÉDIO | Sem `Cache-Control: no-store` nas respostas JSON do proxy. | ✅ **CORRIGIDO** — `no-store` em sucesso+erro | verificação por header |
| **M2** | MÉDIO | SSRF DNS-rebind TOCTOU; allowlist é o controle real. | 🟡 **DOCUMENTADO** (docstring corrigida) — pin de IP completo = alto blast-radius p/ risco baixo | — |
| **L1** | BAIXO | ZIP sem teto de descompressão (zip-bomb). | ✅ **CORRIGIDO** — `_MAX_DESCOMPRIMIDO` (1 GiB) checado antes de `z.read` | testes em `test_cotahist`/`test_cvm_cadastro` |
| **FE3** | BAIXO | `[id]` route sem validação de UUID. | ✅ **CORRIGIDO** — `UUID_RE` compartilhado (`ids.ts`), 400 antes do fetch | — (sem node_modules no worktree) |
| **DB/FORCE** | MÉDIO | Nenhuma tabela usa `FORCE ROW LEVEL SECURITY`. | 🟡 **DEFERIDO** — no-op hoje (owner com BYPASSRLS); aplicar com login (risco de quebrar prod agora) | — |
| **L2** | BAIXO | Prompt-injection residual via conteúdo de documento. | 🟡 Mitigado por system prompt + gate; hardening opcional | — |
| **A09/CSP-report** | MÉDIO | Sem `report-uri` na CSP; sem alerta de anomalia. | ✅ **ESPECIFICADO** em `observabilidade-seguranca.md` (CSP report sem tocar proxy.ts) | — |

## 4. Hardening aplicado e provado (esta entrega)
- **Backend** (todos com regressão, suíte 1038 verde): M1 (rate-limit trusted-hop fail-closed), M3 (strip de imagem markdown), L1 (guarda anti zip-bomb), M2 (docstring do controle real).
- **Frontend** (aditivo, sem conflito com a raia cinematográfica): FE1 (COOP/CORP), FE2 (no-store), FE3 (UUID gate + `ids.ts`).
- **RLS provada:** advisors da produção não acusam `rls_disabled_in_public`; 23/23 tabelas RLS ON; `anon` lê zero.

## 5. Pipeline contínuo de caça a vulnerabilidades (novo)
- **`.github/workflows/security-scheduled.yml`** — cron diário 06:00 UTC + `workflow_dispatch`: re-roda gitleaks (história completa), trivy, pip-audit, npm-audit, semgrep, syft SBOM contra o master ATUAL (pega CVE nova em código inalterado). Ao falhar, **abre/atualiza uma issue `security`** (dedup por marcador) e falha o run. **Actions pinadas por SHA**: as 6 actions compartilhadas com o `ci.yml` (checkout/setup-uv/gitleaks/setup-node/semgrep/upload-artifact) usam os **mesmos pins do `ci.yml @ 1fbcdc2`** (fonte da verdade — o CI de produção roda verde com eles); a única action nova é `actions/github-script` (v9.0.0, SHA real confirmado). Nota de processo (transparência): uma primeira rodada desalinhou 4 pins por comparar com um `ci.yml` de branch defasada; o `auditor-mor` pegou, e foram realinhados ao `ci.yml` do baseline e reauditados.
- **Dependabot** semanal (actions/pip/npm) já ativo. **Red/blue-team** em `.claude/agents` + `gestao-vulnerabilidades` para triagem por SLA.

## 6. O que precisa de VOCÊ (escalonamentos)

**Decisão de produto (o gap #1):**
- **H1 — Autorização.** Antes de ligar login real: (a) filtrar `user_id` do JWT em todo read/write na aplicação, ou (b) rodar o backend sob papel não-privilegiado com RLS forçada. Até lá, galeria pública é **risco aceito e documentado**.

**Conta / plano pago:**
- **WAF + anti-bot na borda** (Cloudflare / Vercel WAF) — defesa contra DoS distribuído/bot que o rate-limit de app não cobre.
- **MFA** nas contas Vercel/Railway/Supabase/GitHub/Anthropic.
- **CodeQL / GitHub Advanced Security** — se o repo for privado (SAST nativo além do semgrep).

**Configuração (grátis, 1 clique):**
- **Supabase → leaked-password-protection** = ON (moot pré-login, mas higiene).
- Confirmar em produção o **hop confiável** do Railway e setar `RATE_LIMIT_TRUSTED_PROXY_HOPS` se o padrão (1) não bater.

**Processo:**
- **Designar o Encarregado/DPO** (LGPD art. 41) e rodar um **tabletop** do runbook de incidente (cenário SEV-1 "segredo vazado").
- Rotação de segredo de produção e merge para produção: **aguardando seu OK** (esta entrega abre só PR/preview).

## 7. Limites honestos (o que este trabalho NÃO é)
- Não é auditoria/pentest **externo** formal — nenhum sistema se auto-certifica.
- Não testou produção de forma intrusiva (só o baseline em worktree + advisors read-only).
- ASVS L3 é medido por controle, não requisito-a-requisito (import formal é o próximo passo).
- "Nível bancário" = teto prático de defesa em profundidade + processo contínuo. Inviolabilidade absoluta não existe.
