# Relatório de Ataque Honesto — Onda 4: A Portaria

**Alvo:** Tese AI — SaaS de teses de investimento com citação rastreável
**Escopo:** white-box, apenas código próprio (`wt-portaria`), pentest autorizado
**Data:** 2026-07-28
**Método:** revisão de código (backend FastAPI + BFF Next) + provas SQL ao vivo no Postgres de produção

---

## 1. Sumário executivo

**Veredito geral: a espinha dorsal de sessão e controle de acesso da Portaria é SÓLIDA.** A virada do modelo de confiança (backend deixa de furar RLS) está provada ao vivo, não apenas no código: como `authenticated` com `sub` arbitrário **e** como `anon`, o atacante lê exatamente o acervo público e **zero** dado privado. O IDOR está morto (GET público-ou-do-dono com 404 uniforme). A validação de JWT é rigorosa (allowlist `ES256` fechada, `aud`/`iss`/`require` pinados — mata alg-confusion e `alg:none`), os cookies são `httpOnly`+`Secure`+`SameSite=Lax` forçados por construção, e o CSRF é fail-closed em todo handler mutante.

**O que está PROVADO (produção, SQL ao vivo):** isolamento de leitura e escrita, integridade do acervo, step-up aal2 vivo (5 policies restritivas), e o cabeçalho de segurança da resposta (CSP diff-zero intacta, HSTS, COOP/CORP, open-redirect neutralizado).

**Nenhum achado crítico ou alto.** O achado de maior severidade honesta é **médio** (LIVE-1: grants `ALL`/`TRUNCATE` que não passam por RLS). Tudo o mais, sob autoexame cético, cai para **baixo** (defesa-em-profundidade / higiene de anti-automação) ou **info** (controles validados). Vários achados originalmente marcados "médio" pela análise inicial foram **rebaixados para baixo** após confronto com controles compensatórios reais (GoTrue gerenciado, policies aal2 vivas, secure-email-change, teto de custo em dólar).

**O que NÃO pôde ser testado ao vivo, e por quê:** a campanha viva de **aplicação** (lifecycle de conta com 2 usuários reais, força-bruta/timing de login, IDOR nos endpoints FastAPI em runtime, abuso de e-mail, bypass de 2FA, corrida) está **diferida**: depende de wiring humano ainda pendente (app_backend LOGIN+senha, `DATABASE_URL_RLS`, `PORTARIA_SECRET`, dashboard Auth do Supabase). Enquanto o app não sobe cabeado, esses testes mediriam o sistema errado. As evidências desses vetores são, por ora, **estáticas** (código) — os achados AUTH-01/SESS-01/MFA-01/LLM-COST-01 são gaps arquiteturais, não exploits provados ao vivo. Ver Seção 6.

**Recomendação de gate de deploy:** os achados são de hardening, não bloqueantes de confidencialidade. Priorizar LIVE-1 (REVOKE de menor-privilégio) e o piso de senha (V2.1.1). Executar a Seção 6 assim que o runtime subir.

---

## 2. Provas vivas em produção (autoritativas)

> Provadas por SQL ao vivo no Postgres de produção. Onde a leitura do código sugeriu o contrário, o estado vivo vence.

### 2.1 Isolamento de leitura
Como `authenticated` (sub arbitrário, aal1) **e** como `anon`, via `SET LOCAL ROLE` + claims forjadas:

| Recurso | Visível | Esperado |
|---|---|---|
| Teses públicas | **327** | 327 |
| Elos públicos | **540** | 540 |
| Teses privadas | **0** | 0 |
| Histórico | **0** | 0 |
| Documentos | **0** | 0 |
| Chunks | **0** | 0 |
| `tese_cache_conteudo` | **0** | 0 |
| `codigos_recuperacao` (cofre) | **0** | 0 |

### 2.2 Isolamento de escrita — 4 provas de negação (todas `ERROR 42501`, nada persistiu)
- **(E)** `authenticated` criar tese pública → **BLOQUEADO**
- **(E2)** `authenticated` forjar tese privada de outro `user_id` → **BLOQUEADO**
- **(F)** `anon` criar tese → **BLOQUEADO**
- **(G)** `authenticated` escrever no cofre `codigos_recuperacao` → **BLOQUEADO**

### 2.3 Integridade
327 teses todas públicas (`user_id NULL`); 0 incoerências (teses/versões/elos); 0 elos órfãos; cofre vazio; backup `_portaria_backup_demo` = 654 linhas.

### 2.4 Step-up aal2
5 policies restritivas aal2 (teses/tese_versoes/elos/documentos/chunks) verificadas **vivas**; predicado usa `tem_fator_totp_verified` + claim `aal` do `request.jwt.claims`. Isolamento 2-usuários + step-up já provados no CI `rls-isolation` contra Postgres real, com as mesmas policies verificadas idênticas em produção.

### 2.5 Cabeçalhos e redirects (prod, `/entrar`)
CSP `script-src self nonce-<rand> strict-dynamic`, **sem** `unsafe-inline`/`unsafe-eval` (**diff-zero intacto**); HSTS 2y preload; X-Frame DENY; Referrer `strict-origin-when-cross-origin`; COOP+CORP same-origin; X-Content-Type nosniff; Permissions-Policy travada; `/entrar` `no-store`. `validaSeguir`: todos os vetores de open-redirect (https / tab / protocol-relative / backslash) neutralizados para `/historico`.

---

## 3. Achados confirmados (ordenados por severidade honesta)

> A coluna "Sev. honesta" reflete o autoexame cético (severidade ajustada). Onde a análise inicial marcou algo mais alto, indico "(orig. X)". "Alcançável?" = atingível por atacante externo hoje.

