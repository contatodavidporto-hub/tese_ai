# Conformidade — ASVS L3 · OWASP Top 10 (Web/API/LLM 2025) · NIST/CIS

> **Baseline:** `origin/master @ 1fbcdc2` (2026-07-11). Aterrado em leitura de código + advisors da produção.
> **Legenda:** ✅ PASS (com evidência) · 🟡 PARCIAL · ❌ GAP (com achado) · ⛔ N/A hoje (pré-login) · 🔒 escalonar (humano/pago).
>
> **Honestidade metodológica (importante):** este mapa é feito no nível de **controle/tema**, com evidência
> `arquivo:linha`. Ele **não** inventa IDs de requisito ASVS individuais (ex.: "V2.1.3") — a importação
> requisito-a-requisito do ASVS 5.0 como issues rastreáveis está documentada no Vault como **plano, não feito**,
> e continua sendo o próximo passo formal (ver §4). Onde um requisito L3 não pôde ser verificado, está marcado
> GAP/PARCIAL, nunca PASS. O alvo **auto-declarado do projeto é ASVS Nível 2**; este documento mede contra **L3**
> (o pedido) e marca explicitamente o *delta* L3 e o que é N/A enquanto não houver login.

## 1. OWASP Top 10 Web (2021→2025)

| # | Categoria | Status | Evidência / Nota |
|---|---|---|---|
| A01 | Broken Access Control | 🟡 / ⛔ | Sem login hoje → sem controle de acesso por usuário. `GET /teses/{id}` público-por-UUID (galeria). RLS ON em 23/23 tabelas mas **backend bypassa** (owner role). **Achado H1** (latente ALTO ao ligar login). |
| A02 | Cryptographic Failures | ✅ | TLS forçado (HSTS 2 anos `next.config.ts:11`; backend `main.py:37`); segredos só em env; anon key pública por design (RLS). At-rest: Supabase gerenciado (AES-256). |
| A03 | Injection | ✅ | Zero SQL raw (único `text()` parametrizado `scheduler.py:349`); ORM parametrizado; sem `eval/exec/subprocess/shell=True`; markdown do LLM → nós React (sem `dangerouslySetInnerHTML`). Semgrep/bandit = 0. |
| A04 | Insecure Design | ✅ | Defesa em profundidade em 5 camadas; gate determinístico fail-closed; deny-by-default (SSRF/CORS/anon). Threat model formalizado (`threat-model.md`). |
| A05 | Security Misconfiguration | ✅ | docs off em prod (`main.py:142-150`); CORS estrito; headers completos; `poweredByHeader:false`. 🟡 falta COOP/CORP (**FE1**). |
| A06 | Vulnerable Components | ✅ | pip-audit=0, npm-audit-high=0, trivy no CI; Dependabot semanal (actions/pip/npm); SBOM syft; actions SHA-pinned. |
| A07 | Identification & Auth Failures | ⛔ | Sem auth hoje. Padrão documentado p/ quando existir: JWT RS256/ES256 via JWKS, HS256 proibido (`Vault/17-Seguranca`). 🔒 leaked-password-protection desligada (toggle free). |
| A08 | Software & Data Integrity | ✅ | Actions por SHA; SBOM; migrações 100% aditivas; `fonte_id NOT NULL` (integridade "sem fonte não é fato"). |
| A09 | Security Logging & Monitoring | 🟡 | structlog com redação de segredo (`logging.py:15-64`). **GAP:** sem alerta de anomalia/SIEM, sem CSP report-uri, sem trilha de auditoria de segurança. Plano em `observabilidade-seguranca.md`. |
| A10 | SSRF | ✅ | Allowlist deny-by-default + bloqueio IP interno + revalidação de redirect + esquema (`http_client.py:36-105`). 🟡 rebind TOCTOU residual, allowlist é o controle real (**M2**). |

## 2. OWASP API Security Top 10 (2023)

