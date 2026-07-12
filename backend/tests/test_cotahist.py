"""Testes offline do conector COTAHIST (app.services.cotahist).

Sem rede real (httpx.MockTransport pula a allowlist — padrão de test_fii_dados)
e sem Postgres: SQLite em memória com as tabelas dos modelos. A fixture
`tests/fixtures/cotahist/cotahist_amostra.txt` é o RECORTE REAL do COTAHIST
diário de 09/07/2026 (header + 9 papéis, colhido em 2026-07-10): sanity conhecido
PETR4 fechou 39,21 e HGLG11 148,78 — os offsets do layout oficial
(SeriesHistoricas_Layout.pdf) são validados contra esse ground truth.

Cobertura das correções do red-team:
- A9  — filtro CODBDI {02,12,14} (S2NA34=BDR/34 sai; BOVA11=ETF/14 entra) e alarme
        "sem série de preço na B3" quando o arquivo está ok e o ticker tem 0 linhas.
- A13 — tabela `precos_diarios` ausente degrada para DadoNaoEncontrado, nunca 500.
"""

from __future__ import annotations

import datetime as dt
import io
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.models import Fonte, PrecoDiario
from app.services import cotahist
from app.services.cotahist import (
    _dias_uteis_atras,
    _parse_registros,
    ensure_precos,
    ingest_arquivo_diario,
    ingest_backfill,
)
from app.services.dados import DadoNaoEncontrado

HOJE = dt.date(2026, 7, 10)  # sexta-feira; pregão da amostra = 2026-07-09 (fresco)
PREGAO_AMOSTRA = dt.date(2026, 7, 9)

FIXTURES = Path(__file__).parent / "fixtures" / "cotahist"
AMOSTRA = (FIXTURES / "cotahist_amostra.txt").read_text(encoding="latin-1")

# Linha REAL do PETR4 na amostra (base para redatar pregões sintéticos no backfill).
_LINHA_PETR4 = next(li for li in AMOSTRA.splitlines() if li[12:24].strip() == "PETR4")
_TRAILER = "99COTAHIST.2026BOVESPA 20260709" + " " * 214  # 245 chars, TIPREG=99


def _url_diario(data: dt.date) -> str:
    return cotahist.COTAHIST_DIARIO_URL.format(dia=data.day, mes=data.month, ano=data.year)


def _url_mensal(ano: int, mes: int) -> str:
    return cotahist.COTAHIST_MENSAL_URL.format(mes=mes, ano=ano)


def _linha_redatada(data: dt.date, linha: str = _LINHA_PETR4) -> str:
    """Cópia da linha real com a DATA DO PREGÃO (posições 3-10) trocada."""
    return linha[:2] + data.strftime("%Y%m%d") + linha[10:]


def _zip_cotahist(texto: str, membro: str = "COTAHIST.TXT") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(membro, texto.encode("latin-1"))
    return buf.getvalue()


def _zip_mensal_petr4(datas: list[dt.date]) -> bytes:
    corpo = "\n".join([AMOSTRA.splitlines()[0], *(_linha_redatada(d) for d in datas), _TRAILER])
    return _zip_cotahist(corpo)


