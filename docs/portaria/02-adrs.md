# ADRs — A Portaria (contas · sessão · 2FA · RLS enforçada)

> Data: 2026-07-27 · Base: `master 627b3c2` (Fortaleza já mergeada) · Worktree: `C:\Users\conta\wt-portaria` (`feat/portaria`).
> Método: conselho de 6 decisões × propostas independentes → síntese → **red-team adversarial antes de codar**
> (22 agentes, 0 erros; bruto em `evidencias/conselho-arquitetura-raw.json`). Veredito do red-team:
> **Aprovado-com-correções** — o núcleo é sólido, mas o plano só vira código depois de **fundir os schemas
> conflitantes numa ADR-mestra única** (este documento), **eleger um único PEP de auth**, e trocar toda leitura
> de `auth.mfa_factors` por `SECURITY DEFINER` + injetar claims completas. Este doc já aplica as 3 correções.

## Fatos verificados AO VIVO (não suposições) — a base de tudo

| Fato | Valor | Como |
|---|---|---|
| JWT do projeto | **já assina ES256 assimétrico** (JWKS `kid 2220fdf2-…`, EC P-256) | JWKS público do projeto |
| `has_table_privilege('authenticated','auth.mfa_factors','SELECT')` | **false** | consulta ao vivo |
| `postgres` tem ADMIN OPTION sobre anon/authenticated/service_role + CREATEROLE | **sim** (PG17) | `pg_roles` |
| Roles: `authenticator`(NOINHERIT, no-bypassrls, pode SET ROLE), `authenticated`/`anon`(no-bypassrls), `service_role`/`postgres`(**bypassrls**) | — | `pg_roles` |
| CSP real (`proxy.ts:18`) | tem `img-src 'self' blob: data:` → `<img src={qr})>` **funciona** | leitura do arquivo |
| GoTrue: **códigos de recuperação nativos** | **NÃO existem** (recomendam 2º TOTP) | doc Supabase |
| GoTrue: rotação + reuse-detection de refresh | **nativas** (reuso → sessão revogada) | doc GoTrue |
| Dados | 1 `auth.users` (demo), **314 teses** todas do demo, 467 elos | consulta ao vivo |

---

## ADR-01 — Modelo de sessão e topologia de auth (`session-model`)

**Decisão:** BFF-cookie puro. **O Next.js é o ÚNICO que fala com o GoTrue** (via `@supabase/ssr`, server-side em
route handlers `/api/auth/*`); a sessão nativa do GoTrue vive em **cookies httpOnly** forçados pelo nosso adapter;
a identidade viaja ao FastAPI como o **access token REAL** (`Authorization: Bearer`), validado localmente por
**JWKS ES256**; rotação/reuse 100% delegadas ao GoTrue. `proxy.ts` **intocado** (o matcher já exclui `/api`).

**Por quê:** a CSP `connect-src 'self'` proíbe o navegador de falar com `*.supabase.co` → auth server-side é a
única via diff-zero, e a topologia já é BFF (`lib/backend.ts` server-only). Pass-through do JWT real (não
re-cunhar) é o que faz `request.jwt.claims` no Postgres refletir a fonte de verdade para a RLS.

**Implementação:** `PyJWT` + `PyJWKClient({SUPABASE_URL}/auth/v1/.well-known/jwks.json)`; decode com
`algorithms=["ES256"]` EXPLÍCITO (rejeita HS256/`none` — alg-confusion), `audience="authenticated"`, `issuer`
pinado, `require:["exp","sub","session_id"]`, `leeway`. Header de perímetro **`X-Portaria`** (segredo
compartilhado Vercel↔Railway, `hmac.compare_digest`) porque o Railway é público e um JWT roubado poderia ser
reproduzido direto no FastAPI. Operações sensíveis exigem `getUser()` (server-confirmed, ciente de revogação) +
aal2. `signOut` sempre com **escopo explícito** (default é global).

**Correção do red-team aplicada:** a rota `confirmar` NUNCA consome token em GET (ver ADR-04/06). E o baseline do
diff-zero é o **`proxy.ts` em disco** (com `img-src`/`font-src`/`base-uri`/`isDev`), nunca a lista resumida do
enunciado.

## ADR-02 — Mecanismo de RLS enforçada (`rls-mechanism`) — camada de MECANISMO sobre o schema da ADR-03

