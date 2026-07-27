# Fortaleza — Relatório de Auditoria Total (Fase A)

> Base imutável: `origin/master @ 4790479` (PR #43, produção viva). Worktree `feat/fortaleza`.

> **Método:** fan-out de 11 leitores por subsistema + verificação ADVERSARIAL por dimensão (22 agentes, ~2,4M tokens, 0 erros). Cada achado re-lido no `arquivo:linha` citado; quem não sobreviveu à refutação foi descartado.

> **Resultado:** 113 achados brutos → **112 sobreviventes** (110 CONFIRMED + 2 PLAUSIBLE; 1 REFUTED). Severidade: 1 crítico · 6 alto · 31 médio · 74 baixo.

> **⚠ Ressalva de honestidade:** a taxa de confirmação (110/113) é alta; os itens CRÍTICO/ALTO foram **re-verificados manualmente** por mim antes de qualquer correção. Os MÉDIO/BAIXO carregam o veredito do verificador adversarial, não uma segunda leitura humana individual — trate PLAUSIBLE/BAIXO como candidatos, não sentença.


---

## 1. Mapa da lógica (ponta a ponta, por subsistema)

### Infra + CI + Supply-chain

*Higiene de supply-chain acima da média para um MVP: actions pinadas por SHA, deps travadas com hash (uv.lock/package-lock), container não-root, gitleaks+semgrep+trivy+pip-audit+npm-audit como gates, SBOM publicado e segredos só em painel de host. As lacunas se concentram nas bordas: instaladores via curl|sh de branch mutável dentro do próprio job de segurança, base image e toolchain de build sem pin, e a imagem de produção real (construída pelo Railway) nunca passa por scan/SBOM/proveniência no CI.*


Dev local: infra/docker-compose.yml sobe Postgres16+pgvector opcional (padrão é Supabase sa-east-1). CI (.github/workflows/ci.yml, permissions contents:read, tudo pinado por SHA): job backend instala exatamente o uv.lock (`uv sync --locked`), roda ruff/black/pytest/bandit/pip-audit; job security roda gitleaks (com allowlist só para chaves publishable do Supabase), semgrep (rulesets de segurança), trivy fs (CRITICAL/HIGH gate) e gera SBOM CycloneDX via syft do diretório, publicado como artefato; job frontend roda npm ci/eslint/build/npm audit high+. Dependabot semanal cobre github-actions, pip e npm. Deploy: Railway constrói backend/Dockerfile (python:3.12-slim, deps de uv.lock via `uv export --frozen`, usuário uid 10001, 1 worker uvicorn para os limites por-processo valerem, healthcheck /health, FORWARDED_ALLOW_IPS=* embutido com racional documentado — a chave de rate-limit usa o XFF mais à direita e não depende disso); Vercel constrói o frontend (sem container), com headers de segurança estáticos em next.config.ts e CSP com nonce no proxy. Segredos: apenas painéis de host (12-factor), .env ignorado no git e no .dockerignore; service_role só no backend.

### DB + Models + Migrations

*Subsistema saudável e acima da média: migrações SQL explícitas com RLS em 100% das tabelas do app, padrão expand-only disciplinado, e as tabelas novas (0005/0006) impõem 'sem fonte não é fato' no banco (NOT NULL + uniques + CHECKs). Os riscos reais são latentes, não incêndios: o isolamento multi-tenant existe só no papel (backend owner bypassa RLS e nada filtra user_id), elos vazam fragmentos de tese para qualquer authenticated, as tabelas de fatos legadas ainda aceitam fonte_id NULL, e alembic_version não tem RLS garantida em código.*


Fluxo: config.py lê DATABASE_URL (normalizado p/ psycopg3) -> session.py cria engine global (pool_pre_ping apenas; None sem .env, /health sobrevive) -> get_session (FastAPI Depends) e SessionLocal direto (BackgroundTasks, scheduler, scripts). Migrações 0001-0006 são SQL manuscrito (env.py só injeta a URL; sem autogenerate): 0001 = núcleo (referência pública + teses/tese_versoes/documentos/chunks com RLS owner-only via auth.uid(); pgvector+HNSW); 0002 = cadastro CVM, pares SEC, elos (grafo causal, leitura pública); 0003 = índices de FK + cache/reaper de teses; 0004 = job_runs (RLS deny-all, ledger do scheduler); 0005 = multiativo (FII/Tesouro, colunas aditivas nullable, ck_elos_ancora, teses.ticker varchar(32)); 0006 = tese profunda (6 tabelas de fatos, todas com fonte_id NOT NULL, uniques e CHECKs). Padrão expand-only consistente, downgrades presentes (0005 destrutivo documentado). Toda gravação de fato passa por get_or_create_fonte (fontes = trilha de auditoria); tese_versoes grava modelo+prompt_hash (rastreabilidade de LLM). Modelo de confiança REAL: o backend conecta como owner e bypassa TODA a RLS — as policies protegem apenas o caminho PostgREST (hoje sem uso); o produto opera mono-usuário (demo_user), teses tratadas como públicas (cache cross-user, GET por UUID sem filtro de dono).

### Core + Observability + App bootstrap

*Subsistema maduro e deliberado: config 100% via env (pydantic-settings) com comentários de decisão, redação de segredos em log, rate-limit anti-spoof por XFF-mais-à-direita, body-size limit ASGI puro e degradação graciosa sem ANTHROPIC_API_KEY/DATABASE_URL/Langfuse. Porém há um bug de concorrência real no guard de vagas de geração (flag compartilhada entre threads vaza permits do semáforo e pode desligar permanentemente a geração de teses até restart), e lacunas médias: redação de segredos não cobre logging stdlib/uvicorn, teto de custo diário fica inoperante se o modelo for sobreposto via env, e app_env livre cria estados intermediários inconsistentes (/docs público com logs JSON).*


Fluxo ponta-a-ponta: (1) config.py — Settings via pydantic-settings (.env relativo ao CWD, extra=ignore), tudo Optional para a app subir sem segredos; get_settings() é singleton lru_cache consumido em import-time por main/limits/ratelimit/session. (2) logging.py — structlog com processor _redact_secrets (por nome de campo e por padrão de valor: DSN postgres, sb_secret, sk-, JWT); ConsoleRenderer em development, JSON caso contrário; merge_contextvars configurado mas nunca alimentado. (3) ratelimit.py — Limiter slowapi com chave = último valor do X-Forwarded-For (anti-spoof atrás de edge-proxy; documentado que exposto direto é inseguro); Redis opcional com fallback em memória. (4) limits.py — defesas por processo do LLM caro: _SlotGeracao (BoundedSemaphore não-bloqueante, default 2) + CustoDiarioTracker (teto USD/dia UTC); consumidos por services/tese.gerar_tese. (5) langfuse_client.py — cliente lazy lru_cache, no-op sem chaves, init tolerante que loga só o tipo da exceção. (6) main.py — stack de middleware (execução: CORS estrito → BodySizeLimit 64KiB com buffer só p/ chunked → SecurityHeaders → SlowAPI → router); lifespan inicia get_langfuse() e a task do scheduler in-app (ledger job_runs + advisory lock, cancelada no shutdown); /health liveness puro isento de rate-limit; /docs//redoc//openapi desligados quando app_env=="production"; 429 tratado pelo handler do slowapi; router /teses aplica limite específico de criação e roda gerar_tese como BackgroundTask com sessão própria.

### Serviços de dados / ingestão / I/O externo

*Subsistema maduro e disciplinado nos invariantes do produto: toda gravação de fato linka Fonte (URL+data), abstenção rotulada é sistemática (DadoNaoEncontrado), anti-SSRF por allowlist deny-by-default com revalidação em redirect, e tetos de download em todos os binários. Não há violação crítica; os achados são de robustez de I/O (retry ausente no download_zip, sem circuit breaker, sem pool de conexões), gargalos de re-download sem gate de staleness (pares SEC, macro, ZIPs FII repetidos) e alguns pontos de lógica frágil (ordem do World Bank presumida, paginação ANEEL que pode fechar parcial).*


Ponta-a-ponta: (1) resolução de identidade — cvm_cadastro.resolve_ticker (cache cvm_cadastro via FCA+CAD, seed offline TICKER_CD_CVM) → dados.ensure_empresa; (2) fundamentos — dados.ingest_fundamentos baixa DFP ZIP (http_client.download_zip, teto 512MB), detecta plano de contas pelo próprio filing (planos_contas.detectar_plano), extrai contas validadas semanticamente por DS (padrão) ou localizadas por DS (banco/seguradora), persiste Fundamento+Fonte e derivadas fail-closed; (3) preços/proventos — cotahist (ZIP posicional B3, staleness 5 dias úteis, backfill mensal ≤64MB) e proventos_b3 (endpoints internos B3, payload base64 server-side, staleness 35d via Fonte); (4) macro — dados.ingest_macro/bcb_sgs (SGS), focus (Olinda OData percent-encoded + CDI), commodities/macro_global (fredgraph/World Bank), tesouro (CSV STN com janela limitada e regra taxa-0=não-ofertado), anbima_ettj (snapshot único, trava ToS), ifdata (REST não documentado com validação de conceito/cadastro), aneel (CKAN com mapa curado e agregação fail-closed); (5) pares — sec.ingest_pares via paralelo.map_concorrente (workers só I/O, persistência serial). Tudo é orquestrado por orquestracao.ingest_*_completo com SAVEPOINT por passo e commit único; scheduler roda jobs idempotentes com ledger job_runs + advisory lock. Todo fato persiste fonte_id via fontes.get_or_create_fonte; saída de rede passa exclusivamente por http_client (allowlist anti-SSRF + IP público + retry de rede em GET/POST).

### Motor de tese (avaliação/orquestração/valuation)

*Subsistema maduro e raro em disciplina anti-alucinação (abstenção rotulada em todo caminho, fonte obrigatória, gate acoplado à produção, trilha prompt_hash) — mas o gate tem dois furos reais (tese com zero citações é servida como ready; a âncora de escala dupla aceita percentual errado por 100×, cuja raiz é o documento citável expor 'pct' em fração crua) e os parâmetros do motor estão pulverizados em constantes duplicadas entre módulos (BOVA11, janela 12m, regexes de origem, detecção de setor), o padrão exato que já produziu os 3 hotfixes TAEE11.*


Fluxo ponta-a-ponta: `criar_tese` resolve a classe (NULL='acao') → `gerar_tese` valida chave/teto (`CUSTO_DIARIO`)/vaga (`GENERATION_SLOTS`) → perfil da classe (ativos/) faz ensure+ingest sob demanda via `orquestracao` (passos SAVEPOINT-isolados; conectores CVM/COTAHIST/proventos/IF.data/ANEEL/macro/SEC; falha vira lacuna) → `coletar` monta um documento citável por Fonte (fundamentos + macro + pares SEC com corte de idade) → `_montar_blocos_novos` (gate `_tem_dado_novo`) computa deterministicamente: `metricas_setor` (registro data-driven por classe/plano/setor, abstenção rotulada com Fonte obrigatória), `tecnica` (indicadores puros com KATs, leituras neutras), `valuation` (grade Ke×g CAPM-lite: Gordon, P/VP justificado, múltiplos, leitura FII — cenários, nunca ponto único), `consenso` (Haiku+web_search com validação programática A11, domínio curado) → documentos extras por ORIGEM (correção TAEE11) + apêndices de system → `_synthesize` (Opus + Citations, streaming, prompt_hash sha256 de system+docs+instrução+modelo, Langfuse) → disclaimer forçado, lacunas detectadas, envelope v3 (markdown, citações→Fonte, elos de `correlacao` com fonte nas 2 pontas e Pearson mensal n≥24, blocos novos + `texto_livre_novo`) → gate `avaliar_tese` por classe (2 superfícies: postura ampla vs proveniência numérica do modelo; carve-out de consenso; relaxamento por citação OU âncora de métrica; bloqueante ⇒ status=error, router fail-closed) → persiste TeseVersao (modelo+prompt_hash) + elos. Cache TTL por ticker e reaper de teses órfãs completam o ciclo.

### IA: Anthropic + Citations + anti-alucinação

*Subsistema maduro com defesa em camadas real e verificável no código: separação instrução×dado (XML tags + sanitização de ticker/nome), validação programática do consenso (número deve constar do cited_text do servidor, domínio allowlisted, sanity-bound), gate determinístico acoplado ao caminho de produção com router fail-closed, citações extraídas deterministicamente de document_index→Fonte, prompt_hash persistido e renderer React sem HTML injetável. Os riscos residuais estão nas bordas: o gate não bloqueia tese com zero citações (cobertura é só nota), a contabilidade do teto de custo diário depende de tabela de preços hardcoded (silenciosamente inoperante se o modelo mudar via .env) e a etapa Haiku de metadados devolve JSON sem validação de tipo, podendo descartar uma geração Opus já paga.*




### Ativos multi-classe (ação/FII/renda fixa)

*Subsistema bem projetado e disciplinado: abstenção estrutural consistente, fonte+data em todo fato coletado, legado da ação preservado byte-idêntico e nenhuma violação dos invariantes do produto (anti-alucinação/CVM/rastreabilidade). Os achados são dívida estrutural e de contrato — interface PerfilClasse não verificada, metadados de base.py mortos em runtime, full scan de macro_series e acoplamento a privados de tese.py — nenhum crítico ou alto.*


Fluxo ponta-a-ponta: (1) POST /teses → identidade.resolver_classe(codigo, session) classifica determinístico: gramática TD-* → renda_fixa; ticker B3 sufixo 11-13 (ambíguo) consulta cvm_cadastro (units vencem) → seed TICKER_CD_CVM → fii_cadastro → senão DadoNaoEncontrado; demais sufixos → acao. Classe gravada em teses.classe_ativo (NULL = acao legado). (2) tese.gerar_tese resolve o perfil via registro.perfil_da_classe (dict de MÓDULOS, import tardio p/ evitar ciclo) e conduz o mesmo pipeline para toda classe: ensure_ativo → precisa_ingest?→ingest (falha isolada por passo em orquestracao) → coletar (lista (Fonte, texto), valor formatado pela unidade, sempre com data; vazio = abstenção) → system_prompt (ação: tese._SYSTEM ± apêndice financeiro; FII/RF: templates próprios sem seção de pares) → montar_elos (grafo legado + elos por classe, fonte nas duas pontas, Pearson n>=24 ou abstém) → gate avaliacao.avaliar_tese por classe → persistir_elos ancorado por empresa_id (ação) ou ativo_codigo (FII/TD, via ancora_elos). comum.py compartilha helpers de macro (filtro por lista explícita + prefixo FOCUS_) e delega formatação em tese._fmt_fundamento. base.py define o registry de metadados (CLASSES) e o Protocol PerfilClasse — ambos documentais, não consumidos pelo runtime.

### Routers + Schemas + contrato de API + authz

*Fronteira bem construída para um produto sem login: validação de entrada estrita (regex B3/TD no pydantic), fail-closed no GET (gate/erro nunca serve markdown/citações), mensagens de erro estáveis sem vazamento, rate-limit com chave XFF anti-spoof e defesas de custo em camadas. O risco real está na camada de capacidade: um bug de concorrência no semáforo de geração (`_SlotGeracao`) vaza vagas permanentemente sob sobreposição rotineira (warm-cache + usuário) e desativa a geração de teses até restart; o resto são dívidas conscientes e bem documentadas (sem authz por desenho, idempotência não-atômica, unions sem Literal).*


POST /teses: middleware (CORS → body-size 64KiB → security headers → slowapi 30/h por IP-XFF-direita) → pydantic valida ticker (regex B3 ou TD-*) → reaper oportunista de órfãs → cache de tese `ready` ≤24h do mesmo ticker (hit devolve id existente, não gasta LLM) → resolver_classe (TD→renda_fixa; sufixo 11-13 consulta cvm_cadastro→seed→fii_cadastro; resto→ação) → criar_tese (dono = demo_user, status=processing, resolve classe DE NOVO) → BackgroundTask abre sessão própria e roda gerar_tese: teto de custo diário (US$25/processo) → semáforo de 2 vagas → ensure/ingest por perfil de classe → coleta de fatos citáveis (cada um com Fonte URL+data) → pré-síntese determinística (técnica/valuation/métricas/consenso, só com dado novo) → Opus + Citations (prompt_hash sha256 de system+docs+modelo na trilha) → gate anti-recomendação por classe (bloqueante ⇒ status=error com motivos, envelope persistido para auditoria) → TeseVersao(conteudo=envelope JSON, modelo, prompt_hash). GET /teses/{id} (sem auth, UUID é a única barreira): última versão por criado_em; status=error ou envelope com 'erro' ⇒ serve SÓ erro+lacunas (fail-closed); senão serve markdown+citações+fontes+lacunas+uso+blocos v3, com disclaimer CVM fixo no schema. Limites (semáforo, custo diário) são por processo; rate-limit vai a Redis se REDIS_URL, senão memória.

### Scripts + Scheduler + jobs

*Subsistema maduro e deliberadamente defensivo: ledger no banco, advisory lock com double-check, jobs idempotentes, degradação graciosa testada (test_scheduler.py cobre os contratos-chave) e credenciais limpas — nenhuma violação dos invariantes críticos. Os riscos residuais são operacionais: o job COTAHIST pede a data errada (pode nunca ingerir), o scheduler esqueceu o passo FII do bootstrap (fork CLI×job), e o teto de custo é por-processo/por-uptime — dívida documentada, mas que deixa o limite diário real de LLM sem enforcement global.*


Fluxo ponta-a-ponta: no startup, main.py:lifespan cria a task `scheduler_loop` (kill-switch `scheduler_enabled`). A cada tick (60s+jitter) o loop percorre EM SÉRIE os 8 jobs de `jobs_configurados` (reaper 15min → refresh_macro 24h → bootstrap_cadastro 168h → cotahist/anbima 24h → ifdata/aneel 720h → warm_cache 24h, ordem é contrato: ingest antes da re-geração). Cada job roda em `asyncio.to_thread` com `wait_for(timeout_s)`; `executar_job_sincrono` pega `pg_try_advisory_lock` numa conexão dedicada (Session pooler Supabase, modo sessão), re-checa "devido?" contra o ledger `job_runs` (cadência por `now - last_run_at >= intervalo`, sobrevive a restart/catch-up), executa, e grava o ledger SEMPRE (sucesso ou falha) antes de soltar o lock no finally. Os corpos dos jobs abrem sessões próprias (uma por item nos que iteram mapas curados), commitam internamente e absorvem `DadoNaoEncontrado` como no-op. Os scripts CLI (`app/scripts/*`) espelham os jobs para cron externo: reaper e refresh_macro delegam a serviços que commitam internamente; warm_cache compartilha o núcleo `aquecer`/`lote_default` com o job (paridade por construção); bootstrap_cadastro DIVERGE do job (só o CLI roda o passo FII). Custo LLM: cada geração do warm_cache passa por `gerar_tese`, que verifica `CUSTO_DIARIO` (tracker em memória por processo, teto US$25/dia) e o semáforo `GENERATION_SLOTS` (2 vagas), abstendo com status=error em vez de estourar. Credenciais só via .env/Settings — nada hardcoded ou impresso.

### Frontend: segurança/deps/contrato/estrutura (NÃO visual)

*Subsistema saudável e acima da média: CSP com nonce por requisição + headers completos, segredo do backend provadamente fora do bundle (server-only), validação de entrada espelhada do backend sem drift, markdown renderizado como nós React com allowlist de hosts, e os 5 invariantes do produto respeitados no que cabe ao frontend. Os achados são assimetrias de defesa em profundidade e dívidas menores (bucket de rate-limit compartilhado sendo o único de severidade média); nenhum crítico.*


Fluxo ponta-a-ponta: src/proxy.ts (substituto do middleware no Next 16) gera nonce por requisição e fixa CSP estrita (script-src nonce+strict-dynamic, connect-src 'self', frame-ancestors 'none'); next.config.ts soma headers estáticos (HSTS, nosniff, XFO, Referrer/Permissions-Policy) em todas as rotas. Como connect-src é 'self', o browser só fala com a própria origem: TeseClient.tsx (client) faz POST /api/teses e polling GET /api/teses/{id}; os route handlers em src/app/api/teses/* resolvem a URL do backend via lib/backend.ts (server-only, API_URL nunca vai ao bundle; produção sem env => 502 claro, nunca localhost), validam o ticker espelhando byte-a-byte o Pydantic do FastAPI (TICKER_RE de lib/tickers.ts = B3 ∪ Tesouro Direto, paridade verificada contra backend/app/schemas/tese.py e renda_fixa.py), repassam com timeout de 10s e devolvem o status verbatim. A tese chega como TeseOut (app/tese/types.ts, espelho do contrato-envelope-v3) e é renderizada por TeseView/Markdown.tsx: parser próprio sem dangerouslySetInnerHTML, links só http(s) e — no corpo da tese — só para hosts presentes no registro de fontes (anti-phishing); lacunas, citações, modelo e custo expostos (trilha de auditoria). Histórico é 100% localStorage (lib/historico.ts, sem endpoint). Footer/saude.ts faz health-check server-side em Suspense. GSAP entra só por import dinâmico pós-idle (lib/gsapSetup.ts, licença Webflow no-charge documentada e pinada).

### Testes + qualidade/cobertura

*Suíte grande (51 arquivos, ~16.5k linhas, ~857 funções de teste), 100% hermética (sem rede/DB real: MockTransport, SQLite in-memory, Anthropic fake, fakeredis) e excepcionalmente forte no gate anti-alucinação/anti-recomendação (3 arquivos, red-team de 67 casos + regressões verbatim de bugs de produção) e nos conectores de dados (fixtures reais congeladas). As lacunas se concentram em: zero teste comportamental de RLS/authz (só lint textual do SQL das migrações), redação de segredos em log sem nenhum teste, caminhos de erro/custo de gerar_tese e o fallback do disclaimer CVM não exercitados, e higiene de harness (sem conftest, estado global do limiter, sensibilidade ao .env local).*


Arquitetura da suíte: (1) Gate anti-alucinação — test_avaliacao.py (843 l.), test_avaliacao_gate_v3.py (841 l.) e test_avaliacao_redteam_v3.py (644 l., 67 casos: 22 furos fechados + 45 não-regressão + 14 anti-falso-positivo) cobrem recomendação multi-idioma, termos vetados-com-número por classe, geopolítica sem hedge, seções universais bloqueantes, cobertura/dedup de fontes, faithfulness numérica e dezenas de frases VERBATIM de bugs vivos (HGLG11/TAEE11). (2) Motor de tese — test_tese_engine/test_synthesize testam helpers puros e o mapeamento determinístico citação→Fonte; test_motor_multiativo (851 l.) e test_pipeline_tese_profunda (1055 l.) rodam gerar_tese fim-a-fim com SQLite+Anthropic fake, incluindo 3 testes com gate REAL reproduzindo bugs de produção; cache/reaper/warm_cache/scheduler têm testes de contrato próprios. (3) Segurança — test_seguranca (SSRF allowlist+DNS rebinding, ticker, teto de custo, slots, zip-bomb, headers, 413 chunked, XFF anti-spoof, 429 plugado, fail-closed do GET em status=error), test_http_client (UA/redirect-hook/retry), test_ratelimit_redis (bucket distribuído via fakeredis), test_guard_httpx_direto (lint anti-bypass do http_client). (4) Serviços de dados — cada conector (tesouro/cotahist/anbima/ifdata/aneel/proventos/sec/cvm/focus/fii_dados/consenso) tem arquivo próprio com fixtures reais em tests/fixtures/; tecnica.py validada contra KATs duplos (bukosabino/ta + Tulip); valuation com golden tests; metricas_setor com SQLite. (5) RLS — apenas asserts textuais sobre o SQL das migrações (test_models_schema*). Refactor SEGURO: avaliacao.py, tecnica.py, valuation.py, metricas_setor.py, conectores, http_client, ratelimit, scheduler, identidade/registro de classes. Refactor ARRISCADO: caminho de erro/custo de gerar_tese, escrita de ingest (_upsert_fundamento/_persistir_derivadas), demo_user.py, logging/redator, qualquer coisa que dependa de RLS/authz.


---

## 2. Achados CRÍTICO e ALTO (detalhados)

#### 🔴 CRÍTICO — Vazamento de vaga no semáforo de geração: flag _adquirido é compartilhada entre threads · ✅ **CORRIGIDO (Onda 1)**

- **Subsistema:** Core + Observability + App bootstrap · **Categoria:** bug · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `backend/app/core/limits.py:52`

- **Evidência:** GENERATION_SLOTS é UMA instância-módulo de _SlotGeracao usada como `with GENERATION_SLOTS:` por várias threads (tese.py:1526; BackgroundTasks de POSTs concorrentes + warm_cache do scheduler). O estado da aquisição é um atributo de instância compartilhado: `__enter__` faz `self._adquirido = True` (linha 48) e `__exit__` faz `if self._adquirido: self._sem.release(); self._adquirido = False` (linhas 52-54). Com 2 gerações sobrepostas (default tese_max_concorrencia=2): T1 adquire (True), T2 adquire (True de novo); a primeira a sair libera e zera a flag; a segunda vê False e NÃO libera — 1 permit do BoundedSemaphore vaza para sempre. O teste existente (tests/test_seguranca.py:128-136) só cobre vagas=1 com aquisição aninhada que FALHA, cenário que não exercita o vazamento.

- **Impacto:** Cada par de gerações sobrepostas vaza 1 vaga. Após 2 sobreposições (ex.: warm_cache diário rodando enquanto um usuário cria tese), o semáforo chega a 0 e TODA geração nova passa a falhar com ConcorrenciaExcedida ('sistema ocupado gerando outras teses') permanentemente, até restart do processo. O produto degrada em silêncio para abstenção total em produção.

- **Recomendação:** Eliminar a flag de instância: fazer o acquire/release no mesmo frame com try/finally, ex. transformar em @contextmanager (`if not self._sem.acquire(blocking=False): raise ConcorrenciaExcedida(...)` / `try: yield` / `finally: self._sem.release()`), ou guardar a flag em threading.local. Adicionar teste com vagas=2 e duas aquisições sobrepostas verificando que ambas liberam (semáforo volta a 2).

- **Verificação adversarial:** limits.py:41-54 confirma: _adquirido é atributo da instância-módulo GENERATION_SLOTS (linha 98) usada por threads concorrentes (tese.py:1526, BackgroundTasks + warm_cache). Com 2 aquisições sobrepostas, a primeira saída zera a flag e a segunda não libera — permit vaza para sempre. Pior que o descrito: __exit__ faz release() e só depois _adquirido=False sem atomicidade, então um __enter__ concorrente entre as duas operações tem sua flag clobberada — pode vazar até a ÚLTIMA vaga (lockout total de geração até restart), não apenas degradar 2→1. Teste existente (test_seguranca.py:128-136) não exercita o caminho. Crítico mantido.



#### 🟠 ALTO — Trivy e syft instalados no CI via curl|sh de branch 'main' mutável, sem pin nem checksum · ✅ **CORRIGIDO (Onda 1)**

- **Subsistema:** Infra + CI + Supply-chain · **Categoria:** seguranca · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `.github/workflows/ci.yml:84`

- **Evidência:** Linha 84: `curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b "$RUNNER_TEMP/trivy"` e linha 91: `curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh ...` — script baixado do branch main (mutável) e executado direto, instalando a 'latest' release sem versão nem verificação de checksum. Contradiz a política declarada no topo do próprio arquivo (linhas 3-5: 'actions fixadas por SHA de commit completo (imutável — mitiga supply-chain via reescrita de tag)').

- **Impacto:** Comprometimento do install.sh (ou da release 'latest') de aquasecurity/anchore executa código arbitrário no runner a cada push/PR — pode falsificar o gate de vulnerabilidade (trivy roda com --exit-code 1 como gate), envenenar o artefato SBOM e ler o código do repo. O GITHUB_TOKEN é contents:read e o deploy não sai do CI, o que contém o raio de dano, mas o job de SEGURANÇA vira o elo menos confiável do pipeline.

- **Recomendação:** Trocar por actions oficiais pinadas por SHA (aquasecurity/trivy-action e anchore/sbom-action — o wrapper atual já suporta setup próprio) OU baixar binário de versão fixa por URL de release + verificar sha256 antes de executar. Manter o Dependabot atualizando os SHAs.

- **Verificação adversarial:** ci.yml:84 e :91 conferem literalmente: install.sh baixado de raw.githubusercontent.com/{aquasecurity/trivy,anchore/syft}/main e pipeado para sh, instalando 'latest' sem versão nem checksum. Contradiz frontalmente a política declarada nas linhas 3-5 do próprio arquivo (pin por SHA imutável). Execução de código de fonte mutável dentro do job 'security' — mitigado apenas parcialmente por permissions: contents: read (linha 12-13), mas um script comprometido poderia neutralizar silenciosamente os gates de segurança. Alto mantido.



#### 🟠 ALTO — Tese com ZERO citações não é bloqueante — servida como 'ready' · ✅ **CORRIGIDO (Onda 1)**

- **Subsistema:** Motor de tese (avaliação/orquestração/valuation) · **Categoria:** logica · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `backend/app/services/avaliacao.py:1463`

- **Evidência:** O subconjunto bloqueante é `bloqueante = bool(violacoes) or bool(alertas_geo) or bool(fontes_sem_url) or bool(elos_sem_fonte) or bool(secoes_ausentes) or bool(termos_vetados) or ...` — `not citacoes` gera apenas o motivo "nenhuma citação ancorada à fonte" e derruba `aprovado`, nunca `bloqueante`. Em `tese.gerar_tese` (tese.py:1684) `tese.status = "error" if laudo["bloqueante"] else "ready"` — `aprovado` não é consultado para o status. O router (routers/teses.py:127) só oculta markdown quando status=error/envelope com 'erro'. `_faithfulness_numerica` baixa também é só nota (e para classe 'acao' nem nota é).

- **Impacto:** Uma síntese degenerada em que o Opus escreve números sem anexar nenhuma citação (falha do provedor, truncamento, regressão do modelo) é servida ao usuário como tese pronta — todos os fatos sem âncora verificável, enfraquecendo o invariante nº 1 (todo fato com fonte ou abstém) exatamente no cenário em que a defesa determinística mais importa.

- **Recomendação:** Incluir `len(citacoes) == 0` (quando há documentos-fonte) no subconjunto bloqueante; opcionalmente também um piso mínimo bloqueante de cobertura (ex.: > 0) distinto do piso de nota (0,5). Um teste de regressão: envelope com markdown numérico e `citacoes=[]` deve produzir `bloqueante=True`.

- **Verificação adversarial:** Verificado: avaliacao.py:1463-1473 — o subconjunto bloqueante não inclui `not citacoes` (que só vira motivo na linha 1495-1496 e derruba `aprovado` na 1510-1516). tese.py:1684 usa apenas laudo['bloqueante'] para o status; routers/teses.py:127-131 serve markdown quando status=ready e envelope sem 'erro'. Cobertura 0% < 0.5 também é só motivo (linha 1499). Fidelidade numérica é nota (e nem isso para classe 'acao', linhas 1456-1460). Tese sem nenhuma citação é servida integralmente como pronta.



#### 🟠 ALTO — Documento citável de métricas expõe 'pct' em fração crua; âncora do gate aceita a escala errada com símbolo %

- **Subsistema:** Motor de tese (avaliação/orquestração/valuation) · **Categoria:** bug · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `backend/app/services/tese.py:1083`

- **Evidência:** `_documentos_metricas` monta o texto que o LLM lê com o valor INTERNO: `f"- {m.nome}: {m.valor} {m.unidade} ({m.formula})..."` — para `unidade='pct'` isso vira ex. "Dividend yield 12m a mercado: 0.0823 pct", enquanto o envelope converte para pontos (8.23, `metricas_para_envelope`). O próprio hotfix 3 (avaliacao.py, item 15) documenta que o modelo já reescreveu ao vivo a escala fração ('0,0823') no markdown. E `_numeros_ancora_de_metricas` (avaliacao.py:781-783) gera âncoras nas DUAS escalas (v e v/100) sem verificar o contexto '%': a frase "DY a mercado de 0,0823%" — numericamente errada por 100× — tem o token 0,0823 casando a âncora v/100 e passa o gate isenta.

- **Impacto:** O insumo textual do LLM é ambíguo em escala (raiz da família de bugs TAEE11) e a mitigação do gate abre um buraco simétrico: uma afirmação percentual errada por fator 100 pode ser servida como validada. Número errado com verniz de fonte é o pior resultado possível (princípio do próprio repositório em derivadas.py).

- **Recomendação:** Formatar o documento citável com a MESMA convenção de exibição do envelope (pontos + '%', via helper compartilhado com `metricas_para_envelope`), eliminando a ambiguidade na origem; no gate, quando o token casar a âncora de escala fração mas for seguido de '%', não isentar (a fração com '%' é sempre errada).

- **Verificação adversarial:** Verificado: tese.py:1083 formata `{m.valor} {m.unidade}` com o valor INTERNO (fração para pct — convenção confirmada na docstring de metricas_para_envelope, metricas_setor.py:1140-1145, que converte ×100 só no envelope). avaliacao.py:781-783 gera âncoras nas duas escalas (v e v/100) sem olhar contexto; `_numeros_de_claim` (avaliacao.py:693-699) exclui o '%' do token, então '0,0823%' (errado 100×) casa a âncora v/100 com tolerância /100 e fica isento do gate de termos vetados. A própria docstring do hotfix 3 (avaliacao.py:1355-1360) admite que o modelo reescreveu a escala fração ao vivo.



#### 🟠 ALTO — Gate não bloqueia tese sem nenhuma citação — cobertura zero é servida como ready · ✅ **CORRIGIDO (Onda 1)**

- **Subsistema:** IA: Anthropic + Citations + anti-alucinação · **Categoria:** logica · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `backend/app/services/avaliacao.py:1463`

- **Evidência:** O subconjunto bloqueante é: `bloqueante = (bool(violacoes) or bool(alertas_geo) or bool(fontes_sem_url) or bool(elos_sem_fonte) or bool(secoes_ausentes) or bool(termos_vetados) or bool(violacoes_tecnica) or bool(violacoes_valuation) or bool(consenso_sem_atribuicao))`. `not citacoes` (linha 1495: só vira motivo) e `cobertura < _COBERTURA_MINIMA` (linha 1499) afetam apenas `aprovado` — e em tese.py:1684 `tese.status = "error" if laudo["bloqueante"] else "ready"`, ou seja `aprovado=False` não impede servir. O router (routers/teses.py:127) só nega markdown quando status=error.

- **Impacto:** Se o Opus devolver texto sem nenhuma citação (comportamento degradado, doc mal formado), a tese é servida como pronta com zero âncoras verificáveis — o invariante 'todo fato com fonte+data' fica garantido apenas pelo system prompt, sem enforcement determinístico. O laudo com aprovado=False fica persistido mas não é exposto na API (TeseOut não serve 'avaliacao'), então o leitor não vê o sinal.

- **Recomendação:** Incluir `len(citacoes) == 0` no subconjunto bloqueante (uma tese factual sem nenhuma citação nunca deveria ser servida — é o mesmo espírito de `fontes_sem_url`). Avaliar também promover `cobertura < mínima` a bloqueante quando `fontes` não está vazio, ou ao menos expor `avaliacao.aprovado`/`cobertura_fontes` no TeseOut para o frontend sinalizar.

- **Verificação adversarial:** Confirmado linha a linha: `bloqueante` (avaliacao.py:1463-1473) exclui `not citacoes` e cobertura — ambos só entram em `motivos` (1495, 1499) e em `aprovado` (1510-1516); tese.py:1684 marca ready sempre que não-bloqueante; routers/teses.py:127-145 serve markdown quando status != error e NÃO expõe `avaliacao`/`aprovado`/`cobertura_fontes` no TeseOut (grep sem matches). O design de dois níveis é documentado como deliberado (docstring do módulo, linhas 15-17), mas zero citação não é listado como bloqueante em lugar nenhum e nenhum sinal chega ao cliente — gap real na promessa central anti-alucinação. Severidade alta mantida.



#### 🟠 ALTO — Vazamento permanente de vagas no semáforo de geração (_SlotGeracao é singleton com estado compartilhado entre threads) · ✅ **CORRIGIDO (Onda 1)**

- **Subsistema:** Routers + Schemas + contrato de API + authz · **Categoria:** bug · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `backend/app/core/limits.py:51`

- **Evidência:** `GENERATION_SLOTS = _SlotGeracao(...)` (linha 98) é UMA instância-módulo usada como context manager por múltiplas threads concorrentes (`with GENERATION_SLOTS:` em services/tese.py:1526, chamado por BackgroundTasks do POST e pelo job warm_cache do scheduler, que gera 13 teses). O flag é de INSTÂNCIA: `__enter__` faz `self._adquirido = True`; `__exit__` faz `if self._adquirido: self._sem.release(); self._adquirido = False`. Interleaving T1.enter → T2.enter (flag continua True) → T1.exit (release, flag=False) → T2.exit (flag False → NÃO faz release). Resultado: 2 acquires, 1 release — uma vaga do BoundedSemaphore some para sempre.

- **Impacto:** Cada episódio de gerações sobrepostas (usuário + warm-cache, ou dois usuários) vaza 1 vaga. Com `tese_max_concorrencia=2`, após 2 sobreposições TODAS as gerações futuras levantam `ConcorrenciaExcedida` e cada tese nova é gravada como error ('sistema ocupado gerando outras teses') até o restart do processo — outage silencioso da funcionalidade central em produção, disparado justamente pelo cenário que o semáforo existe para proteger.

- **Recomendação:** Eliminar o flag de instância: fazer `GENERATION_SLOTS` ser o `threading.BoundedSemaphore` puro e adquirir/soltar por chamada (`if not sem.acquire(blocking=False): raise ...` + `try/finally: sem.release()` em gerar_tese), ou trocar `_SlotGeracao.__enter__` por um `@contextmanager` que retorna um token por aquisição — nunca estado mutável compartilhado no singleton. Adicionar teste de concorrência com 2 threads sobrepostas verificando que o número de releases == acquires.

- **Verificação adversarial:** Código confere exatamente (limits.py:39-54, 98; tese.py:1526). Pior que o interleaving citado: com tese_max_concorrencia=2 (default, config.py:83), QUALQUER par de gerações sobrepostas leaka 1 vaga — o primeiro __exit__ (em qualquer ordem) faz release e zera o flag; o segundo vê flag False e não faz release. Duas sobreposições esgotam o semáforo para sempre; toda geração passa a falhar com ConcorrenciaExcedida até restart. Concorrência real confirmada: BackgroundTasks (threadpool Starlette) + scheduler via asyncio.to_thread (scheduler.py:392). Severidade alto mantida.



#### 🟠 ALTO — RLS/authz sem nenhum teste comportamental — cobertura limita-se a lint textual do SQL das migrações

- **Subsistema:** Testes + qualidade/cobertura · **Categoria:** teste · **Verdito:** CONFIRMED · **Confiança:** alta

- **Local:** `backend/tests/test_models_schema.py:69`

- **Evidência:** A única cobertura de RLS na suíte é assert de presença de texto: `sql.count("enable row level security") == len(_TABELAS_NOVAS)` e `sql.count("create policy")` (repetido em test_models_schema_0005.py:138 e test_models_schema_0006.py:151). Grep por RLS/authz/Authorization em tests/ não encontra nenhum teste que exercite isolamento por usuário/role. A API não tem autenticação (main.py:141 "produto ainda sem login"; GET /teses/{id} serve qualquer UUID sem credencial) e o job grava como service_role que "ignora RLS" (tese.py:1499, docstring de gerar_tese).

- **Impacto:** Uma regressão de policy (ex.: migração futura que dropa/afrouxa uma policy existente, ou mudança de role da conexão) passa 100% verde na suíte. Quando login multiusuário chegar, não existe nenhum andaime de teste de isolamento para construir em cima — o invariante de segurança do produto (RLS owner-only provada manualmente em Supabase) não é regressível por CI.

- **Recomendação:** Adicionar testes comportamentais de RLS num Postgres efêmero (testcontainers ou o próprio branch de dev do Supabase): aplicar as migrações, conectar como `anon`/`authenticated` com JWT de dois usuários distintos e provar que SELECT/INSERT em teses/tese_versoes respeita owner-only e que service_role continua passando. No mínimo, estender o lint atual para afirmar que NENHUMA tabela do metadata fica sem policy (hoje cada teste só olha as tabelas da própria migração).

- **Verificação adversarial:** Verificado: test_models_schema.py:69-76 só faz assert de presença textual (sql.count('enable row level security')/'create policy'), padrão repetido em test_models_schema_0005.py:138-144 e 0006.py:151-159. Grep por rls/anon/authenticated/jwt em tests/ não encontra nenhum teste que exercite isolamento por usuário/role. main.py:141 confirma 'produto ainda sem login'; tese.py:1499 confirma 'Service_role ignora RLS para gravar'; GET /teses/{id} (routers/teses.py) serve qualquer UUID sem credencial. Cada teste de lint só olha as tabelas da própria migração.



## 3. Achados MÉDIO (resumo)

| # | Título | Local | Cat. | Dim | Status |
|---|---|---|---|---|---|

| 1 | Base image python:3.12-slim referenciada por tag mutável, sem digest | `Dockerfile:4` | seguranca | infra-ci-supply | → roadmap |

| 2 | Toolchain de build (uv) instalada sem versão e permanece na imagem final (sem multi-stage) | `Dockerfile:19` | divida | infra-ci-supply | → roadmap |

| 3 | Imagem de produção nunca é construída/escaneada no CI; SBOM é do repositório, não da imagem; sem proveniência | `ci.yml:92` | divida | infra-ci-supply | → roadmap |

| 4 | Dependabot ecosystem 'pip' provavelmente não atualiza o uv.lock (suporte a uv é ecossistema dedicado) | `dependabot.yml:10` | inconsistencia-parametro | infra-ci-supply | → roadmap |

| 5 | Elos derivados de tese (owner-only) são legíveis por qualquer authenticated — classificação de dado inconsistente entre elos e tese_versoes | `0002_refino_dimensoes.py:116` | seguranca | db-models-migrations | → roadmap |

| 6 | Isolamento multi-tenant nunca é exercido: backend conecta como owner (bypassa RLS), GET /teses/{id} não filtra dono e o cache é cross-user por design | `teses.py:95` | acoplamento | db-models-migrations | → roadmap |

| 7 | fonte_id NULLABLE nas tabelas de fatos legadas contradiz o invariante 'sem fonte não é fato' — banco não defende a rastreabilidade | `0001_initial_schema.py:59` | divida | db-models-migrations | → roadmap |

| 8 | Redação de segredos só cobre structlog — logging stdlib/uvicorn/tracebacks passam sem scrub | `logging.py:68` | seguranca | core-observ-app | → roadmap |

| 9 | Teto de custo diário fica silenciosamente inoperante se o modelo de síntese for trocado via env; extração Haiku e tokens do consenso não são contabilizados | `tese.py:286` | logica | core-observ-app | → roadmap |

| 10 | sec.ingest_pares não tem gate de staleness — re-baixa company_tickers.json + companyfacts (MBs) e faz delete+reinsert a cada reingest, contrariando o comentário 'cada um já auto-noop quando fresco' | `sec.py:168` | gargalo | services-dados-ingest | → roadmap |

| 11 | download_zip não tem retry — justamente os downloads maiores e mais propensos a falha transitória (DFP/FCA/COTAHIST/CSV STN) tentam 1 única vez | `http_client.py:205` | inconsistencia-parametro | services-dados-ingest | → roadmap |

| 12 | Paginação da ANEEL encerra silenciosamente com dados parciais quando `total` vem ausente/não-int ou uma página vem vazia — a soma parcial é persistida como 'a RAP' do grupo | `aneel.py:252` | logica | services-dados-ingest | → roadmap |

| 13 | Conectores macro rodam em TODA geração com ingest, sem gate de staleness — ~12 chamadas HTTP repetidas (BCB×6, FRED×2, World Bank×3, CDI×2+) por reingest | `orquestracao.py:148` | gargalo | services-dados-ingest | → roadmap |

| 14 | Teto de custo diário anulado silenciosamente se o modelo for trocado por env | `tese.py:74` | inconsistencia-parametro | services-tese-engine | → roadmap |

| 15 | Regexes de origem duplicadas entre tese.py e avaliacao.py sem teste de paridade | `tese.py:1026` | acoplamento | services-tese-engine | → roadmap |

| 16 | _coletar gera um documento por linha de Fundamento (multi-ano, sem dedup) + N+1 de Fonte | `tese.py:177` | gargalo | services-tese-engine | → roadmap |

| 17 | Metadados do Haiku sem validação de tipo podem derrubar uma geração Opus já paga | `tese.py:473` | bug | ia-anthropic-citations | → roadmap |

| 18 | Teto de custo diário fica silenciosamente inoperante se o modelo de síntese mudar via .env | `tese.py:74` | logica | ia-anthropic-citations | → roadmap |

| 19 | Metadados de base.py (lacunas_estruturais, pares_globais, fonte_primaria, obter_classe) não são consumidos pelo runtime — três fontes de verdade paralelas | `base.py:34` | divida | ativos-classes | → roadmap |

| 20 | ultimo_ponto_macro materializa a tabela macro_series inteira e roda 2x por geração de FII/renda fixa | `comum.py:48` | gargalo | ativos-classes | → roadmap |

| 21 | Fronteira da API sem autenticação/autorização — RLS anunciada nos modelos não é imposta na borda (BOLA/BFLA por desenho 'sem login') | `teses.py:94` | seguranca | routers-schemas-api | → roadmap |

| 22 | Idempotência do POST /teses é check-then-create sem atomicidade — corrida cria gerações LLM duplicadas do mesmo ticker | `teses.py:67` | logica | routers-schemas-api | → roadmap |

| 23 | Job COTAHIST diário pede o arquivo de dt.date.today() (UTC) — quase sempre inexistente na B3 no momento do tick | `scheduler.py:106` | logica | scripts-scheduler | → roadmap |

| 24 | Fork real entre CLI e scheduler no bootstrap de cadastro: _job_bootstrap_cadastro não roda bootstrap_fiis | `scheduler.py:77` | inconsistencia-parametro | scripts-scheduler | → roadmap |

| 25 | Teto de custo diário de LLM é memória por processo: scripts CLI e restarts zeram/duplicam o orçamento | `limits.py:99` | divida | scripts-scheduler | → roadmap |

| 26 | Rate-limit do backend compartilha um único bucket para todos os usuários do site (chave = IP de egress do proxy Vercel), e o proxy não impõe nenhuma contenção por cliente | `route.ts:65` | gargalo | frontend-sec | → roadmap |

| 27 | Redator de segredos do logging (core/logging.py) sem nenhum teste | `logging.py:57` | teste | tests-quality | → roadmap |

| 28 | Fallback do disclaimer CVM em gerar_tese nunca exercitado — todos os markdowns fake já contêm o disclaimer | `tese.py:1601` | teste | tests-quality | → roadmap |

| 29 | Caminhos de erro/custo de gerar_tese sub-testados: _mensagem_estavel, teto de custo e cap de concorrência nunca exercitados no fluxo real | `tese.py:1480` | teste | tests-quality | → roadmap |

| 30 | Suíte sensível ao ambiente da máquina: .env real do backend vaza para os testes (sem conftest de isolamento) | `config.py:18` | teste | tests-quality | → roadmap |

| 31 | Guard anti-bypass do http_client é contornável por `from httpx import ...` ou alias de import | `test_guard_httpx_direto.py:30` | teste | tests-quality | → roadmap |


## 4. Achados BAIXO (compacto)

| # | Título | Local | Cat. | Dim |
|---|---|---|---|---|

| 1 | Dependabot não cobre o ecossistema docker (base image sem atualização automática) | `dependabot.yml:5` | divida | infra-ci-supply |

| 2 | Compose dev expõe Postgres em todas as interfaces com credencial postgres/postgres | `docker-compose.yml:14` | seguranca | infra-ci-supply |

| 3 | semgrep-action deprecada/arquivada e rulesets p/* resolvidos em runtime | `ci.yml:71` | divida | infra-ci-supply |

| 4 | gsap sob licença proprietária (Standard 'no charge', não-OSI) sem gate/registro de compliance de licença | `package.json:12` | divida | infra-ci-supply |

| 5 | get_or_create_fonte é check-then-insert sem unique constraint em fontes — dedup quebra sob concorrência e o SELECT não tem índice de apoio | `fontes.py:43` | logica | db-models-migrations |

| 6 | Claims de zero-downtime imprecisos: 0003 'não bloqueia' usa CREATE INDEX sem CONCURRENTLY e 0005 muda teses.ticker para varchar(32) sob ACCESS EXCLUSIVE com scan de validação | `0003_indices_fk_e_cache.py:21` | divida | db-models-migrations |

| 7 | documentos/chunks (RAG multi-tenant com HNSW) são schema morto: nenhum serviço ou rota escreve/lê essas tabelas | `models.py:283` | estrutura | db-models-migrations |

| 8 | Engine sem orçamento explícito de pool: só pool_pre_ping, sem pool_size/max_overflow/pool_recycle/timeouts, com API + BackgroundTasks + scheduler no mesmo pool | `session.py:18` | divida | db-models-migrations |

| 9 | Drift modelo-ORM vs. banco: tipos divergentes e constraints do SQL ausentes dos modelos que dizem 'espelhar o schema' | `models.py:43` | inconsistencia-parametro | db-models-migrations |

| 10 | app_env é string livre com dois predicados diferentes: 'staging'/'prod' deixam /docs e /openapi.json públicos com logs de produção | `main.py:142` | inconsistencia-parametro | core-observ-app |

| 11 | Nenhuma correlação de request nos logs: merge_contextvars configurado mas request_id nunca é vinculado | `logging.py:71` | divida | core-observ-app |

| 12 | Langfuse nunca é flushado/encerrado no shutdown do lifespan | `main.py:133` | divida | core-observ-app |

| 13 | Task do scheduler morre sem observabilidade: create_task sem done-callback | `main.py:132` | estrutura | core-observ-app |

| 14 | Segredos tipados como str simples em vez de SecretStr | `config.py:37` | seguranca | core-observ-app |

| 15 | env_file='.env' relativo ao CWD: config muda conforme o diretório de onde o processo sobe | `config.py:18` | inconsistencia-parametro | core-observ-app |

| 16 | Cobertura de teste do cap de concorrência não exercita sobreposição real (vagas>=2) | `test_seguranca.py:128` | teste | core-observ-app |

| 17 | ingest_world_bank persiste o PRIMEIRO ponto da resposta, não o mais recente — comentário afirma garantia que o código não implementa | `macro_global.py:104` | logica | services-dados-ingest |

| 18 | Mesmo ZIP do informe mensal FII é baixado até 3× num único fluxo de ingest (ensure_fii + ingest_indicadores ano corrente e ano-1) — sem cache de bytes entre as funções | `fii_dados.py:466` | gargalo | services-dados-ingest |

| 19 | cotahist trata apenas ProgrammingError na degradação de tabela ausente, enquanto o próprio precos_frescos e os conectores irmãos (ifdata, proventos_b3) tratam também OperationalError | `cotahist.py:479` | inconsistencia-parametro | services-dados-ingest |

| 20 | Tabela fontes sem UNIQUE (url, descricao, dt_referencia): get_or_create_fonte em sessões concorrentes (scheduler × request) cria Fontes duplicadas | `fontes.py:39` | estrutura | services-dados-ingest |

| 21 | N+1 de queries nos upserts em lote: cotahist faz 1 SELECT por registro + COUNT por ticker a cada mês do backfill; fii_dados faz 2 SELECTs + SAVEPOINT por fundo do universo inteiro | `cotahist.py:183` | gargalo | services-dados-ingest |

| 22 | http_client abre um httpx.Client novo (TCP+TLS) por requisição e o subsistema não tem circuit breaker — fonte instável é re-martelada a cada passo | `http_client.py:134` | divida | services-dados-ingest |

| 23 | Limite por host do paralelo é de CONCORRÊNCIA (semáforo=5), não de taxa — o comentário promete 'respeitando 10 req/s da SEC' | `sec.py:216` | inconsistencia-parametro | services-dados-ingest |

| 24 | Resposta da B3 com zero proventos não persiste Fonte — o gate de staleness nunca arma e o endpoint é reconsultado em toda geração para tickers sem proventos | `proventos_b3.py:409` | gargalo | services-dados-ingest |

| 25 | TOCTOU de DNS no anti-SSRF: _resolve_publico resolve o host num momento e o httpx resolve de novo na conexão — sem pinning de IP | `http_client.py:83` | seguranca | services-dados-ingest |

| 26 | Acoplamento circular dados ↔ cvm_cadastro (import tardio) e helpers privados (_parse_data/_parse_valor/_normalizar_ds) importados entre módulos | `dados.py:177` | acoplamento | services-dados-ingest |

| 27 | Constante 'BOVA11' duplicada em dois módulos (ingest × cálculo do β) | `tese.py:535` | inconsistencia-parametro | services-tese-engine |

| 28 | _tem_dado_novo ignora FiiIndicador: FII sem preço nunca ganha blocos determinísticos | `tese.py:588` | logica | services-tese-engine |

| 29 | Modelos de valuation estruturalmente mortos em produção (BVPS/num_acoes/peers nunca preenchidos) | `tese.py:793` | divida | services-tese-engine |

| 30 | Cenário 'otimista' de g pode produzir valor abaixo do 'base' (IPCA Focus < meta; β negativo inverte ERP) | `valuation.py:302` | logica | services-tese-engine |

| 31 | persistir_elos/elos_para_llm não impõem `validada` apesar da docstring prometer | `correlacao.py:449` | estrutura | services-tese-engine |

| 32 | Rótulo 'fração decimal (0,15 = 15%)' viaja ao envelope junto de valores já convertidos a pontos | `metricas_setor.py:78` | inconsistencia-parametro | services-tese-engine |

| 33 | Split de frase da guarda geopolítica diverge das demais regras ([.;] vs [.;!?]) | `avaliacao.py:1321` | inconsistencia-parametro | services-tese-engine |

| 34 | Parâmetros do motor espalhados em constantes locais duplicadas (candidatos a config central versionada) | `tese.py:699` | divida | services-tese-engine |

| 35 | Custos Haiku (metadata + tokens do consenso) nunca entram no teto diário | `tese.py:1593` | divida | services-tese-engine |

| 36 | Resumo do Haiku recebe elegibilidade de carve-out de consenso como se fosse texto determinístico | `avaliacao.py:1263` | logica | services-tese-engine |

| 37 | Custo de tokens das chamadas Haiku (consenso e metadados) não entra no teto diário; helper morto | `consenso.py:550` | logica | ia-anthropic-citations |

| 38 | Fonte-âncora 'emprestada': citações de consenso/técnica/valuation resolvem para Fonte imprecisa | `tese.py:1095` | logica | ia-anthropic-citations |

| 39 | Moeda default 'BRL' no envelope de consenso fabrica um fato não verificado | `tese.py:1427` | inconsistencia-parametro | ia-anthropic-citations |

| 40 | Rastreabilidade parcial: prompts/modelos das etapas auxiliares (metadados, consenso) sem versão persistida | `tese.py:1671` | divida | ia-anthropic-citations |

| 41 | Resolução de classe do ativo duplicada no POST (router + criar_tese) | `teses.py:78` | divida | ia-anthropic-citations |

| 42 | Contrato PerfilClasse é apenas documental — nunca verificado estática nem em runtime | `registro.py:19` | estrutura | ativos-classes |

| 43 | Filtro final de elos validados é inconsistente entre construtores, e persistir_elos não filtra apesar do docstring | `acao.py:350` | inconsistencia-parametro | ativos-classes |

| 44 | Idioma de abstenção divergente no contrato coletar: renda_fixa levanta exceção, ação/FII devolvem lista vazia | `renda_fixa.py:346` | inconsistencia-parametro | ativos-classes |

| 45 | Perfis e comum.py dependem de símbolos privados de tese.py (_fmt_fundamento, _coletar, _SYSTEM) com ciclo administrado por imports tardios | `comum.py:34` | acoplamento | ativos-classes |

| 46 | Resolução de identidade duplicada no POST /teses: router resolve e grava a classe, e criar_tese resolve e grava de novo | `teses.py:78` | divida | ativos-classes |

| 47 | montar_elos_rf: primeira série FOCUS_SELIC* sem fonte_id aborta o elo Focus→prefixado mesmo havendo outra série Focus com fonte | `renda_fixa.py:458` | logica | ativos-classes |

| 48 | Inclusão de macro por prefixo FOCUS_ é frágil à adição de novas séries Focus não relacionadas a juros/inflação | `comum.py:38` | divida | ativos-classes |

| 49 | Reaper por criado_em pode marcar 'error' uma geração ainda viva, que depois sobrescreve para 'ready' (transição error→ready) e gasta LLM já 'expirada' | `tese.py:1748` | logica | routers-schemas-api |

| 50 | Teto de custo diário sem reserva: verificação antes da geração e registro só depois permitem exceder o teto com gerações em voo | `limits.py:68` | logica | routers-schemas-api |

| 51 | Resolução de classe duplicada no POST: router e criar_tese resolvem e gravam classe_ativo duas vezes | `teses.py:78` | divida | routers-schemas-api |

| 52 | Cache hit devolve HTTP 202 com status='ready' — semântica de 'Accepted' sem nada aceito para processamento | `teses.py:53` | inconsistencia-parametro | routers-schemas-api |

| 53 | Uniões fechadas do contrato tipadas como str livre nos schemas de saída — sem Literal/Enum, valor inválido do envelope passa ao cliente | `tese.py:120` | estrutura | routers-schemas-api |

| 54 | Tick sequencial: warm_cache (até 3900s) atrasa o reaper e o timeout do wait_for não interrompe o gasto | `scheduler.py:391` | gargalo | scripts-scheduler |

| 55 | Reaper sem heartbeat: geração legítima > 15 min é marcada error em voo e depois regravada ready, com versão de erro espúria na trilha | `tese.py:1748` | logica | scripts-scheduler |

| 56 | Conexão do advisory lock fica 'idle in transaction' durante toda a execução do job (até ~65 min no warm_cache) | `scheduler.py:349` | gargalo | scripts-scheduler |

| 57 | Warm cache via CLI não passa pelo advisory lock: corrida check-then-act pode gerar a mesma tese em dobro | `warm_cache.py:155` | acoplamento | scripts-scheduler |

| 58 | Sinalização de falha divergente entre caminhos: ledger 'ok' com todos os passos falhos, exit 0 com 12/13 falhas | `warm_cache.py:205` | inconsistencia-parametro | scripts-scheduler |

| 59 | Falha transitória em job de intervalo longo espera o intervalo inteiro: cadastro semanal pode ficar ~2 semanas sem rodar | `scheduler.py:323` | divida | scripts-scheduler |

| 60 | GET /api/teses/[id] repassa id sem validação de formato — assimetria com o POST, que espelha a validação do backend | `route.ts:26` | inconsistencia-parametro | frontend-sec |

| 61 | Proxy devolve o corpo bruto do upstream como `detail` quando a resposta não é JSON — vazamento de página de erro da infraestrutura para o cliente | `route.ts:86` | seguranca | frontend-sec |

| 62 | Polling trata qualquer erro não-404 (400/401/403/429/5xx persistentes) como transitório e insiste por até 240s | `TeseClient.tsx:79` | logica | frontend-sec |

| 63 | x-forwarded-for do cliente repassado verbatim ao backend para auditoria — spoofável fora da Vercel | `route.ts:68` | seguranca | frontend-sec |

| 64 | Inversão de camada: src/lib importa tipos do contrato que vivem dentro da pasta de rota src/app/tese | `historico.ts:5` | estrutura | frontend-sec |

| 65 | tsconfig sem noUncheckedIndexedAccess (e allowJs ligado sem nenhum .js no projeto) | `tsconfig.json:7` | divida | frontend-sec |

| 66 | .env.local.example documenta Supabase (URL + publishable key) que o frontend não usa em lugar nenhum | `.env.local.example:5` | divida | frontend-sec |

| 67 | Neutralização de esquema perigoso em _fonte_dict (href da UI) sem teste | `tese.py:520` | teste | tests-quality |

| 68 | Harness duplicado em 3+ arquivos sem conftest: _completar_secoes, fakes do Anthropic e sessões fake copiados | `test_avaliacao_gate_v3.py:59` | divida | tests-quality |

| 69 | Docstring de test_pipeline_tese_profunda afirma 'gate real — não stub', mas o harness stubba avaliar_tese na maioria dos testes | `test_pipeline_tese_profunda.py:262` | teste | tests-quality |

| 70 | Testes por inspeção de código-fonte (inspect.getsource) em test_macro_expandido | `test_macro_expandido.py:18` | teste | tests-quality |

| 71 | Estado global compartilhado entre testes: TestClient/limiter em nível de módulo com resets manuais espalhados | `test_seguranca.py:20` | teste | tests-quality |

| 72 | CI roda pytest sem medição de cobertura — pontos cegos da suíte são invisíveis | `ci.yml:44` | divida | tests-quality |

| 73 | Carve-out de consenso exige H2 'consenso' que nenhum template de classe permite existir | `avaliacao.py:1260` | inconsistencia-parametro | services-tese-engine |

| 74 | Escrita do ingest de fundamentos (upsert/derivadas) sem teste direto — só stubs na orquestração | `dados.py:740` | teste | tests-quality |


---

## 5. O que a Onda 1 (esta entrega) já fechou

- **[CRITICO]** Vazamento de vaga no semáforo de geração: flag _adquirido é compartilhada entre threads (`limits.py:52`)

- **[ALTO]** Trivy e syft instalados no CI via curl|sh de branch 'main' mutável, sem pin nem checksum (`ci.yml:84`)

- **[ALTO]** Tese com ZERO citações não é bloqueante — servida como 'ready' (`avaliacao.py:1463`)

- **[ALTO]** Gate não bloqueia tese sem nenhuma citação — cobertura zero é servida como ready (`avaliacao.py:1463`)

- **[ALTO]** Vazamento permanente de vagas no semáforo de geração (_SlotGeracao é singleton com estado compartilhado entre threads) (`limits.py:51`)

- **[ALTO/prod-probe]** COOP/CORP ausentes em `next.config.ts` → adicionados (build verde).

- **[Governança]** Suíte `docs/security/*` + `SECURITY.md` + `security-scheduled.yml` recuperada do PR#30 órfão e re-hardened.