| ID | Título | Sev. honesta | Alcançável? | Arquivo:linha | ASVS |
|---|---|---|---|---|---|
| **LIVE-1** | Grants `ALL` (incl. `TRUNCATE`, que ignora RLS) a anon/authenticated | **médio** | latente | grants de produção / migração 0007 | V4.1.3 |
| **LIVE-2** | Oráculo de enrolamento 2FA via RPC PostgREST | baixo | não (DBA/white-box) | `mfa.py:95` + fn `public.tem_fator_totp_verified` | V4.3.2, V13.1.3 |
| **LIVE-3** | Cofre e tabelas sem `FORCE ROW LEVEL SECURITY` | baixo | não | `codigos_recuperacao`, `_portaria_backup_demo`, `alembic_version` | V4.1.5 |
| **AC-01** | Exportar LGPD lê no engine de sistema (bypassa RLS) — camada única | baixo | não | `backend/app/routers/conta.py:105` | V4.1.3, V4.2.1, V1.4.4 |
| **AUTH-01** | Sem rate-limit de aplicação nos endpoints de auth do BFF | baixo (orig. médio) | sim | `frontend/src/app/api/auth/entrar/route.ts:24` | V2.2.1, V11.1.4, V6.2.1 |
| **SESS-01** | Revogação de sessão não-imediata (access token stateless vale até o exp) | baixo (orig. médio) | sim* | `frontend/src/app/api/auth/sessoes/route.ts:14` | V3.3.1, V3.3.4, V3.3.2 |
| **MFA-01** | Step-up 2FA fail-open em erro de `listFactors` | baixo (orig. médio) | não | `frontend/src/app/api/conta/senha/route.ts:35` | V2.8.1, V2.2.1, V6.3.3 |
| **MFA-04** | Confirmação em código do oráculo LIVE-2 (SECURITY DEFINER no `public`) | baixo | não | `backend/app/services/mfa.py:95` | V13.1.3, V4.3.2 |
| **LLM-GATE-01** | Gate anti-recomendação: lacuna léxica de enquadramento implícito | baixo (orig. médio) | não | `backend/app/services/avaliacao.py:343` | V1.11.1, V11.1.2 |
| **LLM-COST-01** | Cost-DoS: teto de custo é balde global, sem orçamento por-usuário | baixo (orig. médio) | sim* | `backend/app/core/limits.py:74` | V11.1.4, V11.1.2 |

\* alcançável mas com pré-condição forte e/ou dependente do wiring de runtime (ver detalhe).

**Controles VALIDADOS (PASSOU — info, não são vulnerabilidades):** SESS-03, LLM-CONS-PASS, LLM-INJ-PASS (Seção 3.4).

---

### 3.1 Achados vivos (provados por SQL em produção)

#### LIVE-1 — Violação de menor-privilégio: `ALL`/`TRUNCATE` a anon+authenticated em TODAS as tabelas — **MÉDIO**
- **Evidência (autoritativa):** `information_schema.role_table_grants` ao vivo mostra `anon` e `authenticated` com `DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE` em teses, tese_versoes, elos, documentos, chunks, historico_itens, `codigos_recuperacao`, tese_cache_conteudo, `_portaria_backup_demo`, `alembic_version`. É o `GRANT ALL` default do schema `public` do Supabase: a migração 0007 concede grants **estreitos** (select/insert/update/delete) mas **não REVOGA** o default — por isso o efetivo é `ALL`.
- **Ataque:** RLS mascara hoje (deny-all/policy-gated), **mas `TRUNCATE` não é submetido a RLS**. Se qualquer caminho (injeção; ou migração futura que esqueça RLS numa tabela nova) rodar sob anon/authenticated, o dado cai sem a policy proteger. É cinto (RLS) sem suspensório (grant).
- **Correção:** `REVOKE ALL` de anon/authenticated e conceder o mínimo (anon `SELECT` em teses/versoes/elos; authenticated `SELECT/INSERT/UPDATE/DELETE` só nas tabelas de usuário); `REVOKE TRUNCATE, TRIGGER, REFERENCES` de anon/authenticated em tudo; `ALTER DEFAULT PRIVILEGES` para tabelas novas não herdarem `ALL`.
- **Nota cética:** a migração não é a fonte do problema (ela concede estreito) — o problema é o default não-revogado. Achado REAL; latente hoje porque o app conecta como `app_backend` (nobypassrls, não-dono).

#### LIVE-2 — Oráculo de enrolamento 2FA via RPC PostgREST — **BAIXO**
- **Evidência:** vivo, `SET ROLE authenticated; select public.tem_fator_totp_verified('<uuid arbitrário>')` retorna boolean sem erro. Advisor `authenticated_security_definer_function_executable`. Exposta em `/rest/v1/rpc/tem_fator_totp_verified`.
- **Ataque:** usuário logado com a apikey descobre se um uid alvo tem 2FA verificado. Mitigado por uuid4 não-enumerável + apikey server-only. A prova usou `SET ROLE` direto no DB (ação DBA/white-box), não caminho externo.
- **Correção:** mover a função para schema **não exposto** pelo PostgREST (`private`/`app`), referenciar schema-qualificada nas policies aal2 e no backend; **MANTER** `grant execute to authenticated` (a policy aal2 avalia como role authenticated). **Não revogar EXECUTE.**

#### LIVE-3 — Cofre e tabelas sem `FORCE ROW LEVEL SECURITY` — **BAIXO**
- **Evidência:** `pg_class.relforcerowsecurity=false` para `codigos_recuperacao` (as 7 tabelas centrais têm `force` via 0007; o cofre criado no 0009 só tem `enable`). RLS enabled sem policy = deny-all para não-dono, mas o **dono da tabela (postgres) não é cercado**.
- **Ataque:** defesa em profundidade. Se algum processo conectar como dono, lê/escreve o cofre ignorando RLS. App conecta como `app_backend` (nobypassrls, não-dono) → não explora hoje; risco latente.
- **Correção:** `ALTER TABLE codigos_recuperacao FORCE ROW LEVEL SECURITY` (idem `_portaria_backup_demo` e `alembic_version`).

---

### 3.2 Achados de código — access-control / authn / session