| # | Categoria | Status | Evidência / Nota |
|---|---|---|---|
| API1 | BOLA | ⛔/🟡 | Ver A01 / **H1**. Objeto (tese) hoje é público por design; sem quebra entre usuários porque não há usuários. |
| API2 | Broken Authentication | ⛔ | Sem auth (ver A07). |
| API3 | Broken Object Property Level Auth | ✅ | `TeseCreateIn` expõe só `ticker` (regex); `classe_ativo` setado server-side (`routers/teses.py:82-87`). Sem over-posting. |
| API4 | Unrestricted Resource Consumption | 🟡 | Rate-limit + teto custo/dia + concorrência 2 + body-size + cap download. **Residual:** **M1** (spoof sem edge), **L1** (zip-bomb), **L3** (amplificação de ingestão), sem WAF (🔒 pago). |
| API5 | Broken Function Level Auth | ⛔ | Sem funções privilegiadas expostas; sem admin endpoints no produto. |
| API6 | Unrestricted Access to Sensitive Business Flows | 🟡 | Fluxo caro (geração LLM) protegido por rate-limit/custo/cache; sem anti-bot na borda (🔒). |
| API7 | SSRF | ✅ | Ver A10. |
| API8 | Security Misconfiguration | ✅ | Ver A05. |
| API9 | Improper Inventory Management | ✅ | Superfície mínima (2 rotas + /health); openapi off em prod; SBOM. |
| API10 | Unsafe Consumption of 3rd-party APIs | ✅ | Respostas externas tratadas como não-confiáveis (allowlist, cap de bytes, validação); consenso valida número-na-citação (`consenso.py:316-395`). 🟡 conteúdo → LLM (**L2**). |

## 3. OWASP LLM Top 10 (2025)

| # | Categoria | Status | Evidência / Nota |
|---|---|---|---|
| LLM01 | Prompt Injection | 🟡 | Separação instrução/dado (XML); `_sanitizar_instrucao` (`tese.py:156-166`); **gate determinístico fail-closed** decisivo. **Residual L2** (conteúdo de documento não neutralizado). |
| LLM02 | Sensitive Information Disclosure | ✅/🟡 | Contexto sem PII/segredo; system prompt não-secreto; redação PII documentada. **M3** (exfil-on-render via imagem markdown) — fix nesta entrega. |
| LLM03 | Supply Chain | ✅ | Modelos fixados por id (`config.py:43-44`); deps auditadas; SBOM. |
| LLM04 | Data & Model Poisoning | 🟡 | Fontes allowlistadas + `fonte_id NOT NULL`; consenso valida número. Residual: conteúdo de fonte pública pode conter texto adversarial (mitigado por gate). |
| LLM05 | Improper Output Handling | ✅/🟡 | Saída → nós React (sem HTML bruto); links só host das fontes; scheme sanitizado (`tese.py:517-528`). **M3** cobre imagem markdown no backend. |
| LLM06 | Excessive Agency | ✅ | Nenhuma tool move dinheiro/dados/lê além do escopo; ações em código; gasto de LLM autorizado explicitamente (warm-cache). |
| LLM07 | System Prompt Leakage | ✅ | Prompt não contém segredo; vazá-lo não dá vantagem. |
| LLM08 | Vector/Embedding Weaknesses | ⛔/🟡 | pgvector (`chunks`) com RLS owner-only; `tenant_id` reservado mas sem policy (isolamento por usuário, não tenant) — GAP conhecido p/ multi-tenant futuro. RAG fora do caminho crítico da tese hoje. |
| LLM09 | Misinformation | ✅ | Núcleo do produto: zero alucinação, todo fato com fonte+data, abstenção declarada, Citations verificáveis. |
| LLM10 | Unbounded Consumption | 🟡 | Teto custo/dia + concorrência + rate-limit (ver API4). Residual **M1**/sem WAF. |

## 4. ASVS 5.0 — mapa por capítulo (medido contra **Nível 3**)

> N/A(login) = requisito de auth/sessão não aplicável enquanto o produto é pré-login; vira obrigatório junto com o login.

