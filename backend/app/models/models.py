"""Modelos ORM (SQLAlchemy 2.0).

Espelham o schema aplicado pelas migrações `0001`..`0005`. As colunas
`user_id` apontam para `auth.users` no Supabase (a FK é declarada no SQL da
migração, não aqui, para manter os modelos independentes do schema `auth`).

`fontes` é o coração da auditoria: todo fato persistido referencia uma fonte.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBEDDING_DIM = 1536


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    cd_cvm: Mapped[int | None] = mapped_column(Integer, unique=True)
    cnpj: Mapped[str | None] = mapped_column(String(20), unique=True)
    ticker: Mapped[str | None] = mapped_column(String(12), index=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    setor: Mapped[str | None] = mapped_column(Text)
    # Plano de contas detectado por FILING ('padrao'|'banco'|'seguradora');
    # NULL = ainda não detectado. SETOR_ATIV é telemetria, nunca decide (D2).
    plano_contas: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fundamentos: Mapped[list[Fundamento]] = relationship(back_populates="empresa")


class Fonte(Base):
    """Coração da auditoria: URL + descrição + data de referência."""

    __tablename__ = "fontes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    url: Mapped[str | None] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    dt_referencia: Mapped[dt.date | None] = mapped_column(Date)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Fundamento(Base):
    __tablename__ = "fundamentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conta: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float | None] = mapped_column(Numeric)
    # Unidade do valor ('BRL'|'RAZAO'|'PCT'); NULL = BRL (legado ação, byte-idêntico).
    # Corrige o achado B2: ROE de banco é RAZAO e nunca pode formatar como reais.
    unidade: Mapped[str | None] = mapped_column(Text)
    dt_refer: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped[Empresa] = relationship(back_populates="fundamentos")


class MacroSerie(Base):
    __tablename__ = "macro_series"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    codigo: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    data: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valor: Mapped[float | None] = mapped_column(Numeric)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EventoGeopolitico(Base):
    __tablename__ = "eventos_geopoliticos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    data: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    ativos_afetados: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CvmCadastro(Base):
    """Cache do CAD_CIA_ABERTA + VLMO (CVM) — resolve qualquer ticker B3.

    Fonte de verdade para COMNEG (ticker) -> CD_CVM/CNPJ/razão social/setor.
    `comneg` vem SOMENTE do VLMO/FCA (o CAD não publica ticker); o enriquecimento
    por setor/situação faz JOIN por `cd_cvm`, nunca por razão social (anti-alucinação).
    """

    __tablename__ = "cvm_cadastro"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    cd_cvm: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cnpj: Mapped[str | None] = mapped_column(Text)
    denom_social: Mapped[str] = mapped_column(Text, nullable=False)
    comneg: Mapped[str | None] = mapped_column(Text, index=True)
    especie: Mapped[str | None] = mapped_column(Text)
    sit_reg: Mapped[str | None] = mapped_column(Text)
    setor: Mapped[str | None] = mapped_column(Text)
    dt_referencia: Mapped[dt.date | None] = mapped_column(Date)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Par(Base):
    """Comparável global do setor — uma seleção INTERPRETATIVA (não par oficial).

    `criterio_selecao` + `fonte_id` registram por que a empresa é tratada como par,
    para que o motor rotule isso como interpretação e nunca como fato oficial.
    """

    __tablename__ = "pares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cik: Mapped[str | None] = mapped_column(Text)
    ticker_ext: Mapped[str | None] = mapped_column(Text)
    nome_ext: Mapped[str | None] = mapped_column(Text)
    sic: Mapped[str | None] = mapped_column(Text)
    taxonomia: Mapped[str | None] = mapped_column(Text)
    criterio_selecao: Mapped[str | None] = mapped_column(Text)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ParFundamento(Base):
    """Fato financeiro (XBRL/SEC EDGAR) de um par global, com taxonomia rotulada."""

    __tablename__ = "pares_fundamentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    par_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pares.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conceito: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float | None] = mapped_column(Numeric)
    moeda: Mapped[str | None] = mapped_column(Text)
    dt_refer: Mapped[dt.date | None] = mapped_column(Date, index=True)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Elo(Base):
    """Elo do grafo causal (D5) — fonte validada nas DUAS pontas.

    `metodo` distingue co-movimento estatístico (Pearson, NÃO causal) de interpretação
    causal com hedge; `n_amostras`/`periodo` tornam o coeficiente auditável. Um elo sem
    fonte numa ponta é rejeitado (validada=False) — zero alucinação.
    """

    __tablename__ = "elos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # Âncora do elo: empresa OU ativo_codigo (FII/RF, sem empresa) — o CHECK
    # ck_elos_ancora (migração 0005) garante que nenhum elo fica órfão.
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True
    )
    ativo_codigo: Mapped[str | None] = mapped_column(Text)
    dimensao: Mapped[str | None] = mapped_column(Text)
    origem_label: Mapped[str] = mapped_column(Text, nullable=False)
    origem_fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    destino_label: Mapped[str] = mapped_column(Text, nullable=False)
    destino_fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    ligacao_causal: Mapped[str | None] = mapped_column(Text)
    metodo: Mapped[str | None] = mapped_column(Text)
    forca_ligacao: Mapped[float | None] = mapped_column(Float)
    n_amostras: Mapped[int | None] = mapped_column(Integer)
    periodo: Mapped[str | None] = mapped_column(Text)
    hedge: Mapped[str | None] = mapped_column(Text)
    validada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    tese_versao_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tese_versoes.id", ondelete="SET NULL")
    )
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Tese(Base):
    """Dado do usuário — protegido por RLS (owner-only)."""

    __tablename__ = "teses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Ticker B3 (PETR4/HGLG11) ou código RF (TD-IPCA-2035) — varchar(32) na 0005.
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    # Classe do ativo ('acao'|'fii'|'renda_fixa'); NULL = acao (legado).
    classe_ativo: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="processing")
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    versoes: Mapped[list[TeseVersao]] = relationship(back_populates="tese")


class TeseVersao(Base):
    """Trilha de auditoria da tese (modelo + prompt_hash). RLS owner-only."""

    __tablename__ = "tese_versoes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tese_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    conteudo: Mapped[str | None] = mapped_column(Text)
    modelo: Mapped[str | None] = mapped_column(Text)
    prompt_hash: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tese: Mapped[Tese] = relationship(back_populates="versoes")


class Documento(Base):
    """Documento para RAG — RLS owner-only (multi-tenant)."""

    __tablename__ = "documentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # tenant_id: reservado para tenancy por organização (futuro); NÃO aplicado por RLS hoje.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    titulo: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunks: Mapped[list[Chunk]] = relationship(back_populates="documento")


class Chunk(Base):
    """Trecho vetorizado — RLS por usuário/tenant aplicada no SELECT vetorial."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    documento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # tenant_id: reservado para tenancy por organização (futuro); NÃO aplicado por RLS hoje.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documento: Mapped[Documento] = relationship(back_populates="chunks")