#### AC-01 — Exportar LGPD lê no engine de sistema (bypassa RLS) — camada única — **BAIXO** (alcançável: não)
- **Arquivo:** `backend/app/routers/conta.py:105`
- **Evidência:** o handler declara `session: Annotated[Session, Depends(get_session)]` — `get_session` (`db/session.py:29`) usa o `SessionLocal` do engine de **sistema** (`DATABASE_URL`, role owner/bypassrls), não a lane RLS. Sob esse engine o `after_begin` de `rls.py:84` é no-op → **nenhuma policy aplicada**. As leituras seguintes tocam tabelas com policy `owner_all`: `teses` (`:110`), versão por `TeseVersao.tese_id` (`:113-118`), `historico` (`:136`). Exportar **não** lê o cofre `codigos_recuperacao` que justifica o engine de sistema — logo o bypass de RLS aqui é **desnecessário** e deixa o `WHERE user_id == uid` como único guardião.
- **Ataque (não alcançável hoje):** o `uid` vem puramente do `sub` de um JWT verificado (JWKS ES256, aud/iss pinados) — nenhuma entrada do cliente influencia; queries parametrizadas. O risco é de **regressão/defesa-em-profundidade**: um refactor que adicione consulta sem o `WHERE`, ou um bug na derivação do `uid`, despejaria a tabela multi-tenant inteira, pois o role de sistema ignora as policies. Contraste com GET `/teses/{id}` (RLS camada A + filtro camada B), onde um erro no filtro ainda seria barrado pela RLS.
- **Correção:** rodar exportar sob a lane de usuário (`rls.get_session_usuario`) para Tese/TeseVersao/HistoricoItem (belt+suspenders); reservar o engine de sistema estritamente ao cofre (gerar_codigos/break_glass) e à Admin API do excluir. Se permanecer no engine de sistema, documentar que o `WHERE` é o único controle e cobrir com teste de regressão de escopo por usuário.

#### AUTH-01 — Sem rate-limit de aplicação nos endpoints de auth do BFF — **BAIXO** (orig. médio; alcançável: sim)
- **Arquivo:** `frontend/src/app/api/auth/entrar/route.ts:24`
- **Evidência:** `supabase.auth.signInWithPassword(...)` chamado sem limiter. Nenhum handler de auth do BFF (entrar, criar-conta, recuperar, redefinir, desafio, 2fa/verify, 2fa/enroll) importa rate-limit — grep por `limit|throttle` em `frontend/src/app/api/auth` = 0. O `limiter` do slowapi (`core/ratelimit.py`) só decora rotas do FastAPI, e esses fluxos vão **direto ao GoTrue** via `@supabase/ssr`. Contraste proposital: break-glass tem `limiter.limit("5/hour")` (`conta.py:69`); geração de tese tem 30/hour. CAPTCHA está barrado pela CSP `connect-src 'self'` (`proxy.ts:22`).
- **Ataque:** credential-stuffing scriptado contra `/api/auth/entrar` (a defesa CSRF `mesmaOrigem` não barra automação — o atacante seta o próprio `Origin==Host` e omite `Sec-Fetch-Site`); abuso de e-mail (signup/reset). O vetor mais agudo alegado (força-bruta TOTP no `/desafio`, espaço 10^6) foi **refutado como agudo** no autoexame.
- **Por que baixo (não médio):** produção é um **GoTrue gerenciado** com rate-limits nativos por padrão — cap de envio de e-mail no nível do projeto (contém abuso de signup/reset), limites por-IP de token/OTP, limites de challenge/verify de MFA. A rotação do código TOTP a cada ~30s inviabiliza varrer 10^6 na janela. Sobra como residual **real** apenas credential-stuffing de senha (freado por limites por-IP do GoTrue, evadíveis por rotação de IP) — gap de defesa-em-profundidade legítimo, baixo.
- **Correção:** limiter no edge/BFF (Upstash/Vercel KV) reutilizando `_chave_por_ip`: login com backoff/lockout (ex. 10/min/IP, 5/15min por e-mail), teto por e-mail em signup/recuperar, teto agressivo por sessão em desafio/2fa-verify; confirmar/endurecer os limites nativos do GoTrue no dashboard.

#### SESS-01 — Revogação de sessão não-imediata (JWT stateless) — **BAIXO** (orig. médio; alcançável: sim, com posse prévia da sessão)
- **Arquivo:** `frontend/src/app/api/auth/sessoes/route.ts:14`
- **Evidência:** `:7` anuncia "Encerrar TODAS as sessões — defesa contra token roubado"; `:14` faz `signOut({ scope: "global" })` (revoga **refresh tokens** no GoTrue). Mas o resource-server é 100% stateless: `auth.py:107-138` faz `jwt.decode(... algorithms=["ES256"] ...)` com o único limite temporal sendo `exp` (+leeway 30s) — sem introspecção nem deny-list de session_id. Os caminhos de **dados** usam `getClaims()` (`sessao.ts:20`), cego a revogação (o próprio módulo admite, `sessao.ts:32-34`): `teses/route.ts:39` e `conta/exportar/route.ts:16` (dump LGPD). Só as trocas de credencial (senha `:26`, email `:22`, excluir `:24`) usam `getUser()`.
- **Ataque:** uma sessão viva num navegador que legitimamente detém o cookie (dispositivo compartilhado/esquecido logado); a vítima aciona "encerrar todas" de outro aparelho; o **access token já emitido** segue válido no cookie do atacante até o `exp` (padrão Supabase ~1h), continuando a ler `/historico`, gerar teses e **exportar todos os dados pessoais**. httpOnly não protege — o atacante está dentro do navegador que possui o cookie.
- **Por que baixo (não médio):** pré-condição forte (posse prévia da sessão viva; httpOnly+CSP strict bloqueiam roubo por XSS); **nenhuma capacidade nova** (quem detém a sessão já podia exportar antes do clique) — o achado é sobre **latência** da revogação, não bypass de autz; takeover/lockout já bloqueado (senha/email/excluir usam `getUser()`); janela limitada pelo TTL.
- **Correção:** (1) encurtar TTL do access token no dashboard (5–10 min); (2) corrigir o comentário `sessoes/route.ts:7` para "corte em ATÉ o TTL, não instantâneo"; (3) usar `getUser()` (revogação-ciente) no gate de `conta/exportar` — como já fazem senha/email/excluir — ou deny-list de session_id para operações de alto valor.

