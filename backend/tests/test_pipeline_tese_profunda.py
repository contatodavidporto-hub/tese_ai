"""Testes de integração do pipeline "Tese Profunda" (F3 — ligação do motor).

Cobrem, offline (Anthropic FAKE, SQLite em memória, sem rede), os cenários do
DoD da fase: tese de ação com todos os blocos novos; banco (IF.data); energia
(RAP); FII (P/VP+DY a mercado); RF (curva/inflação implícita); tese legada
sem dado novo (byte-idêntico + envelope SEM os 5 blocos novos); consenso
desligado (lacuna declarada); falha isolada de um bloco novo (não derruba a
tese). Espelha o padrão de `test_motor_multiativo.py` (Anthropic FAKE via
`_FakeClient`/`_FakeMessages`, sessão SQLite com `before_flush` para
id/criado_em, gate real — não stub — para provar o envelope de ponta a ponta).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import Session

from app.models.models import (
    BancoIndicador,
    CurvaSnapshot,
    CvmCadastro,
    Elo,
    Empresa,
    FiiCadastro,
    FiiIndicador,
    Fonte,
    Fundamento,
    MacroSerie,
    Par,
    ParFundamento,
    PrecoDiario,
    Provento,
    SetorIndicador,
    Tese,
    TeseVersao,
    TituloPublico,
)
from app.services import metricas_setor as metricas_svc
from app.services import tese as tese_svc
from app.services.ativos import acao, fii, renda_fixa

_HOJE = dt.date.today()

_TABELAS = (
    Fonte,
    Empresa,
    Fundamento,
    MacroSerie,
    CvmCadastro,
    Par,
    ParFundamento,
    FiiCadastro,
    FiiIndicador,
    TituloPublico,
    Tese,
    TeseVersao,
    Elo,
    PrecoDiario,
    Provento,
    BancoIndicador,
    SetorIndicador,
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


# ---------------------------------------------------------------------------
# Seeds
# ---------------------------------------------------------------------------
def _fonte(sessao: Session, descricao: str, data: dt.date | None = None) -> Fonte:
    f = Fonte(url="https://dados.gov.br/x", descricao=descricao, dt_referencia=data or _HOJE)
    sessao.add(f)
    sessao.flush()
    return f


def _macro(sessao: Session, codigo: str, valor: float, data: dt.date | None = None) -> Fonte:
    f = _fonte(sessao, f"BCB — série {codigo}", data or _HOJE)
    sessao.add(MacroSerie(codigo=codigo, data=data or _HOJE, valor=valor, fonte_id=f.id))
    sessao.flush()
    return f


def _seed_precos(
    sessao: Session, ticker: str, *, dias: int = 60, preco_base: float = 30.0
) -> Fonte:
    """~`dias` pregões úteis terminando em `_HOJE` (fins de semana pulados)."""
    fonte = _fonte(sessao, f"B3 — COTAHIST ({ticker})", _HOJE)
    datas: list[dt.date] = []
    cursor = _HOJE
    while len(datas) < dias:
        if cursor.weekday() < 5:
            datas.append(cursor)
        cursor -= dt.timedelta(days=1)
    datas.reverse()
    for i, data in enumerate(datas):
        preco = preco_base + (i % 7) * 0.3
        sessao.add(
            PrecoDiario(
                ticker=ticker,
                data_pregao=data,
                abertura=preco,
                maxima=preco + 0.6,
                minima=preco - 0.6,
                fechamento=preco,
                volume=1_500_000.0,
                negocios=250,
                codbdi=2,
                fonte_id=fonte.id,
            )
        )
    sessao.flush()
    return fonte


def _seed_provento(sessao: Session, ticker: str, valor: float, dias_atras: int = 30) -> Fonte:
    fonte = _fonte(sessao, f"B3 — proventos ({ticker})", _HOJE)
    sessao.add(
        Provento(
            ticker=ticker,
            tipo="DIVIDENDO",
            valor=valor,
            data_com=_HOJE - dt.timedelta(days=dias_atras),
            data_pagamento=_HOJE - dt.timedelta(days=dias_atras - 5),
            fonte_id=fonte.id,
        )
    )
    sessao.flush()
    return fonte


_CD_CVM_SEQ = iter(range(90001, 99999))


def _empresa(sessao: Session, ticker: str = "ACAO4", **kw) -> Empresa:
    """Empresa PRONTA p/ `dados_svc.ensure_empresa` resolver sem rede: seed do
    `cvm_cadastro` (cache, 1ª prioridade de `resolve_ticker`) com o MESMO
    cd_cvm da `Empresa` já persistida — `ensure_empresa` encontra a linha
    existente por cd_cvm, nunca cria outra."""
    cd_cvm = kw.pop("cd_cvm", None) or next(_CD_CVM_SEQ)
    f = _fonte(sessao, f"CVM DFP — {ticker}")
    f_cad = _fonte(sessao, f"CVM cadastro — {ticker}")
    sessao.add(
        CvmCadastro(
            cd_cvm=cd_cvm,
            denom_social=f"Empresa {ticker}",
            comneg=ticker,
            sit_reg="ATIVO",
            setor=kw.get("setor"),
            fonte_id=f_cad.id,
        )
    )
    empresa = Empresa(nome=f"Empresa {ticker}", ticker=ticker, cnpj=None, cd_cvm=cd_cvm, **kw)
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


# ---------------------------------------------------------------------------
# Anthropic FAKE (padrão test_motor_multiativo._preparar_motor_fake)
# ---------------------------------------------------------------------------
class _FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessages:
    def __init__(self, message):
        self._message = message
        self.captured: dict | None = None

    def stream(self, **kwargs):
        self.captured = kwargs
        return _FakeStream(self._message)


class _FakeClient:
    def __init__(self, message):
        self.messages = _FakeMessages(message)


def _mensagem_fake(markdown: str):
    citation = SimpleNamespace(document_index=0, cited_text="fato citado", document_title="doc 0")
    block = SimpleNamespace(type="text", text=markdown, citations=[citation])
    usage = SimpleNamespace(
        input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )
    return SimpleNamespace(content=[block], usage=usage)


def _preparar_motor_fake(
    monkeypatch: pytest.MonkeyPatch, markdown: str, *, ingest_deve_rodar: bool = False
) -> _FakeClient:
    client = _FakeClient(_mensagem_fake(markdown))
    monkeypatch.setattr(
        tese_svc,
        "get_settings",
        lambda: SimpleNamespace(
            anthropic_api_key="chave-de-teste-offline",
            tese_teto_custo_usd_dia=0,
            tese_model_synthesis="claude-opus-4-8",
            tese_model_extraction="claude-haiku-4-5-20251001",
            tese_max_tokens_sintese=16000,
            consenso_enabled=False,
        ),
    )
    monkeypatch.setattr(tese_svc.anthropic, "Anthropic", lambda api_key=None: client)
    monkeypatch.setattr(tese_svc, "_extract_metadata_haiku", lambda *a, **k: None)
    # Gate REAL não é o alvo destes testes (é escopo da F4) — o fake de
    # citação abaixo cita só 1 documento (`document_index=0`), então a
    # cobertura de citações do gate real cairia conforme o nº de documentos
    # novos crescesse; o mesmo stub do `test_motor_multiativo.py` evita
    # acoplar estes testes de ENVELOPE ao heurístico interno do gate.
    monkeypatch.setattr(
        tese_svc,
        "avaliar_tese",
        lambda envelope, **kwargs: {
            "aprovado": True,
            "bloqueante": False,
            "motivos": [],
            "cobertura_fontes": 1.0,
        },
    )
    # ingest() nunca deve ser chamado nestes testes quando `precisa_ingest`
    # já é False (fundamento/indicador E preço frescos) — travamos
    # explicitamente para que uma regressão que dispare rede real falhe alto
    # e claro. Cenários que seedam fundamento/indicador SEM preço (correção
    # do bug "tese legada silenciosa", 2026-07-11: `precisa_ingest` passa a
    # olhar preço também) esperam ingest() rodar — passam
    # `ingest_deve_rodar=True` e recebem um NO-OP (sem rede, sem gravar
    # nada) em vez do travamento, preservando o cenário "sem dado novo".
    for perfil in (acao, fii, renda_fixa):
        if ingest_deve_rodar:
            monkeypatch.setattr(perfil, "ingest", lambda *_a, **_k: None)
        else:
            monkeypatch.setattr(
                perfil,
                "ingest",
                lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("ingest não deveria rodar")),
            )
    return client


def _criar_tese(sessao: Session, ticker: str, classe: str | None) -> Tese:
    tese = Tese(user_id=uuid.uuid4(), ticker=ticker, classe_ativo=classe, status="processing")
    sessao.add(tese)
    sessao.commit()
    return tese


def _envelope(sessao: Session, tese: Tese) -> dict:
    versao = sessao.execute(
        select(TeseVersao)
        .where(TeseVersao.tese_id == tese.id)
        .order_by(TeseVersao.criado_em.desc())
        .limit(1)
    ).scalar_one()
    return json.loads(versao.conteudo)


_MD_ACAO = (
    "# Tese — ACAO4 (Empresa ACAO4)\n"
    "> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.\n"
    "## 1. Fundamentos\nReceita citada.\n"
    "## 2. Contexto macro (Brasil e global)\nSelic citada.\n"
    "## 3. Pares globais do setor\nSem pares.\n"
    "## 4. Camada geopolítica e correlações (interpretação)\ncenário: juros.\n"
    "## 5. Síntese\n...\n## 6. Riscos e contra-tese (bull × bear)\n...\n"
    "## 7. Fontes\n...\n## 8. Lacunas\n- EBITDA: dado não encontrado\n"
)


# ---------------------------------------------------------------------------
# 1) Ação genérica — TODOS os blocos novos (técnica, valuation, métricas,
#    consenso[desligado], gráficos) + apêndices no system prompt
# ---------------------------------------------------------------------------
def test_tese_acao_generica_com_todos_os_blocos_novos(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _empresa(sessao, "ACAO4")
    _seed_precos(sessao, "ACAO4", dias=60, preco_base=30.0)
    _seed_precos(sessao, "BOVA11", dias=60, preco_base=120.0)
    _seed_provento(sessao, "ACAO4", 1.5)
    _macro(sessao, "SELIC_META_ANUAL", 14.25)
    _macro(sessao, "CDI_ANUAL", 13.65)
    client = _preparar_motor_fake(monkeypatch, _MD_ACAO)
    tese = _criar_tese(sessao, "ACAO4", None)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)

    # Gráficos + técnica.
    assert env["graficos"], "gráficos ausentes"
    assert {g["id"] for g in env["graficos"]} <= {
        "preco_bollinger",
        "macd",
        "rsi",
        "estocastico",
        "williams",
        "volume_ad",
    }
    assert env["tecnica"]["indicadores"]
    assert "ajustados por proventos" in env["tecnica"]["nota"].lower()

    # Valuation: Gordon deve computar (Selic + dividendo/ação presentes).
    assert env["valuation"] is not None
    gordon = next(m for m in env["valuation"]["modelos"] if m["nome"] == "Gordon (dividendos)")
    assert gordon["omitido"] is None
    assert len(gordon["cenarios"]) == 3
    assert any(c["valor"] is not None for c in gordon["cenarios"])
    assert gordon["faixa"] is not None and gordon["faixa"]["unidade"] == "BRL"
    assert "NÃO é preço-alvo" in env["valuation"]["aviso"]

    # Métricas do setor (mesmo que só lacunas — num_acoes nunca é preenchido).
    assert env["metricas_setor"]

    # Consenso desligado -> bloco presente com lacuna declarada.
    assert env["consenso"] is not None
    assert env["consenso"]["itens"] == []
    assert any("desabilitado" in lacuna.lower() for lacuna in env["consenso"]["lacunas"])

    # texto_livre_novo pronto para o F4 (item 6 do escopo).
    assert env["texto_livre_novo"]

    # System prompt ganhou os apêndices (técnica + valuation; consenso sem
    # item validado não ganha apêndice).
    system_enviado = client.messages.captured["system"][0]["text"]
    assert system_enviado.startswith(tese_svc._SYSTEM)
    assert "## Análise técnica (descritiva)" in system_enviado
    assert "## Valuation por cenários (não é preço-alvo)" in system_enviado
    assert "## Consenso de analistas" not in system_enviado

    # Regra H2 geopol/lacun intacta (o gate depende disso) — não deslocada
    # pelos apêndices (que são texto CORRIDO, não novas seções ## na saída).
    assert "## 4. Camada geopolítica e correlações (interpretação)" in tese_svc._SYSTEM


# ---------------------------------------------------------------------------
# 2) Banco — IF.data (Basileia) no bloco de métricas, em PONTOS PERCENTUAIS
# ---------------------------------------------------------------------------
def test_tese_banco_ifdata_no_envelope(sessao: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _empresa(sessao, "BANC4", cd_cvm=555, plano_contas="banco")
    f = _fonte(sessao, "BCB — IF.data (BASILEIA)")
    sessao.add(
        BancoIndicador(
            cd_cvm=555,
            indicador="BASILEIA",
            valor=16.8,  # pontos percentuais (convenção real do IF.data)
            unidade="PCT",
            base="prudencial",
            dt_referencia=_HOJE,
            metodologia="Índice de Basileia (PR/RWA)",
            fonte_id=f.id,
        )
    )
    sessao.commit()
    # Sem COTAHIST seedado: `precisa_ingest` dispara ingest() (correção do
    # bug "tese legada silenciosa") — NO-OP aqui de propósito, o cenário sob
    # teste é IF.data-only (sem técnica/valuation).
    _preparar_motor_fake(monkeypatch, _MD_ACAO, ingest_deve_rodar=True)
    tese = _criar_tese(sessao, "BANC4", None)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    basileia = next(m for m in env["metricas_setor"] if m["nome"] == "Índice de Basileia")
    assert basileia["valor"] == 16.8
    assert basileia["unidade"] == "pct"
    assert basileia["lacuna"] is None
    # Sem COTAHIST: técnica/valuation ficam None (só métricas dispararam).
    assert env.get("tecnica") is None


# ---------------------------------------------------------------------------
# 3) Energia/transmissão — RAP no bloco de métricas + elo RAP→dividendos
# ---------------------------------------------------------------------------
def test_tese_energia_rap_no_envelope(sessao: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _empresa(sessao, "TAEE11", setor="Energia Elétrica")
    f_rap = _fonte(sessao, "ANEEL SIGET — RAP")
    sessao.add(
        SetorIndicador(
            ticker="TAEE11",
            indicador="RAP_CICLO",
            valor=1_500_000_000.0,
            unidade="BRL",
            competencia=_HOJE,
            metodologia="RAP agregada das concessões do grupo Taesa — mapa curado v1",
            fonte_id=f_rap.id,
        )
    )
    _seed_provento(sessao, "TAEE11", 0.8)
    sessao.commit()
    # Sem COTAHIST seedado: `precisa_ingest` dispara ingest() (correção do
    # bug "tese legada silenciosa") — NO-OP aqui de propósito, o cenário sob
    # teste é RAP-only (DY a mercado precisa de preço, fora de escopo aqui;
    # ver `test_tese_energia_dy_mercado_gate_real_no_documento_correto` p/
    # o cenário completo com o gate REAL).
    _preparar_motor_fake(monkeypatch, _MD_ACAO, ingest_deve_rodar=True)
    tese = _criar_tese(sessao, "TAEE11", None)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    rap = next(m for m in env["metricas_setor"] if m["nome"] == "RAP (Receita Anual Permitida)")
    assert rap["valor"] == 1_500_000_000.0
    assert rap["unidade"] == "BRL"
    # Elo RAP -> dividendos persistido (fonte nas duas pontas).
    elos = sessao.execute(select(Elo)).scalars().all()
    assert any(e.dimensao == "rap→receita→dividendos" for e in elos)


# ---------------------------------------------------------------------------
# 3b) Regressão VIVA do bug TAEE11 (2026-07-11): RAP (ANEEL) + DY a mercado
# (COTAHIST/B3) no MESMO bloco de métricas — antes, `_documento_metricas`
# juntava as duas num único documento ancorado na fonte do PRIMEIRO item
# (RAP/ANEEL, por causa da ordem do registro em `metricas_setor._REGISTRO`),
# então uma citação do DY a mercado saía com origem ANEEL e o gate REAL
# bloqueava a frase "DY/dividend yield a mercado com número" por falta de
# citação COTAHIST/B3 — tese LEGÍTIMA reprovada. Roda `avaliar_tese` DE
# VERDADE (sem stub) com um envelope montado PELO PRÓPRIO PIPELINE: o fake
# do Anthropic acha, nos documentos reais que `gerar_tese` monta, aquele que
# contém a métrica de DY a mercado e cita ELE — não um índice fixo — para
# prevar que a citação aponta pra Fonte certa fim a fim.
# ---------------------------------------------------------------------------
class _FakeStreamDinamico:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessagesDinamico:
    """Fake que NÃO fixa `document_index=0`: acha, nos documentos REAIS que
    o pipeline montou (`kwargs["messages"][0]["content"]`), aquele cujo
    texto contém `marcador_doc` e cita ELE — a citação aponta pra Fonte que
    o código de produção escolheu, não pra um índice hardcoded."""

    def __init__(self, markdown: str, marcador_doc: str, numero_citado: str) -> None:
        self._markdown = markdown
        self._marcador_doc = marcador_doc
        self._numero_citado = numero_citado
        self.captured: dict | None = None

    def stream(self, **kwargs):
        self.captured = kwargs
        conteudo = kwargs["messages"][0]["content"]
        # Cita TODOS os documentos (cobertura realista — um LLM real cita a
        # maioria das fontes que recebe), mas o texto citado do documento
        # com `marcador_doc` (o de métricas B3/COTAHIST, pós-correção) traz
        # o MESMO número da frase de DY a mercado — é essa citação que o
        # gate precisa achar para relaxar o termo vetado.
        citacoes = []
        for i, bloco in enumerate(conteudo):
            if bloco.get("type") != "document":
                continue
            texto_citado = (
                self._numero_citado
                if self._marcador_doc in bloco["source"]["data"]
                else "fato citado"
            )
            citacoes.append(
                SimpleNamespace(
                    document_index=i, cited_text=texto_citado, document_title=bloco.get("title")
                )
            )
        assert any(
            self._marcador_doc in bloco["source"]["data"]
            for bloco in conteudo
            if bloco.get("type") == "document"
        ), f"documento com marcador {self._marcador_doc!r} não foi montado pelo pipeline"
        block = SimpleNamespace(type="text", text=self._markdown, citations=citacoes)
        usage = SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        message = SimpleNamespace(content=[block], usage=usage)
        return _FakeStreamDinamico(message)


class _FakeClientDinamico:
    def __init__(self, markdown: str, marcador_doc: str, numero_citado: str) -> None:
        self.messages = _FakeMessagesDinamico(markdown, marcador_doc, numero_citado)


def test_tese_energia_dy_mercado_gate_real_no_documento_correto(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _empresa(sessao, "TAEE11", setor="Energia Elétrica")
    f_rap = _fonte(sessao, "ANEEL SIGET — RAP")
    sessao.add(
        SetorIndicador(
            ticker="TAEE11",
            indicador="RAP_CICLO",
            valor=1_500_000_000.0,
            unidade="BRL",
            competencia=_HOJE,
            metodologia="RAP agregada das concessões do grupo Taesa — mapa curado v1",
            fonte_id=f_rap.id,
        )
    )
    # RAP entra ANTES de DY a mercado em `_REGISTRO[("acao", None,
    # "energia_transmissao")]` — é essa ordem que expôs o bug original.
    _seed_precos(sessao, "TAEE11", dias=60, preco_base=35.0)
    _seed_precos(sessao, "BOVA11", dias=60, preco_base=120.0)
    _seed_provento(sessao, "TAEE11", 0.8)
    sessao.commit()

    frase_dy = (
        "O dividend yield 12m a mercado de TAEE11 soma 9,00%, apurado sobre o "
        "fechamento mais recente do pregão."
    )
    markdown = (
        "# Tese — TAEE11 (Empresa TAEE11)\n"
        "> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.\n"
        "## 1. Fundamentos\nReceita citada.\n"
        "## 2. Contexto macro (Brasil e global)\nSelic citada.\n"
        "## 3. Pares globais do setor\nSem pares.\n"
        "## 4. Camada geopolítica e correlações (interpretação)\ncenário: juros.\n"
        f"## 5. Síntese\n{frase_dy}\n"
        "## 6. Riscos e contra-tese (bull × bear)\n...\n"
        "## 7. Fontes\n...\n## 8. Lacunas\n- EBITDA: dado não encontrado\n"
    )
    client = _FakeClientDinamico(
        markdown,
        "Dividend yield 12m a mercado",  # marcador único do doc de métricas B3/COTAHIST
        "dividend yield 12m a mercado de 9,00%",  # cited_text com o MESMO número da frase
    )
    monkeypatch.setattr(
        tese_svc,
        "get_settings",
        lambda: SimpleNamespace(
            anthropic_api_key="chave-de-teste-offline",
            tese_teto_custo_usd_dia=0,
            tese_model_synthesis="claude-opus-4-8",
            tese_model_extraction="claude-haiku-4-5-20251001",
            tese_max_tokens_sintese=16000,
            consenso_enabled=False,
        ),
    )
    monkeypatch.setattr(tese_svc.anthropic, "Anthropic", lambda api_key=None: client)
    monkeypatch.setattr(tese_svc, "_extract_metadata_haiku", lambda *a, **k: None)
    for perfil in (acao, fii, renda_fixa):
        monkeypatch.setattr(
            perfil,
            "ingest",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("ingest não deveria rodar")),
        )
    # `avaliar_tese` NÃO é stubado aqui — é o gate REAL, o alvo do teste.
    tese = _criar_tese(sessao, "TAEE11", None)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    laudo = env["avaliacao"]
    assert laudo["bloqueante"] is False, laudo["motivos"]
    assert not laudo["termos_vetados"], laudo["termos_vetados"]
    assert laudo["aprovado"] is True, laudo
    # Confirma que RAP e DY seguem AMBAS no bloco de métricas (a correção não
    # perdeu nenhuma métrica — só separou os documentos por origem).
    nomes = {m["nome"] for m in env["metricas_setor"]}
    assert "RAP (Receita Anual Permitida)" in nomes
    assert "Dividend yield 12m a mercado" in nomes


# ---------------------------------------------------------------------------
# 4) FII — P/VP e DY a mercado DESTRAVADOS no bloco de métricas
# ---------------------------------------------------------------------------
def test_tese_fii_pvp_e_dy_mercado(sessao: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    f_cad = _fonte(sessao, "CVM — Informe Mensal FII (geral)")
    fundo = FiiCadastro(
        cnpj="11.728.688/0001-47", nome="FII TESTE", ticker="FTST11", fonte_id=f_cad.id
    )
    sessao.add(fundo)
    sessao.flush()
    f_ind = _fonte(sessao, "CVM — Informe Mensal FII (complemento)")
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
    _seed_precos(sessao, "FTST11", dias=30, preco_base=95.0)
    _seed_provento(sessao, "FTST11", 0.7)
    client = _preparar_motor_fake(monkeypatch, "_MD_FII placeholder")
    md_fii = (
        "# Tese — FTST11 (FII TESTE)\n"
        "> Não é recomendação de investimento.\n"
        "## 1. Fundamentos do fundo\n...\n## 2. Contexto macro e juros\n...\n"
        "## 3. Camada geopolítica e correlações (interpretação)\ncenário: juros.\n"
        "## 4. Síntese\n...\n## 5. Riscos e contra-tese (bull × bear)\n...\n"
        "## 6. Fontes\n...\n## 7. Lacunas\n"
        "- P/VP a preço de mercado: dado não encontrado (cotação B3 é licenciada)\n"
        "- Dividend yield a preço de mercado: dado não encontrado (cotação B3 é licenciada)\n"
    )
    client.messages._message = _mensagem_fake(md_fii)
    tese = _criar_tese(sessao, "FTST11", "fii")

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    nomes = {m["nome"]: m for m in env["metricas_setor"]}
    assert nomes["P/VP a mercado"]["valor"] is not None
    assert nomes["P/VP a mercado"]["lacuna"] is None
    assert nomes["Dividend yield 12m a mercado"]["valor"] is not None
    # Elo preço->P/VP persistido.
    elos = sessao.execute(select(Elo)).scalars().all()
    assert any(e.dimensao == "preço→pvp_fii" for e in elos)
    # Valuation FII: leitura de mercado (sem valor intrínseco).
    modelo_fii = next(
        m for m in env["valuation"]["modelos"] if m["nome"] == "Leitura de mercado (FII)"
    )
    assert modelo_fii["omitido"] is None
    assert modelo_fii["cenarios"] == []  # sem grade Ke×g


# ---------------------------------------------------------------------------
# 4b) Regressão VIVA do Hotfix 2 (2026-07-11, bug TAEE11 na 2ª tentativa):
# `_modelo_fii` (valuation.py) escreve "P/VP a mercado: 0,95"/"DY a mercado
# 12m: 0,73%" — COM NÚMERO — dentro de `descricao` do modelo (observações
# mescladas por `tese._descricao_modelo_envelope`), e `tese._texto_livre_novo`
# inclui essa `descricao` verbatim. É a prova, no pipeline REAL (não em
# fixture sintética de `test_avaliacao_gate_v3.py`), de que o bug do item 14
# da docstring de `avaliacao.py` acontece de fato: texto determinístico do
# backend, com número, chega em `texto_livre_novo` sem NUNCA ter sido citado
# pelo LLM (`texto_livre_novo` é montado DEPOIS da síntese).
#
# `test_tese_fii_pvp_e_dy_mercado` (acima) NÃO cobre isto — estuba
# `avaliar_tese` de propósito (`_preparar_motor_fake`, para não acoplar o
# teste de ENVELOPE ao heurístico do gate). `test_tese_energia_dy_mercado_
# gate_real_no_documento_correto` roda o gate REAL, mas para TAEE11 (classe
# 'acao', modelo de Gordon) `texto_livre_novo` NUNCA carrega um número de DY/
# P-VP a mercado — essa métrica só aparece ali via `_modelo_fii`, exclusivo
# da classe FII (verificado ao vivo: instrumentei as duas suítes e despejei
# `envelope["texto_livre_novo"]` — a variante ação/energia só tem leituras
# técnicas + Gordon/múltiplos, sem números vetados; a variante FII tem os
# dois números exatos usados abaixo). Ou seja: NENHUM teste do repositório
# rodava "gate REAL + texto_livre_novo REAL com número vetado" antes deste —
# o buraco de cobertura não estava no teste nomeado no hotfix, estava aqui.
# ---------------------------------------------------------------------------
def test_tese_fii_pvp_dy_mercado_texto_livre_novo_gate_real_nao_bloqueia(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    f_cad = _fonte(sessao, "CVM — Informe Mensal FII (geral)")
    fundo = FiiCadastro(
        cnpj="33.728.688/0001-47", nome="FII TESTE HOTFIX2", ticker="FTST13", fonte_id=f_cad.id
    )
    sessao.add(fundo)
    sessao.flush()
    f_ind = _fonte(sessao, "CVM — Informe Mensal FII (complemento)")
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
    _seed_precos(sessao, "FTST13", dias=30, preco_base=95.0)
    _seed_provento(sessao, "FTST13", 0.7)

    # Headings SEM numeração ("## Síntese", não "## 4. Síntese") — evita o
    # efeito colateral não relacionado de `_numeros_significativos` tratar o
    # "N." do próprio número da seção como número "de claim" (ponto após
    # dígito conta como separador), que derrubaria a fidelidade numérica
    # (D6d, nota — não bloqueia, mas reprovaria `aprovado` por outro motivo
    # alheio a este teste).
    markdown = (
        "# Tese — FTST13 (FII TESTE HOTFIX2)\n"
        "> Não é recomendação de investimento.\n"
        "## Fundamentos do fundo\nVacância física e valor patrimonial descritos.\n"
        "## Contexto macro e juros\n...\n"
        "## Camada geopolítica e correlações (interpretação)\ncenário: juros.\n"
        "## Síntese\n...\n## Riscos e contra-tese (bull × bear)\n...\n"
        "## Fontes\n...\n## Lacunas\n- EBITDA: dado não encontrado\n"
    )
    # Cita TODOS os documentos (cobertura realista, `_FakeMessagesDinamico`) —
    # mas o `numero_citado` do documento marcado NÃO contém os dígitos "095"/
    # "073" das claims de P/VP-a-mercado/DY-a-mercado: nenhuma citação, por
    # coincidência, relaxa os termos vetados de `texto_livre_novo` — a prova
    # de que é a correção (superfície MODELO sem texto_livre_novo), e não uma
    # citação afortunada, que faz este cenário passar.
    client = _FakeClientDinamico(
        markdown,
        "Leitura de mercado de FII",  # marcador único do doc de valuation
        "leitura de mercado sem número específico citado aqui",
    )
    monkeypatch.setattr(
        tese_svc,
        "get_settings",
        lambda: SimpleNamespace(
            anthropic_api_key="chave-de-teste-offline",
            tese_teto_custo_usd_dia=0,
            tese_model_synthesis="claude-opus-4-8",
            tese_model_extraction="claude-haiku-4-5-20251001",
            tese_max_tokens_sintese=16000,
            consenso_enabled=False,
        ),
    )
    monkeypatch.setattr(tese_svc.anthropic, "Anthropic", lambda api_key=None: client)
    monkeypatch.setattr(tese_svc, "_extract_metadata_haiku", lambda *a, **k: None)
    for perfil in (acao, fii, renda_fixa):
        monkeypatch.setattr(
            perfil,
            "ingest",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("ingest não deveria rodar")),
        )
    # `avaliar_tese` NÃO é stubado (ao contrário de `test_tese_fii_pvp_e_dy_
    # mercado`, que estuba de propósito) — o gate REAL é o alvo desta
    # regressão.
    tese = _criar_tese(sessao, "FTST13", "fii")

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    # Prova viva (não hipótese de fixture): `_modelo_fii` grava o valor REAL
    # com número no `texto_livre_novo` determinístico — se isto deixar de ser
    # verdade num refactor futuro, o que este teste prova muda com ele.
    assert "P/VP a mercado: 0,95" in env["texto_livre_novo"]
    assert "DY a mercado 12m: 0,73%" in env["texto_livre_novo"]
    laudo = env["avaliacao"]
    assert laudo["bloqueante"] is False, laudo["motivos"]
    assert not laudo["termos_vetados"], laudo["termos_vetados"]
    assert laudo["aprovado"] is True, laudo


# ---------------------------------------------------------------------------
# 5) Renda fixa — curva ANBIMA / inflação implícita
# ---------------------------------------------------------------------------
def test_tese_rf_curva_anbima_inflacao_implicita(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    f_titulo = _fonte(sessao, "STN/Tesouro Transparente — Tesouro IPCA+ 2035")
    sessao.add(
        TituloPublico(
            tipo="Tesouro IPCA+",
            data_vencimento=dt.date(2035, 5, 15),
            data_base=_HOJE - dt.timedelta(days=1),
            taxa_compra=7.55,
            taxa_venda=7.61,
            pu_compra=4010.0,
            pu_venda=4000.0,
            pu_base=4000.0,
            fonte_id=f_titulo.id,
        )
    )
    f_anbima = _fonte(sessao, "ANBIMA — ETTJ snapshot")
    sessao.add(
        CurvaSnapshot(
            data_ref=_HOJE,
            curva="IPCA",
            vertice_du=3000,
            taxa=6.5,
            inflacao_implicita=5.8,
            fonte_id=f_anbima.id,
        )
    )
    sessao.add(
        CurvaSnapshot(data_ref=_HOJE, curva="PRE", vertice_du=3000, taxa=12.3, fonte_id=f_anbima.id)
    )
    sessao.commit()
    md_rf = (
        "# Tese — TD-IPCA-2035 (Tesouro IPCA+ 2035)\n"
        "> Não é recomendação de investimento.\n"
        "## 1. Características do título\n...\n## 2. Taxas e preços (com Data Base)\n...\n"
        "## 3. Cenário de juros e inflação\n...\n"
        "## 4. Camada geopolítica e correlações (interpretação)\ncenário: juros globais.\n"
        "## 5. Síntese\n...\n## 6. Riscos (marcação a mercado × carrego)\n...\n"
        "## 7. Fontes\n...\n## 8. Lacunas\n"
        "- Curva DI completa por prazo: dado não encontrado (B3/ANBIMA licenciadas; "
        "taxas do Tesouro prefixado por vencimento servem apenas como proxy nomeado)\n"
    )
    _preparar_motor_fake(monkeypatch, md_rf)
    tese = _criar_tese(sessao, "TD-IPCA-2035", "renda_fixa")

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    nomes = {m["nome"]: m for m in env["metricas_setor"]}
    assert "Inflação implícita (vértice ANBIMA)" in nomes
    implicita = nomes["Inflação implícita (vértice ANBIMA)"]
    assert implicita["valor"] == pytest.approx(5.8)
    assert implicita["lacuna"] is None
    # RF nunca ganha técnica/valuation/gráficos (sem COTAHIST/sem modelo).
    assert "tecnica" not in env
    assert "valuation" not in env
    assert "graficos" not in env


# ---------------------------------------------------------------------------
# 6) Legado — SEM dado novo: envelope SEM os 5 blocos + system byte-idêntico
# ---------------------------------------------------------------------------
def test_tese_legada_sem_dado_novo_envelope_sem_blocos_novos(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _empresa(sessao, "LEGA4")
    # Sem COTAHIST seedado: `precisa_ingest` agora dispara ingest() mesmo com
    # fundamento presente (correção do bug "tese legada silenciosa",
    # 2026-07-11) — NO-OP aqui de propósito, simulando "ingest tentou e não
    # achou nada novo" (ticker sem cobertura/rede indisponível), o único
    # jeito real de preservar o caminho LEGADO (`_tem_dado_novo=False`) para
    # um ticker que já existe.
    client = _preparar_motor_fake(monkeypatch, _MD_ACAO, ingest_deve_rodar=True)
    tese = _criar_tese(sessao, "LEGA4", None)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    for chave in ("graficos", "tecnica", "valuation", "consenso", "metricas_setor"):
        assert chave not in env, f"{chave} não deveria existir sem dado novo"
    assert env["texto_livre_novo"] == ""
    system_enviado = client.messages.captured["system"][0]["text"]
    assert system_enviado == tese_svc._SYSTEM


# ---------------------------------------------------------------------------
# 7) Falha isolada de UM bloco novo não derruba a tese (padrão SAVEPOINT)
# ---------------------------------------------------------------------------
def test_falha_isolada_de_metricas_setor_nao_derruba_a_tese(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _empresa(sessao, "FALH4")
    _seed_precos(sessao, "FALH4", dias=25, preco_base=10.0)

    def _explode(*_a, **_k):
        raise RuntimeError("boom — falha inesperada nas métricas")

    monkeypatch.setattr(metricas_svc, "calcular", _explode)
    _preparar_motor_fake(monkeypatch, _MD_ACAO)
    tese = _criar_tese(sessao, "FALH4", None)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready", _envelope(sessao, tese).get("erro")
    env = _envelope(sessao, tese)
    # Métricas ficaram vazias (falha isolada) mas técnica seguiu computando.
    assert "metricas_setor" not in env
    assert env["tecnica"]["indicadores"]
