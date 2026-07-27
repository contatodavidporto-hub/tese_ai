# Threat Model (STRIDE) — Tese AI

> **Baseline:** `origin/master @ 1fbcdc2` (2026-07-11). Metodologia: STRIDE por componente + attack-trees,
> riscos priorizados por impacto × probabilidade. Aterrado em leitura do código real + advisors da produção
> Supabase (`rjpqaaymwhcwxtinppvc`) — **não** em suposição. Ver `relatorio-seguranca-2026-07-11.md` para os
> achados com correção/regressão.

## 1. Sistema e superfície

| Componente | Tecnologia | Hospedagem | Exposição |
|---|---|---|---|
| Frontend | Next 16 + React 19 + Tailwind v4 | Vercel (edge) | Público (internet) |
| Backend API | FastAPI + SQLAlchemy (psycopg3) | Railway (atrás de edge-proxy) | Público (internet) |
| Banco | Supabase Postgres 17 + pgvector | Supabase (sa-east-1) | Só backend (pooler) + PostgREST (ocioso) |
| Camada IA | Anthropic API (Opus/Haiku) + Citations | SaaS Anthropic | Egress do backend |
| CI/CD | GitHub Actions | GitHub | Repo `contatodavidporto-hub/tese_ai` |
| Conectores | HTTP keyless | egress do backend | CVM, SEC, BCB, B3, ANEEL, ANBIMA, FRED, World Bank, Treasury |

**Postura de produto que é também requisito de segurança:** zero recomendação de compra/venda (CVM) e zero
alucinação (todo fato com fonte). Uma falha que quebre isso é tratada como vulnerabilidade (ver `SECURITY.md`).

## 2. Fluxo de dados (DFD textual)

```
[Navegador] --https--> [Vercel/Next: proxy.ts CSP+nonce; route handlers /api/teses]
     |                        |  (server-only API_URL; connect-src 'self')
     |                        v
     |                 [FastAPI /teses]  --(BackgroundTask)--> [motor de tese]
     |                        |                                     |
     |                        | SQLAlchemy (owner role, BYPASSA RLS)|--> [Supabase Postgres + pgvector]
     |                        |                                     |
     |                        |                                     +--> [Anthropic API] (síntese + Citations)
     |                        |                                     |
     |                        |                                     +--> [Conectores keyless] --https--> [CVM/SEC/BCB/B3/...]
     |                        |                                            (allowlist deny-by-default anti-SSRF)
```

**Dados que trafegam:** ticker (input do usuário, regex-validado), dados públicos de mercado (não-confiáveis
quanto a *conteúdo* — podem conter prompt-injection), markdown de tese gerado pelo LLM, citações/fontes,
custo estimado. **Sem PII de titular hoje** (produto pré-login). Segredos (`ANTHROPIC_API_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`) vivem só no painel do host.

## 3. Fronteiras de confiança (trust boundaries)

- **TB1 — Internet ↔ Vercel:** todo request do navegador. Controles: CSP estrita c/ nonce, headers de segurança, HSTS.
- **TB2 — Vercel ↔ Railway:** o frontend só fala com o backend via route handlers server-side (`API_URL` server-only). O navegador nunca fala com o backend direto (CSP `connect-src 'self'`).
- **TB3 — Railway ↔ Supabase:** conexão SQLAlchemy com papel **owner/pooler** que **BYPASSA RLS**. ⚠️ **Fronteira crítica:** aqui não há RLS efetiva; a autorização depende do código da aplicação (hoje inexistente — ver H1). RLS protege apenas o caminho PostgREST (ocioso hoje).
- **TB4 — Backend ↔ Anthropic:** o *conteúdo* de fontes externas e o input do usuário entram no prompt. Não-confiável → separação instrução/dado por tags XML + gate determinístico fail-closed.
- **TB5 — Backend ↔ Conectores externos:** egress só para hosts allowlistados (anti-SSRF). Respostas são não-confiáveis (tamanho, conteúdo).
- **TB6 — Dev ↔ CI ↔ Produção:** segredos só no painel do host; CI com scanners que falham em HIGH/CRÍTICO; actions pinadas por SHA.

## 4. Ativos protegidos