#### MFA-01 — Step-up 2FA fail-open em erro de `listFactors` — **BAIXO** (orig. médio; alcançável: não)
- **Arquivo:** `frontend/src/app/api/conta/senha/route.ts:35`
- **Evidência:** `const { data: fatores } = await supabase.auth.mfa.listFactors();` — o campo `error` **não é lido**. `const totp = (fatores?.totp ?? []).find(f => f.status === "verified");` `if (totp) { ...challenge+verify... }`. Se `listFactors` devolver `{data:null,error}`, `fatores` é null → `[]`.find = undefined → `if (totp)` falso → step-up **pulado** → cai em `updateUser({password})` (`:50`). Padrão idêntico em `email/route.ts:29-42` e `excluir/route.ts:31-43`. Senha e e-mail são operações **puras do BFF** (sem backstop FastAPI) — o `if (totp)` é a única trava. (Excluir tem backstop: FastAPI `exigir_aal2`, `conta.py:156`.)
- **Ataque:** atacante que já tem a senha da vítima; POST em `/api/conta/senha`; se `listFactors` degradar naquele instante, o TOTP é silenciosamente pulado e `updateUser` troca a senha sem segundo fator.
- **Por que baixo (não account-takeover médio):** o gatilho não é controlável pelo atacante (`listFactors`→`getUser`→`GET /user` logo após um `signInWithPassword` bem-sucedido no mesmo GoTrue; falha isolada é transiente não-correlacionada). Mesmo disparando, a troca de senha **não remove o fator TOTP** → a sessão do atacante permanece **aal1** e as policies aal2 vivas mantêm teses privadas/documentos/chunks/códigos inacessíveis. E-mail é neutralizado por secure-email-change (dupla confirmação); exclusão pelo backstop FastAPI. Pior caso residual = lockout/DoS por quem já tem a senha, sem acesso a dado aal2.
- **Correção:** ler e tratar o erro — `const { data: fatores, error: eF } = ...; if (eF) return redir(...'?erro=indisponivel')`. Nunca inferir "sem 2FA" de uma chamada que falhou; só pular o step-up quando `listFactors` retornar sucesso com lista de verificados comprovadamente vazia. Aplicar em senha/email/excluir/desafio/unenroll/enroll.

#### MFA-04 — Confirmação em código de LIVE-2 — **BAIXO** (alcançável: não)
- **Arquivo:** `backend/app/services/mfa.py:95`
- **Evidência:** `tem_fator_totp_verificado(...)` executa `text("select public.tem_fator_totp_verified(:uid)")`. É a fonte única (a policy aal2 usa a mesma fn), vive no schema `public` → exposta pelo PostgREST como `/rest/v1/rpc/...`. Corrobora LIVE-2.
- **Ataque:** oráculo de estado de enrolamento; mitigado por uuid4 não-enumerável + apikey server-only + `anon` revogado (migração 0009:79). O caller da app (`conta.py:48`) usa o uid do próprio chamador, nunca arbitrário.
- **Correção:** idêntica a LIVE-2 (mover a fn para schema não exposto, referenciar schema-qualificada, **manter** `grant execute to authenticated`).

---

### 3.3 Achados de código — LLM / disponibilidade

#### LLM-GATE-01 — Gate anti-recomendação: lacuna léxica de enquadramento implícito — **BAIXO** (orig. médio; alcançável: não)
- **Arquivo:** `backend/app/services/avaliacao.py:343`
- **Evidência:** `_R11_DIRETIVA_RE` (`:343-348`) é estreito (`compr\w*|vend\w*|aproveite\w*|entrada|oportunidade\s+de\s+(?:compra|venda)|desconto\s+de\s+\d+%...`). Termos de enquadramento como "descontado", "barato", "caro", "atrativo", "assimetria favorável", "clara oportunidade" **não** estão nem no R11 nem em `_PADROES_RECOMENDACAO` (`:172-258`). Ex.: "O valor intrínseco de R$ 80 está bem acima do preço, deixando o papel claramente descontado e atrativo." casa `_R11_TERMO_RE` mas nenhuma diretiva → `bloqueante=False` (`:1469-1480`) → status `ready` → markdown servido (`teses.py:169`).
- **Ataque:** deriva do modelo (não atacante externo) fecha a síntese com enquadramento de subvalorização; o gate determinístico não bloqueia; a tese é servida com recomendação de compra **implícita**.
- **Por que baixo (não médio):** o único input do usuário é `ticker` estritamente validado (`schemas/tese.py:24-39`), sem texto livre injetável; documentos vêm de fontes oficiais (CVM/B3/BCB/ANBIMA). O controle **primário** — system prompt (`tese.py:87-89`) — já proíbe "opinião direcional". O gate é backstop declaradamente heurístico. Válido como item de conformidade porque o serviço é automático (sem revisão humana em runtime).
- **Correção:** expandir o léxico de **postura** (não o numérico) com os enquadramentos implícitos ("descontad[oa]", "sub(valorizad|precificad)[oa]", "barat[oa]/car[oa]" em contexto de preço, "atrativ[oa]", "(clara|boa) oportunidade", "assimetria (favorável|positiva)", "margem de segurança", "espaço para (valorização|apreciação)"), mantendo a exclusão de "acima/abaixo de" (IFRS). Complementar com o juiz de fidelidade/postura (NLI/LLM-judge) sobre a Seção 5 como gate adicional. Fixtures adversariais devem sair `bloqueante=True`.

