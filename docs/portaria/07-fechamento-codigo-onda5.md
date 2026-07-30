# Fechamento de código — A Chave na Fechadura (2026-07-29/30)

> Sessão que destravou a esteira, provou a lane RLS, aplicou as migrações de menor-privilégio
> e fechou **todos os achados que não dependem de runtime**. O que ainda depende de
> credenciais de painel (fiação Vercel/Railway, config de Auth, OAuth, ataque vivo, ciclo de
> login real) está listado em §4 e **não** foi marcado como feito.

**Método:** correções em código + provas SQL/psycopg ao vivo no Postgres de produção (lane
`app_backend` NOBYPASSRLS pelo pooler `aws-1-sa-east-1`) + CI verde (4 jobs + Vercel).

---

## 1. Esteira (pré-requisito de tudo) — VERDE

O `master` não compilava: `react-dom@19.2.8` exige peer `react@^19.2.8`, mas `react` estava
em `19.2.7` → ERESOLVE quebrava `npm ci` no CI **e** o build de produção da Vercel (#51, #37).

- `react` 19.2.7 → **19.2.8**; `typescript` `^7` → **5.9.3** (SEGURAR o major; `dependabot.yml`
  passa a ignorar `version-update:semver-major` de typescript).
- `overrides`: `postcss ^8.5.18` (→8.5.23) + `sharp ^0.35.0` (→0.35.3) — fecha os 2 HIGH do
  Trivy (postcss CVE-2026-45623/GHSA-r28c-9q8g-f849; sharp/libvips GHSA-f88m-g3jw-g9cj).
- **CI verde nos 4 jobs + Vercel** (PR #53). Os jobs `frontend` e `security`, cronicamente
  vermelhos, agora passam.

## 2. Migrações e provas de banco (ao vivo)

Prod está em **`alembic_version = 0011`**. Preflight da lane RLS provado com `app_backend`
(LOGIN, NOBYPASSRLS) pelo pooler **`aws-1-sa-east-1.pooler.supabase.com:5432`** (⚠ o runbook
dizia `aws-0`, que devolve *"tenant/user not found"* — corrigido).

| Prova (lane `app_backend`) | Resultado |
|---|---|
| `SET ROLE authenticated` + claims → teses visíveis | **327** (público), **0** privadas |
| cofre `codigos_recuperacao` | **negado (42501)** |
| escrever tese pública / forjar tese de outro dono | **negado (42501)** |
| `SET ROLE service_role` | **negado (42501)** |
| lane `anon` (vitrine) | 327 teses / 540 elos |
| lane `worker` lê `cvm_cadastro` | OK |

**Reversibilidade PROVADA** (0010+0011): round-trip `downgrade → re-upgrade` em transação
revertida — `private→public→private`, grants `narrow→ALL→narrow`, force `on→off→on`. Prod
intacto (verificado depois).

## 3. Achados — veredito um a um

| ID | Sev. | Veredito | Evidência |
|---|---|---|---|
| **LIVE-1** grants ALL/TRUNCATE | médio | **corrigido** | 0010: `REVOKE ALL` + re-grant mínimo; anon só `SELECT` em teses/versoes/elos; provado ao vivo |
| **LIVE-3** FORCE RLS cofre/backup | baixo | **corrigido** | 0010: `codigos_recuperacao` + `_portaria_backup_demo` forced; `alembic_version` fora (ledger de migração) |
| **LIVE-2 / MFA-04** oráculo 2FA no PostgREST | baixo | **corrigido** | 0011: fn `tem_fator_totp_verified` movida `public→private`; execute mantido a `authenticated`; policies aal2 resolvem por OID (provado) |
| **AC-01** exportar bypassa RLS | baixo | **corrigido** | `/conta/exportar` roda sob a lane `authenticated` (belt+suspenders); cofre/excluir seguem no engine de sistema |
| **MFA-01** step-up fail-open | baixo | **corrigido** | senha/email/excluir leem o `error` de `listFactors` (fail-CLOSED) |
| **SESS-01** revogação não-imediata | baixo | **parcial: código feito, TTL pendente** | `/conta/exportar` confirma por `getUser` (revogação-ciente); comentário de `sessoes` corrigido. **Falta:** encurtar o access-token TTL p/ ~600s (config de dashboard) |
| **MFA-01/senha ASVS V2.1.1** piso 10 | — | **corrigido** | piso 10→**12** (rota + copy) em criar-conta/senha/redefinir |
| **HIBP fail-open** | baixo | **aceito c/ justificativa + endurecido** | defesa-em-profundidade (primário = piso 12 + anti-enumeração); travar cadastro em queda de 3º é pior que o risco marginal. +1 retry curto p/ blips |
| **LLM-COST-01** custo sem teto por usuário | baixo | **corrigido** | orçamento por-usuário/dia (`TESE_TETO_CUSTO_USD_DIA_POR_USUARIO=5.0`); A esgota, B segue. +4 testes. Multi-worker (Redis) = roadmap, como o teto global |
| **LLM-GATE-01** léxico de postura | baixo | **corrigido (parcial ratificada)** | R11 pega enquadramentos implícitos (subvalorizado/atrativo/assimetria favorável/…) só com termo de valuation na MESMA frase; `descontado` exclui DCF por lookbehind. "barato/caro" e "margem de segurança" → juiz de postura (roadmap). +2 fixtures |
| **AUTH-01** sem rate-limit de app | baixo | **pendente de medição (PAT)** | primário = limites nativos do GoTrue (a medir); limiter de edge durável precisa de KV (Pro) → roadmap. Ver §4 |

## 4. O que resta (depende de runtime/credenciais — NÃO feito)

1. **Fiação** (tokens Vercel + Railway): env do Supabase na Vercel; `DATABASE_URL_RLS` + `PORTARIA_SECRET` no Railway; deploy do backend novo (fail-closed) **só após a fiação provada**.
2. **Config de Auth** (PAT Supabase): MFA/TOTP, templates pt-BR, e **medir** TTL do access token (SESS-01), rate-limits do GoTrue (AUTH-01) e cap do SMTP.
3. **Google OAuth**: criar client no Cloud Console + ligar no Supabase (STOP humano).
4. **Smoke + ciclo de login real** (2 usuários) e **campanha de ataque §6** (7 itens) — exigem o runtime cabeado.
5. **Higiene final:** aposentar `demo_user` + varrer teses-lixo residuais (a fonte é o warm-cache do backend ANTIGO; some no deploy do backend novo) + destino do `_portaria_backup_demo` no soak.

## 5. Scorecard ASVS — deltas desta sessão (V2/V3/V4)

Atualiza o §5 do `06-onda4-ataque-asvs.md` para os itens que MUDARAM. "parcial" restante é
runtime-dependente e está declarado (não órfão).

| Ref | Requisito | Antes | Agora |
|---|---|---|---|
| V2.1.1 | Senha ≥ 12 | parcial (10) | **passou** (12) |
| V2.1.7 | Senha vs. vazamentos | parcial (fail-open) | **passou c/ ressalva** (fail-open ratificado + retry; primário = piso 12) |
| V2.2.1 | Anti-automação | parcial | **parcial — pendente medição GoTrue (AUTH-01)** |
| V2.8.1 / V6.3.3 | Step-up TOTP em op. sensível | parcial (MFA-01 fail-open) | **passou** (fail-closed) |
| V3.3.1 / V3.3.4 | Logout/encerrar sessões efetivo | parcial (SESS-01) | **melhorou** (export via getUser); **TTL pendente (dashboard)** |
| V3.3.2 | Timeout absoluto/idle | não-verificável | **pendente runtime** |
| V4.1.3 | Menor privilégio | parcial (LIVE-1) | **passou** (0010, provado) |
| V4.1.5 | Fail-closed | passou | passou |
| V4.2.1 / V1.4.4 | Op. de dados sob autz completa | parcial (AC-01) | **passou** (exportar sob lane RLS) |
| V4.3.2 | Anti-enumeração de metadados | parcial (LIVE-2) | **passou** (fn fora do PostgREST) |

**Sem "parcial" órfão:** os 3 "parcial/pendente" que sobram (V2.2.1, V3.3.1/2) dependem de
número medido no dashboard/GoTrue (PAT) — declarados, não escondidos.
