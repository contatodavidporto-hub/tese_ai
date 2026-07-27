# Observabilidade e alerta de anomalia de segurança — Tese AI

> **Status:** plano v1 (2026-07-11). Honesto sobre o que **existe** (structlog com redação,
> logs de plataforma) vs o que **falta** (SIEM, coletor de CSP, alerta log-based configurado).
> Complementa o runbook `docs/security/plano-resposta-incidentes-lgpd.md` (§3.1 "Detecção &
> triagem" aponta para cá) e o scan agendado `.github/workflows/security-scheduled.yml`.

## 0. O que já existe (base real)

- **Log estruturado com redação de segredo** — `backend/app/core/logging.py`: structlog emite
  **JSON em produção** (`app_env != "development"`) para **stdout**, com o processor `_redact_secrets`
  redigindo por nome de campo sensível E por padrão de valor (connection string, `sb_secret_*`,
  `sk-*`, JWT). Toda linha de log de segurança abaixo herda essa redação — é seguro alertar sobre elas.
- **Coleta de log:** stdout é capturado pelos logs da plataforma — **Railway** (backend FastAPI),
  **Vercel** (frontend Next), **Supabase** (Postgres/Auth/logs de banco). Não há agregador central.
- **Langfuse** é observabilidade de **LLM** (custo/traços/prompts), **não é SIEM**: não vê 429 de
  rede, bloqueio de SSRF, nem falha de job de scheduler. **Lacuna declarada:** nenhuma ferramenta
  correlaciona eventos de segurança das 3 plataformas num só lugar hoje.

## 1. Eventos de segurança → fonte → detecção → alerta

Cada evento abaixo tem um **event name** de log real (ou uma lacuna marcada `[FALTA]`). Nomes de
evento em `código` são os literais do structlog, greppáveis nos logs do Railway.

| Evento de segurança | Fonte (onde loga hoje) | Detecção | Alerta / limiar sugerido |
|---|---|---|---|
| **Pico de 429 (rate-limit)** | slowapi `_rate_limit_exceeded_handler` em `main.py` devolve **HTTP 429**. Limites: `rate_limit_criar_tese=30/hour`, `rate_limit_global=120/minute` (`core/config.py`). **[FALTA]** o handler padrão **não emite log estruturado** — só o status HTTP nos access logs do Railway/Vercel. | Contagem de respostas 429 nos logs HTTP de plataforma, por janela e por IP (a chave é o XFF na posição do hop confiável — `RATE_LIMIT_TRUSTED_PROXY_HOPS`, default 1 = mais à direita, fail-closed; `core/ratelimit.py`). | **> 50 respostas 429 / 5 min** (abuso/scraping) ou **1 IP > 80% dos 429** (ataque dirigido) → alerta. **Melhoria:** registrar um handler custom que loga `rate_limit_excedido` com `path`+chave, para contar sem depender do parse de access log. |
| **Rejeição/abstenção do gate anti-recomendação** | `services/avaliacao.avaliar_tese` → `services/tese.py` loga `tese_gerada` com `aprovado`, `bloqueante`, `cobertura_fontes`. `bloqueante=true` marca a tese `status="error"` (nunca servida). | Filtrar `event="tese_gerada" AND bloqueante=true` (recomendação/evento sem fonte/fonte sem URL vazaram do prompt) ou `aprovado=false` (abstenção/cobertura baixa). | **Qualquer `bloqueante=true`** → alerta imediato (o gate segurou uma violação CVM que o modelo produziu — sinal de regressão de prompt/modelo). **Taxa de `aprovado=false` > 20% / dia** → investigar deriva de qualidade. |
| **Hit do teto de custo LLM** | `core/limits.py`: `CustoDiarioTracker` levanta `TetoCustoExcedido` (teto `tese_teto_custo_usd_dia=25.0`), e loga `custo_llm_acumulado_dia` (usd corrente) a cada geração. A abstenção resultante vira `tese_falhou` (`erro` = mensagem do `TetoCustoExcedido`) em `tese.py`. Concorrência: `ConcorrenciaExcedida` idem. | `event="custo_llm_acumulado_dia"` com `usd` cruzando fração do teto; `event="tese_falhou"` com `erro` contendo "teto de custo" ou "gerações simultâneas". | **`usd >= 0.8 * teto`** → alerta preventivo (custo anômalo antes de estourar). **Qualquer `TetoCustoExcedido`** = teto batido no dia → alerta (pode ser abuso via bypass de rate-limit, cf. SEV-2 do runbook). |
| **Bloqueio da allowlist SSRF** | `services/http_client.HostNaoPermitido` (allowlist deny-by-default + resolução para IP público). **[FALTA]** não é logado como evento próprio no ponto do `raise`; hoje **bubbla** e aparece como `tese_falhou` (`erro=HostNaoPermitido...`) ou `scheduler_job_falhou` (`erro="HostNaoPermitido"`). | Grep por `HostNaoPermitido` no campo `erro` de `tese_falhou`/`scheduler_job_falhou`. | **Qualquer ocorrência** → alerta (a allowlist só dispara se uma URL tentou sair para host não previsto — metadata `169.254.169.254`, rede interna, ou redirect malicioso; nunca acontece no fluxo normal). **Melhoria:** `logger.warning("ssrf_bloqueado", host=...)` no `http_client` para contar direto. |
| **Falha de job do scheduler** | `services/scheduler.py`: `scheduler_job_falhou` (job levantou exceção), `scheduler_job_timeout` (estourou `timeout_s`), `scheduler_tick_falhou`, e `scheduler_job_executado` (com `status`). Falha nunca derruba o processo (try/except por job). | `event IN (scheduler_job_falhou, scheduler_job_timeout, scheduler_tick_falhou)`, ou `scheduler_job_executado AND status="erro"`. | **Mesmo job falhando 2 ticks seguidos** → alerta (fonte externa fora do ar OU schema divergente — o `ledger` `job_runs` grava `last_status`). Distinguir de `sem_dado` (feriado/404, NO-OP esperado — **não** alertar). |
| **Falha de auth/JWT** | **[FALTA — produto sem login hoje]** (`core/ratelimit.py` e o runbook §0 confirmam: sem base de titulares autenticados). Quando o login existir (Supabase Auth): logs de Auth do Supabase + validação de JWT no backend. | (Futuro) `event="auth_falhou"` a instrumentar no backend + logs de Auth do Supabase. | (Futuro) **> N falhas de login / IP / 10 min** → brute-force; **falha de verificação de assinatura JWT** → alerta imediato (token forjado). Ligar ao SEV-2 do runbook (bypass de authz). |

## 2. CSP violation reporting (AUSENTE — a adicionar, sem implementar agora)

Hoje `frontend/src/proxy.ts` emite uma CSP estrita com nonce por requisição, **mas sem
`report-uri`/`report-to`** — violações (ex.: script injetado, tentativa de XSS bloqueada) são
descartadas pelo browser sem nos avisar. Uma CSP que bloqueia e não reporta é cega ao ataque.

> **Não implementar agora:** a CSP está sendo mexida pela raia de frontend. Este é o desenho a
> aplicar quando aquela raia estabilizar, para evitar conflito no `proxy.ts`.

Passos (quando for a hora):

1. **Diretiva de report na CSP** (`proxy.ts`), preferindo o par moderno + fallback legado:
   - `report-to csp-endpoint;` + header `Reporting-Endpoints: csp-endpoint="/api/csp-report"`.
   - `report-uri /api/csp-report;` (fallback para browsers antigos; ainda amplamente suportado).
2. **Coletor (endpoint):** uma rota `POST /api/csp-report` (Next route handler **ou** no FastAPI)
   que aceita `application/csp-report` / `application/reports+json`, **valida tamanho** (payload é
   não-confiável — reusar a política de body-size do backend), **redige** e loga como
   `csp_violation` (structlog já redige segredos). **Nunca** refletir o corpo de volta.
3. **Anti-ruído:** filtrar `blocked-uri` de extensões de browser; começar em **Report-Only**
   (`Content-Security-Policy-Report-Only`) por alguns dias para medir o baseline antes de bloquear.
4. **Alerta:** `event="csp_violation"` com `violated-directive IN (script-src, connect-src)` →
   alerta (indício de XSS/exfiltração), distinto de `style-src`/`img-src` (geralmente ruído).

## 3. Caminho mínimo de alerta e retenção

**Caminho mínimo (log-based → e-mail/Slack), sem SIEM novo:**

1. **Fonte:** logs JSON no **Railway** (backend — onde vivem quase todos os eventos da §1) e
   **Vercel** (frontend/CSP quando existir).
2. **Regra:** log-based alert / log drain da própria plataforma casando o `event` name (ex.:
   `bloqueante=true`, `TetoCustoExcedido`, `HostNaoPermitido`, `scheduler_job_falhou`).
   - Railway: **log drain** (Datadog/Logtail/Better Stack) com alerta por query; ou um webhook que
     dispara no match.
   - Alternativa keyless: os eventos **críticos e raros** (gate `bloqueante`, SSRF) podem emitir
     direto um **webhook de Slack** a partir do backend (atrás de config `.env`, degradação graciosa
     se ausente — mesmo padrão de `redis_url`/Langfuse no projeto).
3. **Destino:** canal `#seguranca` no Slack **+** e-mail do IC (`contato.davidporto@gmail.com`,
   Comandante do Incidente do runbook §1).
4. **Ligação com o IR:** todo alerta que casa um evento de severidade abre o ciclo do runbook
   `plano-resposta-incidentes-lgpd.md` §3.1 (registro de incidente + classificação SEV).

**Retenção de log de segurança:**

| Camada | Retenção hoje | Alvo "nível bancário" |
|---|---|---|
| Railway / Vercel (stdout) | Curta, padrão da plataforma (dias) | **≥ 90 dias** via log drain para storage externo (WORM/append-only se possível). |
| Supabase (Postgres/Auth) | Padrão do plano | **≥ 90 dias**; Auth logs preservados p/ investigação de authz (quando houver login). |
| SBOM CycloneDX | `retention-days: 90` (artefato do `security-scheduled.yml`) | Mantido — permite diff de supply-chain entre dias. |
| `job_runs` (ledger no Postgres) | Persistente (última execução por job) | Mantido — `last_status`/`detalhe` são a trilha de saúde do scheduler. |

## 4. Lacunas priorizadas (pendências do humano / próximas raias)

- [ ] **Log-based alert configurado** (Railway log drain OU webhook Slack) para os eventos da §1 —
      hoje os logs existem mas **ninguém é notificado** automaticamente.
- [ ] **Handler custom de 429** que loga `rate_limit_excedido` (hoje só o status HTTP existe).
- [ ] **`ssrf_bloqueado` explícito** no `http_client` (contável, não escondido em `tese_falhou`).
- [ ] **Coletor de CSP + `report-to`** (§2) — após a raia de frontend estabilizar o `proxy.ts`.
- [ ] **Retenção externa ≥ 90 dias** (log drain) — a retenção padrão de plataforma é curta demais
      para investigação de incidente.
- [ ] **Instrumentação de auth/JWT** — quando o login (Supabase Auth) entrar.
- [ ] Correlação central (SIEM leve) — Langfuse não cobre; decidir entre log drain gerenciado vs.
      solução própria quando o volume justificar.