#### LLM-COST-01 — Cost-DoS: teto de custo global sem orçamento por-usuário — **BAIXO** (orig. médio; alcançável: sim, dependente de runtime)
- **Arquivo:** `backend/app/core/limits.py:74`
- **Evidência:** `CUSTO_DIARIO` é um único `CustoDiarioTracker` process-global (`:63-105`); `verificar` levanta `TetoCustoExcedido` para **qualquer** geração ao atingir `teto` (`tese_teto_custo_usd_dia=25.0`, `config.py:109`; custo/tese ~US$0,60-0,70). Rate-limit é por-usuário `30/hour` (chave `user:{sub}`, `ratelimit.py:22-34`), mas **não há orçamento de custo por-usuário** — grep por `por_usuario|budget|orcamento|teto_usd_dia_por` só retorna o global. Cache só deduplica o **mesmo** ticker.
- **Ataque:** uma conta enviando ~36 tickers válidos distintos não-cacheados exaure os US$25 e bloqueia geração nova para todos até a virada UTC.
- **Por que baixo (não médio):** impacto é **disponibilidade parcial e auto-curável** (<=24h), sem tocar confidencialidade/integridade; o **custo em dólar** (dano primário) está bem contido pelo próprio teto; cap de concorrência `tese_max_concorrencia=2` (`limits.py:51-57`, usado `tese.py:1525`) neutraliza a rajada (obriga a pacear 2-a-2); vitrine pública/cache e GET `/teses/{id}` seguem servindo sem LLM; POST exige conta. É limitação v1 explicitamente documentada.
- **Correção:** orçamento de custo **por-usuário/dia** (`teto_usd_dia_por_sub`) além do global, e/ou cap de gerações-que-gastam-LLM por-usuário/dia (distinto do rate-limit de requests, que conta cache-hits); mover o contador para storage compartilhado (Redis) cross-worker; preservar o teto global como circuit-breaker. Regressão: esgotado o orçamento de A, B ainda gera.

---

### 3.4 Controles VALIDADOS (PASSOU — info, não são vulnerabilidades)

Tentei refutar cada um lendo o código real; nenhum quebrou.

#### SESS-03 — Validação de JWT robusta contra alg-confusion/`none` + sessão correta — **PASSOU**
`auth.py:39` `ALGORITMOS = ["ES256"]` (allowlist fechada); `:107-115` decode com `audience`/`issuer` pinados e `require:["exp","sub","session_id"]`; `:127` guarda extra. Vetores testados e todos rejeitados: `alg:none`; HS256 com a chave EC pública como segredo HMAC; token sem exp/sub/session_id; aud/iss divergentes; `kid` desconhecido (→ 401 fail-closed, não 500). O role Postgres da lane é **hardcoded** (`rls.py:37` `SET LOCAL ROLE authenticated`), não deriva do claim `role` — injetar `role` é inerte. Cookies httpOnly+secure+sameSite forçados (`supabaseServer.ts:39-47`). **Manter; não afrouxar.** Única ressalva (trade-off inerente de JWT stateless, não bug): validação stateless não checa revogação — é o SESS-01.

#### LLM-CONS-PASS — Forja de citação e injeção via web bloqueadas — **PASSOU**
`_validar_item` (`consenso.py:316-395`) só aceita item se: URL em domínio curado (suffix-match correto, derruba `infomoney.com.br.evil.com`); valor numérico consta do `cited_text[:150]` da citação da mesma URL (as citações vêm de `web_search_result_location` geradas pelo servidor Anthropic — o modelo não forja o `cited_text`); staleness/sanity-bound 0,2x–5x; `casa` como substring verificada. Conteúdo web nunca vira texto citável livre. Gate R12 (`avaliacao.py:1223-1286`) amarra número/termo direcional a item **validado** do envelope. Gated por `consenso_enabled` (OFF em prod). **Manter.** Sugestão de robustez: fixture de regressão com envelope adversarial.

#### LLM-INJ-PASS — Injeção via instrução e via conteúdo não subverte a síntese — **PASSOU**
Instrução: `ticker` validado por schema estrito (`schemas/tese.py:24-41`); `nome` vem do DB/CVM (não do request) e passa por `_sanitizar_instrucao` (`tese.py:155-165`). Conteúdo: cada fonte vira bloco `document` estrutural da Anthropic (`:250-269`), imune a forja textual de tags. Backstop fail-closed: `avaliar_tese` grava `envelope['erro']` + `status='error'` e o router recusa servir markdown de tese bloqueada (`teses.py:165-172`). Disclaimer forçado (`tese.py:1600-1601`). **Manter.** Endurecimento opcional: envolver ticker/nome em XML tags + `re.sub` como no consenso; blindar `warm_cache`/`gerar_e_avaliar` que chamam `criar_tese` fora do schema do router.

---

## 4. Achados refutados / rebaixados (transparência)

O revisor cético rebaixou os itens abaixo a **info** (`real=false`) — não são vulnerabilidades acionáveis, mas hardening válido. Documentados para não inflar o placar.

