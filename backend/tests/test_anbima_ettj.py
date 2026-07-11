"""Testes offline do conector ANBIMA ETTJ (app.services.anbima_ettj).

Sem rede real (httpx.MockTransport pula a allowlist — padrão de
test_fii_dados.py) e sem Postgres (SQLite em memória). A fixture principal é
o CSV REAL de 09/07/2026, congelado por download ao vivo em 2026-07-10
(tests/fixtures/anbima/ettj_2026-07-09.csv, latin-1, byte-idêntico em duas
sondas): 67 vértices IPCA (126..8442 du), 20 vértices PRE (126..2520 du),
inflação implícita nos 20 primeiros. O "dia sem dado" real é HTTP 200 com
corpo VAZIO (sonda de domingo 05/07/2026, fixture ettj_vazio_2026-07-05.csv).

Trava ToS ANBIMA testada explicitamente: a função não aceita intervalo de
datas, faz 1 única requisição com data explícita e persiste UM único dia
mesmo quando regride procurando o último snapshot.
"""

from __future__ import annotations

import datetime as dt
import inspect
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import Session

from app.models.models import CurvaSnapshot, Fonte
from app.services import anbima_ettj
from app.services.anbima_ettj import (
    ANBIMA_ETTJ_URL,
    DESCRICAO_FONTE,
    _parse_csv,
    _parse_taxa,
    _parse_vertice,
    ensure_snapshot,
)
from app.services.dados import DadoNaoEncontrado

FIXTURES = Path(__file__).parent / "fixtures" / "anbima"
CSV_REAL = (FIXTURES / "ettj_2026-07-09.csv").read_bytes()
CSV_VAZIO = (FIXTURES / "ettj_vazio_2026-07-05.csv").read_bytes()

DIA_REAL = dt.date(2026, 7, 9)  # quinta-feira, data de referência do CSV real

# Ground truth do CSV real (conferido manualmente na fixture congelada).
N_VERTICES_IPCA = 67  # 126..8442, passo 126
N_VERTICES_PRE = 20  # 126..2520 (vértices longos só têm IPCA)
N_LINHAS_TOTAL = N_VERTICES_IPCA + N_VERTICES_PRE