**Decisão:** Opção **C — defesa em profundidade** com enforcement primário no BANCO. Um **segundo engine**
(`engine_rls`) conecta com o role de login **`app_backend`** (LOGIN, NOINHERIT, **NOBYPASSRLS**); cada transação
do caminho do usuário recebe, num listener `after_begin` do SQLAlchemy, `SET LOCAL ROLE authenticated` +
`SELECT set_config('request.jwt.claims', :claims, true)` **sempre parametrizado**; **camada B** = todo query do
caminho do usuário mantém filtro explícito `user_id == principal.user_id`. O engine `postgres` atual vira
**`engine_sistema`** (só migrações via `postgres`; ingest de referência, reaper, scheduler, warm-cache via a lane
**`app_worker`**, NOLOGIN), com allowlist provada por teste arquitetural. **Fail-closed:** sessão RLS sem escopo →
`RuntimeError`.

**Por quê:** os roles ao vivo permitem `SET ROLE authenticated`; NOINHERIT + sem grants = nega barulhento; sem
claims → `auth.uid()` NULL → nega. Provado ao vivo que `auth.uid()` resolve e 0/314 teses ficam visíveis para
outro `sub`.

**Claims completas (correção do red-team, confirmada ao vivo):** o `set_config` injeta
**`{sub, role, aal, session_id, amr}`** copiado do JWT validado na ADMISSÃO — **nunca só `{sub, role}`**, senão
qualquer função/policy que leia `aal`/`amr` (ex.: geração de códigos 2FA) falha.

**Pitfalls decisivos:** `SET LOCAL` morre no COMMIT e `gerar_tese` comita várias vezes → o carimbo TEM de ser no
`after_begin` (re-dispara a cada autobegin); `SET` sem `LOCAL` vaza identidade pelo pool (confused deputy);
`AUTOCOMMIT` no `engine_rls` torna `SET LOCAL` no-op → proibir com assert + teste. **Pooler:** session mode 5432
(transaction mode 6543 não suporta prepared statements do SQLAlchemy). **Preflight `psql` obrigatório** do login
de `app_backend.<project-ref>` contra o pooler antes do cutover (relatos reais de "Tenant or user not found" com
roles customizados no Supavisor) — se falhar, contingência: `engine_rls` sobre a URL `postgres` com o **mesmo
mecanismo** + guard fail-closed, até resolver.

**Jobs longos:** o `BackgroundTask` recebe `(tese_id, user_id)` capturado do JWT verificado na request e cunha as
claims server-side — independe da vida do token (TTL 600s < geração profunda). service_role **nunca** responde ao
navegador.

**Teste comportamental (fecha a P0 nº 2 da Fortaleza):** job CI `rls-isolation` com **Postgres real** (service
container `pgvector/pgvector:pg17` — `postgres:17` puro quebra no `vector(1536)` do 0001), shim de `auth.uid()`
**verbatim** via `pg_get_functiondef` (a definição real faz `coalesce` lendo o GUC legado
`request.jwt.claim.sub` PRIMEIRO — redigitar aprova policy que reprova em prod), bootstrap de roles/`auth.users`,
`alembic upgrade head`, `pytest -m rls`. Casos: A cria tese → sessão-de-B `session.get` sem filtro = None (prova
o banco, não o filtro); GET como B = 404; B forja `user_id=A` no INSERT → `WITH CHECK` nega; sessão sem escopo →
erro; tenta `SET ROLE service_role`/`postgres` → erro; elos de A invisíveis a B, elos públicos visíveis a anon;
geração fim-a-fim (LLM mockado) nas duas lanes sem escrita negada; arquitetural: routers só importam
`get_session_usuario`/`get_session_anon`, allowlist do `engine_sistema` fechada. **Aditivo aos 1015 (SQLite,
intocados) — marker `rls` + skip se `TEST_PG_URL` ausente.**

## ADR-03 — Acervo do sistema, fronteira público/privado e cache (`demo-user-cache`) — a ADR-MESTRA de dados

> **Esta é a reconciliação exigida pelo red-team.** Ela DESCARTA: `is_publica` (da rls-mechanism), `tese_app`
> (nome do role — vira `app_backend`+`app_worker`), o `clone-on-hit` copiando elos, a policy de elos por join, e
> as **três migrações chamadas "0006"**. Série única: **`0007_portaria_expand` + `0008_portaria_backfill`**
> (0006 já é `0006_tese_profunda`).

