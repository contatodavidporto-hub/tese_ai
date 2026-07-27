# AGENTS.md — PROJETO (código do produto)

> Guia curto para agentes de código que trabalham **dentro de `PROJETO/`**.
> O guia completo do Vault está em `../AGENTS.md` e `../CLAUDE.md` — leia antes de codar.

## Princípios inegociáveis (valem para TODO código)
1. **Nunca inventar dado.** Todo fato vem de dado recuperado, com **fonte+data**. Faltou → **abster**.
2. **Nunca recomendar compra/venda.** Estrutura a tese; o usuário decide (CVM).
3. **Rastreabilidade > esperteza.** Trilha de auditoria (fontes, versão de prompt/modelo).
4. **Segurança desde o dia 1.** RLS ON em toda tabela exposta; segredos só em `.env`.

## Comandos
- Setup: `cd backend && uv venv && uv pip install -e ".[dev]"`
- Backend: `uv run uvicorn app.main:app --reload --port 8000`
- Testes: `uv run pytest -q`  ·  Lint: `uv run ruff check .` + `uv run black --check .`
- Migração: `uv run alembic upgrade head`
- Frontend: `cd frontend && npm run dev`

## Dependências com condição (frontend)
- `gsap@3.15.0` (pin exato): motor de scrollytelling da LANDING — licença Webflow **"Standard no-charge"** (grátis comercial, **não-MIT**; termos próprios, sem redistribuir como ferramenta concorrente). Provado CSP-safe (Chromium/Firefox/WebKit, zero violações; escreve via CSSOM). **Plugin Flip PROIBIDO** (`setAttribute('style')`), `markers` proibido em prod, carregamento SÓ via `import()` dinâmico pós-idle (`src/lib/gsapSetup.ts`); zero gsap em /tese (gate de bundle). Regras: `frontend/DESIGN-TOKENS.md`.

## Convenções
- Python: type hints, `ruff` + `black`, funções pequenas e testáveis. Commits: Conventional Commits.
- Cada função que produz "fato" retorna **valor + fonte**. Sem fonte → não é fato.
- Testes incluem checagem de **não-alucinação** e **segurança** (RLS/authz).

## Segurança (obrigatório)
- RLS ON em toda tabela exposta; policies `(select auth.uid()) is not null and (select auth.uid()) = user_id`.
- `service_role` **só no backend**, nunca no frontend (sem `NEXT_PUBLIC_`).
- Segredos só em `.env`/secret manager. Rode a skill `revisao-seguranca` antes de PR/commit/deploy.
- **Documentação viva de segurança** (`docs/security/`): `threat-model.md` (STRIDE), `compliance-asvs-owasp-nist.md` (OWASP/ASVS/NIST — ver banner de re-baseline), `plano-resposta-incidentes-lgpd.md` (IR + LGPD), `observabilidade-seguranca.md`, `SECURITY.md` (divulgação responsável). Scan diário de CVE: `.github/workflows/security-scheduled.yml` (abre issue `security`).
- **Auditoria + endurecimento "Fortaleza" (2026-07-21):** relatório, scorecard (OWASP/ASVS/SSDF/SLSA/SRE/CIS), ADRs, roadmap e pentest em `docs/fortaleza/`. Ler antes de mexer em `core/limits.py` (semáforo), no gate (`avaliacao.py`) ou no CI.

## Não faça
Recomendação personalizada de investimento · dado sem fonte · segredo no código ·
mover dinheiro/dados via LLM sem autorização.
