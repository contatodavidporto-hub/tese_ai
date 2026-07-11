"""Testes offline do motor por classe (BLOCO F — etapas 10 e 11).

Cobrem, sem rede e sem chave (Anthropic FAKE, padrão test_synthesize):

- REGRESSÃO: hash sha256 da `tese._SYSTEM` PINADO no valor capturado ANTES da
  etapa 11 — o system prompt da ação é byte-idêntico.
- Templates por classe: variante financeira (mesmas 8 seções + crédito/PDD/ROE
  + '3.05 não é EBIT' + lacuna fixa da Basileia), FII e RF (H2 com 'geopol',
  lacunas FIXAS da classe, SEM seção de pares globais).
- setores (etapa 10): 'Bancos' devolve JPM/BAC/C/WFC com critério v2 datado e
  ressalva US-GAAP×IFRS; holding/seguros/desconhecido abstêm gracioso.
- Coleta por classe (SQLite em memória): FII formata pela UNIDADE tipada
  (staleness 90d); RF sempre cita a Data Base, deriva marcação (hedge fixo) e
  carrego vs CDI (rotulado), e abstém no título stale.
- `gerar_tese` DESPACHADO por classe, fim a fim: envelope com campo 'classe',
  fontes e lacunas fixas; gate chamado com kwarg `classe`; elos persistidos com
  `ativo_codigo` quando não há empresa.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import Session

from app.models.models import (
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
    Tese,
    TeseVersao,
    TituloPublico,
)
from app.services import setores
from app.services import tese as tese_svc
from app.services.ativos import acao, fii, renda_fixa
from app.services.dados import DadoNaoEncontrado

# Hash da _SYSTEM capturado ANTES da etapa 11 (2026-07-08, len=2321). Se este
# teste quebrar, o system prompt da AÇÃO deixou de ser byte-idêntico — isso é
# uma REGRESSÃO do contrato D5, não um teste a atualizar.
_SYSTEM_SHA256_PINADO = "9e9e3045303a6d3211acb2a67743ebfe586da12598e73e02e985a37aed21a472"

_HOJE = dt.date.today()


# ---------------------------------------------------------------------------
# Regressão do template da AÇÃO + variantes
# ---------------------------------------------------------------------------
def test_system_da_acao_e_byte_identico_hash_pinado() -> None:
    assert hashlib.sha256(tese_svc._SYSTEM.encode("utf-8")).hexdigest() == _SYSTEM_SHA256_PINADO


def test_perfil_acao_plano_padrao_usa_system_legado_identico() -> None:
    empresa = SimpleNamespace(plano_contas=None)
    assert acao.system_prompt(empresa) is tese_svc._SYSTEM
    empresa_padrao = SimpleNamespace(plano_contas="padrao")
    assert acao.system_prompt(empresa_padrao) is tese_svc._SYSTEM


@pytest.mark.parametrize("plano", ["banco", "seguradora"])
def test_variante_financeira_preserva_as_8_secoes_e_adiciona_regras(plano: str) -> None:
    prompt = acao.system_prompt(SimpleNamespace(plano_contas=plano))
    # Mesmas 8 seções (o prefixo é o _SYSTEM inteiro, byte-idêntico).
    assert prompt.startswith(tese_svc._SYSTEM)
    # Instruções de crédito/PDD/ROE na seção Fundamentos.
    assert "## 1. Fundamentos" in prompt
    assert "PDD" in prompt and "ROE" in prompt
    # Regra explícita do 3.05 e proibição de múltiplos de dívida/EBITDA.
    assert "3.05" in prompt
    assert "NUNCA trate como EBIT" in prompt
    assert "dívida/EBITDA" in prompt
    # Lacuna FIXA da Basileia.
    assert (
        "Índice de Basileia: dado não encontrado (publicado no IF.data/BCB, "
        "não nas demonstrações CVM)" in prompt
    )


def _headings(prompt: str) -> list[str]:
    return [ln for ln in prompt.splitlines() if ln.startswith("## ")]


def test_template_fii_estrutura_geopol_lacunas_fixas_sem_pares() -> None:
    prompt = fii.system_prompt(SimpleNamespace())
    heads = _headings(prompt)
    # H2 com 'geopol' — OBRIGATÓRIO para o gate (D6).
    assert any("geopol" in h.lower() for h in heads)
    assert "## 1. Fundamentos do fundo" in heads
    assert "## 6. Fontes" in heads and "## 7. Lacunas" in heads
    # SEM seção de pares globais (abstenção estrutural — a seção NÃO existe).
    assert not any("pares" in h.lower() for h in heads)
    # Fundamentos do fundo: PL, VP/cota, cotas, cotistas, DY auto-declarado,
    # vacância com metodologia.
    for token in ("patrimônio líquido", "valor patrimonial", "cotistas", "vacância"):
        assert token in prompt.lower()
    assert "auto-declarado" in prompt.lower() or "AUTO-DECLARADOS" in prompt
    # Lacunas FIXAS (preço B3 licenciado).
    assert "- P/VP a preço de mercado: dado não encontrado (cotação B3 é licenciada)" in prompt
    assert (
        "- Dividend yield a preço de mercado: dado não encontrado (cotação B3 é licenciada)"
        in prompt
    )
    # Regras comuns preservadas: fonte+data, abstenção, zero recomendação, disclaimer.
    assert "dado não encontrado" in prompt
    assert "NUNCA dê recomendação" in prompt
    assert "> Não é recomendação de investimento." in prompt


def test_template_rf_estrutura_databases_proxy_e_lacuna_fixa() -> None:
    prompt = renda_fixa.system_prompt(SimpleNamespace())
    heads = _headings(prompt)
    assert any("geopol" in h.lower() for h in heads)
    assert "## 1. Características do título" in heads
    assert "## 2. Taxas e preços (com Data Base)" in heads
    assert "## 6. Riscos (marcação a mercado × carrego)" in heads
    assert not any("pares" in h.lower() for h in heads)
    # Data Base sempre; marcação = variação passada; carrego não é retorno esperado.
    assert "Data Base" in prompt
    assert "VARIAÇÃO PASSADA" in prompt
    assert "o título paga a taxa contratada" in prompt
    assert "NÃO retorno esperado" in prompt
    # Curva DI só como proxy NOMEADO.
    assert "proxy da curva soberana" in prompt
    assert 'NUNCA de "curva DI"' in prompt
    assert (
        "- Curva DI completa por prazo: dado não encontrado (B3/ANBIMA licenciadas; "
        "taxas do Tesouro prefixado por vencimento servem apenas como proxy nomeado)" in prompt
    )
    assert "NUNCA dê recomendação" in prompt
    assert "> Não é recomendação de investimento." in prompt


# ---------------------------------------------------------------------------
# setores (etapa 10, D9) — bancos v2 + abstenções graciosas
# ---------------------------------------------------------------------------
def test_selecionar_pares_bancos_devolve_os_4_com_criterio_v2() -> None:
    info, motivo = setores.selecionar_pares("Bancos")
    assert motivo is None
    assert info["sic"] == "6021"
    assert {t for t, _ in info["pares"]} == {"JPM", "BAC", "C", "WFC"}
    assert setores.CRITERIO_VERSAO == "v2 (2026-07-08)"


def test_criterio_selecao_v2_tem_fonte_e_ressalva_usgaap_ifrs() -> None:
    rotulo = setores.criterio_selecao("6021")
    assert "v2 (2026-07-08)" in rotulo
    assert "SIC 6021" in rotulo
    assert "US-GAAP" in rotulo and "IFRS" in rotulo
    assert "fonte do critério" in rotulo
    assert "interpretação" in rotulo.lower()


def test_holding_seguros_fii_rf_abstem_gracioso() -> None:
    # holding segue abstendo (ITSA4).
    info, motivo = setores.selecionar_pares("Holdings Diversificadas")
    assert info is None and "ambíguo" in motivo
    # seguradoras: sem lista curada nesta fase -> abstém gracioso, com motivo.
    info, motivo = setores.selecionar_pares("Seguradoras e Corretoras")
    assert info is None and "sem lista curada" in motivo
    # FII/RF nunca chegam aqui (abstenção ESTRUTURAL), mas um setor de fundo
    # também não ganha pares por engano.
    info, motivo = setores.selecionar_pares("Fundos Imobiliários")
    assert info is None and "sem lista curada" in motivo


# ---------------------------------------------------------------------------
# Sessão SQLite em memória (padrão test_fii_dados)
# ---------------------------------------------------------------------------
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


def _fonte(sessao: Session, descricao: str, url: str = "https://dados.gov.br/x") -> Fonte:
    f = Fonte(url=url, descricao=descricao, dt_referencia=_HOJE)
    sessao.add(f)
    sessao.flush()
    return f


def _macro(sessao: Session, codigo: str, valor: float, data: dt.date | None = None) -> None:
    f = _fonte(sessao, f"BCB — série {codigo}", "https://api.bcb.gov.br/x")
    sessao.add(MacroSerie(codigo=codigo, data=data or _HOJE, valor=valor, fonte_id=f.id))
    sessao.flush()


def _seed_fii(sessao: Session) -> FiiCadastro:
    f_cad = _fonte(sessao, "CVM — Informe Mensal FII (geral)")
    fundo = FiiCadastro(
        cnpj="11.728.688/0001-47",
        nome="PÁTRIA LOG - FII",
        ticker="HGLG11",
        ticker_metodo="heuristica_isin",
        segmento="Multicategoria",
        mandato="Renda",
        tipo_gestao="Ativa",
        dt_referencia=_HOJE,
        fonte_id=f_cad.id,
    )
    sessao.add(fundo)
    sessao.flush()
    f_ind = _fonte(sessao, "CVM — Informe Mensal FII (complemento)")
    competencia = _HOJE - dt.timedelta(days=5)
    indicadores = (
        ("PL", 7063626090.23, "BRL", None),
        ("VP_COTA", 166.576588, "BRL_POR_COTA", None),
        ("COTAS_EMITIDAS", 42404675.0, "UN", None),
        ("COTISTAS", 525069.0, "UN", None),
        ("DY_MES_INFORME", 0.006635, "PCT", "auto-declarado pelo administrador; informe CVM"),
        (
            "VACANCIA_AGREGADA",
            0.0526,
            "PCT",
            "média ponderada pela área (m²) dos imóveis; auto-declarada",
        ),
    )
    for codigo, valor, unidade, metodologia in indicadores:
        sessao.add(
            FiiIndicador(
                fii_id=fundo.id,
                indicador=codigo,
                valor=valor,
                unidade=unidade,
                metodologia=metodologia,
                dt_referencia=competencia,
                fonte_id=f_ind.id,
            )
        )
    sessao.flush()
    return fundo


def _seed_titulo(sessao: Session, *, stale: bool = False) -> Fonte:
    f = _fonte(
        sessao,
        "STN/Tesouro Transparente — Tesouro IPCA+, venc. 15/05/2035",
        "https://www.tesourotransparente.gov.br/x.csv",
    )
    base = _HOJE - dt.timedelta(days=90 if stale else 1)
    vencimento = dt.date(2035, 5, 15)
    linhas = (
        (base, 7.55, 7.61, 4010.0, 4000.0),
        (base - dt.timedelta(days=30), 7.30, 7.36, 3910.0, 3900.0),
        (base - dt.timedelta(days=365), 6.80, 6.86, 3510.0, 3500.0),
    )
    for data_base, tc, tv, pc, pv in linhas:
        sessao.add(
            TituloPublico(
                tipo="Tesouro IPCA+",
                data_vencimento=vencimento,
                data_base=data_base,
                taxa_compra=tc,
                taxa_venda=tv,
                pu_compra=pc,
                pu_venda=pv,
                pu_base=pv,
                fonte_id=f.id,
            )
        )
    sessao.flush()
    return f


# ---------------------------------------------------------------------------
# Coleta FII — unidade tipada + staleness (delta 4)
# ---------------------------------------------------------------------------
def test_coletar_fii_formata_pela_unidade_e_rotula_autodeclarado(sessao: Session) -> None:
    fundo = _seed_fii(sessao)
    _macro(sessao, "SELIC_META_ANUAL", 14.25)
    itens = fii.coletar(sessao, fundo)
    textos = [t for _f, t in itens]

    assert any("R$ 7.063.626.090,23" in t for t in textos)  # PL em reais crus
    # Cotistas é UN: inteiro pt-BR, JAMAIS "R$" (achado B2).
    assert any("525.069" in t and "R$ 525.069" not in t for t in textos)
    assert any("R$ 166,58 por cota" in t for t in textos)  # VP/cota
    assert any("0,66%" in t and "auto-declarado" in t for t in textos)  # DY do informe
    assert any("Vacância" in t and "metodologia" in t for t in textos)
    # Cadastro auto-declarado + macro relevante presente.
    assert any("Multicategoria" in t for t in textos)
    assert any("Meta Selic" in t for t in textos)
    # Todo item tem Fonte (documento citável).
    assert all(f is not None for f, _t in itens)


def test_coletar_fii_exclui_competencia_stale_90d(sessao: Session) -> None:
    fundo = _seed_fii(sessao)
    # Um indicador velho (120d) NÃO pode entrar na coleta.
    f_velho = _fonte(sessao, "CVM — informe velho")
    sessao.add(
        FiiIndicador(
            fii_id=fundo.id,
            indicador="RENT_EFETIVA_MES",
            valor=0.011383,
            unidade="PCT",
            dt_referencia=_HOJE - dt.timedelta(days=120),
            fonte_id=f_velho.id,
        )
    )
    sessao.flush()
    textos = [t for _f, t in fii.coletar(sessao, fundo)]
    assert not any("Rentabilidade" in t for t in textos)


def test_coletar_fii_sem_indicador_recente_abstem_mesmo_com_macro(sessao: Session) -> None:
    # Delta 4: informe defasado (>90d) -> ABSTÉM. A macro global presente no
    # banco NÃO pode sustentar sozinha uma tese "macro-only" do fundo.
    f_cad = _fonte(sessao, "CVM — Informe Mensal FII (geral)")
    fundo = FiiCadastro(
        cnpj="99.999.999/0001-99", nome="FII DEFASADO", ticker="DEFA11", fonte_id=f_cad.id
    )
    sessao.add(fundo)
    sessao.flush()
    f_velho = _fonte(sessao, "CVM — informe velho")
    sessao.add(
        FiiIndicador(
            fii_id=fundo.id,
            indicador="PL",
            valor=1_000_000.0,
            unidade="BRL",
            dt_referencia=_HOJE - dt.timedelta(days=120),
            fonte_id=f_velho.id,
        )
    )
    sessao.flush()
    _macro(sessao, "SELIC_META_ANUAL", 14.25)
    assert fii.coletar(sessao, fundo) == []


# ---------------------------------------------------------------------------
# Coleta RF — Data Base sempre, derivadas com hedge, staleness 30d
# ---------------------------------------------------------------------------
def test_coletar_rf_cita_data_base_e_deriva_marcacao_e_carrego(sessao: Session) -> None:
    _seed_titulo(sessao)
    _macro(sessao, "CDI_ANUAL", 13.65, _HOJE - dt.timedelta(days=1))
    _macro(sessao, "SELIC_META_ANUAL", 14.25)
    _macro(sessao, "IPCA_MENSAL", 0.4)
    ref = renda_fixa.ensure_ativo(sessao, "TD-IPCA-2035")
    itens = renda_fixa.coletar(sessao, ref)
    textos = [t for _f, t in itens]

    # Fato: taxas/PUs SEMPRE com a Data Base.
    doc_titulo = next(t for t in textos if t.startswith("Título público"))
    assert "Data Base" in doc_titulo
    assert "taxa de compra 7,55% a.a." in doc_titulo
    assert "vencimento em 15/05/2035" in doc_titulo
    # Derivada 1: marcação a mercado (janelas 30/365d) com o hedge FIXO.
    marcacoes = [t for t in textos if "marcação a mercado" in t]
    assert len(marcacoes) == 2
    for t in marcacoes:
        assert "variação passada" in t
        assert "paga a taxa contratada" in t
    assert any("~30 dias" in t for t in marcacoes)
    assert any("~365 dias" in t for t in marcacoes)
    # Derivada 2: carrego vs CDI rotulado (comparação contemporânea).
    carrego = next(t for t in textos if "diferencial de taxa" in t)
    assert "NÃO é retorno esperado" in carrego
    assert "pontos percentuais" in carrego
    assert "REAL" in carrego  # família IPCA: taxa real x CDI nominal não é equivalência
    # Macro relevante presente e citável.
    assert any("Meta Selic" in t for t in textos)


def test_coletar_rf_titulo_stale_abstem_total(sessao: Session) -> None:
    _seed_titulo(sessao, stale=True)  # Data Base a 90d -> fora de oferta
    ref = renda_fixa.ensure_ativo(sessao, "TD-IPCA-2035")
    with pytest.raises(DadoNaoEncontrado):
        renda_fixa.coletar(sessao, ref)


def _seed_titulo_custom(sessao: Session, linhas: tuple) -> Fonte:
    """Linhas (data_base, taxa_compra, taxa_venda, pu_compra, pu_venda) do IPCA+ 2035."""
    f = _fonte(
        sessao,
        "STN/Tesouro Transparente — Tesouro IPCA+, venc. 15/05/2035",
        "https://www.tesourotransparente.gov.br/x.csv",
    )
    for data_base, tc, tv, pc, pv in linhas:
        sessao.add(
            TituloPublico(
                tipo="Tesouro IPCA+",
                data_vencimento=dt.date(2035, 5, 15),
                data_base=data_base,
                taxa_compra=tc,
                taxa_venda=tv,
                pu_compra=pc,
                pu_venda=pv,
                pu_base=pv,
                fonte_id=f.id,
            )
        )
    sessao.flush()
    return f


def test_coletar_rf_taxa_zero_abstem_campo_e_carrego_m1(sessao: Session) -> None:
    # Achado M1: Taxa Compra/Venda = 0 é "não ofertado" (convenção STN) — o doc
    # nunca exibe 'taxa de compra 0,00% a.a.' e o carrego vs CDI abstém.
    base = _HOJE - dt.timedelta(days=1)
    _seed_titulo_custom(sessao, ((base, 0.0, 0.0, 4010.0, 4000.0),))
    _macro(sessao, "CDI_ANUAL", 13.65, _HOJE - dt.timedelta(days=1))
    ref = renda_fixa.ensure_ativo(sessao, "TD-IPCA-2035")
    textos = [t for _f, t in renda_fixa.coletar(sessao, ref)]
    doc_titulo = next(t for t in textos if t.startswith("Título público"))
    assert "0,00% a.a." not in doc_titulo
    assert "taxas: dado não encontrado" in doc_titulo
    assert "PU de venda" in doc_titulo  # campos não-zero seguem
    assert not any("diferencial de taxa" in t for t in textos)  # carrego abstém


def test_coletar_rf_pu_atual_zero_abstem_marcacao_m1(sessao: Session) -> None:
    # Achado M1: PU atual = 0 -> marcação a mercado abstém (nunca variação
    # de -100% contra o PU histórico válido).
    base = _HOJE - dt.timedelta(days=1)
    _seed_titulo_custom(
        sessao,
        (
            (base, 7.55, 7.61, 0.0, 0.0),
            (base - dt.timedelta(days=30), 7.30, 7.36, 3910.0, 3900.0),
            (base - dt.timedelta(days=365), 6.80, 6.86, 3510.0, 3500.0),
        ),
    )
    ref = renda_fixa.ensure_ativo(sessao, "TD-IPCA-2035")
    textos = [t for _f, t in renda_fixa.coletar(sessao, ref)]
    assert not any("marcação a mercado" in t for t in textos)
    assert not any("-100" in t for t in textos)
    doc_titulo = next(t for t in textos if t.startswith("Título público"))
    assert "PUs: dado não encontrado" in doc_titulo
    assert "taxa de compra 7,55% a.a." in doc_titulo  # taxas não-zero seguem


def test_pu_mais_proximo_ignora_pu_zero_m1() -> None:
    # Achado M1: PU 0 é AUSÊNCIA — o vizinho VÁLIDO dentro da tolerância vence
    # (sem o filtro, o 0 "mais próximo" mataria a janela da marcação).
    alvo = dt.date(2026, 6, 7)
    zero = SimpleNamespace(data_base=alvo, pu_venda=0.0)
    valido = SimpleNamespace(data_base=alvo + dt.timedelta(days=2), pu_venda=3900.0)
    assert renda_fixa._pu_mais_proximo([zero, valido], alvo) is valido


def test_rf_ensure_ativo_rejeita_codigo_invalido() -> None:
    with pytest.raises(DadoNaoEncontrado):
        renda_fixa.ensure_ativo(None, "TD-XPTO-2035")


# ---------------------------------------------------------------------------
# gerar_tese despachado por classe (fim a fim, Anthropic FAKE)
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
    monkeypatch: pytest.MonkeyPatch, markdown: str
) -> tuple[_FakeClient, dict]:
    """Anthropic/settings/haiku/gate FAKE — devolve (client, captura do gate)."""
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
            # Consenso desligado por padrão nestes testes offline (LLM06) —
            # gerar_tese chama `_montar_blocos_novos`/`consenso.buscar` de
            # forma incondicional; sem isto o motor não teria o atributo.
            consenso_enabled=False,
        ),
    )
    monkeypatch.setattr(tese_svc.anthropic, "Anthropic", lambda api_key=None: client)
    monkeypatch.setattr(tese_svc, "_extract_metadata_haiku", lambda *a, **k: None)
    captura_gate: dict = {}

    def _gate_stub(envelope, **kwargs):
        captura_gate.update(kwargs)
        captura_gate["envelope"] = envelope
        return {"aprovado": True, "bloqueante": False, "motivos": [], "cobertura_fontes": 1.0}

    # Stub do gate: o parâmetro `classe` está sendo adicionado pelo Bloco G em
    # paralelo — aqui provamos que o MOTOR chama com o kwarg, sem acoplar o
    # teste à assinatura final de avaliacao.py.
    monkeypatch.setattr(tese_svc, "avaliar_tese", _gate_stub)
    return client, captura_gate


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


_MD_FII = (
    "# Tese — HGLG11 (PÁTRIA LOG - FII)\n"
    "> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.\n"
    "## 1. Fundamentos do fundo\nPL citado.\n"
    "## 2. Contexto macro e juros\nSelic citada.\n"
    "## 3. Camada geopolítica e correlações (interpretação)\ncenário: juros.\n"
    "## 4. Síntese\n...\n## 5. Riscos e contra-tese (bull × bear)\n...\n"
    "## 6. Fontes\n...\n## 7. Lacunas\n"
    "- P/VP a preço de mercado: dado não encontrado (cotação B3 é licenciada)\n"
    "- Dividend yield a preço de mercado: dado não encontrado (cotação B3 é licenciada)\n"
)

_MD_RF = (
    "# Tese — TD-IPCA-2035 (Tesouro IPCA+ 2035)\n"
    "> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.\n"
    "## 1. Características do título\n...\n"
    "## 2. Taxas e preços (com Data Base)\n...\n"
    "## 3. Cenário de juros e inflação\n...\n"
    "## 4. Camada geopolítica e correlações (interpretação)\ncenário: juros globais.\n"
    "## 5. Síntese\n...\n## 6. Riscos (marcação a mercado × carrego)\n...\n"
    "## 7. Fontes\n...\n## 8. Lacunas\n"
    "- Curva DI completa por prazo: dado não encontrado (B3/ANBIMA licenciadas; "
    "taxas do Tesouro prefixado por vencimento servem apenas como proxy nomeado)\n"
)

_MD_ACAO = (
    "# Tese — PETR4 (PETROBRAS)\n"
    "> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.\n"
    "## 1. Fundamentos\n...\n## 8. Lacunas\n- EBITDA: dado não encontrado\n"
)


def test_gerar_tese_fii_despacha_template_gate_e_elos_por_classe(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_fii(sessao)
    _macro(sessao, "SELIC_META_ANUAL", 14.25)
    client, captura_gate = _preparar_motor_fake(monkeypatch, _MD_FII)
    tese = _criar_tese(sessao, "HGLG11", "fii")

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready"
    env = _envelope(sessao, tese)
    # Envelope ganha o campo 'classe' e carrega fontes/citações/lacunas fixas.
    assert env["classe"] == "fii"
    assert env["fontes"]
    assert env["citacoes"]
    assert any("P/VP a preço de mercado" in lac for lac in env["lacunas"])
    # Template DA CLASSE foi ao modelo (mesmo caminho Opus/Citations).
    assert client.messages.captured["system"][0]["text"] == fii.system_prompt(None)
    # Gate por classe: chamado com kwarg classe='fii'.
    assert captura_gate["classe"] == "fii"
    # Elos persistidos com ativo_codigo (CHECK exige âncora; FII não tem empresa).
    elos = sessao.execute(select(Elo)).scalars().all()
    assert elos
    assert all(e.ativo_codigo == "HGLG11" and e.empresa_id is None for e in elos)


def test_gerar_tese_rf_despacha_template_gate_e_elos_por_classe(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_titulo(sessao)
    _macro(sessao, "CDI_ANUAL", 13.65, _HOJE - dt.timedelta(days=1))
    _macro(sessao, "SELIC_META_ANUAL", 14.25)
    _macro(sessao, "IPCA_MENSAL", 0.4)
    client, captura_gate = _preparar_motor_fake(monkeypatch, _MD_RF)
    tese = _criar_tese(sessao, "TD-IPCA-2035", "renda_fixa")

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready"
    env = _envelope(sessao, tese)
    assert env["classe"] == "renda_fixa"
    assert env["fontes"]
    assert any("Curva DI completa por prazo" in lac for lac in env["lacunas"])
    assert client.messages.captured["system"][0]["text"] == renda_fixa.system_prompt(None)
    assert captura_gate["classe"] == "renda_fixa"
    # Elos: interpretativo IPCA→IPCA+ (fonte nas 2 pontas) persistido com o código TD.
    elos = sessao.execute(select(Elo)).scalars().all()
    assert elos
    assert all(e.ativo_codigo == "TD-IPCA-2035" and e.empresa_id is None for e in elos)
    assert any("expectativa" in (e.hedge or "").lower() for e in elos)


def test_gerar_tese_acao_legada_continua_com_system_byte_identico(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Empresa já ingerida (seed): o caminho legado não vai à rede.
    f = _fonte(sessao, "CVM DFP 2025 (consolidado) — PETROBRAS")
    empresa = Empresa(cd_cvm=9512, ticker="PETR4", nome="PETROLEO BRASILEIRO S.A.", cnpj=None)
    sessao.add(empresa)
    sessao.flush()
    sessao.add(
        Fundamento(
            empresa_id=empresa.id,
            conta="Receita de Venda de Bens e/ou Serviços (3.01)",
            valor=100.0,
            dt_refer=dt.date(2025, 12, 31),
            fonte_id=f.id,
        )
    )
    sessao.commit()
    client, captura_gate = _preparar_motor_fake(monkeypatch, _MD_ACAO)
    tese = _criar_tese(sessao, "PETR4", None)  # NULL = 'acao' (legado)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready"
    env = _envelope(sessao, tese)
    assert env["classe"] == "acao"
    # REGRESSÃO: mesmo system prompt de hoje, byte-idêntico (hash pinado).
    system_enviado = client.messages.captured["system"][0]["text"]
    assert system_enviado == tese_svc._SYSTEM
    assert hashlib.sha256(system_enviado.encode("utf-8")).hexdigest() == _SYSTEM_SHA256_PINADO
    assert captura_gate["classe"] == "acao"


@pytest.mark.parametrize("plano", ["banco", "seguradora"])
def test_gerar_tese_acao_financeira_gate_recebe_classe_do_plano_m2(
    sessao: Session, monkeypatch: pytest.MonkeyPatch, plano: str
) -> None:
    # Achado M2 (red-team): banco/seguradora são classe 'acao' (D4) — passando
    # `classe=tese.classe_ativo or 'acao'` cru, os tokens/piso de 'banco' do
    # gate NUNCA rodavam. O motor espelha a condição do template variante.
    f = _fonte(sessao, "CVM DFP 2025 (consolidado) — EMISSOR FINANCEIRO")
    empresa = Empresa(
        cd_cvm=19348,
        ticker="ITUB4",
        nome="ITAU UNIBANCO HOLDING S.A.",
        cnpj=None,
        plano_contas=plano,
    )
    sessao.add(empresa)
    sessao.flush()
    sessao.add(
        Fundamento(
            empresa_id=empresa.id,
            conta="Receitas da Intermediação Financeira (3.01)",
            valor=100.0,
            dt_refer=dt.date(2025, 12, 31),
            fonte_id=f.id,
        )
    )
    sessao.commit()
    client, captura_gate = _preparar_motor_fake(monkeypatch, _MD_ACAO)
    tese = _criar_tese(sessao, "ITUB4", None)  # NULL = classe 'acao' (legado)

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "ready"
    # Gate recebe o PLANO como classe (stub captura os kwargs)...
    assert captura_gate["classe"] == plano
    # ...a classe do ATIVO no envelope segue 'acao' (trilha de auditoria)...
    assert captura_gate["envelope"]["classe"] == "acao"
    # ...e o template variante financeiro acompanha (mesma condição espelhada).
    assert client.messages.captured["system"][0]["text"] == acao.system_prompt(empresa)


def test_gerar_tese_fii_sem_dados_abstem_total(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fundo cadastrado mas SEM indicador recente e SEM rede (ingest falha) ->
    # DadoNaoEncontrado -> abstenção total (status=error, mensagem estável).
    f_cad = _fonte(sessao, "CVM — Informe Mensal FII (geral)")
    sessao.add(
        FiiCadastro(cnpj="00.000.000/0001-00", nome="FII VAZIO", ticker="VAZI11", fonte_id=f_cad.id)
    )
    sessao.commit()
    _preparar_motor_fake(monkeypatch, _MD_FII)
    # ingest por classe vira no-op (sem rede em teste): nada é ingerido.
    from app.services.ativos import registro

    monkeypatch.setattr(registro.PERFIS["fii"], "ingest", lambda _s, _f: None)
    tese = _criar_tese(sessao, "VAZI11", "fii")

    tese_svc.gerar_tese(sessao, tese.id)

    sessao.refresh(tese)
    assert tese.status == "error"
    env = _envelope(sessao, tese)
    assert "dado não encontrado" in env["erro"]