| ID | Título | Por que NÃO é vuln alcançável |
|---|---|---|
| **AC-02 / AUTH-03 / SESS-02 / MFA-02** | Freshness do break-glass fail-open com `amr` sem timestamp (`conta.py:61`) | O ramo fail-open é REAL no código, mas o `amr` viaja num JWT ES256 **inforjável**; o GoTrue emite o timestamp numérico em operação normal → ramo não disparado hoje. Dupla mitigação: break-glass exige **código de recuperação single-use de 80 bits** que só o dono tem; a operação é sobre a própria UID (sem cross-tenant). Fix fail-closed é higiene barata. Quatro achados apontam o mesmo ponto. |
| **AUTH-02** | `token_hash` de reset ecoado na query string em redirect de erro (`redefinir/route.ts:25,30`) | O token já chega via GET na URL do link de e-mail e pousa no histórico/logs **antes** de qualquer erro; o redirect só repete o mesmo segredo nos mesmos canais que já o têm — sem canal novo. Single-use + TTL curto + no-store + Referrer-Policy contêm. Risco incremental ~nulo. |
| **MFA-03** | Sem throttle de app na força-bruta TOTP do `/desafio` (`desafio/route.ts:29-35`) | Fato verdadeiro, mas exige sessão aal1 (senha já comprometida); CSRF `mesmaOrigem` fail-closed; rate-limit de MFA nativo do GoTrue (default seguro) + janela TOTP ~30s + 3 round-trips por tentativa tornam a varredura de 10^6 inviável. Contingente a uma má-config externa não demonstrada. Subsumido por AUTH-01. |
| **LLM-GATE-02** | Varredura do gate não normaliza Unicode/zero-width (`avaliacao.py:1247-1258`) | Observação acurada, mas exige injeção bem-sucedida + jailbreak do modelo + obediência a inserir zero-width no verbo; um modelo já jailbroken evade por paráfrase semântica (zero-width não adiciona capacidade). O "contraste" com `_sem_acentos` é falso (NFD não remove U+200B). Hardening pesado (NFKC + remoção Cf + confusable map), não bloqueante. |
| **LLM-EXFIL-01** | Markdown do LLM servido cru; imagens não neutralizadas server-side (`tese.py:1612`, `teses.py:169`) | Fatos corretos, mas o único renderizador (`Markdown.tsx`) é inerte (sem `dangerouslySetInnerHTML`, nunca emite `<img>`). O "outro consumidor" que dispararia o beacon **não existe** (grep por marked/react-markdown/pdfkit/weasyprint = 0). `/conta/exportar` devolve JSON (não dispara GET de imagem). Sem exfil cross-tenant. Hardening para consumidores futuros. |
| **INJ-SSRF-01** | Anti-SSRF valida DNS uma vez sem pinar o IP (TOCTOU/rebinding) | Nenhum host é controlado pelo usuário (URLs hardcoded; allowlist fechada só de domínios .gov/financeiros). Explorar rebinding exigiria controlar o DNS autoritativo de um órgão público — comprometimento maior que o próprio SSRF. Defesa-em-profundidade já presente (bloqueio de IP interno + revalidação por event_hook). |
| **INJ-SSRF-02** | CSP `img-src` permite `data:`/`blob:` (`proxy.ts:18`) | Não há sink `<img>` para saída do LLM em nenhuma rota; `![alt](...)` vira `<a>` (o `!` fica texto) e é filtrado por `hostsOk`; `data:`/`blob:` nem casam no `LINK_RE`. Requisito atendido por **ausência de sink**. `data:`/`blob:` provavelmente servem o WebGL/gráficos. |
| **FS-1** | Fail-closed do perímetro por match exato de `APP_ENV`, default "development" (`perimetro.py:29`, `config.py:25`) | Exige misconfig composta do operador (não controlável pelo atacante). O mesmo `app_env` que desarma o guard expõe `/docs,/redoc,/openapi.json` (`main.py`) — o runbook `DEPLOY.md:40-41` checa que dão 404 em prod, e o log de startup mostra `app_env=development`. X-Portaria é defesa-em-profundidade explícita, não auth primário; sobrevivem JWT ES256, RLS viva e rate-limit backend. |
| **LGPD-01** | Scrubber de log orientado a segredos, não a PII (`logging.py:15-33`) | Descrição correta, mas nenhum caminho leva PII real a log hoje (o único `logger.info(email=...)` emite a constante `demo@tese-ai.local`; `conta.py:140` é resposta ao dono, não log). Convenção viva usa só `user_id` UUID. Hardening preventivo contra código futuro. |
| **LGPD-02** | Exportar no engine bypassrls — isolamento só pelo WHERE | Mesmo ponto de AC-01; o `uid` vem do JWT verificado (não IDOR), queries parametrizadas. "Não explorável hoje"; risco especulativo de refactor. Consistência/defesa-em-profundidade, info. (Ver AC-01, mantido como baixo por ser dado LGPD-sensível.) |
| **LGPD-03** | Exportação traz só a última versão de cada tese (`conta.py:113-118` `limit(1)`) | Exporta **menos** dados (não vaza nada), escopado + aal2. A premissa "versões históricas omitidas" é insubsistente: cada geração cria exatamente **uma** `TeseVersao`; não há fluxo de "regenerar" que empilhe versão. O `limit(1)` não descarta histórico — ele não existe. Falso-positivo de segurança; nota de produto/documentação. |

---

## 5. Scorecard OWASP ASVS — V2 (Autenticação), V3 (Sessão), V4 (Controle de Acesso)

Auditoria white-box do worktree `wt-portaria`, ancorada no código real e nas provas vivas de produção. O desenho de sessão e o núcleo de controle de acesso são fortes: validação de JWT rigorosa (allowlist `ES256` explícita, `aud`/`iss`/`require` pinados — mata alg-confusion e `alg:none`), cookies `httpOnly`+`Secure`+`SameSite=Lax` forçados por construção, CSRF fail-closed em todo handler mutante, e IDOR morto (leitura público-ou-do-dono, 404 uniforme, provado vivo: 0 teses privadas vazadas). As lacunas são de **defesa em profundidade e higiene de anti-automação**, todas baixas/médias e confirmadas: menor-privilégio de grants (LIVE-1, TRUNCATE não passa por RLS), ausência de rate-limit de aplicação nos endpoints de auth do BFF (AUTH-01), revogação não-imediata do access token stateless (SESS-01), step-up 2FA fail-open em erro de `listFactors` (MFA-01), oráculo de enrolamento via RPC PostgREST (LIVE-2/MFA-04) e exportação LGPD em engine de sistema com proteção em camada única (AC-01). Comprimento mínimo de senha está em 10, abaixo do piso ASVS de 12. Itens dependentes de runtime marcados como não-verificáveis.

