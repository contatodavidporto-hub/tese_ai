"""multiativo — FII (cadastro + indicadores tipados), Tesouro Direto e colunas de classe

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-08

Fundação da Fase 2 multiativo (decisão D3 do conselho, base Design B: separação
limpa por domínio). Cria 3 tabelas de REFERÊNCIA (RLS ON, leitura para
`authenticated`; `service_role` grava):

- `fii_cadastro`    — cadastro de FII (informe mensal CVM, bloco "geral"). O
  `ticker` vem de HEURÍSTICA sobre o ISIN e é rotulado em `ticker_metodo`
  (ex.: 'heuristica_isin'); colisão ou sufixo 12/13 -> ticker NULL e o fundo
  resolve só por CNPJ — a heurística nunca vira fato oficial.
- `fii_indicadores` — indicadores TIPADOS (código canônico + valor + unidade +
  fonte por competência). Armazenamento tipado elimina o parse de texto que
  transformaria 525.069 cotistas em "R$ 525.069,00" (pior falha do Design A).
- `titulos_publicos` — preços/taxas diários do Tesouro Direto (STN), em tabela
  PRÓPRIA (fora de `macro_series`, para não poluir o contexto macro das teses
  de ação). Resolução TD-código -> título usa max(data_base) por (tipo,
  vencimento) — o CSV da STN NÃO é cronológico (reconciliação, delta 5).

ALTERs em tabelas existentes: só ADIÇÕES de coluna nullable (NULL preserva o
comportamento legado byte-idêntico) e dois RELAXAMENTOS monotônicos
metadata-only, comentados no SQL com a justificativa (riscos residuais do
veredito: ratificados pelo maestro; migração aplicada ANTES do código).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
-- ---------- FII: cadastro (informe mensal CVM — inf_mensal_fii_geral) ----------
create table fii_cadastro (
    id            uuid primary key default gen_random_uuid(),
    cnpj          text unique not null,
    nome          text not null,
    ticker        text unique,     -- heurística ISIN; colisão/sufixo 12-13 -> NULL (resolve por CNPJ)
    ticker_metodo text,            -- ex.: 'heuristica_isin' — rotula o método, nunca fato oficial
    isin          text,
    segmento      text,            -- cadastral auto-declarado; vazio -> 'não informado', nunca inventa
    mandato       text,
    tipo_gestao   text,
    mercado_bolsa text,
    dt_referencia date,
    fonte_id      uuid references fontes (id),
    criado_em     timestamptz not null default now()
);
create index ix_fii_cadastro_fonte_id on fii_cadastro (fonte_id);

-- ---------- FII: indicadores TIPADOS (valor + unidade + fonte por competência) ----------
create table fii_indicadores (
    id            uuid primary key default gen_random_uuid(),
    fii_id        uuid not null references fii_cadastro (id) on delete cascade,
    indicador     text not null,   -- código canônico: 'PL','VP_COTA','COTAS_EMITIDAS','COTISTAS','DY_MES_INFORME','RENT_EFETIVA_MES','VACANCIA_AGREGADA'
    valor         numeric not null,
    unidade       text not null,   -- 'BRL' | 'BRL_POR_COTA' | 'UN' | 'PCT' | 'RAZAO'
    metodologia   text,            -- derivadas declaram o método (ex.: vacância ponderada por área m²)
    dt_referencia date not null,
    fonte_id      uuid not null references fontes (id),  -- sem fonte não é fato
    criado_em     timestamptz not null default now(),
    unique (fii_id, indicador, dt_referencia)
);
create index ix_fii_indicadores_fii_id   on fii_indicadores (fii_id);
create index ix_fii_indicadores_fonte_id on fii_indicadores (fonte_id);

-- ---------- Renda fixa: preços/taxas do Tesouro Direto (STN) ----------
create table titulos_publicos (
    id              uuid primary key default gen_random_uuid(),
    tipo            text not null,  -- nome oficial STN (ex.: 'Tesouro IPCA+')
    data_vencimento date not null,
    data_base       date not null,
    taxa_compra     numeric,        -- % a.a.
    taxa_venda      numeric,
    pu_compra       numeric,
    pu_venda        numeric,
    pu_base         numeric,
    fonte_id        uuid not null references fontes (id),  -- sem fonte não é fato
    criado_em       timestamptz not null default now(),
    unique (tipo, data_vencimento, data_base)
);
create index ix_titulos_publicos_fonte_id  on titulos_publicos (fonte_id);
-- Resolução TD-código -> título: max(data_base) por (tipo, vencimento) — o CSV da STN
-- não é cronológico; o índice desc serve o SELECT DISTINCT/max sem full scan.
create index ix_titulos_publicos_resolucao on titulos_publicos (tipo, data_vencimento, data_base desc);

-- ---------- RLS: tudo referência (leitura para authenticated; service_role grava) ----------
alter table fii_cadastro     enable row level security;
alter table fii_indicadores  enable row level security;
alter table titulos_publicos enable row level security;

create policy "ref_read_fii_cadastro"     on fii_cadastro     for select to authenticated using (true);
create policy "ref_read_fii_indicadores"  on fii_indicadores  for select to authenticated using (true);
create policy "ref_read_titulos_publicos" on titulos_publicos for select to authenticated using (true);

-- ---------- Colunas ADITIVAS nullable (NULL = comportamento legado byte-idêntico) ----------
alter table empresas    add column plano_contas text;  -- 'padrao'|'banco'|'seguradora'; NULL = não detectado
alter table teses       add column classe_ativo text;  -- 'acao'|'fii'|'renda_fixa'; NULL = acao (legado)
alter table fundamentos add column unidade      text;  -- 'BRL'|'RAZAO'|'PCT'; NULL = BRL (legado) — corrige B2 (ROE "R$ 0,18")
alter table elos        add column ativo_codigo text;  -- âncora de elo p/ FII/RF (sem empresa)

-- ---------- Relaxamentos monotônicos (metadata-only) — únicos ALTERs não-CREATE ----------
-- JUSTIFICATIVA: elos de FII/RF não têm empresa; empresa_id vira NULLABLE e o CHECK
-- garante que TODO elo continua ancorado (empresa OU ativo_codigo) — nunca órfão.
-- Remover o NOT NULL não reescreve a tabela nem invalida linha existente (monotônico).
alter table elos alter column empresa_id drop not null;
alter table elos add constraint ck_elos_ancora check (empresa_id is not null or ativo_codigo is not null);

-- JUSTIFICATIVA: teses.ticker passa a aceitar códigos RF (ex.: 'TD-IPCA-2035').
-- No ORM é widening (String(12) -> String(32)); no banco o tipo era text (0001) e o
-- varchar(32) fixa um teto sano como defesa em profundidade do validador da API
-- (max 16). Valores existentes são tickers B3 (<= 7 chars): o ALTER valida sem
-- rewrite e nenhuma linha muda de valor.
alter table teses alter column ticker type varchar(32);
"""

DOWNGRADE_SQL = """
-- Ordem inversa da criação. ATENÇÃO: restaurar o NOT NULL de elos.empresa_id exige
-- APAGAR ANTES os elos ancorados só por ativo_codigo (empresa_id IS NULL) — sem o
-- DELETE o SET NOT NULL falha. Perda aceitável: esses elos só existem no mundo
-- multiativo que este downgrade remove.
drop table if exists titulos_publicos cascade;
drop table if exists fii_indicadores cascade;
drop table if exists fii_cadastro cascade;

alter table teses alter column ticker type text;  -- restaura o tipo da 0001

alter table elos drop constraint if exists ck_elos_ancora;
delete from elos where empresa_id is null;
alter table elos alter column empresa_id set not null;
alter table elos drop column if exists ativo_codigo;

alter table fundamentos drop column if exists unidade;
alter table teses       drop column if exists classe_ativo;
alter table empresas    drop column if exists plano_contas;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