| Ativo | Sensibilidade | Ameaça primária |
|---|---|---|
| Segredos de produção (Anthropic/service_role/DB) | **Crítica** | Exposição → tomada de conta, custo, vazamento de dados |
| Orçamento de LLM (custo por tese) | Alta | Cost-DoS (abuso do endpoint caro) |
| Integridade da tese (sem recomendação, com fonte) | Alta (regulatório CVM) | Prompt-injection subvertendo o gate |
| Disponibilidade (galeria/geração) | Média | DoS / esgotamento de recurso |
| Dados de usuário (futuro, pós-login) | **Crítica** (LGPD) | BOLA/IDOR se RLS/authz não cobrir o caminho backend |

## 5. Atores de ameaça
- **Abusador anônimo** (custo-DoS, scraping, fuzzing) — probabilidade ALTA, sofisticação baixa.
- **Fonte de dados envenenada** (documento CVM/SEC com prompt-injection) — probabilidade BAIXA, impacto médio.
- **Atacante de supply-chain** (dependência/action comprometida) — probabilidade BAIXA, impacto alto.
- **Insider/erro operacional** (segredo commitado/logado) — probabilidade BAIXA (hooks+CI), impacto crítico.
- **Usuário mal-intencionado autenticado** (futuro, pós-login: BOLA) — N/A hoje, ALTO ao ligar login.

## 6. STRIDE por componente

### Frontend (Next/Vercel)
| STRIDE | Ameaça | Mitigação existente | Residual |
|---|---|---|---|
| Spoofing | Origem falsa | mesma-origem; CORS estrito no backend | — |
| Tampering | XSS injetando script | CSP nonce+strict-dynamic; sem `dangerouslySetInnerHTML`; markdown → nós React | `img-src data:` (INFO) |
| Repudiation | — | logs Vercel | — |
| Info disclosure | Segredo no bundle; cache de dado sensível | `server-only` API_URL; sem NEXT_PUBLIC sensível | **FE2** (no-store ausente) |
| DoS | — | edge Vercel | — |
| Elevation | Clickjacking/tab-napping | `frame-ancestors 'none'`, X-Frame DENY | **FE1** (COOP/CORP ausentes) |

### Backend (FastAPI/Railway)
| STRIDE | Ameaça | Mitigação existente | Residual |
|---|---|---|---|
| Spoofing | Spoof de IP p/ burlar rate-limit | chave XFF-rightmost (edge-escrito) | **M1** (fail-closed/hop configurável) |
| Tampering | Injeção SQL/command; SSRF | ORM parametrizado (zero raw SQL); allowlist SSRF deny-by-default | **M2** (rebind TOCTOU; allowlist é o controle real) |
| Repudiation | — | structlog c/ redação de segredo | trilha de auditoria de segurança (roadmap) |
| Info disclosure | Vazamento por erro/log; markdown exfil | erros estáveis; docs off em prod; redação | **M3** (imagem markdown) |
| DoS | Endpoint LLM caro; zip-bomb; payload gigante | teto custo/dia + concorrência 2 + body-size + cap download | **L1** (descompressão), **M1** |
| Elevation | Ler tese de outro usuário | (nenhuma hoje — ver H1) | **H1** (sem authz; RLS bypassada) |

### Banco (Supabase/Postgres)
| STRIDE | Ameaça | Mitigação existente | Residual |
|---|---|---|---|
| Tampering/Info | Leitura cross-tenant | RLS ON em 23/23 tabelas; policies owner-only hardened; anon default-deny | **H1/DB** (backend bypassa RLS; sem FORCE) |
| Elevation | Bypass de policy | `TO authenticated`, `IS NOT NULL`, USING+WITH CHECK | FORCE RLS (defer p/ pós-login) |

### Camada IA (Anthropic)
| STRIDE | Ameaça | Mitigação existente | Residual |
|---|---|---|---|
| Tampering | Prompt-injection subverte a tese | system prompt forte; separação instrução/dado (XML); **gate determinístico fail-closed**; consenso valida número na citação | **L2** (conteúdo de doc), **M3** (exfil-on-render) |
| Info disclosure | Vazar system prompt | prompt não é secreto | aceito |
| Elevation | LLM executa ação sensível | nenhuma tool move dinheiro/dados; ações em código, não delegadas | — |

### CI/CD (GitHub Actions)
| STRIDE | Ameaça | Mitigação existente | Residual |
|---|---|---|---|
| Tampering | Action/dep comprometida | actions pinadas por SHA; Dependabot; SBOM syft | — |
| Info disclosure | Segredo commitado | gitleaks (história) + hook protect-secrets + .gitignore | — |
| DoS/Elevation | Build malicioso | `permissions: contents:read`; gates falham em HIGH/CRÍTICO | scan agendado (adicionado nesta entrega) |