| Ref | Requisito | Veredito | Evidência (arquivo:linha ou prova viva) |
|---|---|---|---|
| V2.1.1 | Senha com no mínimo 12 caracteres | parcial | `MIN_SENHA = 10` em cadastro/troca/reset — abaixo do piso ASVS de 12. `criar-conta/route.ts:13,24`; `conta/senha/route.ts:12,21`; `recuperar/redefinir/route.ts:14,24` |
| V2.1.7 | Verificar senha contra listas de vazamento | parcial | HIBP por k-anonimato em set/reset, nunca no login (correto) — mas **FAIL-OPEN**: HIBP indisponível → `{vazada:false}` e o cadastro segue. `hibp.ts:16-34`; `criar-conta/route.ts:26-27` |
| V2.1.9 | Sem regras de composição obrigatórias | passou | Política "comprimento acima de tudo", sem classes de caractere. `criar-conta/route.ts:8-9,24` |
| V2.2.1 | Anti-automação (rate-limit/lockout) na autenticação | parcial | Sem rate-limit de aplicação em login/cadastro/reset/desafio do BFF (AUTH-01); depende do GoTrue upstream. Break-glass TEM `5/hour`. `entrar/route.ts:13-24`; contraste `conta.py:66-69` |
| V2.2.x | Mensagens anti-enumeração no login/cadastro | passou | Login sempre `?erro=credenciais`; cadastro sempre `/confirmar/pendente`. `entrar/route.ts:25-29`; `criar-conta/route.ts:37-38` |
| V2.5.6 | Reset por token de uso único, consumido fora de GET | passou | `verifyOtp(type:"recovery")` single-use consumido só no POST. `recuperar/redefinir/route.ts:10-11,34-38` |
| V2.5.x | Códigos de recuperação: hash + single-use atômico | passou | SHA-256 de 80 bits CSPRNG, plaintext nunca ao banco, `UPDATE … WHERE usado_em IS NULL RETURNING` (atômico). `mfa.py:37-40,43-54,57-77`. Vivo: cofre deny-all |
| V2.8.1 | TOTP no login em 2 fatores | passou | Challenge+verify do fator verificado eleva a aal2. `desafio/route.ts:24-37`; gate `entrar/route.ts:35-39` |
| V2.8.1 / V6.3.3 | Step-up TOTP em operações sensíveis | parcial | **Fail-open (MFA-01)**: `listFactors()` ignora `error` → step-up pulado. `conta/senha/route.ts:35-37`; idem `conta/email/route.ts:29-31` |
| V2.10.4 | Segredo serviço-a-serviço protegido | passou | X-Portaria com `hmac.compare_digest` + fail-closed no startup em prod. `perimetro.py:29-32,44-46`. Vivo: header presente |
| V3.2.1 | Tokens de sessão por componente confiável | passou | GoTrue via `@supabase/ssr`; cliente instanciado **por requisição**. `supabaseServer.ts:24-31` |
| V3.2.3 | Token de sessão armazenado com segurança | passou | Cookies forçados `httpOnly:true, secure:true, sameSite:"lax", path:"/"`. `supabaseServer.ts:39-47` |
| V3.3.1 | Logout invalida a sessão efetivamente | parcial | **SESS-01**: `signOut({scope:"global"})` revoga refresh; access token stateless vale até o `exp`. `sessoes/route.ts:13-14` |
| V3.3.4 | Encerrar todas as sessões ativas | parcial | Mesma limitação; confirmação forte via `getUser()` não aplicada a cada request. `sessoes/route.ts:10-18`; `sessao.ts:35-40` |
| V3.4.1/.2 | Cookie `Secure` e `HttpOnly` | passou | Ambos forçados no `setAll`. `supabaseServer.ts:42-45` |
| V3.4.3 | Cookie `SameSite` | passou | `sameSite:"lax"` forçado; segunda camada do CSRF. `supabaseServer.ts:36-45`; `csrf.ts:6` |
| V3.5.2 | Token stateless verificado (assinatura, aud, iss, exp) | passou | `jwt.decode` JWKS, `audience`+`issuer` pinados, `require:["exp","sub","session_id"]`. `auth.py:107-128` (SESS-03) |
| V3.5.3 | Prevenção de alg-confusion / `alg:none` | passou | `ALGORITMOS = ["ES256"]` allowlist fechada. `auth.py:37-39,110` (SESS-03) |
| V4.1.1 | Controle de acesso em camada confiável (servidor) | passou | RLS enforçada (lane `SET LOCAL ROLE` + claims, engine NOBYPASSRLS) + filtro explícito. `rls.py:44-58,81-88`; `teses.py:124-135`. Vivo |
| V4.1.3 | Princípio de menor privilégio | parcial | **LIVE-1 (médio)**: anon/authenticated têm `ALL` (incl. TRUNCATE, que ignora RLS) — `GRANT ALL` default não revogado. Prova: `information_schema.role_table_grants` |
| V4.1.5 | Controle de acesso fail-closed | passou | Lane RLS ausente → `RlsSemEscopo`; perímetro aborta startup sem segredo em prod. `rls.py:40-58`; `perimetro.py:27-32` |
| V4.2.1 | Autorização em nível de objeto / anti-IDOR | passou | `get_tese` só pública OU do dono; 404 uniforme. `teses.py:127-135`. Vivo: anon/authenticated forjado veem 327 públicas, 0 privadas |
| V4.2.2 | CSRF em operações que mudam estado | passou | `mesmaOrigem()` fail-closed (recusa Origin/Sec-Fetch-Site ausentes) em todo POST mutante. `csrf.ts:15-33` |
| V4.3.2 | Impedir enumeração / vazamento de metadados de autz | parcial | **LIVE-2 / MFA-04**: `tem_fator_totp_verified` SECURITY DEFINER no `public`, chamável via RPC com uid arbitrário → oráculo 2FA. Mitigado por uuid4 + apikey server-only. `mfa.py:95-101` |
| V4.2.1 / V1.4.4 | Operações de dados sob autz completa | parcial | **AC-01**: `exportar_dados`/`excluir_conta` (LGPD) no engine de SISTEMA (bypassa RLS), só `WHERE user_id == uid`. `conta.py:102-110,149-160` |

**Notas:** anti-automação dependente do GoTrue upstream (V2.2.1) e timeout absoluto/idle de sessão (V3.3.2) são **não-verificáveis sem runtime** — não marcados "passou". Os "passou" de sessão (V3.2/V3.4/V3.5) e IDOR (V4.2.1) são corroborados pelo código **e** pelas provas vivas autoritativas.

