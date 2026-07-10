"""tese profunda — preços diários, proventos, indicadores banco/setor, curva ANBIMA, consenso

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-10

Fundação (F0) do PROMPT-MÃE "Tese Profunda". Cria 6 tabelas de REFERÊNCIA
(RLS ON, leitura para `authenticated`; `service_role` grava) — mesmo padrão
da 0005 (§2.2 do plano):

- `precos_diarios`      — OHLCV diário por ticker (COTAHIST B3). Preços NÃO
  ajustados por proventos (rótulo obrigatório no consumidor — técnica/β
  "aproximados"). `codbdi` filtra o tipo de mercado (02=lote-padrão,
  12=FII, 14=ETF — sonda 2026-07-10, ver correção A9).
- `proventos`           — dividendos/JCP/rendimentos por ticker (B3
  cashDividends) — base do DY a mercado (destrava FII/ação).
- `banco_indicadores`   — indicadores TIPADOS do IF.data (BCB): Basileia,
  PR, RWA, carteira de crédito, ativos problemáticos, LL anualizado, cada
  um com `base` declarada ('prudencial'|'societario') — nunca misturadas
  no mesmo indicador (Res. 4966 muda a base a partir de 2025).
- `setor_indicadores`   — registro genérico extensível por
  (ticker, indicador, competência): hoje só RAP (ANEEL/energia);
  varejo/saneamento/seguros entram depois como DADO, não como tabela nova.
- `curva_snapshot`      — ETTJ ANBIMA, SNAPSHOT do dia (nunca série
  sistemática — ToS ANBIMA proíbe redistribuir a base histórica).
- `consenso_analistas`  — itens de consenso de terceiros (web_search),
  sempre ATRIBUÍDOS (veículo/casa/URL/data), com `cited_text` truncado
  (≤150 chars, CHECK) — o motor nunca cita a página bruta como documento,
  só o item estruturado validado (correção A11, defesa contra
  prompt-injection do conteúdo da página).

Todo fato tem `fonte_id NOT NULL references fontes(id)` — sem fonte não é
fato. Migração puramente ADITIVA: só CREATE TABLE, nenhum ALTER em tabela
existente, nenhum DROP.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
-- ---------- Preços diários (COTAHIST B3) — OHLCV NÃO ajustado por proventos ----------
create table precos_diarios (
    id          uuid primary key default gen_random_uuid(),
    ticker      text not null,
    data_pregao date not null,
    abertura    numeric,
    maxima      numeric,
    minima      numeric,
    fechamento  numeric,
    volume      numeric,
    negocios    integer,
    codbdi      integer,        -- 02=lote-padrão, 12=FII, 14=ETF (COTAHIST; correção A9)
    fonte_id    uuid not null references fontes (id),  -- sem fonte não é fato
    criado_em   timestamptz not null default now(),
    unique (ticker, data_pregao)
);
create index ix_precos_diarios_fonte_id  on precos_diarios (fonte_id);
-- Técnica/gráfico busca as últimas N datas de um ticker: desc serve direto (sem sort).
create index ix_precos_diarios_ticker_data on precos_diarios (ticker, data_pregao desc);

-- ---------- Proventos (B3 cashDividends) — base do DY a mercado ----------
create table proventos (
    id             uuid primary key default gen_random_uuid(),
    ticker         text not null,
    tipo           text not null,  -- 'DIVIDENDO'|'JCP'|'RENDIMENTO'|...
    valor          numeric not null,
    data_com       date not null,
    data_pagamento date,
    fonte_id       uuid not null references fontes (id),
    criado_em      timestamptz not null default now(),
    unique (ticker, tipo, data_com)
);
create index ix_proventos_fonte_id on proventos (fonte_id);

-- ---------- Indicadores de banco (IF.data/BCB) — tipados, base declarada ----------
create table banco_indicadores (
    id            uuid primary key default gen_random_uuid(),
    cd_cvm        integer not null,
    indicador     text not null,   -- 'BASILEIA','PR','RWA','CARTEIRA_CREDITO','ATIVOS_PROBLEMATICOS','LL_ANUALIZADO'
    valor         numeric not null,
    unidade       text not null,   -- 'PCT'|'BRL'|'RAZAO'
    base          text not null,   -- 'prudencial'|'societario' — nunca misturar no mesmo indicador
    dt_referencia date not null,
    metodologia   text,
    fonte_id      uuid not null references fontes (id),
    criado_em     timestamptz not null default now(),
    unique (cd_cvm, indicador, dt_referencia, base),
    constraint ck_banco_indicadores_base check (base in ('prudencial', 'societario'))
);
create index ix_banco_indicadores_fonte_id on banco_indicadores (fonte_id);

-- ---------- Indicadores de setor — registro genérico extensível (RAP hoje) ----------
create table setor_indicadores (
    id          uuid primary key default gen_random_uuid(),
    empresa_id  uuid references empresas (id) on delete set null,  -- opcional: liga ao cadastro quando existir
    ticker      text not null,
    indicador   text not null,   -- ex.: 'RAP' (ANEEL); setor novo = novo valor, não nova tabela
    valor       numeric not null,
    unidade     text not null,
    competencia date not null,
    metodologia text,
    fonte_id    uuid not null references fontes (id),
    criado_em   timestamptz not null default now(),
    unique (ticker, indicador, competencia)
);
create index ix_setor_indicadores_fonte_id   on setor_indicadores (fonte_id);
create index ix_setor_indicadores_empresa_id on setor_indicadores (empresa_id);

-- ---------- Curva ANBIMA (ETTJ) — SNAPSHOT do dia, nunca série sistemática ----------
create table curva_snapshot (
    id                 uuid primary key default gen_random_uuid(),
    data_ref           date not null,
    curva              text not null,     -- 'PRE'|'IPCA'
    vertice_du         integer not null,  -- dias úteis até o vértice
    taxa               numeric not null,
    inflacao_implicita numeric,
    fonte_id           uuid not null references fontes (id),
    criado_em          timestamptz not null default now(),
    unique (data_ref, curva, vertice_du),
    constraint ck_curva_snapshot_curva check (curva in ('PRE', 'IPCA'))
);
create index ix_curva_snapshot_fonte_id on curva_snapshot (fonte_id);

-- ---------- Consenso de analistas — itens ATRIBUÍDOS (nunca a página bruta) ----------
create table consenso_analistas (
    id         uuid primary key default gen_random_uuid(),
    ticker     text not null,
    casa       text,           -- corretora/casa de análise, quando identificável
    metrica    text not null,  -- ex.: 'preco_alvo'|'rating'
    valor      numeric,
    moeda      text,
    veiculo    text not null,  -- veículo de mídia (atribuição obrigatória — gate R12)
    url        text not null,
    titulo     text not null,
    cited_text text not null,  -- trecho citado, truncado — defesa contra prompt-injection da página
    page_age   text,           -- idade da página no momento da busca (web_search), staleness na leitura
    data_busca timestamptz not null default now(),
    fonte_id   uuid not null references fontes (id),
    criado_em  timestamptz not null default now(),
    constraint ck_consenso_analistas_cited_text_len check (char_length(cited_text) <= 150)
);
create index ix_consenso_analistas_fonte_id    on consenso_analistas (fonte_id);
-- Validação de staleness lê o item mais recente por ticker primeiro.
create index ix_consenso_analistas_ticker_data on consenso_analistas (ticker, data_busca desc);

-- ---------- RLS: tudo referência (leitura para authenticated; service_role grava) ----------
alter table precos_diarios     enable row level security;
alter table proventos          enable row level security;
alter table banco_indicadores  enable row level security;
alter table setor_indicadores  enable row level security;
alter table curva_snapshot     enable row level security;
alter table consenso_analistas enable row level security;

create policy "ref_read_precos_diarios"     on precos_diarios     for select to authenticated using (true);
create policy "ref_read_proventos"          on proventos          for select to authenticated using (true);
create policy "ref_read_banco_indicadores"  on banco_indicadores  for select to authenticated using (true);
create policy "ref_read_setor_indicadores"  on setor_indicadores  for select to authenticated using (true);
create policy "ref_read_curva_snapshot"     on curva_snapshot     for select to authenticated using (true);
create policy "ref_read_consenso_analistas" on consenso_analistas for select to authenticated using (true);
"""

DOWNGRADE_SQL = """
-- Ordem inversa da criação. Todas as 6 tabelas são novas nesta migração (sem
-- ALTER em tabela existente), então o downgrade é só DROP — sem reconciliação.
drop table if exists consenso_analistas cascade;
drop table if exists curva_snapshot cascade;
drop table if exists setor_indicadores cascade;
drop table if exists banco_indicadores cascade;
drop table if exists proventos cascade;
drop table if exists precos_diarios cascade;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
