# Plano de Resposta a Incidentes de Segurança + LGPD — Tese AI

> **Status:** runbook operacional (v1, 2026-07-11). Preenche a exigência documentada em
> `Vault/17 - Seguranca/Segurança - LGPD e Incidentes.md` ("runbook de incidente documentado e
> testado"), que até aqui existia como obrigação, não como documento.
> **Não é parecer jurídico.** Os prazos e obrigações LGPD abaixo reproduzem a posição já
> documentada pelo projeto; validar com assessoria antes de depender em um incidente real.

## 0. Escopo e premissas

- **Superfície coberta:** Frontend Next (Vercel), Backend FastAPI (Railway), Supabase (Postgres+RLS+pgvector),
  camada Anthropic, CI (GitHub Actions), conectores externos keyless (CVM/SEC/BCB/B3/ANEEL/ANBIMA/FRED/World Bank).
- **Dado pessoal hoje:** o produto está **sem login**; não há base de titulares autenticados. O e-mail
  operacional público (User-Agent dos conectores) não é dado pessoal de titular-cliente. Logo, a exposição
  LGPD atual é **baixa** — mas este runbook já entra em vigor porque (a) segredos de produção existem
  (`ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`) e (b) o login virá.
- **Quando o login existir:** dados de titular (e-mail, eventualmente CPF/pagamento via Asaas-Pix) passam a
  estar em escopo LGPD pleno — reavaliar a classificação de severidade abaixo.

## 1. Papéis (RACI mínimo)

| Papel | Quem | Responsabilidade no incidente |
|---|---|---|
| **Comandante do Incidente (IC)** | Fundador (David) | Declara o incidente, decide contenção/rollback, autoriza rotação de segredo de produção, comunica. |
| **Encarregado/DPO** | **A DESIGNAR** (pendência do humano) | Avalia dever de notificar ANPD/titulares; conduz comunicação regulatória. |
| **Operador técnico** | Claude Code (maestro + especialistas) sob autorização do IC | Executa contenção/erradicação/recuperação reversíveis; propõe (não executa) as irreversíveis. |

> **Ação pendente do humano:** designar formalmente o Encarregado/DPO (exigência LGPD art. 41). Enquanto
> não houver, o IC acumula o papel.

## 2. Classificação de severidade (define o relógio)

| Sev | Definição | Exemplos | SLA de contenção |
|---|---|---|---|
| **SEV-1 (crítico)** | Vazamento/perda de dado pessoal de titular **ou** comprometimento de segredo de produção **ou** RCE/controle do backend. | `SERVICE_ROLE_KEY` exposta; dump de tabela de usuários; atacante executa código no Railway. | **imediato** (≤1h) |
| **SEV-2 (alto)** | Acesso não autorizado sem exfiltração confirmada; bypass de authz; DoS derrubando produção. | Bypass de rate-limit esgotando teto de custo LLM; RLS falha em ambiente com login. | ≤4h |
| **SEV-3 (médio)** | Vulnerabilidade explorável sem impacto ativo; scanner achando HIGH/CRITICAL em produção. | CVE HIGH nova numa dependência em produção; header de segurança ausente explorável. | ≤24h |
| **SEV-4 (baixo)** | Fraqueza sem exploração prática; achado informativo. | `img-src data:`; índice não usado. | próximo ciclo |

## 3. Ciclo de resposta (NIST SP 800-61)

### 3.1 Detecção & triagem
- **Fontes de sinal:** alertas de anomalia (ver §5 e `docs/security/observabilidade-seguranca.md`),
  scan agendado (`.github/workflows/security-scheduled.yml`), Dependabot/CVE, logs do Railway/Vercel/Supabase,
  relato externo (ver `SECURITY.md`).
- **Primeira ação:** o receptor abre um registro de incidente (timestamp, sinal, sistemas afetados) e
  classifica a severidade. **Preserve evidência antes de mexer** (logs, headers, request ids).

### 3.2 Contenção
Reversível → o operador técnico executa sob OK do IC. **Irreversível → propõe e espera o IC** (trava do projeto):
- Bloquear origem/IP no edge (quando houver WAF).
- Desligar o job de geração (`SCHEDULER_ENABLED=false` / `RATE_LIMIT_CRIAR_TESE` mais estrito) para conter abuso/custo.
- **Rotação de segredo de produção** que possa derrubar o serviço → **decisão do IC** (não fazer autonomamente).
- **Rollback** (Vercel Instant Rollback / Railway redeploy da versão anterior — ver `infra/DEPLOY.md`).

### 3.3 Erradicação
- Corrigir a causa-raiz (patch/config), adicionar **teste de regressão permanente** (padrão do projeto:
  todo achado fechado ganha regressão), rodar `revisao-seguranca` + scanners antes do redeploy.

### 3.4 Recuperação
- Redeploy do artefato corrigido; validar smoke de produção (`infra/DEPLOY.md`); monitorar reincidência 24-72h.

### 3.5 Pós-incidente
- **Post-mortem sem culpa em ≤5 dias úteis**: linha do tempo, causa-raiz, o que funcionou, ações preventivas
  com dono e prazo. Vira nota no Vault (`17 - Seguranca`) e, se aplicável, novo caso de red-team/regressão.

## 4. Trilho LGPD — notificação à ANPD (quando houver dado pessoal em escopo)

> Reproduz a posição documentada em `Segurança - LGPD e Incidentes.md`.

1. **Gatilho:** incidente de segurança com dado pessoal que **possa acarretar risco ou dano relevante** aos titulares.
2. **Prazo:** **3 (três) dias úteis** a contar do conhecimento — base declarada: **Resolução CD/ANPD nº 15,
   de 24/04/2024, arts. 6º e 9º** (para agente de **pequeno porte**, o prazo é de 6 dias úteis). *Não* atribuir
   o prazo ao art. 48 da Lei (que fala em "prazo razoável").
3. **Como:** comunicação **preliminar** via **SEI!ANPD**, conduzida pelo Encarregado/DPO; **comunicação
   complementar** detalhando em até **20 dias úteis**.
4. **Titulares:** comunicar os titulares afetados quando o risco for relevante (mensagem clara: o que houve,
   quais dados, o que o titular deve fazer).
5. **Conteúdo mínimo:** natureza dos dados, titulares envolvidos, medidas técnicas/segurança usadas, riscos,
   medidas adotadas para reverter/mitigar.

**Checklist de decisão (anexar ao registro):** [ ] houve dado pessoal? [ ] risco/dano relevante? [ ] pequeno
porte? [ ] relógio de 3/6 dias úteis iniciado em ___/___/___ ? [ ] DPO acionado? [ ] SEI!ANPD aberto?

## 5. Ganchos de observabilidade e comunicação
- **Detecção:** ver `docs/security/observabilidade-seguranca.md` (eventos de segurança + alertas de anomalia).
- **Canal de relato externo:** `SECURITY.md` (política de divulgação responsável).
- **Registro:** cada incidente vira um arquivo `AAAA-MM-DD-titulo.md` neste diretório com a linha do tempo.

## 6. Pendências do humano (para "nível bancário")
- [ ] **Designar o Encarregado/DPO** (LGPD art. 41).
- [ ] Validar prazos/obrigações com assessoria jurídica (este runbook não é parecer).
- [ ] Exercício de mesa (tabletop) do cenário SEV-1 "segredo de produção vazado" — testar o runbook.
- [ ] Definir RTO/RPO e política de backup/restore testada do Supabase (ver §3.4).
- [ ] (Quando houver login/pagamento) reavaliar classificação e obrigações de titular.
