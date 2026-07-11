"""Testes do gatilho `precisa_ingest` por classe — bug "tese legada
silenciosa" (2026-07-11, hotfix `fix/ingest-dado-novo`).

Evidência viva: VALE3 (empresa com fundamentos já persistidos, mas SEM
nenhuma linha em `precos_diarios`) gerou tese `ready` sem os blocos novos
(técnica/valuation/métricas) porque `acao.precisa_ingest` só olhava para
`fundamentos` — o mesmo padrão existia em `fii.precisa_ingest` (só olhava
`fii_indicadores`) e faltava em `renda_fixa.precisa_ingest` (só o título, sem
o snapshot ANBIMA). Estes testes provam, por classe, que:

1. sem NENHUM fato-âncora (fundamento/indicador/título) -> `precisa_ingest`
   segue True (comportamento LEGADO intocado);
2. com o fato-âncora presente mas SEM preço/snapshot fresco -> `precisa_
   ingest` PASSA a ser True (a correção);
3. com tudo fresco -> `precisa_ingest` é False (nenhum reingest desnecessário).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import Session

from app.models.models import (
    CurvaSnapshot,
    Empresa,
    FiiCadastro,
    FiiIndicador,
    Fonte,
    Fundamento,
    PrecoDiario,
    TituloPublico,
)
from app.services.ativos import acao, fii, renda_fixa

_HOJE = dt.date.today()

_TABELAS = (
    Fonte,
    Empresa,
    Fundamento,
    FiiCadastro,
    FiiIndicador,
    PrecoDiario,
    TituloPublico,
    CurvaSnapshot,
)


@pytest.fixture()
def sessao() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    meta = MetaData()
    for modelo in _TABELAS:
        copia = modelo.__table__.to_metadata(meta)
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


def _fonte(sessao: Session, descricao: str) -> Fonte:
    f = Fonte(url="https://dados.gov.br/x", descricao=descricao, dt_referencia=_HOJE)
    sessao.add(f)
    sessao.flush()
    return f


def _seed_preco(sessao: Session, ticker: str, *, data_pregao: dt.date) -> None:
    fonte = _fonte(sessao, f"B3 — COTAHIST ({ticker})")
    sessao.add(
        PrecoDiario(
            ticker=ticker,
            data_pregao=data_pregao,
            abertura=30.0,
            maxima=30.5,
            minima=29.5,
            fechamento=30.1,
            volume=1_000_000.0,
            negocios=100,
            codbdi=2,
            fonte_id=fonte.id,
        )
    )
    sessao.commit()


# ---------------------------------------------------------------------------
# AÇÃO
# ---------------------------------------------------------------------------
def _empresa_com_fundamento(sessao: Session, ticker: str = "VALE3") -> Empresa:
    f = _fonte(sessao, f"CVM DFP — {ticker}")
    empresa = Empresa(nome=f"Empresa {ticker}", ticker=ticker, cd_cvm=4170)
    sessao.add(empresa)
    sessao.flush()
    sessao.add(
        Fundamento(
            empresa_id=empresa.id,
            conta="Receita de Venda de Bens e/ou Serviços (3.01)",
            valor=100.0,
            dt_refer=dt.date(_HOJE.year - 1, 12, 31),
            fonte_id=f.id,
        )
    )
    sessao.commit()
    return empresa


def test_acao_precisa_ingest_true_sem_fundamento(sessao: Session) -> None:
    empresa = Empresa(nome="Empresa Nova", ticker="NOVA3", cd_cvm=1)
    sessao.add(empresa)
    sessao.commit()

    assert acao.precisa_ingest(sessao, empresa) is True


def test_acao_precisa_ingest_true_com_fundamento_sem_preco(sessao: Session) -> None:
    """Cenário VIVO do bug: fundamento já persistido, NENHUMA linha de preço."""
    empresa = _empresa_com_fundamento(sessao, "VALE3")

    assert acao.precisa_ingest(sessao, empresa) is True


def test_acao_precisa_ingest_true_com_fundamento_e_preco_stale(sessao: Session) -> None:
    empresa = _empresa_com_fundamento(sessao, "VALE3")
    _seed_preco(sessao, "VALE3", data_pregao=_HOJE - dt.timedelta(days=30))

    assert acao.precisa_ingest(sessao, empresa) is True


def test_acao_precisa_ingest_false_com_tudo_fresco(sessao: Session) -> None:
    empresa = _empresa_com_fundamento(sessao, "VALE3")
    _seed_preco(sessao, "VALE3", data_pregao=_HOJE)

    assert acao.precisa_ingest(sessao, empresa) is False


def test_acao_precisa_ingest_false_sem_ticker_nao_verifica_preco(sessao: Session) -> None:
    """Sem ticker (nunca deveria ocorrer p/ ação, mas defensivo): a checagem de
    preço é pulada — não há como consultar COTAHIST sem código de negociação."""
    f = _fonte(sessao, "CVM DFP — SEMTICK")
    empresa = Empresa(nome="Sem Ticker", ticker=None, cd_cvm=2)
    sessao.add(empresa)
    sessao.flush()
    sessao.add(
        Fundamento(
            empresa_id=empresa.id,
            conta="Receita de Venda de Bens e/ou Serviços (3.01)",
            valor=100.0,
            dt_refer=dt.date(_HOJE.year - 1, 12, 31),
            fonte_id=f.id,
        )
    )
    sessao.commit()

    assert acao.precisa_ingest(sessao, empresa) is False


# ---------------------------------------------------------------------------
# FII
# ---------------------------------------------------------------------------
def _fii_com_indicador(sessao: Session, ticker: str = "HGLG11") -> FiiCadastro:
    f_cad = _fonte(sessao, f"CVM — Informe Mensal FII (geral) — {ticker}")
    fundo = FiiCadastro(
        cnpj="11.728.688/0001-47", nome=f"FII {ticker}", ticker=ticker, fonte_id=f_cad.id
    )
    sessao.add(fundo)
    sessao.flush()
    f_ind = _fonte(sessao, f"CVM — Informe Mensal FII (complemento) — {ticker}")
    sessao.add(
        FiiIndicador(
            fii_id=fundo.id,
            indicador="VP_COTA",
            valor=100.0,
            unidade="BRL_POR_COTA",
            dt_referencia=_HOJE - dt.timedelta(days=5),
            fonte_id=f_ind.id,
        )
    )
    sessao.commit()
    return fundo


def test_fii_precisa_ingest_true_sem_indicador(sessao: Session) -> None:
    f_cad = _fonte(sessao, "CVM — Informe Mensal FII (geral)")
    fundo = FiiCadastro(
        cnpj="00.000.000/0001-00", nome="FII Vazio", ticker="VAZI11", fonte_id=f_cad.id
    )
    sessao.add(fundo)
    sessao.commit()

    assert fii.precisa_ingest(sessao, fundo) is True


def test_fii_precisa_ingest_true_com_indicador_sem_preco(sessao: Session) -> None:
    """Mesmo padrão do bug de ação: informe fresco, NENHUMA linha de preço."""
    fundo = _fii_com_indicador(sessao, "HGLG11")

    assert fii.precisa_ingest(sessao, fundo) is True


def test_fii_precisa_ingest_true_com_indicador_e_preco_stale(sessao: Session) -> None:
    fundo = _fii_com_indicador(sessao, "HGLG11")
    _seed_preco(sessao, "HGLG11", data_pregao=_HOJE - dt.timedelta(days=30))

    assert fii.precisa_ingest(sessao, fundo) is True


def test_fii_precisa_ingest_false_com_tudo_fresco(sessao: Session) -> None:
    fundo = _fii_com_indicador(sessao, "HGLG11")
    _seed_preco(sessao, "HGLG11", data_pregao=_HOJE)

    assert fii.precisa_ingest(sessao, fundo) is False


# ---------------------------------------------------------------------------
# RENDA FIXA
# ---------------------------------------------------------------------------
def _titulo_ref() -> renda_fixa.TituloRef:
    return renda_fixa.TituloRef(
        codigo="TD-IPCA-2035", familia="IPCA", ano=2035, tipo="Tesouro IPCA+"
    )


def _seed_titulo(sessao: Session, *, data_base: dt.date) -> None:
    f = _fonte(sessao, "STN/Tesouro Transparente — Tesouro IPCA+ 2035")
    sessao.add(
        TituloPublico(
            tipo="Tesouro IPCA+",
            data_vencimento=dt.date(2035, 5, 15),
            data_base=data_base,
            taxa_compra=7.55,
            taxa_venda=7.61,
            pu_compra=4010.0,
            pu_venda=4000.0,
            pu_base=4000.0,
            fonte_id=f.id,
        )
    )
    sessao.commit()


def _seed_curva(sessao: Session, *, data_ref: dt.date) -> None:
    f = _fonte(sessao, "ANBIMA — ETTJ snapshot")
    sessao.add(
        CurvaSnapshot(
            data_ref=data_ref,
            curva="IPCA",
            vertice_du=3000,
            taxa=6.5,
            inflacao_implicita=5.8,
            fonte_id=f.id,
        )
    )
    sessao.commit()


def test_rf_precisa_ingest_true_sem_titulo(sessao: Session) -> None:
    assert renda_fixa.precisa_ingest(sessao, _titulo_ref(), hoje=_HOJE) is True


def test_rf_precisa_ingest_true_com_titulo_fresco_sem_snapshot_anbima(sessao: Session) -> None:
    """Correção do escopo RF: título ATUAL presente, mas sem snapshot ANBIMA
    do dia — o on-demand é fallback do job diário do scheduler (nota do
    hotfix), mas ainda assim precisa disparar o ingest quando falta."""
    _seed_titulo(sessao, data_base=_HOJE - dt.timedelta(days=1))

    assert renda_fixa.precisa_ingest(sessao, _titulo_ref(), hoje=_HOJE) is True


def test_rf_precisa_ingest_true_com_titulo_stale(sessao: Session) -> None:
    _seed_titulo(sessao, data_base=_HOJE - dt.timedelta(days=60))
    _seed_curva(sessao, data_ref=_HOJE)

    assert renda_fixa.precisa_ingest(sessao, _titulo_ref(), hoje=_HOJE) is True


def test_rf_precisa_ingest_false_com_tudo_fresco(sessao: Session) -> None:
    _seed_titulo(sessao, data_base=_HOJE - dt.timedelta(days=1))
    _seed_curva(sessao, data_ref=_HOJE)

    assert renda_fixa.precisa_ingest(sessao, _titulo_ref(), hoje=_HOJE) is False
