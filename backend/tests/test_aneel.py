"""Testes offline do conector ANEEL SIGET (app.services.aneel).

Sem rede real (httpx.MockTransport pula a allowlist — padrão de
test_anbima_ettj.py) e sem Postgres (SQLite em memória). A fixture principal
são as 3 páginas REAIS do CKAN datastore congeladas em 2026-07-10
(tests/fixtures/aneel/aneel_rap_grupo_taesa_p{1,2,3}.json): 1043 registros do
grupo Taesa (12 siglas do mapa curado v1), dos quais 966 vigentes ("Ativa")
no ciclo 2026-2027 (DatRefCiclo 2026-06-01), somando R$ 2.960.155.718,79
(ground truth recomputado da fixture congelada, cruzado com a RAP ~R$3,0 bi
divulgada pela companhia para as concessões 100%).

Correção A8 testada: metodologia declara o mapa curado + escopo; CNPJ fora do
mapa no ciclo-alvo -> abstenção (sigla reatribuída nunca é somada em silêncio).
Correção A13 testada: tabela `setor_indicadores` ausente -> DadoNaoEncontrado.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import Session

from app.models.models import Empresa, Fonte, SetorIndicador
from app.services.aneel import (
    _CAMPOS,
    _GRUPOS_RAP_V1,
    ANEEL_DATASTORE_URL,
    DATASET_URL,
    DESCRICAO_FONTE,
    INDICADOR_RAP,
    RESOURCE_ID_RAP,
    UNIDADE_RAP,
    _parse_ciclo,
    _parse_valor_brl,
    ensure_rap,
)
from app.services.dados import DadoNaoEncontrado

FIXTURES = Path(__file__).parent / "fixtures" / "aneel"

# Registros REAIS do grupo Taesa (3 páginas do datastore congeladas em 2026-07-10).
REGISTROS_REAIS: list[dict[str, Any]] = []
for _pagina in (1, 2, 3):
    _corpo = json.loads(
        (FIXTURES / f"aneel_rap_grupo_taesa_p{_pagina}.json").read_text(encoding="utf-8")
    )
    REGISTROS_REAIS.extend(_corpo["result"]["records"])

# Ground truth da fixture congelada (conferido manualmente — ver docstring).
N_REGISTROS = 1043
N_ATIVOS_CICLO = 966
SOMA_GRUPO = Decimal("2960155718.79")
CICLO = dt.date(2026, 6, 1)  # DatRefCiclo do ciclo 2026-2027
DATA_GERACAO = dt.date(2026, 7, 10)  # DatGeracaoConjuntoDados do dataset
N_ATOS = 67  # NumAtoRAP distintos entre os registros vigentes do ciclo

SIGLAS_TAESA = _GRUPOS_RAP_V1["TAEE11"].siglas


def _registro(
    valor: str = "100,00",
    *,
    sigla: str = "TAESA",
    cnpj: str = "07859971000130",
    sit: str = "Ativa",
    ciclo: str = "2026-06-01 00:00:00",
    ato: str = "REH 9999/2026",
    geracao: str = "2026-07-10",
    anos: str = "2026-2027",
) -> dict[str, Any]:
    """Registro sintético no shape real do datastore (campos de `_CAMPOS`)."""
    return {
        "SigConcessionariaReceita": sigla,
        "NumCNPJConcessionariaUsr": cnpj,
        "VlrRAPCiclo": valor,
        "DatRefCiclo": ciclo,
        "DcsSitRAP": sit,
        "NumAtoRAP": ato,
        "DatGeracaoConjuntoDados": geracao,
        "QtdAnosCcoTar": anos,
    }


# --- Transporte fake: emula o CKAN datastore (filters + paginação) -----------
def _transport_datastore(
    registros: list[dict[str, Any]], chamadas: list[tuple[int, tuple[str, ...]]] | None = None
) -> httpx.MockTransport:
    """Serve `registros` paginados por offset/limit, validando o contrato da URL."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url).startswith(ANEEL_DATASTORE_URL)
        params = request.url.params
        assert params["resource_id"] == RESOURCE_ID_RAP
        assert params["fields"] == ",".join(_CAMPOS)
        filtros = json.loads(params["filters"])
        assert set(filtros) == {"SigConcessionariaReceita"}
        offset, limit = int(params["offset"]), int(params["limit"])
        if chamadas is not None:
            chamadas.append((offset, tuple(filtros["SigConcessionariaReceita"])))
        lote = registros[offset : offset + limit]
        return httpx.Response(
            200, json={"success": True, "result": {"records": lote, "total": len(registros)}}
        )

    return httpx.MockTransport(handler)


