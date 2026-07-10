"""Testes offline da identidade de ativo (BLOCO C — D4/etapa 6).

Sem rede/DB real: sessões FAKE despacham por ENTIDADE consultada (CvmCadastro
vs FiiCadastro), o que também prova a ORDEM de consulta (cvm_cadastro vence).
Cobre: gramática TD-* + mapa STN completo, união do schema (B3 | TD), a
desambiguação de sufixo 11-13, a abstenção estável e o router (POST grava
teses.classe_ativo para classes novas; GET expõe classe_ativo).
"""

from __future__ import annotations

import contextlib
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.models import CvmCadastro, FiiCadastro
from app.schemas.tese import TeseCreateIn, TeseOut
from app.services.ativos import CLASSES
from app.services.ativos.identidade import resolver_classe
from app.services.ativos.renda_fixa import SIGLA_PARA_TIPO, TIPO_PARA_SIGLA
from app.services.dados import DadoNaoEncontrado

client = TestClient(app)


# ---------------------------------------------------------------------------
# Sessão fake: despacha por entidade consultada e registra a ORDEM das consultas.
# ---------------------------------------------------------------------------
class _FakeScalars:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    def __init__(self, cvm: list | None = None, fii: list | None = None) -> None:
        self._por_entidade = {CvmCadastro: list(cvm or []), FiiCadastro: list(fii or [])}
        self.consultas: list[type] = []
        self.commits = 0

    def execute(self, stmt) -> _FakeResult:
        entidade = stmt.column_descriptions[0]["entity"]
        self.consultas.append(entidade)
        return _FakeResult(self._por_entidade.get(entidade, []))

    def commit(self) -> None:
        self.commits += 1


# ---------------------------------------------------------------------------
# Renda fixa: gramática TD-* + mapa STN completo (recon delta 5)
# ---------------------------------------------------------------------------
def test_td_ipca_2035_resolve_renda_fixa_sem_tocar_o_banco() -> None:
    classe, payload = resolver_classe("TD-IPCA-2035", session=None)
    assert classe == "renda_fixa"
    assert payload["familia"] == "Tesouro IPCA+"
    assert payload["ano"] == 2035
    assert payload["sigla"] == "IPCA"


@pytest.mark.parametrize(("sigla", "tipo"), sorted(SIGLA_PARA_TIPO.items()))
def test_mapa_stn_cada_sigla_resolve_a_familia_oficial(sigla: str, tipo: str) -> None:
    classe, payload = resolver_classe(f"TD-{sigla}-2032", session=None)
    assert classe == "renda_fixa"
    assert payload["familia"] == tipo


def test_mapa_stn_completo_e_bijetivo() -> None:
    # Mapa COMPLETO dos títulos vivos (recon delta 5) — 8 famílias, sem duplicata.
    assert len(SIGLA_PARA_TIPO) == 8
    assert set(SIGLA_PARA_TIPO) == {
        "PRE",
        "PREJ",
        "SELIC",
        "IPCA",
        "IPCAJ",
        "IGPMJ",
        "RENDA",
        "EDUCA",
    }
    assert len(TIPO_PARA_SIGLA) == 8  # nenhum 'Tipo Titulo' oficial repetido
    assert TIPO_PARA_SIGLA == {tipo: sigla for sigla, tipo in SIGLA_PARA_TIPO.items()}
    assert SIGLA_PARA_TIPO["PREJ"] == "Tesouro Prefixado com Juros Semestrais"
    assert SIGLA_PARA_TIPO["RENDA"] == "Tesouro Renda+ Aposentadoria Extra"
    assert SIGLA_PARA_TIPO["EDUCA"] == "Tesouro Educa+"


# ---------------------------------------------------------------------------
# Schema: união (regex B3 | gramática TD), sanitização e limites
# ---------------------------------------------------------------------------
def test_schema_aceita_uniao_b3_e_td_e_normaliza() -> None:
    assert TeseCreateIn(ticker="td-ipca-2035").ticker == "TD-IPCA-2035"
    assert TeseCreateIn(ticker=" hglg11 ").ticker == "HGLG11"
    assert TeseCreateIn(ticker="PETR4").ticker == "PETR4"
    assert TeseCreateIn(ticker="TD-RENDA-2065").ticker == "TD-RENDA-2065"


@pytest.mark.parametrize(
    "ruim",
    [
        "TD-XXXX-2035",  # sigla fora do mapa STN
        "TD-IPCA-35",  # ano com 2 dígitos
        "TD-IPCA-3035",  # século fora de 19xx/20xx
        "DROP TABLE",  # injeção — não casa com nenhuma gramática
        "TD--2035",
        "TD-IPCA-",
    ],
)
def test_schema_rejeita_codigos_invalidos_422(ruim: str) -> None:
    with pytest.raises(ValidationError):
        TeseCreateIn(ticker=ruim)


