# Fortaleza — ADRs (decisões de arquitetura desta entrega)

> Formato curto: Contexto · Decisão · Alternativas · Consequências. Cada uma com trade-off honesto.

## ADR-001 — Semáforo de geração: remover o flag de instância (não reescrever para `@contextmanager`)

**Contexto.** `_SlotGeracao` (singleton-módulo `GENERATION_SLOTS`) guardava `_adquirido` na instância
compartilhada entre threads. Duas gerações sobrepostas (ex.: warm-cache + usuário) vazavam 1 vaga: a 2ª
saída via o flag já zerado pela 1ª e não liberava. Com `tese_max_concorrencia=2`, após 2 sobreposições o
semáforo caía a 0 e **toda** geração passava a falhar (`ConcorrenciaExcedida`) até o restart. **CRÍTICO.**

**Decisão.** Remover `_adquirido`; `__enter__` adquire (levanta se cheio), `__exit__` **sempre libera**. O
contrato do `with` garante que `__exit__` só roda após um `__enter__` bem-sucedido — logo a liberação é
balanceada e o `BoundedSemaphore` é a única fonte de verdade.

**Alternativas.** (a) `@contextmanager` dedicado (mudaria os call-sites `with GENERATION_SLOTS:`); (b)
`threading.local` (desajeitado com `with` em objeto compartilhado). Rejeitadas: mais churn, mesmo resultado.

**Consequências.** Fix mínimo (+13 −7), interface preservada. Teste determinístico que reproduz o vazamento
por sobreposição (`test_slot_geracao_nao_vaza_vaga_em_sobreposicao`). Um `__exit__` chamado sem `__enter__`
(uso indevido fora de `with`) levantaria `ValueError` do BoundedSemaphore — falha **alta e ruidosa**, não
vazamento silencioso; aceitável (nenhum call-site faz isso).

## ADR-002 — Grounding duro: tese com fontes e ZERO citações vira BLOQUEANTE (escopo mínimo)

**Contexto.** O gate marcava `aprovado=False` para 0 citações, mas **não** `bloqueante`; o status
`ready`/`error` só olha `bloqueante` (`tese.py:1684`). Uma síntese degenerada (0 citações) era servida como
pronta — enfraquece o invariante nº1 exatamente no pior cenário.

**Decisão.** Adicionar `(bool(fontes) and not citacoes)` ao subconjunto bloqueante — o caso claro de
"fato com fonte disponível mas nenhuma âncora". **Não** promovi `cobertura < mínima` a bloqueante (é decisão
de produto que pode reprovar teses legítimas de cobertura moderada — fica no roadmap).

**Consequências.** +2 testes (vermelho/verde). Tese totalmente **abstida** (sem fontes) não cai na regra —
não é "fato sem fonte", é abstenção legítima. Zero regressão (o único teste pré-existente de 0-citações só
checava `aprovado`, que continua False).

## ADR-003 — Recuperar os artefatos de segurança do PR#30 órfão, NUNCA mergear o branch

**Contexto.** `AGENTS.md` referencia `docs/security/*`, `SECURITY.md`, `security-scheduled.yml` como
existentes; **não estão em master**. Vivem em `feat/seguranca-nivel-bancario` (`095ceba`, 11/07), que está
**stale**: mergear apagaria **18.750 linhas** do sistema visual das 7 missões (viola invariante nº4).

**Decisão.** `git checkout <branch> -- <path>` apenas dos artefatos **duráveis e code-independentes** (docs +
workflow), **re-validando cada alegação** contra o master atual (ver scorecard §7). **Não** recuperar arquivos
de frontend (stale) nem o teste `test_ratelimit_trusted_hops.py` (escrito contra `ratelimit.py` divergente).
As modificações `.py` do branch = diff individual no roadmap, nunca cherry-pick cego.

**Consequências.** Fecha o gap de governança sem tocar o visual. O doc de compliance foi **re-baselinado**
(banner + §7 do scorecard) para não herdar as alegações "fix nesta entrega" do PR#30 que nunca mergeou.

## ADR-004 — CI: pinar `trivy`/`syft` por SHA de commit + versão (não migrar já para action oficial)

**Contexto.** O job de **segurança** instalava trivy/syft via `curl … /main/… | sh` (branch mutável) +
`latest` — RCE latente no próprio gate de segurança, contradizendo a política de SHA-pin do repo. **ALTO.**

**Decisão.** Baixar o `install.sh` de um **SHA de commit imutável** e instalar uma **versão fixa** (trivy
`v0.72.0` @ `75c4dc0f…`, syft `v1.49.0` @ `e854078f…`, SHAs resolvidos via `gh api`). Mesma invocação de scan.

**Alternativas.** Migrar para `aquasecurity/trivy-action`/`anchore/sbom-action` pinadas por SHA
(Dependabot-tracked). Rejeitada **por ora**: (1) o wrapper trivy-action já quebrou o repo antes (setup-trivy
removido); (2) **não consigo validar o CI localmente** (sem `act`/Docker) — a mudança de menor blast-radius é
pinar o script atual. Migração para action oficial = **roadmap #8**.

**Consequências.** Elimina o vetor mutável-`main` e mutável-`latest`. Trade-off honesto: curl-pin **não** é
coberto pelo Dependabot → bump manual. **Validação:** YAML parseia; o gate real é o **CI do próprio PR**.

## ADR-005 — Adiar o fix de ambiguidade de escala `pct` (não mexer no gate battle-tested sem red-team ao vivo)

**Contexto.** Achado ALTO (invariante nº1): doc citável emite fração crua; a âncora do gate aceita duas
escalas **de propósito** ("hotfix 3", porque o doc mostra fração). O conserto é interligado (doc ↔ âncora ↔
testes red-team) num gate provado **ao vivo** (família TAEE11).

**Decisão.** **Não** consertar nesta sessão. Um meio-conserto pode **enfraquecer** o gate; a cultura do repo
exige validação ao vivo para mudança de gate — que precisa da `ANTHROPIC_API_KEY` (pendência humana).

**Consequências.** Fica como **roadmap P0 #1** com o plano completo (formatar doc em pontos+% via helper único
→ estreitar a âncora-fração → re-rodar red-team ao vivo em ticker pct-pesado). Honesto: preferir invariante
preservado a fix apressado que regride.

## ADR-006 — Autonomia até PR, NÃO até merge/deploy (ratificação humana dos gates de deploy seguro)

**Contexto.** O prompt autoriza merge+deploy. Mas: (1) não consigo rodar DAST/tri-engine visual/cross-tenant
RLS aqui; (2) o inegociável de "deploy seguro" exige `revisao-seguranca` + pentest **registrados antes do
merge** e smoke pós-deploy; (3) merge para o master de produção e deploy são ações **externas e difíceis de
reverter**.

**Decisão.** Trabalho isolado no worktree `feat/fortaleza`, commit + push do branch + **PR (draft)** com todos
os relatórios anexados. **Parar antes do merge/deploy**, entregando para ratificação humana + o **CI do PR**
como gate objetivo. Não desmonto o WIP alheio no checkout compartilhado (raias paralelas).

**Consequências.** Handoff honesto e reversível. O que exige conta/serviço/chave (deploy Vercel/Railway,
`ANTHROPIC_API_KEY`, Supabase branch) fica declarado como pendência, não simulado.