def _transport_fixo(resposta: int | str | dict) -> httpx.MockTransport:
    """Resposta fixa: int -> status HTTP; str -> corpo texto; dict -> corpo JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(resposta, int):
            return httpx.Response(resposta, text="erro")
        if isinstance(resposta, str):
            return httpx.Response(200, text=resposta)
        return httpx.Response(200, json=resposta)

    return httpx.MockTransport(handler)


# --- Sessão SQLite em memória (padrão de test_anbima_ettj.py) ----------------
def _make_sessao(tabelas: tuple) -> Iterator[Session]:
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
    yield from _make_sessao((Fonte.__table__, Empresa.__table__, SetorIndicador.__table__))


@pytest.fixture()
def sessao_sem_tabela() -> Iterator[Session]:
    """Banco SEM setor_indicadores — simula deploy antes da migração 0006 (A13)."""
    yield from _make_sessao((Fonte.__table__,))


def _linhas(sessao: Session) -> list[SetorIndicador]:
    return list(sessao.execute(select(SetorIndicador)).scalars().all())


# ---------------------------------------------------------------------------
# Helpers puros de parsing
# ---------------------------------------------------------------------------
def test_parse_valor_brl_formatos_do_siget() -> None:
    assert _parse_valor_brl("26244,99") == Decimal("26244.99")
    assert _parse_valor_brl("1.234.567,89") == Decimal("1234567.89")
    assert _parse_valor_brl("-12,5") == Decimal("-12.5")
    assert _parse_valor_brl("345479") == Decimal("345479")
    # Fora do formato pt-BR -> None (nunca "adivinhar" a escala do número).
    assert _parse_valor_brl("12.34") is None  # "." decimal seria 100x errado
    assert _parse_valor_brl("") is None
    assert _parse_valor_brl(None) is None
    assert _parse_valor_brl("n/d") is None


def test_parse_ciclo_do_datref() -> None:
    assert _parse_ciclo("2026-06-01 00:00:00") == CICLO
    assert _parse_ciclo("2026-06-01") == CICLO
    assert _parse_ciclo("") is None
    assert _parse_ciclo("junho/2026") is None


# ---------------------------------------------------------------------------
# ensure_rap — fixture real do grupo Taesa (contrato + ground truth)
# ---------------------------------------------------------------------------
def test_ensure_rap_persiste_agregado_real_do_grupo(sessao: Session) -> None:
    assert len(REGISTROS_REAIS) == N_REGISTROS  # fixture íntegra
    linha = ensure_rap(sessao, "TAEE11", transport=_transport_datastore(REGISTROS_REAIS))
    assert linha is not None
    assert linha.ticker == "TAEE11"
    assert linha.indicador == INDICADOR_RAP
    assert linha.unidade == UNIDADE_RAP
    assert linha.competencia == CICLO
    assert Decimal(linha.valor) == SOMA_GRUPO
    assert len(_linhas(sessao)) == 1  # UM agregado por ciclo, nunca RAP por subsidiária


def test_ensure_rap_cria_fonte_aneel_com_atribuicao(sessao: Session) -> None:
    linha = ensure_rap(sessao, "TAEE11", transport=_transport_datastore(REGISTROS_REAIS))
    fontes = list(sessao.execute(select(Fonte)).scalars().all())
    assert len(fontes) == 1
    fonte = fontes[0]
    assert fonte.url == DATASET_URL
    assert fonte.descricao == DESCRICAO_FONTE
    assert "ODbL" in fonte.descricao  # atribuição ANEEL (licença dos dados abertos)
    assert fonte.dt_referencia == DATA_GERACAO
    assert linha is not None and linha.fonte_id == fonte.id  # sem fonte não é fato


def test_metodologia_declara_criterio_do_mapa_curado(sessao: Session) -> None:
    """Correção A8: escopo do agregado SEMPRE declarado na métrica."""
    linha = ensure_rap(sessao, "TAEE11", transport=_transport_datastore(REGISTROS_REAIS))
    assert linha is not None and linha.metodologia is not None
    met = linha.metodologia
    assert "mapa curado v1 (2026-07-10)" in met
    assert "exclui" in met and "participações parciais" in met
    for sigla in SIGLAS_TAESA:  # todas as siglas do escopo, auditáveis
        assert sigla in met
    assert f"{N_ATIVOS_CICLO} registros" in met
    assert "situação 'Ativa'" in met
    assert "2026-2027" in met and "DatRefCiclo 2026-06-01" in met
    assert "ANEEL SIGET" in met and "ODbL" in met
    # Atos legais (NumAtoRAP): os primeiros por extenso + contagem do restante.
    assert "CC 001/2002" in met
    assert f"(+{N_ATOS - 10} outros atos)" in met


def test_ensure_rap_pagina_ate_o_total(sessao: Session) -> None:
    chamadas: list[tuple[int, tuple[str, ...]]] = []
    ensure_rap(sessao, "TAEE11", transport=_transport_datastore(REGISTROS_REAIS, chamadas))
    assert [offset for offset, _ in chamadas] == [0, 500, 1000]
    # Filtro exato pelas siglas do mapa curado em TODAS as páginas.
    assert all(siglas == SIGLAS_TAESA for _, siglas in chamadas)


def test_ensure_rap_idempotente_nao_duplica(sessao: Session) -> None:
    transport = _transport_datastore(REGISTROS_REAIS)
    ensure_rap(sessao, "TAEE11", transport=transport)
    linha = ensure_rap(sessao, "TAEE11", transport=transport)
    assert linha is not None
    assert len(_linhas(sessao)) == 1
    assert len(list(sessao.execute(select(Fonte)).scalars().all())) == 1


def test_ensure_rap_atualiza_valor_no_mesmo_ciclo(sessao: Session) -> None:
    ensure_rap(sessao, "TAEE11", transport=_transport_datastore([_registro("100,00")]))
    linha = ensure_rap(sessao, "TAEE11", transport=_transport_datastore([_registro("120,50")]))
    assert linha is not None and Decimal(linha.valor) == Decimal("120.50")
    assert len(_linhas(sessao)) == 1  # upsert por (ticker, indicador, competência)


# ---------------------------------------------------------------------------
# Regras de agregação — vigência e ciclo mais recente
# ---------------------------------------------------------------------------
def test_soma_somente_vigentes_do_ciclo_mais_recente(sessao: Session) -> None:
    registros = [
        _registro("100,00"),  # Ativa, ciclo novo -> entra
        _registro("23,45", sigla="JANAUBA", cnpj="26617923000180"),  # entra
        _registro("50,00", sit="Prevista"),  # obra prevista -> fora
        _registro("999,99", ciclo="2025-06-01 00:00:00", anos="2025-2026"),  # ciclo velho
    ]
    linha = ensure_rap(sessao, "TAEE11", transport=_transport_datastore(registros))
    assert linha is not None
    assert Decimal(linha.valor) == Decimal("123.45")
    assert linha.competencia == CICLO


def test_grupo_sem_registro_vigente_abstem(sessao: Session) -> None:
    registros = [_registro("50,00", sit="Prevista")]
    with pytest.raises(DadoNaoEncontrado, match="sem registro vigente"):
        ensure_rap(sessao, "TAEE11", transport=_transport_datastore(registros))
    assert _linhas(sessao) == []


# ---------------------------------------------------------------------------
# Escopo do mapa curado (correção A8)
# ---------------------------------------------------------------------------
def test_ticker_fora_do_mapa_devolve_none_sem_tocar_a_rede(sessao: Session) -> None:
    chamadas: list[tuple[int, tuple[str, ...]]] = []
    assert ensure_rap(sessao, "PETR4", transport=_transport_datastore([], chamadas)) is None
    assert ensure_rap(sessao, "taee3", transport=_transport_datastore([], chamadas)) is None
    assert chamadas == []  # abstenção de escopo: nenhuma requisição
    assert _linhas(sessao) == []


def test_cnpj_fora_do_mapa_abstem_com_alarme(sessao: Session) -> None:
    """Sigla reatribuída a outra empresa NUNCA entra na soma em silêncio."""
    registros = [_registro(), _registro("77,00", cnpj="99999999000199")]
    with pytest.raises(DadoNaoEncontrado, match="fora do mapa curado"):
        ensure_rap(sessao, "TAEE11", transport=_transport_datastore(registros))
    assert _linhas(sessao) == []  # nunca soma parcial


def test_valor_malformado_no_ciclo_alvo_abstem(sessao: Session) -> None:
    registros = [_registro(), _registro("12.34")]  # "." decimal = formato inesperado
    with pytest.raises(DadoNaoEncontrado, match="malformado"):
        ensure_rap(sessao, "TAEE11", transport=_transport_datastore(registros))
    assert _linhas(sessao) == []


def test_zero_registros_para_o_grupo_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="mapa curado"):
        ensure_rap(sessao, "TAEE11", transport=_transport_datastore([]))
    assert _linhas(sessao) == []


# ---------------------------------------------------------------------------
# Alarmes de contrato da fonte (schema/layout)
# ---------------------------------------------------------------------------
def test_resposta_sem_success_true_abstem(sessao: Session) -> None:
    corpo = {"success": False, "error": {"fields": "campo inexistente"}}
    with pytest.raises(DadoNaoEncontrado, match="success=true"):
        ensure_rap(sessao, "TAEE11", transport=_transport_fixo(corpo))


def test_resposta_nao_json_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="não é JSON"):
        ensure_rap(sessao, "TAEE11", transport=_transport_fixo("<html>manutenção</html>"))


def test_http_nao_200_sem_historico_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="HTTP 500"):
        ensure_rap(sessao, "TAEE11", transport=_transport_fixo(500))
    assert _linhas(sessao) == []


# ---------------------------------------------------------------------------
# Degradações — fonte fora do ar e tabela ausente (correção A13)
# ---------------------------------------------------------------------------
def test_fonte_fora_do_ar_devolve_ultimo_agregado_persistido(sessao: Session) -> None:
    ensure_rap(sessao, "TAEE11", transport=_transport_datastore(REGISTROS_REAIS))
    linha = ensure_rap(sessao, "TAEE11", transport=_transport_fixo(503))
    assert linha is not None  # fato datado já persistido: melhor que abster
    assert linha.competencia == CICLO
    # Round-trip do SQLite (Numeric vira float no storage do teste): tolerância.
    # No Postgres real a coluna é `numeric` exata — a exatidão da SOMA é provada
    # em test_ensure_rap_persiste_agregado_real_do_grupo, antes do round-trip.
    assert float(linha.valor) == pytest.approx(float(SOMA_GRUPO))
    assert len(_linhas(sessao)) == 1


def test_sem_tabela_setor_indicadores_degrada_para_abstencao(
    sessao_sem_tabela: Session,
) -> None:
    with pytest.raises(DadoNaoEncontrado, match="setor_indicadores indisponível"):
        ensure_rap(sessao_sem_tabela, "TAEE11", transport=_transport_datastore(REGISTROS_REAIS))
    # O SAVEPOINT foi desfeito: a transação externa segue utilizável (nunca 500).
    assert list(sessao_sem_tabela.execute(select(Fonte)).scalars().all()) == []