def test_schema_max_length_16() -> None:
    with pytest.raises(ValidationError):
        TeseCreateIn(ticker="TD-EDUCA-2035XXXX")  # 17 chars > teto


def test_tese_out_classe_ativo_opcional_default_none() -> None:
    tese = TeseOut(id=uuid.uuid4(), ticker="PETR4", status="ready")
    assert tese.classe_ativo is None
    tese_fii = TeseOut(id=uuid.uuid4(), ticker="HGLG11", status="ready", classe_ativo="fii")
    assert tese_fii.classe_ativo == "fii"


# ---------------------------------------------------------------------------
# Identidade B3: sufixo 3-8 direto; 11-13 desambiguado pelo cadastro (D4)
# ---------------------------------------------------------------------------
def test_petr4_resolve_acao_direto_sem_sessao() -> None:
    classe, payload = resolver_classe("PETR4", session=None)
    assert classe == "acao"
    assert payload["metodo"] == "sufixo_b3"


def test_sufixo_direto_nao_consulta_o_banco() -> None:
    sessao = _FakeSession()
    classe, _payload = resolver_classe("VALE3", sessao)
    assert classe == "acao"
    assert sessao.consultas == []  # sufixo 3 não é ambíguo — zero query


def test_hglg11_com_fii_cadastro_e_sem_cvm_resolve_fii() -> None:
    sessao = _FakeSession(
        fii=[FiiCadastro(cnpj="08.431.747/0001-06", nome="CSHG LOGÍSTICA FII", ticker="HGLG11")]
    )
    classe, payload = resolver_classe("HGLG11", sessao)
    assert classe == "fii"
    assert payload["metodo"] == "fii_cadastro"
    assert payload["cnpj"] == "08.431.747/0001-06"
    # cvm_cadastro é consultado PRIMEIRO (units vencem); só então o fii_cadastro.
    assert sessao.consultas == [CvmCadastro, FiiCadastro]


def test_sanb11_presente_em_cvm_cadastro_resolve_acao() -> None:
    sessao = _FakeSession(
        cvm=[CvmCadastro(cd_cvm=20766, denom_social="BCO SANTANDER (BRASIL) S.A.", comneg="SANB11")]
    )
    classe, payload = resolver_classe("SANB11", sessao)
    assert classe == "acao"
    assert payload["metodo"] == "cvm_cadastro"
    assert payload["cd_cvm"] == 20766
    assert sessao.consultas == [CvmCadastro]  # nem chegou ao fii_cadastro


def test_unit_vence_mesmo_com_homonimo_no_fii_cadastro() -> None:
    # D4: sufixo 11-13 -> cvm_cadastro VENCE (protege units SANB11/TAEE11/BPAC11).
    sessao = _FakeSession(
        cvm=[CvmCadastro(cd_cvm=20766, denom_social="BCO SANTANDER", comneg="SANB11")],
        fii=[FiiCadastro(cnpj="99.999.999/0001-99", nome="FALSO FII", ticker="SANB11")],
    )
    classe, _payload = resolver_classe("SANB11", sessao)
    assert classe == "acao"


def test_mxrf12_sem_cadastro_nenhum_abstem_com_mensagem_estavel() -> None:
    sessao = _FakeSession()  # cvm_cadastro e fii_cadastro vazios
    with pytest.raises(DadoNaoEncontrado, match="MXRF12") as exc:
        resolver_classe("MXRF12", sessao)
    assert "dado não encontrado" in str(exc.value)
    assert sessao.consultas == [CvmCadastro, FiiCadastro]


def test_codigo_fora_das_gramaticas_abstem_mesmo_sem_schema() -> None:
    # Defesa em profundidade: o schema já barra com 422, mas a identidade também abstém.
    with pytest.raises(DadoNaoEncontrado):
        resolver_classe("TD-IPCA-35", session=None)


# ---------------------------------------------------------------------------
# Registry por classe (D5): metadados mínimos
# ---------------------------------------------------------------------------
def test_registry_tem_as_tres_classes_com_metadados() -> None:
    assert set(CLASSES) == {"acao", "fii", "renda_fixa"}
    assert CLASSES["acao"].pares_globais is True
    assert CLASSES["fii"].pares_globais is False  # abstenção ESTRUTURAL (D5)
    assert CLASSES["renda_fixa"].pares_globais is False
    assert any("P/VP" in lac for lac in CLASSES["fii"].lacunas_estruturais)
    assert any("curva DI" in lac for lac in CLASSES["renda_fixa"].lacunas_estruturais)
    assert CLASSES["acao"].lacunas_estruturais == ()  # Basileia é lacuna do PLANO banco


# ---------------------------------------------------------------------------
# Router: POST grava classe_ativo (classes novas); ação legada fica NULL;
# GET expõe classe_ativo. Sem DB/LLM (padrão da suíte de segurança).
# ---------------------------------------------------------------------------
def _tese_fake(ticker: str):
    class _TeseFake:
        id = uuid.uuid4()
        classe_ativo = None

    tese = _TeseFake()
    tese.ticker = ticker
    tese.status = "processing"
    return tese


