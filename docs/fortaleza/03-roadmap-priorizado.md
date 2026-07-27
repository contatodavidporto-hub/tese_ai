# Fortaleza — Roadmap Priorizado (o que NÃO coube nesta entrega)

> Honesto por construção: cada item diz **por que** não entrou agora e o **esforço**
> (S ≤½dia · M 1–3 dias · L >3 dias / decisão de produto). Prioridade: **P0** = fazer já
> na próxima raia · **P1** = curto prazo · **P2** = quando a frente exigir.
> Detalhe de cada achado: `00-relatorio-auditoria.md`. Pendências humanas ao fim.

## P0 — Alta severidade, exige passo que um solo pré-receita não fecha sozinho aqui

### 1. Ambiguidade de escala `pct` no documento citável + âncora do gate (HIGH, invariante nº1) — M
- **Onde:** `services/tese.py:1083` (`_documentos_metricas` emite a fração crua `0,0823 pct`) × `services/avaliacao.py:744` (`_numeros_ancora_de_metricas` aceita DUAS escalas — pontos e fração — de propósito, "hotfix 3", porque o doc mostra fração).
- **Por que não entrou:** o conserto é **interligado** (formato do doc ↔ âncora dupla ↔ testes red-team do gate v3) e mexe num gate **battle-tested ao vivo** (família TAEE11). Um meio-conserto pode **enfraquecer** o gate. A cultura do repo exige validação **ao vivo** para mudança de gate ("provado ao vivo na 2ª tentativa").
- **Fix completo:** (a) formatar o doc citável na MESMA convenção do envelope (pontos + `%`, via helper único compartilhado com `metricas_para_envelope`); (b) então **remover/estreitar a âncora-fração** (ela só existia porque o doc mostrava fração) OU não isentar token de escala-fração seguido de `%` (fração com `%` é sempre errada); (c) **re-rodar red-team ao vivo** num ticker pct-pesado (TAEE11/BBAS3) com a `ANTHROPIC_API_KEY` ativa. Precisa da chave (pendência humana) para validar de verdade.

### 2. RLS/authz sem teste comportamental (HIGH) — M
- **Onde:** `tests/test_models_schema*.py` só faz **lint textual** do SQL (`sql.count('create policy')`). Zero prova de isolamento owner-only em runtime.
- **Por que não entrou:** exige **Postgres efêmero** (testcontainers ou branch de dev do Supabase). O ambiente desta sessão **não tem Docker**; o branch do Supabase toca infra real e custa (confirmar custo).
- **Fix:** teste que aplica as migrações num Postgres, conecta como `authenticated` com JWT de **dois** usuários e prova que `SELECT/INSERT` em `teses`/`tese_versoes` respeita owner-only e que a conexão do app (owner role) é o **motivo** do bypass atual (achado H1). Adicionar serviço Postgres ao job de CI. **Andaime pode ser escrito já** (marcado `skip` sem Docker); a prova verde roda no CI.

## P1 — Correção/robustez de médio impacto (código, sem bloqueio externo)

### 3. Integridade do teto de custo de LLM (3 achados) — S/M
- Teto **anulado silenciosamente** se o modelo de síntese for trocado por env (`tese.py:74/286`); extração Haiku e tokens do consenso **não contabilizados**; teto é **memória por processo** (scripts CLI e restart zeram/duplicam). **Fix:** contabilização central de custo por chamada (todas as chamadas Anthropic passam por um registrador único), independente do id do modelo; considerar persistência (Redis/DB) para o teto valer multi-worker — hoje é `1 worker` por design.

### 4. Gates de staleness na ingestão (4 achados) — M
- `sec.ingest_pares` re-baixa MBs sem checar frescor; conectores macro rodam **~12 HTTP/geração** sem gate; `download_zip` **sem retry** (justo os arquivos grandes); paginação ANEEL **encerra parcial** silenciosamente. **Fix:** gate de frescor (TTL por fonte) antes de re-baixar; retry com backoff no `download_zip`; ANEEL deve **abster** (não persistir parcial) quando `total` vem ausente/inconsistente.

### 5. Idempotência do `POST /teses` (race → geração LLM duplicada) — M
- `routers/teses.py:67` é check-then-create sem atomicidade. **Fix:** unique constraint/`ON CONFLICT` por (user_id, ticker, janela) ou advisory lock; alinhado com o custo (evita gastar 2× o LLM no mesmo ticker).

