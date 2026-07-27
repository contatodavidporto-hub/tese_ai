# Fortaleza — Scorecard (framework a framework: atingido vs pendente)

> **Baseline:** `origin/master @ 4790479` (produção) + **Onda 1 desta entrega**.
> **Legenda:** ✅ atingido (com evidência) · 🟡 parcial · ❌ gap · ⛔ N/A hoje (pré-login) · 🔒 escalonar (humano/pago).
> **Honestidade:** "atingido" só com evidência anexada. Onde não pude provar (sem Docker/DAST/creds/chave), está **pendente**, nunca "passou". Este scorecard **re-mede contra o master atual** e corrige alegações do doc órfão de 11/07 (ver §7).

## 1. OWASP Top 10 (Web / API / LLM) · ASVS · NIST/CIS

Mapa detalhado por controle (aterrado em `arquivo:linha`) recuperado e **re-baselinado** em
`docs/security/compliance-asvs-owasp-nist.md`. Resumo do veredito atual:

- **Web:** injeção/cripto/comunicação/config/SSRF **✅**; A05 (misconfig) subiu para **✅** com o COOP/CORP da Onda 1; A09 (logging/monitoração) **🟡** (redação só structlog — roadmap P1 #6); A01/A07 (access/auth) **⛔ pré-login** com **gap latente H1**.
- **API:** superfície mínima **✅**; API4/API6 (consumo/fluxo caro) **🟡** (rate-limit+teto+cache; sem WAF 🔒).
- **LLM:** LLM09 (misinformation) é o núcleo do produto **✅** (fonte+data ou abstém, gate determinístico); LLM01/LLM05 **🟡** (defesa em profundidade; conteúdo de doc não neutralizado = achado L2).
- **ASVS 5.0 vs L3:** alvo auto-declarado do projeto é **L2**. Espírito de L3 em injeção/cripto/comunicação/config/arquitetura **✅**; **gap estrutural em Authorization** (H1) — **não** declaramos "L3 conforme" (exigiria login + import requisito-a-requisito + auditoria externa).
- **NIST CSF 2.0 / SP 800-53 / CIS v8 IG1:** Protect forte; Detect/Respond/Recover cobertos por processo (docs recuperados); IG2/IG3 exigem MFA/monitoração contínua (🔒).

## 2. NIST SSDF (SP 800-218) — práticas de desenvolvimento seguro

| Prática | Status | Evidência |
|---|---|---|
| PO (Prepare the Org) | 🟡 | `SECURITY.md` (divulgação responsável), threat model, IR/LGPD — recuperados nesta entrega. Falta: papéis formais além do solo. |
| PS (Protect Software) | ✅ | Segredos só em env/painel (hook `protect-secrets`); actions SHA-pinned; **installers trivy/syft pinados por SHA+versão nesta entrega** (era `curl\|sh` de `main` — achado ALTO). |
| PW (Produce Well-Secured) | ✅/🟡 | Gate de PR: ruff/black/bandit/pip-audit/gitleaks/semgrep/trivy/SBOM; revisão de segurança documentada. 🟡 sem threat-model-por-feature formal. |
| RV (Respond to Vulns) | 🟡→✅ | Dependabot (actions/pip/npm) + **`security-scheduled.yml`** (re-scan diário → abre issue `security`) recuperado e hardened. 🟡 `uv.lock` não coberto pelo ecossistema `pip` do Dependabot (roadmap #8). |

**Veredito SSDF:** alinhamento **forte** no PS/PW/RV para a escala; a lacuna é organizacional (PO), esperada num solo. Sem certificação — é alinhamento de prática.

## 3. SLSA (proveniência de build / supply-chain)

| Nível | Status | Nota |
|---|---|---|
| Fonte versionada + build por serviço | 🟡 | Build de backend por `Dockerfile` no Railway **fora do CI**; frontend no Vercel. |
| Dependências pinadas (L2-ish) | ✅ | `uv.lock` (hash) + `package-lock.json`; `uv sync --locked` como gate anti-drift; SBOM CycloneDX (syft) publicado. |
| Proveniência assinada / build isolado (L3) | ❌ | **Sem atestação de proveniência**; a **imagem de produção real nunca é construída/escaneada no CI** (SBOM é do repo, não da imagem). Roadmap #8: `docker build`+`trivy image`+`syft <image>`+`attest-build-provenance`. |

**Veredito SLSA:** ~**L1→L2** em pinning/SBOM; **L3 pendente** (proveniência + scan da imagem). Honesto: o artefato que roda em produção não passa hoje por gate de imagem.

## 4. Google SRE (confiabilidade)

| Tema | Status | Evidência / gap |
|---|---|---|
| Timeouts / retries / backoff | 🟡 | `http_client` com timeout + cap de bytes; **`download_zip` sem retry** (achado, roadmap #4). |
| Circuit breaker / degradação graciosa | ✅ | Cascata Opus→Haiku; **abstém** sem `ANTHROPIC_API_KEY` (degrada com dignidade); gate fail-closed. |
| Idempotência | 🟡 | Jobs em sua maioria idempotentes; **`POST /teses` é check-then-create** (race → geração dupla, roadmap #5). |
| Health / readiness | ✅ | `/health` (Railway healthcheck); docs off em prod. |
| Guardas de capacidade | ✅/🟡 | Rate-limit spoof-resistant (XFF direito), teto de custo/dia, cap concorrência. **Corrigido nesta entrega: vazamento de vaga do semáforo (CRÍTICO)** que travava TODA geração até restart. 🟡 teto por-processo (multi-worker = roadmap #3). |
| SLI/SLO + error budget | ❌ | **Não definidos.** Proposta P1: SLI de disponibilidade do `/health` + latência p95 de geração + taxa de abstenção; SLO 99,5% / error budget mensal. Langfuse/structlog já dão a matéria-prima. |
| Observabilidade / correlação | 🟡 | structlog + langfuse; **sem alerta de anomalia/SIEM** nem correlação de request formal (`observabilidade-seguranca.md`). |

## 5. 12-Factor + CIS (infra/container)

| Item | Status | Evidência |
|---|---|---|
| Config no ambiente (III) | ✅ | Segredos só em painel do host; `.env` no `.gitignore`/`.dockerignore`. |
| Processos stateless / port binding / logs como stream | ✅ | uvicorn 1-worker; logs para stdout (structlog). |
| Dev/prod parity | 🟡 | `uv sync --locked` alinha deps; base image por tag (não digest) diverge SO entre builds (roadmap #8). |
| CIS Docker: não-root, base mínima | ✅/🟡 | Usuário uid 10001 não-root, `python:3.12-slim`. 🟡 base sem digest; single-stage deixa `uv`/`pip` na imagem (roadmap #8). |
| Menor privilégio no host | ✅ | `service_role` só no backend; RLS ON em toda tabela; CI `permissions: contents: read`. |

## 6. Invariantes do produto (regressão-zero — a alma)

| Invariante | Status | Evidência desta sessão |
|---|---|---|
| Anti-alucinação (fonte+data ou abstém) | ✅ **reforçado** | Gate agora **bloqueia** tese com fontes e ZERO citações (antes servia como `ready`) — +2 testes. Ambiguidade `pct` = roadmap P0 #1 (não regredir o gate). |
| CVM (nunca recomenda) | ✅ | Gate de linguagem de recomendação/valuation/técnica intacto; 1015 testes verdes. |
| Rastreabilidade | ✅/🟡 | Trilha por `fonte_id`/versão de prompt-modelo preservada; `fonte_id NULLABLE` legado = roadmap #10. |
| Sistema visual (7 missões) | ✅ | Frontend intocado exceto **headers HTTP** (COOP/CORP) — build verde, zero mudança visual. |
| Contrato externo | ✅ | Nenhuma rota/payload alterado; correções são por dentro. |

## 7. Reconciliação honesta com o doc órfão de 11/07 (PR#30)

O `compliance-asvs-owasp-nist.md` recuperado citava fixes "nesta entrega" que viviam **só no PR#30 órfão** (nunca mergeado — o branch está stale, aniquilaria o visual das 7 missões). Estado REAL hoje:

- **FE1 (COOP/CORP):** era "nesta entrega" do PR#30 → **de fato feito agora, na Onda 1 Fortaleza** (build verde). ✅
- **M3 (exfil-on-render por imagem markdown):** o renderer de markdown foi endurecido em master (commit `5923399`, "fecha M1+B1..B4 do renderer"); **M3 específico não re-verificado** nesta sessão — tratar como 🟡 até prova.
- **L1 (cap de descompressão / zip-bomb):** o cap de **bytes** (`RespostaGrandeDemais`) está em master (teste existe); o cap de **razão de descompressão** era do PR#30 → **não confirmado** em master (🟡, roadmap).
- **M1 (rate-limit spoof):** a chave por XFF-direita está em master e documentada no `DEPLOY.md` ✅.

**Conclusão de governança:** o `AGENTS.md` prometia `docs/security/*` + `SECURITY.md` + scan agendado que **não existiam** em produção. Esta entrega **recupera os artefatos duráveis** (threat model, ASVS, IR/LGPD, observabilidade, SECURITY.md, scan agendado) **re-baselinados/hardened**, fechando o gap entre o que a doc promete e o que produção tem.
