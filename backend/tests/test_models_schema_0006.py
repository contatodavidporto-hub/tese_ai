"""Testes offline da Fundação (F0) da Fase "Tese Profunda": modelos ORM + migração 0006.

Sem rede/DB: valida que os 6 modelos novos importam e mapeiam o schema
esperado, e que o SQL textual da migração 0006 cria as 6 tabelas com RLS +
policy + índice em toda FK, `fonte_id NOT NULL` em todas, os dois CHECKs de
enum ('prudencial'|'societario' e 'PRE'|'IPCA') e o CHECK de tamanho de
`cited_text`, sem nenhum ALTER destrutivo, e que o downgrade reverte limpo.
NÃO altera test_models_schema.py/test_models_schema_0005.py (pinados).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models.models import (
    BancoIndicador,
    ConsensoAnalista,
    CurvaSnapshot,
    PrecoDiario,
    Provento,
    SetorIndicador,
)

# A migração tem nome de módulo iniciando por dígito e vive fora de um pacote
# importável — carregamos pelo caminho do arquivo (robusto, sem __init__.py).
_MIGRACAO_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0006_tese_profunda.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0006", _MIGRACAO_PATH)
assert _spec and _spec.loader
_migracao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migracao)

_TABELAS_NOVAS = (
    "precos_diarios",
    "proventos",
    "banco_indicadores",
    "setor_indicadores",
    "curva_snapshot",
    "consenso_analistas",
)

# Toda FK nova precisa de índice de cobertura (padrão da 0003/0005).
_INDICES_FK = (
    "ix_precos_diarios_fonte_id",
    "ix_proventos_fonte_id",
    "ix_banco_indicadores_fonte_id",
    "ix_setor_indicadores_fonte_id",
    "ix_setor_indicadores_empresa_id",
    "ix_curva_snapshot_fonte_id",
    "ix_consenso_analistas_fonte_id",
)


# ---------------------------------------------------------------------------
# Modelos ORM
# ---------------------------------------------------------------------------
def test_modelos_novos_tem_tablename_esperado() -> None:
    assert PrecoDiario.__tablename__ == "precos_diarios"
    assert Provento.__tablename__ == "proventos"
    assert BancoIndicador.__tablename__ == "banco_indicadores"
    assert SetorIndicador.__tablename__ == "setor_indicadores"
    assert CurvaSnapshot.__tablename__ == "curva_snapshot"
    assert ConsensoAnalista.__tablename__ == "consenso_analistas"


def test_preco_diario_e_ohlcv_nao_ajustado_com_fonte_obrigatoria() -> None:
    cols = set(PrecoDiario.__table__.columns.keys())
    assert {
        "ticker",
        "data_pregao",
        "abertura",
        "maxima",
        "minima",
        "fechamento",
        "volume",
        "negocios",
        "codbdi",
        "fonte_id",
    } <= cols
    for obrigatoria in ("ticker", "data_pregao", "fonte_id"):
        assert PrecoDiario.__table__.columns[obrigatoria].nullable is False, obrigatoria
    # OHLCV pode faltar num pregão incompleto — nullable; só ticker/data/fonte são hard.
    assert PrecoDiario.__table__.columns["fechamento"].nullable is True


def test_provento_tem_chave_natural_e_fonte_obrigatoria() -> None:
    cols = set(Provento.__table__.columns.keys())
    assert {"ticker", "tipo", "valor", "data_com", "data_pagamento", "fonte_id"} <= cols
    for obrigatoria in ("ticker", "tipo", "valor", "data_com", "fonte_id"):
        assert Provento.__table__.columns[obrigatoria].nullable is False, obrigatoria
    assert Provento.__table__.columns["data_pagamento"].nullable is True


def test_banco_indicador_declara_base_prudencial_ou_societario() -> None:
    cols = set(BancoIndicador.__table__.columns.keys())
    assert {"cd_cvm", "indicador", "valor", "unidade", "base", "dt_referencia"} <= cols
    obrigatorias = ("cd_cvm", "indicador", "valor", "unidade", "base", "dt_referencia", "fonte_id")
    for obrigatoria in obrigatorias:
        assert BancoIndicador.__table__.columns[obrigatoria].nullable is False, obrigatoria


def test_setor_indicador_e_generico_com_empresa_opcional() -> None:
    cols = set(SetorIndicador.__table__.columns.keys())
    assert {"empresa_id", "ticker", "indicador", "valor", "unidade", "competencia"} <= cols
    assert SetorIndicador.__table__.columns["empresa_id"].nullable is True
    for obrigatoria in ("ticker", "indicador", "valor", "unidade", "competencia", "fonte_id"):
        assert SetorIndicador.__table__.columns[obrigatoria].nullable is False, obrigatoria


def test_curva_snapshot_tem_vertice_e_inflacao_implicita_opcional() -> None:
    cols = set(CurvaSnapshot.__table__.columns.keys())
    assert {"data_ref", "curva", "vertice_du", "taxa", "inflacao_implicita"} <= cols
    assert CurvaSnapshot.__table__.columns["inflacao_implicita"].nullable is True
    for obrigatoria in ("data_ref", "curva", "vertice_du", "taxa", "fonte_id"):
        assert CurvaSnapshot.__table__.columns[obrigatoria].nullable is False, obrigatoria


def test_consenso_analista_exige_atribuicao_e_cited_text() -> None:
    # Atribuição obrigatória (gate R12): veiculo/url/titulo/cited_text NOT NULL;
    # casa/valor/moeda/page_age podem faltar (item ainda assim é atribuído).
    cols = set(ConsensoAnalista.__table__.columns.keys())
    assert {
        "ticker",
        "casa",
        "metrica",
        "valor",
        "moeda",
        "veiculo",
        "url",
        "titulo",
        "cited_text",
        "page_age",
        "data_busca",
    } <= cols
    for obrigatoria in ("ticker", "metrica", "veiculo", "url", "titulo", "cited_text", "fonte_id"):
        assert ConsensoAnalista.__table__.columns[obrigatoria].nullable is False, obrigatoria
    for opcional in ("casa", "valor", "moeda", "page_age"):
        assert ConsensoAnalista.__table__.columns[opcional].nullable is True, opcional


# ---------------------------------------------------------------------------
# Migração 0006 — aditiva, RLS, índices de FK, CHECKs, reversível
# ---------------------------------------------------------------------------
def test_migracao_encadeia_em_0005() -> None:
    assert _migracao.revision == "0006"
    assert _migracao.down_revision == "0005"


def test_upgrade_habilita_rls_e_policy_para_cada_tabela_nova() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        assert f"create table {tabela} " in sql, f"faltou create table {tabela}"
        assert f"alter table {tabela}" in sql and "enable row level security" in sql
        assert f"on {tabela}" in sql, f"faltou policy em {tabela}"
    assert sql.count("enable row level security") == len(_TABELAS_NOVAS)
    assert sql.count("create policy") == len(_TABELAS_NOVAS)
    assert "to authenticated using (true)" in sql


def test_upgrade_cria_indice_para_toda_fk_nova() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    for indice in _INDICES_FK:
        assert indice in sql, f"faltou índice de FK {indice}"


def test_upgrade_indexa_series_temporais_por_data_desc() -> None:
    # Técnica/gráfico e staleness de consenso leem "os mais recentes primeiro".
    sql = _migracao.UPGRADE_SQL.lower()
    assert "ix_precos_diarios_ticker_data" in sql
    assert "(ticker, data_pregao desc)" in sql
    assert "ix_consenso_analistas_ticker_data" in sql
    assert "(ticker, data_busca desc)" in sql


def test_upgrade_toda_tabela_tem_fonte_id_not_null() -> None:
    # Sem fonte não é fato: cada uma das 6 tabelas novas referencia fontes(id) NOT NULL.
    sql = _migracao.UPGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        inicio = sql.index(f"create table {tabela} ")
        # O fechamento do CREATE TABLE fica sozinho na linha ("\n);"); buscar só
        # ");" quebraria em comentários inline que também contêm ");" (ex.: a
        # nota "(ANEEL);" dentro de setor_indicadores).
        fim = sql.index("\n);", inicio)
        bloco = sql[inicio:fim]
        assert "fonte_id" in bloco and "not null references fontes (id)" in bloco, tabela


def test_upgrade_tem_unicidade_por_granularidade() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    assert "unique (ticker, data_pregao)" in sql
    assert "unique (ticker, tipo, data_com)" in sql
    assert "unique (cd_cvm, indicador, dt_referencia, base)" in sql
    assert "unique (ticker, indicador, competencia)" in sql
    assert "unique (data_ref, curva, vertice_du)" in sql


def test_upgrade_declara_checks_de_enum_e_tamanho() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    assert "check (base in ('prudencial', 'societario'))" in sql
    assert "check (curva in ('pre', 'ipca'))" in sql
    assert "check (char_length(cited_text) <= 150)" in sql


def test_upgrade_e_aditivo_sem_alter_em_tabela_existente() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    assert "drop table" not in sql
    assert "drop column" not in sql
    assert "rename" not in sql
    # F0 não toca em nenhuma tabela pré-existente (só as 6 novas + RLS delas).
    for tabela_existente in ("empresas", "fundamentos", "teses", "elos", "fontes"):
        assert f"alter table {tabela_existente} " not in sql


def test_downgrade_dropa_as_seis_tabelas_novas() -> None:
    down = _migracao.DOWNGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        assert f"drop table if exists {tabela}" in down


def test_downgrade_nao_toca_em_tabela_pre_existente() -> None:
    down = _migracao.DOWNGRADE_SQL.lower()
    for tabela_existente in ("empresas", "fundamentos", "teses", "elos", "fontes"):
        assert tabela_existente not in down
