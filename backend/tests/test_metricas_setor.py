"""Testes offline do registro de métricas por setor (app.services.metricas_setor).

100% offline: SQLite em memória com as tabelas dos modelos (server_defaults do
Postgres removidos e preenchidos por evento de sessão — padrão de
test_fii_dados.py); nenhuma rede (o módulo só LÊ fatos persistidos). Cada seed
grava a `Fonte` junto — fato sem fonte é abstido pelo próprio módulo.

Foco anti-alucinação: dado ausente/stale/sem metodologia -> valor=None + lacuna
declarada (nunca 0-fill); degradação A13 (tabela ausente -> lacuna rotulada);
linguagem dos templates NEUTRA (pré-checagem do gate A5 via avaliacao).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import Session

from app.models.models import (
    BancoIndicador,
    CurvaSnapshot,
    Empresa,
    FiiCadastro,
    FiiIndicador,
    Fonte,
    Fundamento,
    PrecoDiario,
    Provento,
    SetorIndicador,
    TituloPublico,
)
from app.services import metricas_setor
from app.services.avaliacao import _violacoes_recomendacao
from app.services.metricas_setor import (
    ContextoMetricas,
    FonteMetrica,
    MetricaSetor,
    calcular,
    metricas_para_envelope,
)

HOJE = dt.date(2026, 7, 10)
CD_CVM_ITAU = 19348

_TABELAS_TODAS = (
    Fonte.__table__,
    Empresa.__table__,
    Fundamento.__table__,
    BancoIndicador.__table__,
    SetorIndicador.__table__,
    PrecoDiario.__table__,
    Provento.__table__,
    FiiCadastro.__table__,
    FiiIndicador.__table__,
    CurvaSnapshot.__table__,
    TituloPublico.__table__,
)


def _sessao_com(tabelas: tuple) -> Iterator[Session]:
    engine = create_engine("sqlite://")
    meta = MetaData()
    for tabela in tabelas:
        copia = tabela.to_metadata(meta)
        for col in copia.columns:
            col.server_default = None  # gen_random_uuid()/now() não existem no SQLite
    meta.create_all(engine)
    with Session(engine) as s:

        @event.listens_for(s, "before_flush")
        def _defaults(sess, _ctx, _instances) -> None:
            for obj in sess.new:
                if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()
                if hasattr(obj, "criado_em") and getattr(obj, "criado_em", None) is None:
                    obj.criado_em = dt.datetime.now(dt.UTC)

        yield s
    engine.dispose()


@pytest.fixture()
def sessao() -> Iterator[Session]:
    yield from _sessao_com(_TABELAS_TODAS)


@pytest.fixture()
def sessao_sem_precos() -> Iterator[Session]:
    """Banco SEM `precos_diarios` — degradação A13 (migração 0006 pendente)."""
    yield from _sessao_com(tuple(t for t in _TABELAS_TODAS if t.name != "precos_diarios"))


# --- Seeds (todo fato com Fonte) ---------------------------------------------
def _fonte(sessao: Session, descricao: str, data: dt.date, url: str = "https://fonte/x") -> Fonte:
    fonte = Fonte(url=url, descricao=descricao, dt_referencia=data)
    sessao.add(fonte)
    sessao.flush()
    return fonte


def _empresa(sessao: Session, cd_cvm: int = CD_CVM_ITAU, ticker: str = "ITUB4") -> Empresa:
    empresa = Empresa(cd_cvm=cd_cvm, ticker=ticker, nome="Empresa Teste S.A.")
    sessao.add(empresa)
    sessao.flush()
    return empresa


def _fundamento(
    sessao: Session,
    empresa: Empresa,
    conta: str,
    valor: float,
    data: dt.date,
    unidade: str | None = None,
) -> Fundamento:
    fonte = _fonte(sessao, f"CVM DFP — {conta}", data)
    linha = Fundamento(
        empresa_id=empresa.id,
        conta=conta,
        valor=valor,
        unidade=unidade,
        dt_refer=data,
        fonte_id=fonte.id,
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def _preco(sessao: Session, ticker: str, data: dt.date, fechamento: float) -> PrecoDiario:
    fonte = _fonte(
        sessao,
        f"B3 — COTAHIST, pregão {data.isoformat()}: preços não ajustados por proventos",
        data,
    )
    linha = PrecoDiario(ticker=ticker, data_pregao=data, fechamento=fechamento, fonte_id=fonte.id)
    sessao.add(linha)
    sessao.flush()
    return linha


def _provento(sessao: Session, ticker: str, data_com: dt.date, valor: float) -> Provento:
    fonte = _fonte(sessao, "B3 — proventos (cashDividends)", data_com)
    linha = Provento(
        ticker=ticker, tipo="RENDIMENTO", valor=valor, data_com=data_com, fonte_id=fonte.id
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def _banco_indicador(
    sessao: Session,
    indicador: str,
    valor: float,
    data: dt.date,
    unidade: str = "PCT",
    base: str = "prudencial",
    metodologia: str | None = None,
) -> BancoIndicador:
    fonte = _fonte(sessao, f"BCB — IF.data ({indicador})", data)
    linha = BancoIndicador(
        cd_cvm=CD_CVM_ITAU,
        indicador=indicador,
        valor=valor,
        unidade=unidade,
        base=base,
        dt_referencia=data,
        metodologia=metodologia,
        fonte_id=fonte.id,
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def _fii(sessao: Session, ticker: str = "HGLG11") -> FiiCadastro:
    fii = FiiCadastro(cnpj="11.728.688/0001-47", nome="FII Teste", ticker=ticker)
    sessao.add(fii)
    sessao.flush()
    return fii


def _fii_indicador(
    sessao: Session,
    fii: FiiCadastro,
    codigo: str,
    valor: float,
    data: dt.date,
    unidade: str = "PCT",
    metodologia: str | None = None,
) -> FiiIndicador:
    fonte = _fonte(sessao, f"CVM — Informe FII ({codigo})", data)
    linha = FiiIndicador(
        fii_id=fii.id,
        indicador=codigo,
        valor=valor,
        unidade=unidade,
        metodologia=metodologia,
        dt_referencia=data,
        fonte_id=fonte.id,
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def _vertice(
    sessao: Session,
    curva: str,
    vertice_du: int,
    taxa: float,
    data_ref: dt.date,
    implicita: float | None = None,
) -> CurvaSnapshot:
    fonte = _fonte(sessao, "ANBIMA — ETTJ (estrutura a termo), reprodução com atribuição", data_ref)
    linha = CurvaSnapshot(
        data_ref=data_ref,
        curva=curva,
        vertice_du=vertice_du,
        taxa=taxa,
        inflacao_implicita=implicita,
        fonte_id=fonte.id,
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def _titulo(
    sessao: Session,
    data_base: dt.date,
    taxa_compra: float | None = 7.65,
    vencimento: dt.date = dt.date(2035, 5, 15),
) -> TituloPublico:
    fonte = _fonte(sessao, "STN/Tesouro Transparente — Tesouro Direto", data_base)
    linha = TituloPublico(
        tipo="Tesouro IPCA+",
        data_vencimento=vencimento,
        data_base=data_base,
        taxa_compra=taxa_compra,
        fonte_id=fonte.id,
    )
    sessao.add(linha)
    sessao.flush()
    return linha


def _ctx_banco(empresa: Empresa | None = None, **kwargs) -> ContextoMetricas:
    return ContextoMetricas(
        ticker="ITUB4",
        classe="acao",
        plano_contas="banco",
        setor="Bancos",
        cd_cvm=CD_CVM_ITAU,
        empresa_id=empresa.id if empresa else None,
        **kwargs,
    )


_FONTE_N_ACOES = FonteMetrica(
    descricao="FCA/CVM — composição do capital (nº de ações)",
    url="https://dados.cvm.gov.br/fca",
    dt_referencia=dt.date(2025, 12, 31),
)


def _por_nome(metricas: list[MetricaSetor], nome: str) -> MetricaSetor:
    por_nome = {m.nome: m for m in metricas}
    assert nome in por_nome, f"métrica {nome!r} ausente: {sorted(por_nome)}"
    return por_nome[nome]


def _texto_varredura(metricas: list[MetricaSetor]) -> str:
    partes: list[str] = []
    for m in metricas:
        partes += [m.nome, m.formula, m.o_que_mede, m.implicacao, *m.rotulos]
        if m.lacuna:
            partes.append(m.lacuna)
        partes += [f.descricao for f in m.fontes]
    return " ".join(partes)


# ---------------------------------------------------------------------------
# Resolução do registro (classe, plano_contas, setor)
# ---------------------------------------------------------------------------
def test_classe_none_resolve_para_acao_generica(sessao: Session) -> None:
    metricas = calcular(sessao, ContextoMetricas(ticker="VALE3"), hoje=HOJE)
    nomes = [m.nome for m in metricas]
    assert nomes == ["P/L", "EV/EBITDA", "Dívida líquida/EBITDA", "Margem líquida", "P/VP"]


def test_plano_banco_resolve_metricas_de_banco(sessao: Session) -> None:
    metricas = calcular(sessao, _ctx_banco(), hoje=HOJE)
    nomes = [m.nome for m in metricas]
    assert nomes == [
        "Índice de Basileia",
        "ROE",
        "NIM (aproximada)",
        "Ativos problemáticos",
        "P/VP",
    ]


def test_setor_energia_resolve_chave_energia_transmissao(sessao: Session) -> None:
    ctx = ContextoMetricas(ticker="TAEE11", classe="acao", setor="Energia Elétrica")
    nomes = [m.nome for m in calcular(sessao, ctx, hoje=HOJE)]
    assert nomes == ["RAP (Receita Anual Permitida)", "Dividend yield 12m a mercado", "P/L"]


def test_classe_fii_resolve_metricas_de_fii(sessao: Session) -> None:
    ctx = ContextoMetricas(ticker="HGLG11", classe="fii")
    nomes = [m.nome for m in calcular(sessao, ctx, hoje=HOJE)]
    assert nomes == [
        "P/VP a mercado",
        "Dividend yield mensal (informe)",
        "Dividend yield 12m a mercado",
        "Vacância agregada",
        "Cap rate",
    ]


def test_classe_renda_fixa_resolve_metricas_de_rf(sessao: Session) -> None:
    ctx = ContextoMetricas(ticker="TD-IPCA-2035", classe="renda_fixa")
    nomes = [m.nome for m in calcular(sessao, ctx, hoje=HOJE)]
    assert nomes == ["Inflação implícita (vértice ANBIMA)", "Diferencial vs vértice PRE (proxy)"]


def test_classe_desconhecida_devolve_lista_vazia(sessao: Session) -> None:
    assert calcular(sessao, ContextoMetricas(ticker="X", classe="cripto"), hoje=HOJE) == []


# ---------------------------------------------------------------------------
# Banco — Basileia / ROE / NIM / ativos problemáticos / P/VP
# ---------------------------------------------------------------------------
def test_basileia_com_valor_rotulo_prudencial_e_fonte(sessao: Session) -> None:
    # Reconciliação de escala (F3, 2026-07-10): IF.data grava a Basileia já em
    # PONTOS PERCENTUAIS (ifdata.py: "o REST devolve fração; gravamos em %
    # (×100)" — ex. real "Basileia Itaú = 14,77%"). A fixture usa 16,8 (pontos)
    # e `_calc_basileia` normaliza para a convenção interna do módulo (fração
    # decimal, `_ROTULO_PCT_FRACAO`) — o envelope reconverte para pontos.
    _banco_indicador(sessao, "BASILEIA", 16.8, dt.date(2026, 3, 31))
    m = _por_nome(calcular(sessao, _ctx_banco(), hoje=HOJE), "Índice de Basileia")
    assert m.valor == Decimal("0.168")
    assert m.unidade == "pct"
    assert m.formula == "PR / RWA (patrimônio de referência ÷ ativos ponderados pelo risco)"
    assert m.lacuna is None
    assert any("prudencial" in r for r in m.rotulos)
    assert any("data-base 2026-03-31" in r for r in m.rotulos)
    assert m.fontes and "IF.data" in m.fontes[0].descricao


def test_basileia_ausente_abstem_com_lacuna(sessao: Session) -> None:
    m = _por_nome(calcular(sessao, _ctx_banco(), hoje=HOJE), "Índice de Basileia")
    assert m.valor is None
    assert m.lacuna is not None and "dado não encontrado" in m.lacuna
    assert m.fontes == ()


def test_roe_reusa_fundamento_derivado_do_ingestor(sessao: Session) -> None:
    empresa = _empresa(sessao)
    _fundamento(sessao, empresa, "ROE (derivado)", 0.2132, dt.date(2025, 12, 31), unidade="RAZAO")
    m = _por_nome(calcular(sessao, _ctx_banco(empresa), hoje=HOJE), "ROE")
    assert m.valor == Decimal("0.2132")
    assert m.unidade == "pct"
    assert any("patrimônio líquido de fim de período" in r for r in m.rotulos)  # metodologia
    assert any("reutilizado do ingestor DFP" in r for r in m.rotulos)


def test_nim_aproximada_com_rotulo_aprox_e_duas_fontes(sessao: Session) -> None:
    empresa = _empresa(sessao)
    _fundamento(
        sessao,
        empresa,
        "Resultado Bruto da Intermediação Financeira (3.03)",
        90_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    _banco_indicador(
        sessao, "CARTEIRA_CREDITO", 1_000_000_000_000.0, dt.date(2026, 3, 31), unidade="BRL"
    )
    m = _por_nome(calcular(sessao, _ctx_banco(empresa), hoje=HOJE), "NIM (aproximada)")
    assert m.valor == Decimal("0.09")
    assert "aprox." in m.rotulos
    assert any("datas distintas" in r for r in m.rotulos)
    assert len(m.fontes) == 2  # DFP (3.03) + IF.data (carteira)


def test_nim_sem_carteira_abstem(sessao: Session) -> None:
    empresa = _empresa(sessao)
    _fundamento(
        sessao,
        empresa,
        "Resultado Bruto da Intermediação Financeira (3.03)",
        90_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    m = _por_nome(calcular(sessao, _ctx_banco(empresa), hoje=HOJE), "NIM (aproximada)")
    assert m.valor is None
    assert m.lacuna is not None and "CARTEIRA_CREDITO" in m.lacuna


def test_ativos_problematicos_com_nota_res_4966(sessao: Session) -> None:
    _banco_indicador(sessao, "ATIVOS_PROBLEMATICOS", 0.052, dt.date(2026, 3, 31))
    m = _por_nome(calcular(sessao, _ctx_banco(), hoje=HOJE), "Ativos problemáticos")
    assert m.valor == Decimal("0.052")
    assert any("4.966" in r for r in m.rotulos)


def test_pvp_banco_preco_vezes_acoes_sobre_pl(sessao: Session) -> None:
    empresa = _empresa(sessao)
    _preco(sessao, "ITUB4", dt.date(2026, 7, 9), 34.0)
    _fundamento(
        sessao,
        empresa,
        "Patrimônio Líquido Consolidado (2.08)",
        200_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    ctx = _ctx_banco(empresa, num_acoes=Decimal(10_000_000_000), num_acoes_fonte=_FONTE_N_ACOES)
    m = _por_nome(calcular(sessao, ctx, hoje=HOJE), "P/VP")
    assert m.valor == Decimal("1.7")  # 34 × 10e9 / 200e9
    assert m.unidade == "x"
    assert len(m.fontes) == 3  # COTAHIST + DFP + fonte do nº de ações
    assert any("não ajustados" in r for r in m.rotulos)


def test_pvp_sem_num_acoes_abstem_com_lacuna(sessao: Session) -> None:
    empresa = _empresa(sessao)
    _preco(sessao, "ITUB4", dt.date(2026, 7, 9), 34.0)
    _fundamento(
        sessao,
        empresa,
        "Patrimônio Líquido Consolidado (2.08)",
        200_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    m = _por_nome(calcular(sessao, _ctx_banco(empresa), hoje=HOJE), "P/VP")
    assert m.valor is None
    assert m.lacuna is not None and "número de ações" in m.lacuna


def test_num_acoes_sem_fonte_e_descartado(sessao: Session) -> None:
    empresa = _empresa(sessao)
    _preco(sessao, "ITUB4", dt.date(2026, 7, 9), 34.0)
    _fundamento(
        sessao,
        empresa,
        "Patrimônio Líquido Consolidado (2.08)",
        200_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    ctx = _ctx_banco(empresa, num_acoes=Decimal(10_000_000_000))  # SEM fonte
    m = _por_nome(calcular(sessao, ctx, hoje=HOJE), "P/VP")
    assert m.valor is None
    assert m.lacuna is not None and "sem fonte" in m.lacuna


# ---------------------------------------------------------------------------
# Ação genérica — P/L, EV/EBITDA, dívida líquida/EBITDA, margem líquida
# ---------------------------------------------------------------------------
def _ctx_acao(empresa: Empresa, **kwargs) -> ContextoMetricas:
    return ContextoMetricas(
        ticker="VALE3",
        classe="acao",
        setor="Mineração",
        empresa_id=empresa.id,
        **kwargs,
    )


def test_pl_acao_golden(sessao: Session) -> None:
    """P/L = 60 × 4e9 / 80e9 = 3,0 (contas feitas à mão)."""
    empresa = _empresa(sessao, cd_cvm=4170, ticker="VALE3")
    _preco(sessao, "VALE3", dt.date(2026, 7, 9), 60.0)
    _fundamento(
        sessao, empresa, "Lucro/Prejuízo do Período (3.11)", 80_000_000_000.0, dt.date(2025, 12, 31)
    )
    ctx = _ctx_acao(empresa, num_acoes=Decimal(4_000_000_000), num_acoes_fonte=_FONTE_N_ACOES)
    m = _por_nome(calcular(sessao, ctx, hoje=HOJE), "P/L")
    assert m.valor == Decimal("3")
    assert any("não é LTM" in r for r in m.rotulos)


def test_pl_nao_casa_resultado_antes_dos_tributos(sessao: Session) -> None:
    """O matcher de lucro NUNCA pode casar 'Resultado antes dos Tributos sobre o Lucro'."""
    empresa = _empresa(sessao, cd_cvm=4170, ticker="VALE3")
    _preco(sessao, "VALE3", dt.date(2026, 7, 9), 60.0)
    _fundamento(
        sessao,
        empresa,
        "Resultado antes dos Tributos sobre o Lucro (3.09)",
        999_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    ctx = _ctx_acao(empresa, num_acoes=Decimal(4_000_000_000), num_acoes_fonte=_FONTE_N_ACOES)
    m = _por_nome(calcular(sessao, ctx, hoje=HOJE), "P/L")
    assert m.valor is None
    assert m.lacuna is not None and "dado não encontrado" in m.lacuna


def test_pl_lucro_nao_positivo_abstem(sessao: Session) -> None:
    empresa = _empresa(sessao, cd_cvm=4170, ticker="VALE3")
    _preco(sessao, "VALE3", dt.date(2026, 7, 9), 60.0)
    _fundamento(
        sessao, empresa, "Lucro/Prejuízo do Período (3.11)", -1_000_000.0, dt.date(2025, 12, 31)
    )
    ctx = _ctx_acao(empresa, num_acoes=Decimal(4_000_000_000), num_acoes_fonte=_FONTE_N_ACOES)
    m = _por_nome(calcular(sessao, ctx, hoje=HOJE), "P/L")
    assert m.valor is None
    assert m.lacuna is not None and "não positivo" in m.lacuna


def test_ev_ebitda_reusa_derivadas_do_ingestor(sessao: Session) -> None:
    """EV/EBITDA = (60×4e9 + 60e9) / 100e9 = 3,0 (contas feitas à mão)."""
    empresa = _empresa(sessao, cd_cvm=4170, ticker="VALE3")
    _preco(sessao, "VALE3", dt.date(2026, 7, 9), 60.0)
    _fundamento(sessao, empresa, "EBITDA (derivado)", 100_000_000_000.0, dt.date(2025, 12, 31))
    _fundamento(
        sessao, empresa, "Dívida líquida (derivado)", 60_000_000_000.0, dt.date(2025, 12, 31)
    )
    ctx = _ctx_acao(empresa, num_acoes=Decimal(4_000_000_000), num_acoes_fonte=_FONTE_N_ACOES)
    m = _por_nome(calcular(sessao, ctx, hoje=HOJE), "EV/EBITDA")
    assert m.valor == Decimal("3")
    assert any("reuso do ingestor" in r for r in m.rotulos)
    assert len(m.fontes) == 4


def test_divliq_ebitda_e_abstencao_sem_ebitda(sessao: Session) -> None:
    empresa = _empresa(sessao, cd_cvm=4170, ticker="VALE3")
    _fundamento(sessao, empresa, "EBITDA (derivado)", 100_000_000_000.0, dt.date(2025, 12, 31))
    _fundamento(
        sessao, empresa, "Dívida líquida (derivado)", 60_000_000_000.0, dt.date(2025, 12, 31)
    )
    metricas = calcular(sessao, _ctx_acao(empresa), hoje=HOJE)
    m = _por_nome(metricas, "Dívida líquida/EBITDA")
    assert m.valor == Decimal("0.6")

    empresa2 = _empresa(sessao, cd_cvm=9512, ticker="PETR4")
    ctx2 = ContextoMetricas(ticker="PETR4", classe="acao", empresa_id=empresa2.id)
    m2 = _por_nome(calcular(sessao, ctx2, hoje=HOJE), "Dívida líquida/EBITDA")
    assert m2.valor is None
    assert m2.lacuna is not None and "EBITDA" in m2.lacuna


def test_margem_liquida_exige_mesmo_exercicio(sessao: Session) -> None:
    empresa = _empresa(sessao, cd_cvm=4170, ticker="VALE3")
    _fundamento(
        sessao, empresa, "Lucro/Prejuízo do Período (3.11)", 20_000_000_000.0, dt.date(2025, 12, 31)
    )
    _fundamento(
        sessao,
        empresa,
        "Receita de Venda de Bens e/ou Serviços (3.01)",
        100_000_000_000.0,
        dt.date(2024, 12, 31),  # exercício DIFERENTE -> quimera vetada
    )
    m = _por_nome(calcular(sessao, _ctx_acao(empresa), hoje=HOJE), "Margem líquida")
    assert m.valor is None
    assert m.lacuna is not None and "exercícios distintos" in m.lacuna

    _fundamento(
        sessao,
        empresa,
        "Receita de Venda de Bens e/ou Serviços (3.01)",
        100_000_000_000.0,
        dt.date(2025, 12, 31),
    )
    m2 = _por_nome(calcular(sessao, _ctx_acao(empresa), hoje=HOJE), "Margem líquida")
    assert m2.valor == Decimal("0.2")


# ---------------------------------------------------------------------------
# Energia/transmissão — RAP + DY 12m a mercado
# ---------------------------------------------------------------------------
def _ctx_energia(**kwargs) -> ContextoMetricas:
    return ContextoMetricas(ticker="TAEE11", classe="acao", setor="Energia Elétrica", **kwargs)


def _rap(sessao: Session, metodologia: str | None, valor: float = 4_200_000_000.0) -> None:
    fonte = _fonte(
        sessao,
        "ANEEL/SIGET — RAP homologada (Resolução Homologatória, ciclo 2026-27)",
        dt.date(2026, 7, 1),
    )
    sessao.add(
        SetorIndicador(
            ticker="TAEE11",
            indicador="RAP_CICLO",
            valor=valor,
            unidade="BRL",
            competencia=dt.date(2026, 7, 1),
            metodologia=metodologia,
            fonte_id=fonte.id,
        )
    )
    sessao.flush()


def test_rap_com_metodologia_do_mapa_curado(sessao: Session) -> None:
    metodologia = (
        "RAP agregada das concessões do grupo Taesa no ciclo 2026-27; critério: mapa "
        "curado v1; fonte ANEEL SIGET"
    )
    _rap(sessao, metodologia)
    m = _por_nome(calcular(sessao, _ctx_energia(), hoje=HOJE), "RAP (Receita Anual Permitida)")
    assert m.valor == Decimal("4200000000")
    assert m.unidade == "BRL"
    assert metodologia in m.rotulos
    assert any("competência 2026-07-01" in r for r in m.rotulos)


def test_rap_sem_metodologia_abstem(sessao: Session) -> None:
    """A8: RAP sem escopo de agregação declarado nunca sai como 'a RAP' do emissor."""
    _rap(sessao, metodologia=None)
    m = _por_nome(calcular(sessao, _ctx_energia(), hoje=HOJE), "RAP (Receita Anual Permitida)")
    assert m.valor is None
    assert m.lacuna is not None and "metodologia" in m.lacuna


def test_rap_ausente_abstem_com_lacuna(sessao: Session) -> None:
    m = _por_nome(calcular(sessao, _ctx_energia(), hoje=HOJE), "RAP (Receita Anual Permitida)")
    assert m.valor is None
    assert m.lacuna is not None and "mapa curado" in m.lacuna


def test_dy_12m_mercado_janela_e_metodologia(sessao: Session) -> None:
    """DY = (1,00 + 1,20) / 40 = 5,5%; provento fora da janela de 12m NÃO entra."""
    _preco(sessao, "TAEE11", dt.date(2026, 7, 9), 40.0)
    _provento(sessao, "TAEE11", dt.date(2026, 3, 10), 1.00)
    _provento(sessao, "TAEE11", dt.date(2025, 9, 10), 1.20)
    _provento(sessao, "TAEE11", dt.date(2024, 9, 10), 9.99)  # velho: fora da janela
    m = _por_nome(calcular(sessao, _ctx_energia(), hoje=HOJE), "Dividend yield 12m a mercado")
    assert m.valor == Decimal("0.055")
    assert any(r.startswith("metodologia:") for r in m.rotulos)
    assert len(m.fontes) == 2  # proventos B3 + preço COTAHIST


def test_dy_12m_sem_proventos_abstem(sessao: Session) -> None:
    _preco(sessao, "TAEE11", dt.date(2026, 7, 9), 40.0)
    m = _por_nome(calcular(sessao, _ctx_energia(), hoje=HOJE), "Dividend yield 12m a mercado")
    assert m.valor is None
    assert m.lacuna is not None and "provento" in m.lacuna


# ---------------------------------------------------------------------------
# FII — P/VP a mercado, DY do informe, DY 12m, vacância, cap rate
# ---------------------------------------------------------------------------
def _ctx_fii(**kwargs) -> ContextoMetricas:
    return ContextoMetricas(ticker="HGLG11", classe="fii", **kwargs)


def test_pvp_fii_duas_fontes_e_nota_de_defasagem(sessao: Session) -> None:
    fii = _fii(sessao)
    _preco(sessao, "HGLG11", dt.date(2026, 7, 9), 149.92)
    _fii_indicador(sessao, fii, "VP_COTA", 166.576588, dt.date(2026, 6, 1), unidade="BRL_POR_COTA")
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "P/VP a mercado")
    assert m.valor is not None
    assert m.valor.quantize(Decimal("0.0001")) == Decimal("0.9000")
    assert len(m.fontes) == 2  # COTAHIST + informe CVM (DUAS fontes com datas)
    assert any("defasagem" in r and "2026-07-09" in r and "2026-06-01" in r for r in m.rotulos)


def test_pvp_fii_vp_cota_stale_abstem(sessao: Session) -> None:
    """Reuso do staleness de 90d de fii_dados.indicadores_recentes."""
    fii = _fii(sessao)
    _preco(sessao, "HGLG11", dt.date(2026, 7, 9), 149.92)
    _fii_indicador(sessao, fii, "VP_COTA", 166.57, dt.date(2025, 12, 1))  # > 90 dias
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "P/VP a mercado")
    assert m.valor is None
    assert m.lacuna is not None and "competência recente" in m.lacuna


def test_dy_informe_reusa_metodologia_e_nao_anualiza(sessao: Session) -> None:
    fii = _fii(sessao)
    _fii_indicador(
        sessao,
        fii,
        "DY_MES_INFORME",
        0.006635,
        dt.date(2026, 6, 1),
        metodologia="auto-declarado pelo administrador; informe mensal CVM",
    )
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "Dividend yield mensal (informe)")
    assert m.valor == Decimal("0.006635")
    assert any("auto-declarado pelo administrador" in r for r in m.rotulos)
    assert any("não anualizado" in r for r in m.rotulos)


def test_dy_12m_fii_a_mercado(sessao: Session) -> None:
    _preco(sessao, "HGLG11", dt.date(2026, 7, 9), 150.0)
    _provento(sessao, "HGLG11", dt.date(2026, 6, 30), 1.10)
    _provento(sessao, "HGLG11", dt.date(2026, 5, 30), 1.10)
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "Dividend yield 12m a mercado")
    assert m.valor is not None
    assert m.valor.quantize(Decimal("0.000001")) == Decimal("0.014667")


def test_vacancia_reusa_metodologia_do_conector(sessao: Session) -> None:
    fii = _fii(sessao)
    _fii_indicador(
        sessao,
        fii,
        "VACANCIA_AGREGADA",
        0.030051,
        dt.date(2026, 6, 30),
        metodologia=(
            "média ponderada pela área (m²) dos imóveis; vacância auto-declarada por "
            "imóvel no informe trimestral CVM"
        ),
    )
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "Vacância agregada")
    assert m.valor == Decimal("0.030051")
    assert any("média ponderada pela área" in r for r in m.rotulos)


def test_cap_rate_e_lacuna_consciente(sessao: Session) -> None:
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "Cap rate")
    assert m.valor is None
    assert m.lacuna is not None
    assert "cap rate de mercado não disponível publicamente" in m.lacuna


def test_fii_sem_cadastro_abstem_indicadores_do_informe(sessao: Session) -> None:
    m = _por_nome(calcular(sessao, _ctx_fii(), hoje=HOJE), "Dividend yield mensal (informe)")
    assert m.valor is None
    assert m.lacuna is not None and "sem cadastro" in m.lacuna


# ---------------------------------------------------------------------------
# Renda fixa — inflação implícita do vértice + diferencial vs PRE (proxy)
# ---------------------------------------------------------------------------
def _ctx_rf(**kwargs) -> ContextoMetricas:
    return ContextoMetricas(ticker="TD-IPCA-2035", classe="renda_fixa", **kwargs)


def test_inflacao_implicita_escolhe_vertice_mais_proximo_da_duration(sessao: Session) -> None:
    """Vencimento 2035-05-15 com hoje=2026-07-10 -> ~2231 du: vértice 2268 vence 1512."""
    _titulo(sessao, data_base=dt.date(2026, 7, 9))
    _vertice(sessao, "IPCA", 1512, 7.30, dt.date(2026, 7, 9), implicita=5.60)
    _vertice(sessao, "IPCA", 2268, 7.40, dt.date(2026, 7, 9), implicita=5.86)
    m = _por_nome(calcular(sessao, _ctx_rf(), hoje=HOJE), "Inflação implícita (vértice ANBIMA)")
    assert m.valor == Decimal("0.0586")  # % a.a. -> fração decimal
    assert any("vértice de 2268 du" in r for r in m.rotulos)
    assert any("ANBIMA — ETTJ, snapshot de 2026-07-09" in r for r in m.rotulos)
    assert any("aprox." in r for r in m.rotulos)


def test_inflacao_implicita_sem_snapshot_abstem(sessao: Session) -> None:
    _titulo(sessao, data_base=dt.date(2026, 7, 9))
    m = _por_nome(calcular(sessao, _ctx_rf(), hoje=HOJE), "Inflação implícita (vértice ANBIMA)")
    assert m.valor is None
    assert m.lacuna is not None and "curva IPCA" in m.lacuna


def test_spread_pre_com_rotulo_proxy_e_duas_fontes(sessao: Session) -> None:
    """Spread = (7,65 − 13,80)/100 = −0,0615 (taxa REAL vs vértice NOMINAL, rotulado)."""
    _titulo(sessao, data_base=dt.date(2026, 7, 9), taxa_compra=7.65)
    _vertice(sessao, "PRE", 2268, 13.80, dt.date(2026, 7, 9))
    m = _por_nome(calcular(sessao, _ctx_rf(), hoje=HOJE), "Diferencial vs vértice PRE (proxy)")
    assert m.valor == Decimal("-0.0615")
    assert any(r.startswith("proxy") for r in m.rotulos)
    assert any("REAL" in r and "NOMINAL" in r for r in m.rotulos)
    assert len(m.fontes) == 2  # STN + ANBIMA


def test_rf_titulo_stale_abstem(sessao: Session) -> None:
    """Data Base além do corte de 30d do tesouro.titulo_atual -> abstenção."""
    _titulo(sessao, data_base=dt.date(2026, 5, 1))
    _vertice(sessao, "IPCA", 2268, 7.40, dt.date(2026, 7, 9), implicita=5.86)
    m = _por_nome(calcular(sessao, _ctx_rf(), hoje=HOJE), "Inflação implícita (vértice ANBIMA)")
    assert m.valor is None
    assert m.lacuna is not None and "staleness" in m.lacuna


def test_rf_taxa_zerada_pela_convencao_stn_abstem_spread(sessao: Session) -> None:
    """Taxa 0 no CSV da STN = 'não ofertado' (M1) -> vira None -> spread abstém."""
    _titulo(sessao, data_base=dt.date(2026, 7, 9), taxa_compra=0.0)
    _vertice(sessao, "PRE", 2268, 13.80, dt.date(2026, 7, 9))
    m = _por_nome(calcular(sessao, _ctx_rf(), hoje=HOJE), "Diferencial vs vértice PRE (proxy)")
    assert m.valor is None
    assert m.lacuna is not None and "taxa de compra indisponível" in m.lacuna


# ---------------------------------------------------------------------------
# Degradação A13 — tabela ausente vira lacuna rotulada, nunca exceção/500
# ---------------------------------------------------------------------------
def test_tabela_ausente_degrada_para_lacuna_rotulada(sessao_sem_precos: Session) -> None:
    """Sem `precos_diarios` (migração 0006 pendente): métricas de preço abstêm
    com lacuna rotulada e as DEMAIS métricas seguem funcionando."""
    sessao = sessao_sem_precos
    fii = _fii(sessao)
    _fii_indicador(
        sessao,
        fii,
        "DY_MES_INFORME",
        0.006635,
        dt.date(2026, 6, 1),
        metodologia="auto-declarado pelo administrador; informe mensal CVM",
    )
    metricas = calcular(sessao, _ctx_fii(), hoje=HOJE)
    pvp = _por_nome(metricas, "P/VP a mercado")
    assert pvp.valor is None
    assert pvp.lacuna is not None
    assert "migração 0006" in pvp.lacuna and "dado não encontrado" in pvp.lacuna
    # A métrica que NÃO depende da tabela ausente segue com valor.
    dy = _por_nome(metricas, "Dividend yield mensal (informe)")
    assert dy.valor == Decimal("0.006635")


def test_erro_de_sql_que_nao_e_tabela_ausente_propaga() -> None:
    """Só tabela inexistente degrada; outro ProgrammingError é bug e propaga."""
    from sqlalchemy.exc import ProgrammingError

    exc = ProgrammingError("stmt", {}, Exception("syntax error at or near SELECT"))
    with pytest.raises(ProgrammingError):
        metricas_setor._degradar_tabela_ausente(exc)


# ---------------------------------------------------------------------------
# Gate (A5) — nenhum texto user-visible com linguagem de recomendação
# ---------------------------------------------------------------------------
def test_templates_de_todas_as_classes_passam_no_gate(sessao: Session) -> None:
    """Roda o registro inteiro (com e sem dados) e varre TODOS os textos
    user-visible com o detector de recomendação do gate — deve vir limpo."""
    empresa = _empresa(sessao)
    _banco_indicador(sessao, "BASILEIA", 0.168, dt.date(2026, 3, 31))
    _fundamento(sessao, empresa, "ROE (derivado)", 0.2132, dt.date(2025, 12, 31), unidade="RAZAO")
    _preco(sessao, "ITUB4", dt.date(2026, 7, 9), 34.0)
    todas: list[MetricaSetor] = []
    contextos = [
        _ctx_banco(empresa, num_acoes=Decimal(10**10), num_acoes_fonte=_FONTE_N_ACOES),
        ContextoMetricas(ticker="VALE3", classe="acao"),
        _ctx_energia(),
        _ctx_fii(),
        _ctx_rf(),
    ]
    for ctx in contextos:
        todas.extend(calcular(sessao, ctx, hoje=HOJE))
    assert todas
    assert _violacoes_recomendacao(_texto_varredura(todas)) == []


# ---------------------------------------------------------------------------
# Serialização para o envelope v3 (§5)
# ---------------------------------------------------------------------------
def test_metricas_para_envelope_shape_do_contrato(sessao: Session) -> None:
    # Fixture em pontos percentuais (convenção real do IF.data — ver
    # reconciliação de escala F3 acima); o envelope v3 exibe `pct` em PONTOS
    # PERCENTUAIS (decisão do maestro 2026-07-10), então o valor de saída bate
    # com o de entrada (16,8) — a normalização fração<->pontos acontece só na
    # travessia interna (`_calc_basileia` -> `_valor_envelope`).
    _banco_indicador(sessao, "BASILEIA", 16.8, dt.date(2026, 3, 31))
    metricas = calcular(sessao, _ctx_banco(), hoje=HOJE)
    envelope = metricas_para_envelope(metricas)
    assert len(envelope) == len(metricas)
    item = next(e for e in envelope if e["nome"] == "Índice de Basileia")
    assert set(item) == {
        "nome",
        "valor",
        "unidade",
        "formula",
        "o_que_mede",
        "implicacao",
        "fontes",
        "rotulos",
        "lacuna",
    }
    assert isinstance(item["valor"], float) and item["valor"] == 16.8
    assert item["lacuna"] is None
    fonte = item["fontes"][0]
    assert set(fonte) == {"descricao", "url", "dt_referencia"}
    assert fonte["dt_referencia"] == "2026-03-31"  # data ISO
    ausente = next(e for e in envelope if e["nome"] == "NIM (aproximada)")
    assert ausente["valor"] is None
    assert isinstance(ausente["lacuna"], str)