## 7. Attack trees (principais)

**AT1 — Cost-DoS no endpoint LLM (objetivo: esgotar orçamento/negar serviço)**
```
Esgotar custo de LLM
├── burlar rate-limit
│   ├── rotacionar X-Forwarded-For .............. mitigado por chave XFF-rightmost; RESIDUAL M1 (se sem edge)
│   └── distribuir IPs (botnet) .................. RESIDUAL: sem WAF/anti-bot (escalonar — pago)
├── forçar geração cara repetida ................ mitigado: cache 24h por ticker + teto custo/dia + concorrência 2
└── amplificar ingestão (tickers válidos-sem-dado) RESIDUAL L3 (fetch externo antes de abster)
```
**AT2 — Exfiltração de dado via LLM (objetivo: vazar contexto/rastrear usuário)**
```
Exfiltrar via saída do LLM
├── injetar imagem markdown p/ beacon .......... RESIDUAL M3 (backend não remove) → frontend allowlist mitiga
├── injetar link de phishing ................... mitigado: frontend só linka host das fontes reais
└── vazar system prompt ........................ aceito (prompt não-secreto); contexto sem PII/segredo
```
**AT3 — Comprometer segredo de produção**
```
Obter ANTHROPIC_API_KEY / service_role
├── segredo no código/log ...................... mitigado: hooks + gitleaks + structlog redação
├── segredo no bundle do cliente ............... mitigado: server-only; gitleaks allowlista só anon pública
└── comprometer o host (Railway/Vercel) ........ fora de escopo do código; MFA na conta (escalonar)
```

## 8. Riscos priorizados (impacto × probabilidade)

| Risco | Impacto | Prob. | Nível | Achado | Ação |
|---|---|---|---|---|---|
| BOLA ao ligar login (RLS bypassada) | Alto | Alta (quando login) | **ALTO (latente)** | H1 | Escalar decisão + regressão |
| Cost-DoS sem WAF/anti-bot | Médio | Média | **MÉDIO** | AT1 | Escalar (WAF pago) + M1 |
| Rate-limit spoof sem edge | Médio | Baixa | MÉDIO | M1 | Fix (hop configurável) |
| Exfil-on-render markdown | Médio | Baixa | MÉDIO | M3 | Fix (remover imagem) |
| Tab-napping / cache sensível | Baixo | Baixa | MÉDIO | FE1/FE2 | Fix (headers) |
| SSRF rebind | Baixo | Muito baixa | BAIXO | M2 | Doc + futuro pin |
| Zip-bomb | Baixo | Muito baixa | BAIXO | L1 | Fix (teto descompressão) |
| Prompt-injection via conteúdo | Baixo | Baixa | BAIXO | L2 | Opcional (sanitizar) |

## 9. Camadas de defesa em profundidade (existentes — não regredir)
1. **Claude Code:** hooks (block-dangerous/protect-secrets/enforce-boundary), deny-rules, sandbox opcional.
2. **App/API:** CSP nonce, headers, CORS estrito, rate-limit anti-spoof, body-size, teto custo, concorrência.
3. **Dados:** RLS ON em toda tabela, policies owner-only hardened, anon default-deny, `fonte_id NOT NULL` (sem fonte não é fato).
4. **LLM:** separação instrução/dado, gate determinístico fail-closed, consenso valida número-na-citação, nenhuma tool com agência financeira.
5. **CI:** gitleaks + semgrep + bandit + trivy + pip-audit + npm audit + syft, falha em HIGH/CRÍTICO, actions SHA-pinned, Dependabot; **+ scan agendado (esta entrega)**.

## 10. Risco residual e decisões pendentes (do humano)
- **H1 (authn/authz):** decidir modelo antes do login real — (a) authz na aplicação por `user_id` do JWT em todo read/write, ou (b) backend sob papel não-privilegiado com RLS forçada. Até lá, galeria pública é risco aceito e documentado.
- **WAF/anti-bot na borda** (Cloudflare/Vercel WAF) — exige plano pago.
- **MFA nas contas** Vercel/Railway/Supabase/GitHub/Anthropic — ação de conta.
- **Leaked-password-protection** no Supabase — toggle free (moot pré-login).
- **DPO/Encarregado** designado + tabletop do runbook de IR.
