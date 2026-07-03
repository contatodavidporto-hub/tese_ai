"""Testes offline do Estágio 1 do refino: novos modelos ORM + migração 0002.

Sem rede/DB: valida que os modelos importam e que o SQL textual da migração
0002 é aditivo, tem RLS + policy para cada tabela nova, e reverte limpo.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models.models import CvmCadastro, Elo, Par, ParFundamento

# A migração tem nome de módulo iniciando por dígito e vive fora de um pacote
# importável — carregamos pelo caminho do arquivo (robusto, sem __init__.py).
_MIGRACAO_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0002_refino_dimensoes.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0002", _MIGRACAO_PATH)
assert _spec and _spec.loader
_migracao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migracao)

_TABELAS_NOVAS = ("cvm_cadastro", "pares", "pares_fundamentos", "elos")


# ---------------------------------------------------------------------------
# Modelos ORM
# ---------------------------------------------------------------------------
def test_modelos_novos_tem_tablename_esperado() -> None:
    assert CvmCadastro.__tablename__ == "cvm_cadastro"
    assert Par.__tablename__ == "pares"
    assert ParFundamento.__tablename__ == "pares_fundamentos"
    assert Elo.__tablename__ == "elos"


def test_cvm_cadastro_tem_comneg_e_cd_cvm() -> None:
    cols = set(CvmCadastro.__table__.columns.keys())
    assert {"cd_cvm", "cnpj", "denom_social", "comneg", "especie", "setor"} <= cols


def test_par_registra_criterio_de_selecao_interpretativo() -> None:
    # Achado A3: a seleção de par é interpretação, precisa de critério + fonte.
    cols = set(Par.__table__.columns.keys())
    assert {"criterio_selecao", "fonte_id", "taxonomia", "sic"} <= cols


def test_elo_distingue_co_movimento_de_causalidade() -> None:
    # Achado A4: co-movimento (Pearson) não é causal; n/período tornam auditável.
    cols = set(Elo.__table__.columns.keys())
    assert {
        "origem_fonte_id",
        "destino_fonte_id",
        "metodo",
        "n_amostras",
        "periodo",
        "hedge",
    } <= cols


# ---------------------------------------------------------------------------
# Migração 0002 — aditiva, RLS, reversível
# ---------------------------------------------------------------------------
def test_migracao_encadeia_em_0001() -> None:
    assert _migracao.revision == "0002"
    assert _migracao.down_revision == "0001"


def test_upgrade_habilita_rls_e_policy_para_cada_tabela_nova() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        assert f"create table {tabela} " in sql, f"faltou create table {tabela}"
        assert "enable row level security" in sql
        assert f"on {tabela}" in sql, f"faltou policy em {tabela}"
    assert sql.count("enable row level security") == len(_TABELAS_NOVAS)
    assert sql.count("create policy") == len(_TABELAS_NOVAS)


def test_upgrade_nao_altera_tabelas_existentes() -> None:
    # Aditiva: nenhuma tabela pré-existente pode ser alterada/dropada.
    sql = _migracao.UPGRADE_SQL.lower()
    assert "alter table fundamentos" not in sql
    assert "alter table macro_series" not in sql
    assert "drop table" not in sql


def test_downgrade_dropa_as_quatro_tabelas_novas() -> None:
    down = _migracao.DOWNGRADE_SQL.lower()
    for tabela in _TABELAS_NOVAS:
        assert f"drop table if exists {tabela}" in down


def test_elo_tem_check_de_forca_entre_zero_e_um() -> None:
    sql = _migracao.UPGRADE_SQL.lower()
    assert "forca_ligacao" in sql
    assert "forca_ligacao >= 0" in sql and "forca_ligacao <= 1" in sql