| Capítulo ASVS (tema) | Status vs L3 | Evidência / delta L3 |
|---|---|---|
| Encoding & Sanitization | ✅ | Saída LLM → React; scheme sanitizado; sem HTML bruto; **M3** fecha imagem markdown. |
| Validation & Business Logic | ✅ | Pydantic v2 + regex de ticker (server-side é o que conta); gate de negócio determinístico. |
| Web Frontend Security | 🟡→✅ | CSP nonce+strict-dynamic, headers fortes. Delta L3: COOP/CORP (**FE1**), no-store (**FE2**) — fix nesta entrega; CSP report-uri (roadmap). |
| API & Web Service | 🟡 | Superfície mínima, deny-by-default. Delta: consumo de recurso (**M1/L1/L3**). |
| File Handling | 🟡 | Downloads com cap de bytes + allowlist. Delta L3: cap de **descompressão** (**L1**) — fix nesta entrega. |
| Authentication | ⛔ N/A(login) | Sem auth. Padrão L3 documentado (JWKS RS256/ES256, MFA) — a implementar com login. |
| Session Management | ⛔ N/A(login) | Sem sessão/cookie (grep vazio). |
| Authorization | ❌ | **H1**: sem authz de app; RLS bypassada no caminho backend. Requisito central de L3 — **decisão de produto** antes do login. |
| Self-contained Tokens (JWT) | ⛔ N/A(login) | Padrão documentado (validar exp/aud, JWKS). |
| OAuth/OIDC | ⛔ N/A | Não usado. |
| Cryptography | ✅ | TLS forte; segredos gerenciados; sem cripto caseira. Delta L3: rotação formal de segredo (runbook — roadmap). |
| Secure Communication | ✅ | HTTPS forçado (HSTS+preload); `upgrade-insecure-requests`; connect-src 'self'. |
| Configuration | ✅ | Segredos em env/painel; docs off; deny-by-default; hooks anti-segredo. |
| Data Protection | 🟡 | Sem PII hoje; no-store (**FE2**) fecha cache. Delta L3 (pós-login): classificação de dados, retenção/expurgo (LGPD). |
| Secure Coding & Architecture | ✅ | ORM, sem sinks perigosos, defesa em camadas, threat model. |
| Security Logging & Error Handling | 🟡 | Redação de segredo; erros estáveis. Delta L3: log de auditoria de segurança + alerta de anomalia (`observabilidade-seguranca.md`). |

**Veredito ASVS L3 honesto:** o baseline atinge o **espírito de L3** nos capítulos de injeção, cripto, comunicação,
configuração e arquitetura; está **PARCIAL** em frontend/logging (fechável nesta entrega + roadmap curto); e tem
**GAP estrutural em Authorization** (ASVS não é "cumprível" em L3 sem um modelo de autorização — **H1**, decisão de
produto). Vários capítulos de Auth/Sessão/Token são **N/A enquanto não há login** e devem ser reavaliados no dia em
que o login entrar. **Não declaramos "ASVS L3 conforme" de forma absoluta** — isso exigiria login + o import
requisito-a-requisito (plano no Vault) + auditoria formal externa.

## 5. NIST / CIS (alinhamento de framework)

| Framework | Alinhamento | Nota |
|---|---|---|
| **NIST CSF 2.0** | Identify 🟡 · Protect ✅ · Detect 🟡 · Respond 🟡 · Recover 🟡 | Protect forte (hardening/CI). Detect/Respond/Recover endereçados por `observabilidade-seguranca.md` + `plano-resposta-incidentes-lgpd.md` (novos). Identify: threat model + SBOM feitos; falta inventário de ativos formal. |
| **NIST SP 800-53 (moderate, temas)** | AC 🟡(H1) · AU 🟡 · CM ✅ · IA ⛔ · SC ✅ · SI ✅ · RA 🟡 | Mapeado por família a título de alinhamento, não certificação. |
| **CIS Controls v8 (IG1)** | ✅ maioria | Inventário SW (SBOM), config segura, gestão de vuln (scanners+Dependabot+scan agendado), proteção de dados (TLS/RLS), log (parcial). IG2/IG3 exigem MFA/monitoração contínua (🔒). |
| **CIS Benchmarks** | 🟡 | Contêiner 1-worker minimal; recomendação: hardening do Dockerfile (usuário não-root, base slim) — verificar no `backend/Dockerfile` (fora do scan local; trivy no CI cobre CVE de base). |

## 6. Próximos passos formais (para fechar L3 de verdade)
1. **Decidir e implementar autorização** (H1) — pré-requisito inegociável de L3.
2. **Import requisito-a-requisito do ASVS 5.0** como issues rastreáveis (plano já documentado no Vault).
3. **Auditoria externa/pentest formal** — nenhum sistema se auto-certifica L3.
4. **WAF/anti-bot + MFA nas contas** (🔒 pago/conta).
5. **CSP report-uri + alerta de anomalia** (observabilidade).