def _neutralizar_pipeline(monkeypatch: pytest.MonkeyPatch, tese_fake) -> None:
    from app.routers import teses as teses_router

    monkeypatch.setattr(teses_router, "reaper_teses_orfas", lambda s, t: 0)
    monkeypatch.setattr(teses_router, "buscar_tese_cache", lambda s, t, h: None)
    monkeypatch.setattr(teses_router, "criar_tese", lambda s, t: tese_fake)
    monkeypatch.setattr(teses_router, "_run_generation", lambda tid: None)


def _post(monkeypatch: pytest.MonkeyPatch, sessao: _FakeSession, ticker: str):
    from app.db.session import get_session

    tese = _tese_fake(ticker)
    _neutralizar_pipeline(monkeypatch, tese)
    app.dependency_overrides[get_session] = lambda: sessao
    with contextlib.suppress(Exception):
        app.state.limiter.reset()
    try:
        resposta = client.post("/teses", json={"ticker": ticker})
    finally:
        app.dependency_overrides.pop(get_session, None)
        with contextlib.suppress(Exception):
            app.state.limiter.reset()
    return resposta, tese


def test_post_teses_grava_classe_fii(monkeypatch: pytest.MonkeyPatch) -> None:
    sessao = _FakeSession(
        fii=[FiiCadastro(cnpj="08.431.747/0001-06", nome="CSHG LOG", ticker="HGLG11")]
    )
    resposta, tese = _post(monkeypatch, sessao, "HGLG11")
    assert resposta.status_code == 202
    assert tese.classe_ativo == "fii"
    assert sessao.commits == 1  # persistiu a classe nova


def test_post_teses_grava_classe_renda_fixa_sem_query(monkeypatch: pytest.MonkeyPatch) -> None:
    sessao = _FakeSession()
    resposta, tese = _post(monkeypatch, sessao, "TD-IPCA-2035")
    assert resposta.status_code == 202
    assert tese.classe_ativo == "renda_fixa"
    assert sessao.consultas == []  # gramática TD não toca o banco (etapa 8 resolve o título)


def test_post_teses_acao_legada_fica_null_sem_commit_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessao = _FakeSession()
    resposta, tese = _post(monkeypatch, sessao, "PETR4")
    assert resposta.status_code == 202
    assert tese.classe_ativo is None  # NULL = 'acao' (legado byte-idêntico)
    assert sessao.commits == 0  # nenhuma escrita extra no caminho legado


def test_post_teses_abstencao_preserva_contrato_202(monkeypatch: pytest.MonkeyPatch) -> None:
    # MXRF12 sem cadastro nenhum: a identidade abstém, mas o POST mantém o
    # contrato legado (202) — o job de geração abstém com "dado não encontrado".
    sessao = _FakeSession()
    resposta, tese = _post(monkeypatch, sessao, "MXRF12")
    assert resposta.status_code == 202
    assert tese.classe_ativo is None
    assert sessao.commits == 0


def test_get_tese_inclui_classe_ativo_quando_existir() -> None:
    from app.db.session import get_session

    tid = uuid.uuid4()
    envelope = {"markdown": "## Tese", "citacoes": [], "fontes": [], "lacunas": []}

    class _FakeTese:
        id = tid
        ticker = "TD-IPCA-2035"
        status = "ready"
        criado_em = None
        classe_ativo = "renda_fixa"

    class _FakeVersao:
        conteudo = json.dumps(envelope, ensure_ascii=False)

    class _SessaoGet:
        def get(self, _model, _id):
            return _FakeTese()

        def execute(self, _stmt):
            class _R:
                def scalar_one_or_none(self):
                    return _FakeVersao()

            return _R()

    app.dependency_overrides[get_session] = lambda: _SessaoGet()
    try:
        resposta = client.get(f"/teses/{tid}")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert resposta.status_code == 200
    assert resposta.json()["classe_ativo"] == "renda_fixa"


def test_get_tese_legada_sem_atributo_classe_devolve_none() -> None:
    from app.db.session import get_session

    tid = uuid.uuid4()

    class _FakeTeseLegada:  # sem o atributo classe_ativo (pré-Fase 2)
        id = tid
        ticker = "PETR4"
        status = "processing"
        criado_em = None

    class _SessaoGet:
        def get(self, _model, _id):
            return _FakeTeseLegada()

        def execute(self, _stmt):
            class _R:
                def scalar_one_or_none(self):
                    return None

            return _R()

    app.dependency_overrides[get_session] = lambda: _SessaoGet()
    try:
        resposta = client.get(f"/teses/{tid}")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert resposta.status_code == 200
    assert resposta.json()["classe_ativo"] is None