class JobRun(Base):
    """Ledger de jobs agendados (scheduler in-app) — decisão do conselho.

    A cadência é decidida por "está vencido?" contra `last_run_at` (relógio de
    parede no banco), NUNCA por timer em memória — deploy/restart não zera a
    cadência e job semanal dispara mesmo com deploys frequentes (catch-up).
    Tabela exclusiva do backend: RLS ON sem policy (deny-all), como alembic_version.
    """

    __tablename__ = "job_runs"

    job_name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_run_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_status: Mapped[str | None] = mapped_column(Text)
    detalhe: Mapped[str | None] = mapped_column(Text)
    atualizado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FiiCadastro(Base):
    """Cadastro de FII (informe mensal CVM, bloco "geral") — referência.

    `ticker` vem de HEURÍSTICA sobre o ISIN e `ticker_metodo` rotula o método
    (ex.: 'heuristica_isin'); colisão ou sufixo 12/13 -> ticker NULL e o fundo
    resolve só por CNPJ. A heurística nunca é apresentada como fato oficial.
    """

    __tablename__ = "fii_cadastro"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    cnpj: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str | None] = mapped_column(Text, unique=True)
    ticker_metodo: Mapped[str | None] = mapped_column(Text)
    isin: Mapped[str | None] = mapped_column(Text)
    segmento: Mapped[str | None] = mapped_column(Text)
    mandato: Mapped[str | None] = mapped_column(Text)
    tipo_gestao: Mapped[str | None] = mapped_column(Text)
    mercado_bolsa: Mapped[str | None] = mapped_column(Text)
    dt_referencia: Mapped[dt.date | None] = mapped_column(Date)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    indicadores: Mapped[list[FiiIndicador]] = relationship(back_populates="fii")