**Decisão:** Aposentar o `demo_user` convertendo as 314 teses em **acervo do sistema**: `teses.user_id` vira
**NULLABLE** (NULL = sistema) + coluna **`visibilidade IN ('publica','privada')`** amarrada por
**`CHECK ((user_id IS NULL) = (visibilidade='publica'))`** em `teses`, `tese_versoes` e `elos` (denormalizado —
`elos` ganha `user_id`+`visibilidade` e perde o `using(true)` que vazava fragmentos). Sem usuário-sentinela (a
identidade GoTrue é deletável por um clique e a FK `ON DELETE CASCADE` apagaria as 314 teses; NULL declara "do
sistema" no tipo e blinda a exclusão LGPD). Curadoria da vitrine continua em `tickers.ts` (não é fronteira de
segurança). **Tudo que o usuário gera é SEMPRE privado** (policy `restrictive` garante).

**Histórico/favoritos:** tabela `historico_itens` owner-only, FK para `teses` (tese pública entra como LINK; os
UUIDs das 314 são preservados porque o `/historico` do visitante é `localStorage` com esses ids).

**Cache em 3 degraus no POST autenticado:** (1) hit no acervo público (ticker, ready, TTL) devolve o id público +
upsert do vínculo; (2) hit na tese privada do próprio usuário; (3) miss → `pg_advisory_xact_lock` por ticker →
`tese_cache_conteudo` (chave `ticker+prompt_hash`, **worker-only**, nunca semeia erro) → hit copia o envelope para
tese **privada** do usuário a **custo LLM zero** → miss gera e semeia. Isso preserva "o que é do usuário é só
dele" sem pagar LLM em dobro.

**IDOR morre em duas camadas:** `WHERE` explícito (braço do dono só quando autenticado — ⚠ `Tese.user_id == None`
compila `IS NULL` e casaria o acervo público) **+** RLS real. **404 uniforme** (mesmo status+shape+mensagem de
inexistente — sem oráculo de UUID).

**Migração `0007_portaria_expand` (roda como `postgres`):** colunas + CHECKs `NOT VALID` (só validam linhas
novas; código atual `privada`+dono segue válido); índices parciais (`… where visibilidade='publica' and
status='ready'`); `historico_itens` + policy owner + índice; role `app_worker NOLOGIN` + grants + default
privileges; `tese_cache_conteudo` worker-only (RLS ON, policy só p/ `app_worker`); `codigos_recuperacao`
worker-only (ver ADR-04); policies de leitura pública `to anon, authenticated using (visibilidade='publica')`;
`drop policy "ref_read_elos"` + `elos_publica`/`elos_owner`; policies `restrictive for insert … with check
(visibilidade='privada')`; policies `worker_all_*`; **grants explícitos** (RLS ≠ grant; Supabase migrando default
para revogar); **um `ALTER TABLE … FORCE ROW LEVEL SECURITY` por tabela** (multi-tabela é sintaxe inválida).
`downgrade()` reverso completo (recria `ref_read_elos`).

**Migração `0008_portaria_backfill`:** `_portaria_backup_demo` (deny-all) → `UPDATE elos/tese_versoes/teses SET
user_id=NULL, visibilidade='publica' WHERE user_id=<demo_uid>` (ordem: filhos antes; auditar `elos` órfãos com
`tese_versao_id IS NULL` antes) → `VALIDATE CONSTRAINT`. **Ordem fatal:** deploy do código SEM `demo_user`
PRIMEIRO (o `lru_cache` de um processo velho recriaria o demo depois do backfill), depois 0008.

**Contract (operacional, pós-soak + ratificação):** `aposentar_demo_user.py` verifica count=0 do demo nas 4
tabelas com FK CASCADE (teses, tese_versoes, **documentos, chunks** — cascateiam igual) → `admin.deleteUser` via
service_role → apaga `demo_user.py` + `demo_user_email` do config + teste que falha se voltar → drop backup +30d.

## ADR-04 — 2FA TOTP + códigos de recuperação (`twofa-recovery`)

