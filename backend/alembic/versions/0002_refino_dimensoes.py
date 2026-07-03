"""refino das dimensões da visão — cadastro universal B3, pares globais, elos de correlação

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-30

Migração ADITIVA (não altera nenhuma tabela existente; a tese PETR4 pronta não
regride). Cria 4 tabelas de REFERÊNCIA (RLS ON, leitura para `authenticated`;
`service_role` grava):

- `cvm_cadastro`  — cache CAD_CIA_ABERTA + VLMO (CVM): resolve QUALQUER ticker B3
  (COMNEG) -> CD_CVM/CNPJ/razão social/setor. Fim do registro manual de tickers.
  IMPORTANTE (achado A2 do red-team): `comneg` vem SOMENTE do VLMO/FCA (o CAD não
  tem ticker); o enriquecimento (setor/situação) faz JOIN por `cd_cvm`, nunca por
  razão social (fuzzy match é fonte de alucinação).
- `pares` — comparáveis globais do setor. `criterio_selecao` + `fonte_id` gravam
  que a seleção é uma INTERPRETAÇÃO setorial (achado A3), não um "par oficial".
- `pares_fundamentos` — fatos XBRL dos pares (SEC EDGAR), com `taxonomia`
  (us-gaap|ifrs-full) rotulada para nunca comparar padrões contábeis sem ressalva.
- `elos` — grafo causal auditável (D5). Cada elo tem fonte validada nas DUAS
  pontas; `metodo` distingue co-movimento estatístico (Pearson, NÃO causal — achado
  A4) de interpretação causal com hedge; `n_amostras`/`periodo` tornam o r auditável.

Séries macro globais/commodities NÃO exigem DDL: reutilizam `macro_series` com
convenção de `codigo` (prefixos GLOBAL_* e COMMODITY_*).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
-- ---------- Cadastro universal B3 (CAD_CIA_ABERTA + VLMO da CVM) ----------
create table cvm_cadastro (
    id            uuid primary key default gen_random_uuid(),
    cd_cvm        integer not null,
    cnpj          text,
    denom_social  text not null,
    comneg        text,           -- código de negociação (ticker B3); vem só do VLMO/FCA
    especie       text,           -- ON/PN/UNIT... (classe do valor mobiliário)
    sit_reg       text,           -- situação de registro na CVM (ex.: ATIVO)
    setor         text,
    dt_referencia date,
    fonte_id      uuid references fontes (id),
    criado_em     timestamptz not null default now(),
    unique (comneg, especie)
);
create index ix_cvm_cadastro_comneg on cvm_cadastro (comneg);
create index ix_cvm_cadastro_cd_cvm on cvm_cadastro (cd_cvm);

-- ---------- Pares globais do setor (comparáveis SELECIONADOS) ----------
create table pares (
    id               uuid primary key default gen_random_uuid(),
    empresa_id       uuid not null references empresas (id) on delete cascade,
    cik              text,        -- SEC Central Index Key (10 dígitos, zero-pad)
    ticker_ext       text,
    nome_ext         text,
    sic              text,        -- SEC Standard Industrial Classification
    taxonomia        text,        -- 'us-gaap' | 'ifrs-full'
    criterio_selecao text,        -- por que é par (ex.: 'SIC 1311 — critério setorial interno v1')
    fonte_id         uuid references fontes (id),
    criado_em        timestamptz not null default now()
);
create index ix_pares_empresa on pares (empresa_id);

create table pares_fundamentos (
    id         uuid primary key default gen_random_uuid(),
    par_id     uuid not null references pares (id) on delete cascade,
    conceito   text not null,     -- ex.: 'Receita (us-gaap)' / 'Receita (ifrs-full)'
    valor      numeric,
    moeda      text,
    dt_refer   date,
    fonte_id   uuid references fontes (id),
    criado_em  timestamptz not null default now()
);
create index ix_pares_fundamentos_par on pares_fundamentos (par_id);
create index ix_pares_fundamentos_dt on pares_fundamentos (dt_refer);

-- ---------- Grafo causal auditável (motor de correlação D5) ----------
create table elos (
    id               uuid primary key default gen_random_uuid(),
    empresa_id       uuid not null references empresas (id) on delete cascade,
    dimensao         text,
    origem_label     text not null,
    origem_fonte_id  uuid references fontes (id),
    destino_label    text not null,
    destino_fonte_id uuid references fontes (id),
    ligacao_causal   text,        -- só preenchida por interpretação COM hedge (achado A4)
    metodo           text,        -- 'co_movimento_pearson' (NÃO causal) | 'interpretacao_hedge'
    forca_ligacao    double precision check (forca_ligacao >= 0 and forca_ligacao <= 1),
    n_amostras       integer,     -- n do co-movimento (auditável; abster se pequeno)
    periodo          text,        -- janela do co-movimento (ex.: '2025-01..2025-12')
    hedge            text,
    validada         boolean not null default true,
    tese_versao_id   uuid references tese_versoes (id) on delete set null,
    criado_em        timestamptz not null default now()
);
create index ix_elos_empresa_validada on elos (empresa_id, validada);

-- ---------- RLS: tudo referência (leitura para authenticated; service_role grava) ----------
alter table cvm_cadastro      enable row level security;
alter table pares             enable row level security;
alter table pares_fundamentos enable row level security;
alter table elos              enable row level security;

create policy "ref_read_cvm_cadastro"      on cvm_cadastro      for select to authenticated using (true);
create policy "ref_read_pares"             on pares             for select to authenticated using (true);
create policy "ref_read_pares_fundamentos" on pares_fundamentos for select to authenticated using (true);
create policy "ref_read_elos"              on elos              for select to authenticated using (true);
"""

DOWNGRADE_SQL = """
drop table if exists elos cascade;
drop table if exists pares_fundamentos cascade;
drop table if exists pares cascade;
drop table if exists cvm_cadastro cascade;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