def _transport(mapa: dict[str, bytes], chamadas: list[str] | None = None) -> httpx.MockTransport:
    """Serve os ZIPs por URL exata; fora do mapa -> 404 (feriado/mês sem arquivo)."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if chamadas is not None:
            chamadas.append(url)
        corpo = mapa.get(url)
        if corpo is None:
            return httpx.Response(404, text="nao existe")
        return httpx.Response(200, content=corpo)

    return httpx.MockTransport(handler)


# --- Sessão SQLite em memória (padrão de test_fii_dados) ----------------------
@pytest.fixture()
def sessao() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    meta = MetaData()
    for tabela in (Fonte.__table__, PrecoDiario.__table__):
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


def _seed_preco(sessao: Session, ticker: str, data: dt.date, fechamento: float = 10.0) -> None:
    fonte = Fonte(url="https://bvmf.bmfbovespa.com.br/x.zip", descricao="seed", dt_referencia=data)
    sessao.add(fonte)
    sessao.flush()
    sessao.add(
        PrecoDiario(
            ticker=ticker,
            data_pregao=data,
            fechamento=fechamento,
            codbdi=2,
            fonte_id=fonte.id,
        )
    )
    sessao.flush()


def _precos_db(sessao: Session, ticker: str) -> list[PrecoDiario]:
    return list(
        sessao.execute(
            select(PrecoDiario)
            .where(PrecoDiario.ticker == ticker)
            .order_by(PrecoDiario.data_pregao)
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Parser posicional — offsets validados contra o pregão REAL de 09/07/2026
# ---------------------------------------------------------------------------
def test_parser_offsets_petr4_ground_truth() -> None:
    regs = {r.ticker: r for r in _parse_registros(AMOSTRA)}
    petr4 = regs["PETR4"]
    assert petr4.data_pregao == PREGAO_AMOSTRA
    assert petr4.codbdi == 2
    assert petr4.abertura == pytest.approx(39.74)
    assert petr4.maxima == pytest.approx(39.98)
    assert petr4.minima == pytest.approx(38.89)
    assert petr4.fechamento == pytest.approx(39.21)  # sanity conhecido do pregão
    assert petr4.negocios == 44428
    assert petr4.volume == pytest.approx(1_312_684_500.00)  # VOLTOT com 2 decimais implícitos


def test_parser_offsets_hglg11_fii_e_bova11_etf() -> None:
    regs = {r.ticker: r for r in _parse_registros(AMOSTRA)}
    hglg = regs["HGLG11"]
    assert hglg.codbdi == 12  # FII
    assert hglg.fechamento == pytest.approx(148.78)  # sanity conhecido do pregão
    bova = regs["BOVA11"]
    assert bova.codbdi == 14  # ETF entra no filtro (correção A9)
    assert bova.fechamento == pytest.approx(169.80)


def test_parser_filtra_codbdi_fora_da_lista() -> None:
    # S2NA34 é BDR (CODBDI 34, TPMERC 010): fora de {02,12,14} -> excluído.
    tickers = {r.ticker for r in _parse_registros(AMOSTRA)}
    assert "S2NA34" not in tickers
    assert tickers == {"ALUP11", "BOVA11", "ITUB4", "SAPR11", "PETR4", "HGLG11", "VALE3", "TAEE11"}


def test_parser_filtra_tpmerc_nao_a_vista() -> None:
    # Mesma linha real do PETR4 com TPMERC trocado para 070 (termo) -> excluída.
    linha_termo = _LINHA_PETR4[:24] + "070" + _LINHA_PETR4[27:]
    assert list(_parse_registros(linha_termo)) == []


def test_parser_ignora_header_trailer_e_linha_curta() -> None:
    texto = "\n".join([AMOSTRA.splitlines()[0], _TRAILER, "01lixo-curto", _LINHA_PETR4])
    regs = list(_parse_registros(texto))
    assert [r.ticker for r in regs] == ["PETR4"]


# ---------------------------------------------------------------------------
# ingest_arquivo_diario — só tickers rastreados; 404 = feriado, sem erro
# ---------------------------------------------------------------------------
def test_ingest_diario_grava_somente_tickers_rastreados(sessao: Session) -> None:
    mapa = {_url_diario(PREGAO_AMOSTRA): _zip_cotahist(AMOSTRA)}
    n = ingest_arquivo_diario(
        sessao, PREGAO_AMOSTRA, tickers={"PETR4", "HGLG11"}, transport=_transport(mapa)
    )
    assert n == 2
    assert [p.ticker for p in _precos_db(sessao, "PETR4")] == ["PETR4"]
    assert _precos_db(sessao, "VALE3") == []  # está no arquivo, mas NÃO é rastreado
    petr4 = _precos_db(sessao, "PETR4")[0]
    assert float(petr4.fechamento) == pytest.approx(39.21)
    assert petr4.codbdi == 2
    assert petr4.negocios == 44428
    assert float(petr4.volume) == pytest.approx(1_312_684_500.00)


def test_ingest_diario_fonte_tem_url_do_zip_data_e_rotulos(sessao: Session) -> None:
    url = _url_diario(PREGAO_AMOSTRA)
    transport = _transport({url: _zip_cotahist(AMOSTRA)})
    ingest_arquivo_diario(sessao, PREGAO_AMOSTRA, tickers={"PETR4"}, transport=transport)
    preco = _precos_db(sessao, "PETR4")[0]
    assert preco.fonte_id is not None  # sem fonte não é fato
    fonte = sessao.get(Fonte, preco.fonte_id)
    assert fonte is not None
    assert fonte.url == url
    assert fonte.dt_referencia == PREGAO_AMOSTRA
    assert "B3 — COTAHIST (dados de fim de dia)" in fonte.descricao
    assert "preços não ajustados por proventos" in fonte.descricao  # rótulo obrigatório


def test_ingest_diario_404_feriado_retorna_zero_sem_erro(sessao: Session) -> None:
    feriado = dt.date(2026, 9, 7)
    assert ingest_arquivo_diario(sessao, feriado, tickers={"PETR4"}, transport=_transport({})) == 0
    assert _precos_db(sessao, "PETR4") == []


def test_ingest_diario_idempotente_nao_duplica(sessao: Session) -> None:
    mapa = {_url_diario(PREGAO_AMOSTRA): _zip_cotahist(AMOSTRA)}
    transport = _transport(mapa)
    ingest_arquivo_diario(sessao, PREGAO_AMOSTRA, tickers={"PETR4"}, transport=transport)
    n = ingest_arquivo_diario(sessao, PREGAO_AMOSTRA, tickers={"PETR4"}, transport=transport)
    assert n == 1  # upsert (atualiza), não duplica
    assert len(_precos_db(sessao, "PETR4")) == 1


def test_ingest_diario_sem_tickers_nao_toca_a_rede(sessao: Session) -> None:
    chamadas: list[str] = []
    n = ingest_arquivo_diario(
        sessao, PREGAO_AMOSTRA, tickers=set(), transport=_transport({}, chamadas)
    )
    assert n == 0
    assert chamadas == []  # nunca o mercado inteiro; sem alvo, sem download


def test_ingest_diario_zip_corrompido_retorna_zero(sessao: Session) -> None:
    mapa = {_url_diario(PREGAO_AMOSTRA): b"nao sou um zip"}
    n = ingest_arquivo_diario(sessao, PREGAO_AMOSTRA, tickers={"PETR4"}, transport=_transport(mapa))
    assert n == 0


# ---------------------------------------------------------------------------
# Correção L1 — teto de tamanho DESCOMPRIMIDO do membro do ZIP (zip-bomb)
# ---------------------------------------------------------------------------
def test_checar_tamanho_membro_levanta_quando_excede_o_teto() -> None:
    # Zip pequeno (poucos bytes comprimidos), mas cujo `file_size` (tamanho REAL
    # descomprimido) excede um teto de teste baixo -> levanta.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("COTAHIST.TXT", b"x" * 500)
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
        info = z.getinfo("COTAHIST.TXT")
    assert info.file_size == 500
    with pytest.raises(cotahist.ZipDescompactadoGrandeDemais, match="500"):
        cotahist._checar_tamanho_membro(info, teto=100)


def test_checar_tamanho_membro_nao_levanta_dentro_do_teto() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("COTAHIST.TXT", b"x" * 50)
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
        info = z.getinfo("COTAHIST.TXT")
    cotahist._checar_tamanho_membro(info, teto=100)  # não levanta


def test_texto_do_zip_degrada_para_none_quando_membro_excede_o_teto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fim a fim: com o teto de módulo baixado (monkeypatch), um ZIP cujo membro
    # excede o teto nunca chega a `z.read()` — degrada como zip inválido
    # (mesmo padrão de abstenção de `_texto_do_zip`), nunca estoura RAM/500.
    monkeypatch.setattr(cotahist, "_MAX_DESCOMPRIMIDO", 100)
    zip_bytes = _zip_cotahist("x" * 500)
    assert cotahist._texto_do_zip(zip_bytes) is None


def test_ingest_diario_zip_bomba_degrada_como_zip_invalido_sem_gravar(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Prova ponta a ponta pelo caminho público: um "zip-bomb" simulado (membro
    # descomprimido > teto) não grava nenhum preço, sem 500.
    monkeypatch.setattr(cotahist, "_MAX_DESCOMPRIMIDO", 100)
    mapa = {_url_diario(PREGAO_AMOSTRA): _zip_cotahist(AMOSTRA)}
    n = ingest_arquivo_diario(sessao, PREGAO_AMOSTRA, tickers={"PETR4"}, transport=_transport(mapa))
    assert n == 0
    assert _precos_db(sessao, "PETR4") == []


# ---------------------------------------------------------------------------
# ingest_backfill — arquivos MENSAIS para trás até cobrir a janela de pregões
# ---------------------------------------------------------------------------
def test_backfill_para_ao_cobrir_a_janela_sem_baixar_meses_extras(sessao: Session) -> None:
    chamadas: list[str] = []
    mapa = {
        _url_mensal(2026, 7): _zip_mensal_petr4([dt.date(2026, 7, 8), dt.date(2026, 7, 9)]),
        _url_mensal(2026, 6): _zip_mensal_petr4([dt.date(2026, 6, 10)]),
    }
    n = ingest_backfill(
        sessao, {"PETR4"}, janela_pregoes=2, hoje=HOJE, transport=_transport(mapa, chamadas)
    )
    assert n == 2
    assert chamadas == [_url_mensal(2026, 7)]  # janela coberta: junho nem é pedido
    assert [p.data_pregao for p in _precos_db(sessao, "PETR4")] == [
        dt.date(2026, 7, 8),
        dt.date(2026, 7, 9),
    ]


def test_backfill_cascata_tolera_404_de_mes_sem_arquivo(sessao: Session) -> None:
    chamadas: list[str] = []
    mapa = {
        _url_mensal(2026, 7): _zip_mensal_petr4([dt.date(2026, 7, 8), dt.date(2026, 7, 9)]),
        # 2026-06 ausente (404) -> tolerado, segue para maio
        _url_mensal(2026, 5): _zip_mensal_petr4(
            [dt.date(2026, 5, 5), dt.date(2026, 5, 6), dt.date(2026, 5, 7)]
        ),
    }
    n = ingest_backfill(
        sessao, {"PETR4"}, janela_pregoes=4, hoje=HOJE, transport=_transport(mapa, chamadas)
    )
    assert n == 5
    assert chamadas == [_url_mensal(2026, 7), _url_mensal(2026, 6), _url_mensal(2026, 5)]
    assert len(_precos_db(sessao, "PETR4")) == 5


def test_backfill_no_op_quando_serie_fresca_e_completa(sessao: Session) -> None:
    _seed_preco(sessao, "PETR4", dt.date(2026, 7, 8))
    _seed_preco(sessao, "PETR4", dt.date(2026, 7, 9))
    chamadas: list[str] = []
    n = ingest_backfill(
        sessao, {"PETR4"}, janela_pregoes=2, hoje=HOJE, transport=_transport({}, chamadas)
    )
    assert n == 0
    assert chamadas == []  # coberto e fresco: zero rede


def test_backfill_fonte_por_data_de_pregao(sessao: Session) -> None:
    datas = [dt.date(2026, 7, 8), dt.date(2026, 7, 9)]
    mapa = {_url_mensal(2026, 7): _zip_mensal_petr4(datas)}
    ingest_backfill(sessao, {"PETR4"}, janela_pregoes=2, hoje=HOJE, transport=_transport(mapa))
    fontes = {sessao.get(Fonte, p.fonte_id).dt_referencia for p in _precos_db(sessao, "PETR4")}
    assert fontes == set(datas)  # uma fonte por (URL do ZIP, data do pregão)


# ---------------------------------------------------------------------------
# ensure_precos — leitura, staleness, backfill direcionado e alarme A9
# ---------------------------------------------------------------------------
def test_ensure_precos_fresco_le_do_banco_sem_rede(sessao: Session) -> None:
    _seed_preco(sessao, "PETR4", dt.date(2026, 7, 8), 39.0)
    _seed_preco(sessao, "PETR4", dt.date(2026, 7, 9), 39.21)
    chamadas: list[str] = []
    precos = ensure_precos(
        sessao, "petr4", janela_pregoes=252, hoje=HOJE, transport=_transport({}, chamadas)
    )
    assert chamadas == []  # série fresca: zero rede
    assert [p.data_pregao for p in precos] == [dt.date(2026, 7, 8), dt.date(2026, 7, 9)]


def test_ensure_precos_vazio_dispara_backfill_e_devolve_ascendente(sessao: Session) -> None:
    mapa = {_url_mensal(2026, 7): _zip_mensal_petr4([dt.date(2026, 7, 8), dt.date(2026, 7, 9)])}
    precos = ensure_precos(sessao, "PETR4", janela_pregoes=2, hoje=HOJE, transport=_transport(mapa))
    datas = [p.data_pregao for p in precos]
    assert datas == sorted(datas)
    assert datas == [dt.date(2026, 7, 8), dt.date(2026, 7, 9)]
    assert all(p.fonte_id is not None for p in precos)  # sem fonte não é fato


def test_ensure_precos_stale_dispara_backfill_direcionado(sessao: Session) -> None:
    _seed_preco(sessao, "PETR4", dt.date(2026, 6, 10))  # > 5 dias úteis atrás -> stale
    chamadas: list[str] = []
    mapa = {_url_mensal(2026, 7): _zip_mensal_petr4([dt.date(2026, 7, 9)])}
    precos = ensure_precos(
        sessao, "PETR4", janela_pregoes=252, hoje=HOJE, transport=_transport(mapa, chamadas)
    )
    assert _url_mensal(2026, 7) in chamadas  # stale forçou o refresh
    assert precos[-1].data_pregao == dt.date(2026, 7, 9)


def test_ensure_precos_janela_limita_e_mantem_os_mais_recentes(sessao: Session) -> None:
    for dia in range(1, 11):  # 10 pregões seed, todos frescos o suficiente? não importa:
        _seed_preco(sessao, "PETR4", dt.date(2026, 7, dia))  # último = 2026-07-10 (fresco)
    precos = ensure_precos(sessao, "PETR4", janela_pregoes=5, hoje=HOJE, transport=_transport({}))
    assert [p.data_pregao for p in precos] == [dt.date(2026, 7, d) for d in range(6, 11)]


def test_ensure_precos_ticker_sem_linhas_em_arquivo_ok_alarma_a9(sessao: Session) -> None:
    # Arquivo mensal EXISTE e parseia (só PETR4) -> XXXX3 sem linha = alarme, nunca silêncio.
    mapa = {_url_mensal(2026, 7): _zip_mensal_petr4([dt.date(2026, 7, 9)])}
    with pytest.raises(DadoNaoEncontrado, match="sem série de preço na B3"):
        ensure_precos(sessao, "XXXX3", janela_pregoes=2, hoje=HOJE, transport=_transport(mapa))


def test_ensure_precos_nenhum_arquivo_acessivel_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="COTAHIST indisponível"):
        ensure_precos(sessao, "PETR4", janela_pregoes=2, hoje=HOJE, transport=_transport({}))


# ---------------------------------------------------------------------------
# Correção A13 — tabela ausente degrada para abstenção rotulada, nunca 500
# ---------------------------------------------------------------------------
class _SessaoSemTabela:
    """Dublê: qualquer execute levanta o ProgrammingError do Postgres (UndefinedTable)."""

    def __init__(self, mensagem: str) -> None:
        self._mensagem = mensagem

    def execute(self, *_args, **_kwargs):
        raise ProgrammingError("SELECT precos_diarios", {}, Exception(self._mensagem))


def test_a13_tabela_ausente_vira_dado_nao_encontrado() -> None:
    sessao = _SessaoSemTabela('relation "precos_diarios" does not exist')
    with pytest.raises(DadoNaoEncontrado, match="migração 0006"):
        ensure_precos(sessao, "PETR4", hoje=HOJE, transport=_transport({}))


def test_a13_backfill_tabela_ausente_tambem_abstem() -> None:
    sessao = _SessaoSemTabela('relation "precos_diarios" does not exist')
    mapa = {_url_mensal(2026, 7): _zip_mensal_petr4([dt.date(2026, 7, 9)])}
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        ingest_backfill(sessao, {"PETR4"}, hoje=HOJE, transport=_transport(mapa))


def test_a13_programming_error_de_outra_natureza_propaga() -> None:
    sessao = _SessaoSemTabela("syntax error at or near SELECT")
    with pytest.raises(ProgrammingError):
        ensure_precos(sessao, "PETR4", hoje=HOJE, transport=_transport({}))


# ---------------------------------------------------------------------------
# Staleness — dias úteis
# ---------------------------------------------------------------------------
def test_dias_uteis_atras_pula_fim_de_semana() -> None:
    # 2026-07-10 é sexta: 5 dias úteis para trás = sexta anterior (2026-07-03).
    assert _dias_uteis_atras(dt.date(2026, 7, 10), 5) == dt.date(2026, 7, 3)
    # De uma segunda, 1 dia útil para trás cruza o fim de semana até a sexta.
    assert _dias_uteis_atras(dt.date(2026, 7, 6), 1) == dt.date(2026, 7, 3)