---

## 6. Campanha DIFERIDA pendente de runtime

A campanha de **banco** já foi executada (Seção 2). A campanha viva de **aplicação** exige o wiring humano antes de ser executável — enquanto não sobe, esses testes mediriam o sistema errado.

**Pré-requisitos de wiring (bloqueiam a execução):**
- Railway: `app_backend` LOGIN + senha; `DATABASE_URL_RLS` (lane de usuário); `PORTARIA_SECRET` (perímetro X-Portaria).
- Supabase dashboard: Auth com MFA/OAuth habilitados, templates de e-mail, TTL do access token (verificar valor — relevante a SESS-01), rate-limits nativos do GoTrue (relevante a AUTH-01/MFA-03).

**Plano EXATO de ataque a executar assim que subir:**

1. **Lifecycle de conta com 2 usuários reais (A e B):** signup → confirm por e-mail → login → enroll 2FA (TOTP) → OAuth Google → recuperação por código single-use. Verificar cada transição de estado e a emissão/rotação de cookies.
2. **Força-bruta / timing no login:** medir se `/api/auth/entrar` aceita alta taxa scriptada (validar AUTH-01 ao vivo; confirmar limites por-IP do GoTrue e se são evadíveis por rotação de IP); medir timing de e-mail inexistente vs. senha errada (anti-enumeração V2.2.x).
3. **IDOR vivo nos endpoints FastAPI:** com token de A, tentar ler/mutar recursos de B por manipulação de identificadores (path/query/body) em GET/POST `/teses`, `/conta/*`; confirmar 404 uniforme e ausência de oráculo de UUID. Provar que a lane RLS + filtro batem com o isolamento já provado no banco.
4. **Abuso de e-mail:** disparar signup/recuperar em loop e medir se o cap de envio no nível do projeto do Supabase contém (validar a mitigação alegada em AUTH-01).
5. **Bypass de 2FA:** (a) reproduzir o fail-open de MFA-01 induzindo falha de `listFactors` (fault injection no GoTrue) durante troca de senha/e-mail; (b) força-bruta TOTP no `/desafio` medindo o rate-limit real de MFA do GoTrue e a janela de ~30s (validar/refutar MFA-03 ao vivo); (c) break-glass: tentar remover 2FA sem código de recuperação válido e com `amr` estale (AC-02/SESS-02).
6. **Corrida (TOCTOU):** consumo concorrente do mesmo código de recuperação (provar atomicidade do `UPDATE … WHERE usado_em IS NULL RETURNING`); step-up concorrente; dupla submissão de geração de tese vs. cap de concorrência e teto de custo (validar LLM-COST-01 e o semáforo de 2).
7. **Revogação de sessão (SESS-01) ao vivo:** com A logado em 2 navegadores, acionar "encerrar todas" num e medir por quanto tempo o access token do outro segue lendo `/historico` e exportando dados (medir o TTL efetivo, não pinado no código).

---

## 7. Lacunas residuais (não cobertas)

- **TTL do access token e rate-limits nativos do GoTrue:** são **config de dashboard**, não pinados no nosso código → não verificáveis white-box. Impactam SESS-01 (janela de revogação) e AUTH-01/MFA-03 (barreira upstream). Devem ser confirmados no runtime (Seção 6, itens 2, 5, 7).
- **Timeout absoluto/idle de sessão (V3.3.2):** não verificável sem ambiente vivo.
- **HIBP fail-open (V2.1.7):** `hibp.ts:16-34` retorna `{vazada:false}` quando o serviço está indisponível, e o cadastro segue — não elevado a achado próprio nesta onda, mas é um fail-open de política de senha que vale endurecer (falhar fechado ou reter o cadastro) além do piso de 12 caracteres (V2.1.1).
- **OAuth Google (callback/estado):** o fluxo (`api/auth/oauth`, `callback`) não teve exploração viva (depende do dashboard) — cobrir CSRF de `state`, fixation e binding de sessão no runtime.
- **Fluxos internos fora do schema do router:** `warm_cache`/`gerar_e_avaliar` chamam `criar_tese` sem passar pelo schema estrito do router (usam tickers curados hoje) — endurecimento sugerido em LLM-INJ-PASS, não coberto por teste adversarial.
- **`consenso_enabled` OFF em produção:** LLM-CONS-PASS foi validado por leitura de código com a feature desligada; a superfície de consenso ao vivo (web_search real) não foi exercida.
- **Concorrência multi-worker do teto de custo:** o teto global escala por processo (limitação v1 documentada); o comportamento cross-worker real depende do deploy (número de workers) e não foi medido.

**Fechamento honesto:** nenhum achado forçado. O núcleo de autenticação, sessão e controle de acesso da Portaria resiste ao ceticismo e está provado ao vivo. Os gaps são de menor-privilégio, anti-automação e defesa-em-profundidade — corrigíveis a baixo custo, nenhum bloqueante de confidencialidade. A prova definitiva dos vetores de aplicação aguarda o wiring de runtime (Seção 6).

**Arquivos-chave inspecionados (absolutos):** `C:/Users/conta/wt-portaria/backend/app/core/auth.py`, `.../backend/app/db/rls.py`, `.../backend/app/core/perimetro.py`, `.../backend/app/core/config.py`, `.../backend/app/core/limits.py`, `.../backend/app/routers/teses.py`, `.../backend/app/routers/conta.py`, `.../backend/app/services/tese.py`, `.../backend/app/services/mfa.py`, `.../backend/app/services/avaliacao.py`, `.../backend/app/services/consenso.py`, `.../frontend/src/lib/auth/{supabaseServer,sessao,csrf,seguir,hibp,http}.ts`, `.../frontend/src/lib/backend.ts`, `.../frontend/src/app/api/auth/{entrar,criar-conta,sessoes,desafio,recuperar/redefinir,renovar}/route.ts`, `.../frontend/src/app/api/conta/{senha,email,excluir,exportar}/route.ts`, `.../frontend/src/proxy.ts`.