**Decisão:** **MFA TOTP nativo do GoTrue**, todo server-side no BFF; **códigos de recuperação implementados por
nós** (gap real confirmado); perda do 2º fator = **break-glass honesto** (código válido → FastAPI chama
`admin.mfa.delete_factor` → volta a aal1, avisa e força re-enroll — um código **nunca** minta sessão aal2);
`aal2` imposto em 3 camadas (BFF, FastAPI, RLS restrictive opt-in) **por último**, depois do fluxo MFA no ar e da
virada de role.

**Correções do red-team aplicadas (críticas):**
- **`auth.mfa_factors` é ilegível por `authenticated` (confirmado ao vivo)** → criar
  **`public.tem_fator_totp_verified(uid) RETURNS boolean SECURITY DEFINER`** (owner `postgres`, `search_path=''`,
  `revoke from public, anon`) e usá-la **tanto na policy restrictive quanto no `exigir_aal2` do FastAPI**. Ler
  `auth.mfa_factors` direto = policy restrictive que ERRA = **nega TODA query de teses de TODO usuário**.
- **UM cofre de códigos** (não dois): tabela **`codigos_recuperacao`** deny-all/**worker-only** (RLS ON, acesso só
  pela lane de serviço — sem `grant execute … to authenticated`, que seria chamável via PostgREST por fora do
  rate-limit), **um** gerador (FastAPI), **SHA-256 de 80 bits CSPRNG calculado NA APLICAÇÃO** (o plaintext nunca
  entra em SQL/`pg_stat_statements`/logs), single-use via `UPDATE … WHERE usado_em IS NULL RETURNING`.
- **QR = `<img src={data.totp.qr_code}>`** direto (`img-src data:` confirmado no `proxy.ts:18`) + secret em
  `<code>`. **A fase inteira de sanitização de SVG inline foi DESCARTADA** (construída sobre leitura errada).
- **Rate-limit próprio por usuário** (o do GoTrue em challenge/verify é por IP e o egress da Vercel compartilha
  bucket); `Sb-Forwarded-For` só com ratificação (exige `sb_secret` no BFF — tangencia o invariante).

**Enforcement por último:** ordem obrigatória = fluxo MFA no ar → virada `SET ROLE` → policies `restrictive`
(template oficial `as restrictive`, senão vira `OR` e o gate é decorativo). Perda total (sem fator e sem códigos)
= runbook manual em `docs/security/` (mesma postura do próprio Supabase).

## ADR-05 — Rate-limit por usuário+IP, lockout e senha vazada (`ratelimit-hibp`)

**Decisão (com o PEP unificado do red-team):** **o Next é o único chamador do GoTrue**; a contenção vive **no
fluxo**: o handler Next chama um endpoint interno do FastAPI de **pré-cobrança** (`contencao_tentar`) ANTES do
GoTrue e **zera no sucesso** — o FastAPI mantém as funções SQL de lockout, o **HIBP** e o break-glass. **Deletar**
qualquer endpoint FastAPI de password-grant (`/auth/login|signup`) — os dois PEPs não coexistem.

- **Chave por conta E por IP**, backoff, lockout temporário. Estado no Redis (`slowapi` já tem storage
  behind-config; `fakeredis` na venv para testes). Cumpre o TODO do próprio `ratelimit.py` ("com login, a chave
  passa a ser o usuário").
- **HIBP k-anonimato** (envia só o prefixo SHA-1, nunca a senha) **SÓ em cadastro/troca/reset — NUNCA no login**
  (mandar o prefixo da senha correta a um terceiro a cada login não protege nada e abre canal de timing). Política
  de força honesta (comprimento acima de tudo). **Falha de rede do HIBP = fail-open com telemetria** (não travar
  cadastro por indisponibilidade de terceiro) — *ratificar*.
- **Enumeração impossível:** mensagens **E tempos** uniformes entre "existe" e "não existe" no cadastro, login e
  reset (piso de tempo). `/criar-conta` e `/recuperar` respondem a mesma tela exista ou não a conta.

## ADR-06 — Forma da UI (`ui-form-factor`)

**Decisão:** **Páginas dedicadas server-rendered** para 100% das superfícies de conta — **zero modal de auth**.
Grupo de rotas `(portaria)` na medida-padrão da Bancada, forms nativos **POST→303→GET (PRG)**, `proxy.ts`
diff-zero, `service_role` só no FastAPI.

**Por quê:** três fluxos entram por URL externa (confirmação, recuperação, callback OAuth) → modal não é
endereçável; gerenciadores de senha preenchem melhor `<form>` nativo em URL estável; sob CSP estrita sem lib de
UI, modal exigiria focus-trap/inert/scroll-lock artesanais (superfície nova de falha WCAG + CLS); PRG funciona com
zero JS e sobrevive a chunk falho/rede ruim/botão voltar; precedente da casa: `/historico` é 100% server-rendered.

**Rotas:** `/entrar`, `/entrar/desafio`, `/criar-conta`, `/confirmar/[estado]`, `/recuperar`,
`/recuperar/redefinir`, `/conta` (+ `/conta/dois-fatores`, `/conta/dois-fatores/codigos`, `/conta/email`,
`/conta/senha`, `/conta/dados`, `/conta/excluir`). Uma folha `portaria.css` **escopada por rota** (precedente
`graficos.css`), masthead do `/historico`, ritmo `--ritmo-*`, **zero conectoras novas** (`conectoras-censo.json`
inalterado), **zero glow**, **CLS 0**.

**Correções do red-team aplicadas:**
- **Links de e-mail NUNCA consomem token em GET** — aterrissam em página inerte com botão **POST → verifyOtp**
  (confirm, recovery, email_change). Scanners corporativos (Outlook SafeLinks) fazem GET e queimam o token
  single-use.
- **OAuth Google via `<a href>` (GET)** — form POST cujo 303 vai a `supabase.co` é bloqueável pelo Chrome
  (`form-action 'self'` aplica à cadeia de redirect).
- **`/sair` POST-only** (GET seria disparado pelo prefetch do `next/link`).
- **CSRF explícito** (`Origin`/`Sec-Fetch-Site` + `SameSite=Lax`) em TODO handler mutante — o matcher do proxy
  exclui `/api`, então a defesa mora nos handlers.
- **Layout das rotas PÚBLICAS 100% cookie-free** — um menu de conta lendo `cookies()` torna a vitrine dynamic e
  fragmenta/envenena o ISR (Set-Cookie cacheado = usuário logado como outro). Estado de conta só em segmentos
  dinâmicos.
- **`Cache-Control: no-store` explícito** em toda resposta de handler de auth que escreve cookie (inclusive os 303
  de `renovar`/`callback`/`confirmar`).
- **Oráculo no histórico:** `PATCH /historico/{id}` e o upsert validam tese pública-ou-do-dono antes de gravar;
  recusa byte-idêntica ao 404 de inexistente.
- **`@supabase/ssr` cookies NÃO são httpOnly por padrão** → forçar no adapter; **cookies `sb-*` são chunked**
  (`.0`/`.1`) → sempre `getAll`/`setAll`, logout limpa por PREFIXO.

---

## Correções transversais do red-team (valem para TODAS as ondas)

1. **`X-Portaria` fail-closed:** `PORTARIA_SECRET` ausente em produção = **startup abortado**; bypass explícito só
   em teste. Nunca `if settings.portaria_secret:` condicional (desliga o perímetro em silêncio).
2. **Regressão dos 1015:** adicionar `Depends(usuario_atual)` + middleware `X-Portaria` quebra os testes que
   chamam `/teses` sem JWT/header. **Plano de fixture obrigatório no `conftest`:** `dependency_overrides`
   (`Identidade` fake), `PORTARIA_SECRET` de teste, middleware desligável por setting em ambiente de teste. Os
   1015 passam **sem editar asserção**; nada apagado.
3. **Gate de leitura ATÔMICO num único PR:** `Depends` de auth + filtro de dono no `GET /teses/{id}` **+** rota
   pública `GET /teses/publicas/{ticker}` (lane anon) **+** flip dos cards da vitrine — nunca faseado entre PRs
   (senão os 13 cards tomam 401/404 e a vitrine pública regride).
4. **Asserção E2E de rede** ("navegador nunca fala com `*.supabase.co`") escopada a **`fetch`/`xhr`** — a
   navegação top-level do OAuth para `supabase.co` é permitida e esperada.
5. **`funções mfa_*`/cofre de códigos:** `revoke execute from authenticated/anon/public`; acesso só pela lane de
   serviço; desligar o Data API (PostgREST) no dashboard como defesa extra, **nunca** como substituto das
   policies.
6. **Checklist visual das rotas novas:** zero entradas novas em `conectoras-censo.json`, zero import de
   `ticker-luz.css`, comentários `.tsx` citando utilities Tailwind **em MAIÚSCULA** (pegadinha Arremate — o
   scanner emite CSS de comentário minúsculo), CLS de carga 0 (min-height reservada na região de erro).

## Ondas (sequência de PRs)

- **Onda 1 — A virada da RLS (o P0, atômica):** `0007_portaria_expand` + `0008_portaria_backfill`; `core/auth.py`
  (JWKS ES256); `db/rls.py` (engine_rls + listener `after_begin` + lanes + claims completas + fail-closed);
  `db/session.py` split (`engine_sistema`/`engine_worker`); `routers/teses.py` (GET dono + `GET /teses/publicas`
  + POST exige auth + cache 3 degraus + flip vitrine — **atômico**); `services/tese.py` split de planos + aposenta
  `demo_user` do request path; rate-limit por `sub`; `tem_fator_totp_verified` (SECURITY DEFINER); conftest
  fixtures; **teste `rls-isolation` no CI** (Postgres real). Roda `revisao-seguranca` antes do PR.
- **Onda 2 — Contas (BFF):** `@supabase/ssr`, `lib/supabase-server.ts`/`sessao.ts`/`csrf.ts`/`seguir.ts`/`hibp.ts`;
  handlers `/api/auth/*` (entrar/sair/criar-conta/confirmar/recuperar/oauth-google/callback/renovar); pré-cobrança
  de contenção; rotas `(portaria)` `/entrar`, `/criar-conta`, `/confirmar`, `/recuperar`.
- **Onda 3 — 2FA + conta + LGPD:** enroll/verify/unenroll TOTP; `codigos_recuperacao` + break-glass; `/conta/*`
  (email/senha/dados/excluir); policies `restrictive` aal2 (por último).
- **Onda 4 — Ataque provado + scorecard ASVS V2/V3/V4 + deploy gated.**

## Escalonamentos (só o humano)

- **Google Cloud Console:** OAuth consent + client ID/secret → cadastrar no provider Google do Supabase.
- **Dashboard Supabase:** Confirm email ON; Site URL + redirect allow-list (prod + previews Vercel); templates de
  e-mail com `{{ .TokenHash }}` → nossa origem; access token TTL 600s; reuse-detection ligada; "Require current
  password"; notificações de segurança. **NÃO tocar em Signing Keys** (já ES256). Desligar Data API (opcional).
- **SQL editor:** `ALTER ROLE app_backend LOGIN PASSWORD '…'` (senha out-of-band, nunca em migração). Preflight
  `psql` do login contra o pooler ANTES do cutover.
- **Vercel:** env server-only `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`/`ANON_KEY`, `PORTARIA_SECRET` (sem
  `NEXT_PUBLIC_`). **Railway:** `SUPABASE_URL`, `PORTARIA_SECRET`, `DATABASE_URL_RLS`(app_backend) +
  `DATABASE_URL_MIGRATIONS`(postgres); trocar senha do `postgres` após o cutover.
- **Plano pago:** Leaked Password Protection (compensado por HIBP); SMTP customizado se o embutido estrangular.
- **CRÍTICA pré-existente:** crédito `ANTHROPIC_API_KEY` no Railway (desde 11/07) — sem ele não há prova
  fim-a-fim de geração com conta nova.
- **Ratificação humana** do merge/deploy em produção e do soak do backfill (padrão Fortaleza).

## Questões em aberto (a ratificar)

- Hit público no POST devolve o **id público** (histórico aponta para objeto compartilhado) vs cópia privada
  própria mesmo para tickers da vitrine (custo: 1 cópia de texto, zero LLM).
- HIBP fora do ar: **fail-open com log** (proposto) vs fail-closed.
- `/historico` do visitante anônimo: manter `localStorage` como fallback (proposto) vs exigir login.
- `documentos`/`chunks` do demo: contagem real (esperado 0); se >0, decidir destino antes do contract.
- 2FA opcional desde o dia 1 (presumido) vs obrigatório para exclusão de conta.
- Limite de conexões do Supavisor no Free (dimensionar os dois pools) — conferir antes do deploy.