### 6. Redação de segredo cobre só structlog (SECURITY) — S
- `core/logging.py:68`: tracebacks e logs stdlib/uvicorn passam **sem scrub**. **Fix:** `logging.Filter` de redação anexado ao root logger + teste (o redator **não tem teste** hoje — `logging.py:57`). Tightening puro.

### 7. Haiku metadata sem validação de tipo derruba geração Opus paga — S
- `tese.py:473`: metadados do Haiku sem validação podem crashar uma síntese Opus **já paga**. **Fix:** validar/coagir tipos com fallback gracioso (a geração cara não morre por metadado ruim).

### 8. Endurecimento de container/supply-chain (4 achados) — M
- `backend/Dockerfile:4` base por **tag** (sem digest); `uv` **sem pin** + **single-stage** (uv/pip ficam na imagem); a **imagem de produção nunca é escaneada** no CI (SBOM é do repo, não da imagem; sem proveniência SLSA); Dependabot `pip` **não** atualiza `uv.lock`. **Fix:** pinar base por `@sha256`; pinar `uv` (COPY do binário oficial) + multi-stage; `docker build` + `trivy image` + `syft <image>` no CI; migrar curl-pins de trivy/syft (feito nesta entrega) para action oficial pinada por SHA (Dependabot-tracked); avaliar `actions/attest-build-provenance`.

### 9. Bugs de scheduler — S
- COTAHIST pede o arquivo de `today()` UTC (quase sempre inexistente na B3 no tick) — `scheduler.py:106`; `_job_bootstrap_cadastro` **não roda `bootstrap_fiis`** (fork CLI×scheduler) — `scheduler.py:77`. **Fix:** D-1/últimos pregões; unificar o bootstrap.

### 10. Rastreabilidade no banco (2 achados) — S/M (migração)
- `fonte_id` **NULLABLE** nas tabelas de fato legadas (`0001`) contradiz "sem fonte não é fato"; elos derivados legíveis por **qualquer** authenticated (`0002:116`) — inconsistente com `tese_versoes` owner-only. **Fix:** migração expand/contract para `NOT NULL` (com backfill) e policy owner-only nos elos.

## P2 — Estrutura, testes e itens de menor severidade
- **Metadados de `ativos/base.py` não consumidos** (3 fontes de verdade paralelas) — `base.py:34`. Consolidar ou remover.
- **`ultimo_ponto_macro` materializa `macro_series` inteira 2×/geração** — `ativos/comum.py:48`. Query pontual.
- **Regexes de origem duplicadas** tese.py × avaliacao.py sem teste de paridade — `tese.py:1026`.
- **Test gaps** (dim tests-quality): disclaimer CVM fallback nunca exercitado; caminhos de erro/custo de `gerar_tese` sub-testados; `.env` real vaza para os testes (falta `conftest` de isolamento); guard anti-`httpx` contornável por alias de import.
- **Rate-limit = bucket único** por egress do proxy Vercel (sem contenção por cliente no proxy) — `frontend/.../route.ts:65`. Endereçável de verdade só com **login** (chave por usuário).
- **74 achados BAIXO**: ver tabela §4 do relatório de auditoria (nomenclatura, comentários, micro-dívidas).

## Pentest — o que ficou fora do alcance desta sessão (ver `04-relatorio-pentest.md`)
- **DAST dinâmico completo** (OWASP ZAP, nuclei, fuzzing): exige **Docker + as ferramentas** (ausentes aqui) e um staging de pé. Fizemos o **estático** (bandit/semgrep/pip-audit) + **sondagem não-destrutiva de produção** (TLS/headers). DAST fica como P1 quando houver runner com Docker.
- **Teste de cruzamento de tenant** contra DB real: ver item 2 (precisa Postgres/creds).
- **Scan da imagem de produção real** (camada de SO): ver item 8.

## Pendências do HUMANO (o Fable não resolve — só quem tem as contas)
1. **Crédito/limite da `ANTHROPIC_API_KEY` no Railway** — CRÍTICA desde 11/07. Bloqueia a validação ao vivo do item 1 (pct) e a geração real. O sistema **degrada com dignidade** sem ela (abstém), mas o produto não gera.
2. `CONSENSO_ENABLED=true` no Railway.
3. **Leaked-password protection** no Supabase (toggle grátis).
4. **Fila Dependabot #33–#39**: #33–#36/#38/#39 = merge seguro; **#37 (typescript 7.0.2) = SEGURAR** (build FAIL).
5. Clearance **INPI** da marca (classes 36/42).
6. **WAF/anti-bot** (🔒 pago) — fecha API4/API6 de verdade.
