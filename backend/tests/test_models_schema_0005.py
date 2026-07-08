"""Testes offline do Bloco 1 da Fase 2 multiativo: modelos ORM + migração 0005.

Sem rede/DB: valida que os modelos importam e que o SQL textual da migração
0005 cria as 3 tabelas novas com RLS + policy + índice em toda FK, que os
ALTERs em tabelas existentes se limitam a adições nullable e aos dois
relaxamentos monotônicos permitidos (D3), e que o downgrade reverte limpo
(incluindo o DELETE obrigatório antes de restaurar o NOT NULL de elos).
NÃO altera test_models_schema.py (pinado na 0002).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models.models import (
    Elo,
    Empresa,
    FiiCadastro,
    FiiIndicador,
    Fundamento,
    Tese,
    TituloPublico,
)

# A migração tem nome de módulo iniciando por dígito e vive fora de um pacote
# importável — carregamos pelo caminho do arquivo (robusto, sem __init__.py).
_MIGRACAO_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0005_multiativo.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0005", _MIGRACAO_PATH)
assert _spec and _spec.loader
_migracao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migracao)

_TABELAS_NOVAS = ("fii_cadastro", "fii_indicadores", "titulos_publicos")

# Toda FK nova precisa de índice de cobertura (padrão da 0003).
_INDICES_FK = (
    "ix_fii_cadastro_fonte_id",
    "ix_fii_indicadores_fii_id",
    "ix_fii_indicadores_fonte_id",
    "ix_titulos_publicos_fonte_id",
)

_COLUNAS_ADITIVAS = (
    ("empresas", "plano_contas"),
    ("teses", "classe_ativo"),
    ("fundamentos", "unidade"),
    ("elos", "ativo_codigo"),
)


# ---------------------------------------------------------------------------
# Modelos ORM
# ---------------------------------------------------------------------------
def test_modelos_novos_tem_tablename_esperado() -> None:
    assert FiiCadastro.__tablename__ == "fii_cadastro"
    assert FiiIndicador.__tablename__ == "fii_indicadores"
    assert TituloPublico.__tablename__ == "titulos_publicos"


def test_fii_cadastro_rotula_a_heuristica_de_ticker() -> None:
    # O ticker de FII vem de heurística ISIN: `ticker_metodo` rotula o método,
    # para nunca apresentar a heurística como fato oficial (anti-alucinação).
    cols = set(FiiCadastro.__table__.columns.keys())
    assert {
        "cnpj",
        "nome",
        "ticker",
        "ticker_metodo",
        "isin",
        "segmento",
        "mandato",
        "tipo_gestao",
        "mercado_bolsa",
        "fonte_id",
    } <= cols
    assert FiiCadastro.__table__.columns["cnpj"].nullable is False
    assert FiiCadastro.__table__.columns["ticker"].nullable is True  # colisão ISIN -> NULL


def test_fii_indicador_e_tipado_com_unidade_e_fonte_obrigatorias() -> None:
    # Armazenamento TIPADO (indicador/valor/unidade) — nada de parse de texto;
    # sem fonte não é fato (fonte_id NOT NULL).
    cols = set(FiiIndicador.__table__.columns.keys())
    assert {"fii_id", "indicador", "valor", "unidade", "metodologia", "dt_referencia"} <= cols
    for obrigatoria in ("fii_id", "indicador", "valor", "unidade", "dt_referencia", "fonte_id"):
        assert FiiIndicador.__table__.columns[obrigatoria].nullable is False, obrigatoria


def test_titulo_publico_tem_granularidade_e_fonte_obrigatoria() -> None:
    cols = set(TituloPublico.__table__.columns.keys())
    assert {
        "tipo",
        "data_vencimento",
        "data_base",
        "taxa_compra",
        "taxa_venda",
        "pu_compra",
        "pu_venda",
        "pu_base",
    } <= cols
    for obrigatoria in ("tipo", "data_vencimento", "data_base", "fonte_id"):
        assert TituloPublico.__table__.columns[obrigatoria].nullable is False, obrigatoria


def test_colunas_novas_espelhadas_nos_modelos_existentes() -> None:
    assert "plano_contas" in Empresa.__table__.columns
    assert "classe_ativo" in Tese.__table__.columns
    assert "unidade" in Fundamento.__table__.columns
    assert "ativo_codigo" in Elo.__table__.columns
    # NULL preserva o legado: todas nullable.
    assert Empresa.__table__.columns["plano_contas"].nullable is True
    assert Tese.__table__.columns["classe_ativo"].nullable is True
    assert Fundamento.__table__.columns["unidade"].nullable is True


def test_tese_ticker_comporta_codigos_de_renda_fixa() -> None:
    # 'TD-IPCA-2035' (12 chars) e a gramática TD-* cabem no String(32).
    assert Tese.__table__.columns["ticker"].type.length == 32


def test_elo_ancora_por_empresa_ou_ativo_codigo() -> None:
    # elos de FII/RF não têm empresa: empresa_id nullable + ativo_codigo novo.
    assert Elo.__table__.columns["empresa_id"].nullable is True
    assert Elo.__table__.columns["ativo_codigo"].nullable is True


# ---------------------------------------------------------------------------
# Migração 0005 — aditiva, RLS, índices de FK, reversível
# ---------------------------------------------------------------------------
def test_migracao_encadeia_em_0004() -> None:
    assert _migracao.revision == "0005"
    assert _migracao.down_revision == "0004"


def test_upgrade_habilita_rls_e_policy_para_cada_tabela_nova() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        assert f"create table {tabela} " in sql, f"faltou create table {tabela}"
        assert f"alter table {tabela}" in sql and "enable row level security" in sql
        assert f"on {tabela}" in sql, f"faltou policy em {tabela}"
    assert sql.count("enable row level security") == len(_TABELAS_NOVAS)
    assert sql.count("create policy") == len(_TABELAS_NOVAS)


def test_upgrade_cria_indice_para_toda_fk_nova() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    for indice in _INDICES_FK:
        assert indice in sql, f"faltou índice de FK {indice}"


def test_upgrade_indexa_a_resolucao_de_titulo_por_data_base_desc() -> None:
    # max(data_base) por (tipo, vencimento): o CSV da STN não é cronológico.
    sql = _migracao.UPGRADE_SQL.lower()
    assert "ix_titulos_publicos_resolucao" in sql
    assert "(tipo, data_vencimento, data_base desc)" in sql


def test_upgrade_tem_unicidade_por_granularidade() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    assert "unique (fii_id, indicador, dt_referencia)" in sql
    assert "unique (tipo, data_vencimento, data_base)" in sql
    assert "cnpj          text unique not null" in sql  # 1 FII por CNPJ


def test_upgrade_e_aditivo_sem_drop_de_tabela_ou_coluna() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    assert "drop table" not in sql
    assert "drop column" not in sql
    assert "rename" not in sql


def test_upgrade_adiciona_as_colunas_nullable_da_d3() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    for tabela, coluna in _COLUNAS_ADITIVAS:
        assert (
            f"alter table {tabela}" in sql and f"add column {coluna}" in sql
        ), f"faltou {tabela}.{coluna}"
        # Aditiva de verdade: nenhuma das colunas novas nasce NOT NULL.
        idx = sql.index(f"add column {coluna}")
        linha = sql[idx : sql.index("\n", idx)]
        assert "not null" not in linha, f"{tabela}.{coluna} não pode nascer not null"


def test_relaxamentos_sao_somente_os_dois_permitidos() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    # 1) elos.empresa_id nullable, protegido pelo CHECK de âncora.
    assert "alter table elos alter column empresa_id drop not null" in sql
    assert sql.count("drop not null") == 1
    assert "constraint ck_elos_ancora" in sql
    assert "check (empresa_id is not null or ativo_codigo is not null)" in sql
    # 2) teses.ticker -> varchar(32) (widening do contrato p/ códigos RF).
    assert "alter table teses alter column ticker type varchar(32)" in sql
    assert sql.count("alter column ticker type") == 1


def test_downgrade_dropa_tabelas_e_colunas_novas() -> None:
    down = _migracao.DOWNGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        assert f"drop table if exists {tabela}" in down
    for _tabela, coluna in _COLUNAS_ADITIVAS:
        assert f"drop column if exists {coluna}" in down
    assert "drop constraint if exists ck_elos_ancora" in down
    assert "alter table teses alter column ticker type text" in down


def test_downgrade_deleta_elos_sem_empresa_antes_de_restaurar_not_null() -> None:
    # SET NOT NULL falharia com elos ancorados só por ativo_codigo: o DELETE
    # documentado precisa vir ANTES (e depois do drop do CHECK).
    down = _migracao.DOWNGRADE_SQL.lower()
    i_delete = down.index("delete from elos where empresa_id is null")
    i_set = down.index("alter table elos alter column empresa_id set not null")
    i_drop_ck = down.index("drop constraint if exists ck_elos_ancora")
    assert i_drop_ck < i_delete < i_set