# --- Transporte fake: roteia pelo Dt_Ref do corpo form-encoded ---------------
def _transport(
    respostas: dict[str, bytes | int], chamadas: list[str] | None = None
) -> httpx.MockTransport:
    """Serve `respostas[Dt_Ref]` (bytes -> 200; int -> status); ausente -> corpo vazio."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == ANBIMA_ETTJ_URL
        corpo = parse_qs(request.read().decode())
        assert corpo["Idioma"] == ["PT"]  # contrato do endpoint
        assert corpo["saida"] == ["csv"]
        dt_ref = corpo["Dt_Ref"][0]
        if chamadas is not None:
            chamadas.append(dt_ref)
        resposta = respostas.get(dt_ref, b"")
        if isinstance(resposta, int):
            return httpx.Response(resposta, text="erro")
        return httpx.Response(200, content=resposta, headers={"content-type": "text/csv"})

    return httpx.MockTransport(handler)


# --- Sessão SQLite em memória (padrão de test_fii_dados.py) ------------------
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
    yield from _make_sessao((Fonte.__table__, CurvaSnapshot.__table__))


@pytest.fixture()
def sessao_sem_tabela() -> Iterator[Session]:
    """Banco SEM curva_snapshot — simula deploy antes da migração 0006 (A13)."""
    yield from _make_sessao((Fonte.__table__,))


def _linhas(sessao: Session, curva: str | None = None) -> list[CurvaSnapshot]:
    stmt = select(CurvaSnapshot).order_by(CurvaSnapshot.curva, CurvaSnapshot.vertice_du)
    if curva is not None:
        stmt = stmt.where(CurvaSnapshot.curva == curva)
    return list(sessao.execute(stmt).scalars().all())


def _linha(sessao: Session, curva: str, vertice: int) -> CurvaSnapshot:
    return sessao.execute(
        select(CurvaSnapshot).where(
            CurvaSnapshot.curva == curva, CurvaSnapshot.vertice_du == vertice
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# Helpers puros de parsing
# ---------------------------------------------------------------------------
def test_parse_vertice_com_separador_de_milhar() -> None:
    assert _parse_vertice("1.008") == 1008
    assert _parse_vertice("126") == 126
    assert _parse_vertice("") is None
    assert _parse_vertice("Vertices") is None


def test_parse_taxa_virgula_decimal() -> None:
    assert _parse_taxa("13,8285") == pytest.approx(13.8285)
    assert _parse_taxa("9,0792") == pytest.approx(9.0792)
    assert _parse_taxa("") is None
    assert _parse_taxa("n/d") is None


def test_parse_csv_extrai_data_e_vertices_do_arquivo_real() -> None:
    data_arquivo, vertices = _parse_csv(CSV_REAL.decode("latin-1"))
    assert data_arquivo == DIA_REAL
    assert len(vertices) == N_VERTICES_IPCA
    assert vertices[0].vertice_du == 126
    assert vertices[-1].vertice_du == 8442
    # Vértice longo: só IPCA (sem PRE nem implícita) — abstenção, não extrapolação.
    assert vertices[-1].taxa_pre is None
    assert vertices[-1].inflacao_implicita is None


def test_parse_csv_corpo_nao_reconhecido_devolve_none() -> None:
    assert _parse_csv("<html>erro</html>") is None


# ---------------------------------------------------------------------------
# ensure_snapshot — dia explícito (1 requisição, dados reais, fonte ANBIMA)
# ---------------------------------------------------------------------------
def test_ensure_snapshot_persiste_curvas_do_dia_real(sessao: Session) -> None:
    gravados = ensure_snapshot(
        sessao,
        DIA_REAL,
        transport=_transport({"09/07/2026": CSV_REAL}),
    )
    assert len(gravados) == N_LINHAS_TOTAL
    assert len(_linhas(sessao, "IPCA")) == N_VERTICES_IPCA
    assert len(_linhas(sessao, "PRE")) == N_VERTICES_PRE
    assert all(linha.data_ref == DIA_REAL for linha in _linhas(sessao))

    # Ground truth do CSV congelado (taxas em % a.a.).
    assert float(_linha(sessao, "IPCA", 126).taxa) == pytest.approx(9.0792)
    assert float(_linha(sessao, "PRE", 126).taxa) == pytest.approx(13.8285)
    assert float(_linha(sessao, "IPCA", 126).inflacao_implicita) == pytest.approx(4.3539)
    # Separador de milhar: '1.008' -> vértice 1008.
    assert float(_linha(sessao, "IPCA", 1008).taxa) == pytest.approx(8.4121)
    assert float(_linha(sessao, "PRE", 2520).taxa) == pytest.approx(14.5796)


def test_ensure_snapshot_inflacao_implicita_so_na_linha_ipca(sessao: Session) -> None:
    ensure_snapshot(sessao, DIA_REAL, transport=_transport({"09/07/2026": CSV_REAL}))
    assert all(linha.inflacao_implicita is None for linha in _linhas(sessao, "PRE"))
    ipca_curtos = [li for li in _linhas(sessao, "IPCA") if li.vertice_du <= 2520]
    assert all(li.inflacao_implicita is not None for li in ipca_curtos)
    # Vértices longos: implícita ausente no arquivo -> None (abstenção).
    assert _linha(sessao, "IPCA", 8442).inflacao_implicita is None


def test_ensure_snapshot_cria_fonte_anbima_com_data(sessao: Session) -> None:
    gravados = ensure_snapshot(sessao, DIA_REAL, transport=_transport({"09/07/2026": CSV_REAL}))
    fontes = list(sessao.execute(select(Fonte)).scalars().all())
    assert len(fontes) == 1  # uma única fonte para o snapshot inteiro
    fonte = fontes[0]
    assert fonte.url == ANBIMA_ETTJ_URL
    assert fonte.descricao == DESCRICAO_FONTE
    assert fonte.dt_referencia == DIA_REAL
    assert all(linha.fonte_id == fonte.id for linha in gravados)  # sem fonte não é fato


def test_ensure_snapshot_data_explicita_faz_uma_unica_requisicao(sessao: Session) -> None:
    chamadas: list[str] = []
    ensure_snapshot(sessao, DIA_REAL, transport=_transport({"09/07/2026": CSV_REAL}, chamadas))
    assert chamadas == ["09/07/2026"]  # trava ToS: nunca loop histórico


def test_ensure_snapshot_idempotente_nao_duplica(sessao: Session) -> None:
    transport = _transport({"09/07/2026": CSV_REAL})
    ensure_snapshot(sessao, DIA_REAL, transport=transport)
    ensure_snapshot(sessao, DIA_REAL, transport=transport)
    assert len(_linhas(sessao)) == N_LINHAS_TOTAL
    assert len(list(sessao.execute(select(Fonte)).scalars().all())) == 1


# ---------------------------------------------------------------------------
# ensure_snapshot — regressão de dias úteis (data_ref=None)
# ---------------------------------------------------------------------------
def test_regressao_acha_ultimo_dia_util_pulando_fim_de_semana(sessao: Session) -> None:
    # hoje = segunda 13/07; 13 e 10 sem dado (corpo vazio real) -> acha 09/07.
    chamadas: list[str] = []
    gravados = ensure_snapshot(
        sessao,
        hoje=dt.date(2026, 7, 13),
        transport=_transport(
            {"13/07/2026": CSV_VAZIO, "10/07/2026": CSV_VAZIO, "09/07/2026": CSV_REAL},
            chamadas,
        ),
    )
    assert chamadas == ["13/07/2026", "10/07/2026", "09/07/2026"]  # sáb/dom nunca pedidos
    assert len(gravados) == N_LINHAS_TOTAL
    # UM único dia persistido (trava ToS): nunca acumula série na regressão.
    assert {linha.data_ref for linha in _linhas(sessao)} == {DIA_REAL}


def test_regressao_comeca_na_sexta_quando_hoje_e_sabado(sessao: Session) -> None:
    chamadas: list[str] = []
    ensure_snapshot(
        sessao,
        hoje=dt.date(2026, 7, 11),  # sábado
        transport=_transport({"10/07/2026": CSV_VAZIO, "09/07/2026": CSV_REAL}, chamadas),
    )
    assert chamadas[0] == "10/07/2026"  # 1º candidato = sexta, não o sábado


def test_regressao_tolera_status_http_nao_200(sessao: Session) -> None:
    gravados = ensure_snapshot(
        sessao,
        hoje=dt.date(2026, 7, 10),
        transport=_transport({"10/07/2026": 404, "09/07/2026": CSV_REAL}),
    )
    assert len(gravados) == N_LINHAS_TOTAL


def test_regressao_limitada_abstem_sem_dado_em_todos_os_candidatos(sessao: Session) -> None:
    chamadas: list[str] = []
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        ensure_snapshot(sessao, hoje=dt.date(2026, 7, 13), transport=_transport({}, chamadas))
    # 1 tentativa + 5 regressões de DIAS ÚTEIS, nunca varredura além disso.
    assert chamadas == [
        "13/07/2026",
        "10/07/2026",
        "09/07/2026",
        "08/07/2026",
        "07/07/2026",
        "06/07/2026",
    ]
    assert _linhas(sessao) == []  # abstenção: nada gravado


def test_data_do_arquivo_vence_a_data_pedida(sessao: Session) -> None:
    # Fonte devolve o arquivo de 09/07 para o pedido de 10/07: rotulagem honesta
    # usa a data DO ARQUIVO (nunca rotula dado de um dia como sendo de outro).
    ensure_snapshot(sessao, dt.date(2026, 7, 10), transport=_transport({"10/07/2026": CSV_REAL}))
    assert {linha.data_ref for linha in _linhas(sessao)} == {DIA_REAL}


# ---------------------------------------------------------------------------
# Trava ToS ANBIMA — a API não aceita intervalo de datas
# ---------------------------------------------------------------------------
def test_trava_tos_assinatura_nao_aceita_intervalo_de_datas() -> None:
    parametros = set(inspect.signature(ensure_snapshot).parameters)
    assert parametros == {"session", "data_ref", "hoje", "transport"}
    proibidos = {"data_inicio", "data_fim", "inicio", "fim", "datas", "janela_dias", "dias"}
    assert parametros.isdisjoint(proibidos)


def test_trava_tos_documentada_no_modulo_e_na_funcao() -> None:
    assert "ToS ANBIMA" in (anbima_ettj.__doc__ or "")
    docstring_normalizada = " ".join((ensure_snapshot.__doc__ or "").split())
    assert "não aceita intervalo de datas" in docstring_normalizada


# ---------------------------------------------------------------------------
# Alarme de layout — cabeçalho/tabela mudou na fonte -> abstenção, nunca chute
# ---------------------------------------------------------------------------
def test_layout_sem_tabela_de_vertices_alarma_e_abstem(sessao: Session) -> None:
    csv_sem_tabela = "09/07/2026;Beta 1;Beta 2\nPREFIXADOS;0,14;-0,03\n".encode("latin-1")
    with pytest.raises(DadoNaoEncontrado, match="layout inesperado"):
        ensure_snapshot(sessao, DIA_REAL, transport=_transport({"09/07/2026": csv_sem_tabela}))
    assert _linhas(sessao) == []


def test_layout_cabecalho_renomeado_alarma_e_abstem(sessao: Session) -> None:
    csv_renomeado = (
        "09/07/2026;Beta 1\n\nETTJ Inflação Implicita (IPCA)\n"
        "Prazos;IPCA;PREF;II\n126;9,0792;13,8285;4,3539\n"
    ).encode("latin-1")
    with pytest.raises(DadoNaoEncontrado, match="layout inesperado"):
        ensure_snapshot(sessao, DIA_REAL, transport=_transport({"09/07/2026": csv_renomeado}))


# ---------------------------------------------------------------------------
# Degradação sem tabela (correção A13) — abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
def test_sem_tabela_curva_snapshot_degrada_para_abstencao(sessao_sem_tabela: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="curva_snapshot indisponível"):
        ensure_snapshot(sessao_sem_tabela, DIA_REAL, transport=_transport({"09/07/2026": CSV_REAL}))
    # O SAVEPOINT foi desfeito: a transação externa segue utilizável.
    assert list(sessao_sem_tabela.execute(select(Fonte)).scalars().all()) == []
