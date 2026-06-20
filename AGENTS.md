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

## Convenções
- Python: type hints, `ruff` + `black`, funções pequenas e testáveis. Commits: Conventional Commits.
- Cada função que produz "fato" retorna **valor + fonte**. Sem fonte → não é fato.
- Testes incluem checagem de **não-alucinação** e **segurança** (RLS/authz).

## Segurança (obrigatório)
- RLS ON em toda tabela exposta; policies `(select auth.uid()) is not null and (select auth.uid()) = user_id`.
- `service_role` **só no backend**, nunca no frontend (sem `NEXT_PUBLIC_`).
- Segredos só em `.env`/secret manager. Rode a skill `revisao-seguranca` antes de PR/commit/deploy.

## Não faça
Recomendação personalizada de investimento · dado sem fonte · segredo no código ·
mover dinheiro/dados via LLM sem autorização.