class FiiIndicador(Base):
    """Indicador TIPADO de FII — código canônico + valor + unidade + fonte.

    O armazenamento tipado (indicador/valor/unidade) elimina o parse de texto do
    Design A (que transformaria 525.069 cotistas em "R$ 525.069,00"). Códigos:
    'PL','VP_COTA','COTAS_EMITIDAS','COTISTAS','DY_MES_INFORME',
    'RENT_EFETIVA_MES','VACANCIA_AGREGADA'. Derivadas declaram `metodologia`;
    `fonte_id` é NOT NULL — sem fonte não é fato.
    """

    __tablename__ = "fii_indicadores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    fii_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fii_cadastro.id", ondelete="CASCADE"), nullable=False, index=True
    )
    indicador: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float] = mapped_column(Numeric, nullable=False)
    unidade: Mapped[str] = mapped_column(Text, nullable=False)  # BRL|BRL_POR_COTA|UN|PCT|RAZAO
    metodologia: Mapped[str | None] = mapped_column(Text)
    dt_referencia: Mapped[dt.date] = mapped_column(Date, nullable=False)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fii: Mapped[FiiCadastro] = relationship(back_populates="indicadores")


class TituloPublico(Base):
    """Preço/taxa diário de título do Tesouro Direto (STN) — referência.

    Tabela PRÓPRIA, fora de `macro_series` (não polui o contexto macro das teses
    de ação). A resolução TD-código -> título usa max(data_base) por (tipo,
    vencimento) — o CSV da STN não é cronológico. `fonte_id` NOT NULL.
    """

    __tablename__ = "titulos_publicos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)  # nome oficial (ex.: 'Tesouro IPCA+')
    data_vencimento: Mapped[dt.date] = mapped_column(Date, nullable=False)
    data_base: Mapped[dt.date] = mapped_column(Date, nullable=False)
    taxa_compra: Mapped[float | None] = mapped_column(Numeric)  # % a.a.
    taxa_venda: Mapped[float | None] = mapped_column(Numeric)
    pu_compra: Mapped[float | None] = mapped_column(Numeric)
    pu_venda: Mapped[float | None] = mapped_column(Numeric)
    pu_base: Mapped[float | None] = mapped_column(Numeric)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PrecoDiario(Base):
    """OHLCV diário por ticker (COTAHIST B3) — referência, NÃO ajustado por proventos.

    Técnica/β calculados sobre este preço são "aproximados" (rótulo obrigatório
    no consumidor). `codbdi` filtra o tipo de mercado do COTAHIST (02=lote-padrão,
    12=FII, 14=ETF). `fonte_id` NOT NULL — sem fonte não é fato.
    """

    __tablename__ = "precos_diarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    data_pregao: Mapped[dt.date] = mapped_column(Date, nullable=False)
    abertura: Mapped[float | None] = mapped_column(Numeric)
    maxima: Mapped[float | None] = mapped_column(Numeric)
    minima: Mapped[float | None] = mapped_column(Numeric)
    fechamento: Mapped[float | None] = mapped_column(Numeric)
    volume: Mapped[float | None] = mapped_column(Numeric)
    negocios: Mapped[int | None] = mapped_column(Integer)
    codbdi: Mapped[int | None] = mapped_column(Integer)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Provento(Base):
    """Dividendo/JCP/rendimento por ticker (B3 cashDividends) — base do DY a mercado.

    `fonte_id` NOT NULL — sem fonte não é fato.
    """

    __tablename__ = "proventos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)  # 'DIVIDENDO'|'JCP'|'RENDIMENTO'|...
    valor: Mapped[float] = mapped_column(Numeric, nullable=False)
    data_com: Mapped[dt.date] = mapped_column(Date, nullable=False)
    data_pagamento: Mapped[dt.date | None] = mapped_column(Date)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BancoIndicador(Base):
    """Indicador TIPADO do IF.data (BCB) — Basileia/PR/RWA/carteira/LL anualizado.

    `base` ('prudencial'|'societario') nunca é misturada dentro do mesmo
    indicador (Res. 4966 muda a base a partir de 2025). `fonte_id` NOT NULL.
    """

    __tablename__ = "banco_indicadores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    cd_cvm: Mapped[int] = mapped_column(Integer, nullable=False)
    indicador: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float] = mapped_column(Numeric, nullable=False)
    unidade: Mapped[str] = mapped_column(Text, nullable=False)  # 'PCT'|'BRL'|'RAZAO'
    base: Mapped[str] = mapped_column(Text, nullable=False)  # 'prudencial'|'societario'
    dt_referencia: Mapped[dt.date] = mapped_column(Date, nullable=False)
    metodologia: Mapped[str | None] = mapped_column(Text)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SetorIndicador(Base):
    """Registro genérico extensível por (ticker, indicador, competência).

    Hoje só RAP (ANEEL/energia); varejo/saneamento/seguros entram depois como
    DADO (novo valor de `indicador`), não como tabela nova. `empresa_id` é
    opcional (liga ao cadastro quando existir); `fonte_id` NOT NULL.
    """

    __tablename__ = "setor_indicadores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("empresas.id", ondelete="SET NULL")
    )
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    indicador: Mapped[str] = mapped_column(Text, nullable=False)
    valor: Mapped[float] = mapped_column(Numeric, nullable=False)
    unidade: Mapped[str] = mapped_column(Text, nullable=False)
    competencia: Mapped[dt.date] = mapped_column(Date, nullable=False)
    metodologia: Mapped[str | None] = mapped_column(Text)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CurvaSnapshot(Base):
    """ETTJ ANBIMA — SNAPSHOT do dia (nunca série sistemática, ToS ANBIMA).

    `fonte_id` NOT NULL; unicidade por (data_ref, curva, vertice_du).
    """

    __tablename__ = "curva_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    data_ref: Mapped[dt.date] = mapped_column(Date, nullable=False)
    curva: Mapped[str] = mapped_column(Text, nullable=False)  # 'PRE'|'IPCA'
    vertice_du: Mapped[int] = mapped_column(Integer, nullable=False)
    taxa: Mapped[float] = mapped_column(Numeric, nullable=False)
    inflacao_implicita: Mapped[float | None] = mapped_column(Numeric)
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ConsensoAnalista(Base):
    """Item de consenso de terceiros (web_search) — sempre ATRIBUÍDO.

    `cited_text` é o trecho citado, truncado a 150 chars (CHECK no banco):
    o motor nunca cita a página bruta como documento, só o item estruturado
    validado (defesa contra prompt-injection do conteúdo da página).
    `fonte_id` NOT NULL — sem fonte não é fato.
    """

    __tablename__ = "consenso_analistas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    casa: Mapped[str | None] = mapped_column(Text)
    metrica: Mapped[str] = mapped_column(Text, nullable=False)  # ex.: 'preco_alvo'|'rating'
    valor: Mapped[float | None] = mapped_column(Numeric)
    moeda: Mapped[str | None] = mapped_column(Text)
    veiculo: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    cited_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_age: Mapped[str | None] = mapped_column(Text)
    data_busca: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    fonte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fontes.id"), nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
