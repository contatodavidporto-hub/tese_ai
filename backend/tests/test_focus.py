"""Testes offline do conector Focus/Olinda + CDI (app.services.focus).

Sem rede/DB reais: httpx.MockTransport + sessão fake de macro_series. Cobre o
delta 6 da reconciliação: OData PERCENT-ENCODED (%24filter/%20, nunca '+'),
baseCalculo=0, falha do Olinda -> exceção limpa (FocusIndisponivel), e os
rótulos canônicos (padrão A5) das séries novas.
"""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.services import focus
from app.services.focus import (
    CDI_SERIES,
    FocusIndisponivel,
    _intervalos_sgs,
    _url_odata,
    ingest_cdi,
    ingest_focus,
)
from app.services.rotulos import ROTULOS_MACRO, rotulo_macro

_HOJE = dt.date(2026, 7, 7)


def _obs_reuniao(reuniao: str, mediana: float, base: int = 0, data: str = "2026-07-03") -> dict:
    return {
        "Indicador": "Selic",
        "Data": data,
        "Reuniao": reuniao,
        "Mediana": mediana,
        "baseCalculo": base,
    }


def _obs_anual(indicador: str, ano_ref: str, mediana: float, data: str = "2026-07-03") -> dict:
    return {
        "Indicador": indicador,
        "Data": data,
        "DataReferencia": ano_ref,
        "Mediana": mediana,
        "baseCalculo": 0,
    }


# Pesquisa mais recente = 2026-07-03; a de 2026-06-26 é antiga e a linha com
# baseCalculo=1 (99.99) é filtrada mesmo se o servidor devolver (defesa dupla).
_SELIC_JSON = {
    "value": [
        _obs_reuniao("R6/2026", 14.50),
        _obs_reuniao("R5/2026", 14.75),
        _obs_reuniao("R8/2026", 14.00),
        _obs_reuniao("R7/2026", 14.25),
        _obs_reuniao("R1/2027", 13.75),
        _obs_reuniao("R5/2026", 99.99, base=1),
        _obs_reuniao("R5/2026", 15.00, data="2026-06-26"),
    ]
}

_ANUAIS_SELIC_JSON = {
    "value": [
        _obs_anual("Selic", "2026", 14.50),
        _obs_anual("Selic", "2027", 12.50),
        _obs_anual("Selic", "2028", 11.00),
    ]
}

_ANUAIS_IPCA_JSON = {
    "value": [
        _obs_anual("IPCA", "2026", 4.30),
        _obs_anual("IPCA", "2027", 4.00),
    ]
}


# ---------------------------------------------------------------------------
# _url_odata — percent-encoding manual (delta 6: httpx params= geraria '+')
# ---------------------------------------------------------------------------
def test_url_odata_e_percent_encoded_sem_mais() -> None:
    url = _url_odata("ExpectativasMercadoSelic", "Data ge '2026-06-01' and baseCalculo eq 0", 10)
    assert "%24top=10" in url and "%24format=json" in url and "%24filter=" in url
    assert "%20" in url and "%27" in url  # espaço e aspas simples codificados
    assert "+" not in url and " " not in url  # NUNCA '+' (Olinda responde 400)
    assert url.startswith("https://olinda.bcb.gov.br/")


# ---------------------------------------------------------------------------
# ingest_focus — fixtures Olinda com sessão fake de macro_series
# ---------------------------------------------------------------------------
class _SessaoMacro:
    """Upsert em memória chaveado por (codigo, data)."""

    def __init__(self) -> None:
        self.series: dict[tuple, object] = {}

    def execute(self, stmt):
        params = stmt.compile().params
        obj = self.series.get((params["codigo_1"], params["data_1"]))
        return SimpleNamespace(scalar_one_or_none=lambda o=obj: o)

    def add(self, serie) -> None:
        self.series[(serie.codigo, serie.data)] = serie


def _stub_fontes(monkeypatch) -> list[str]:
    descricoes: list[str] = []

    def _fake(session, *, url, descricao, dt_referencia=None):
        descricoes.append(descricao)
        return uuid.uuid4()

    monkeypatch.setattr(focus, "get_or_create_fonte", _fake)
    return descricoes


def _transport_olinda() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.query  # bytes crus preservam o percent-encoding enviado
        assert b"%24filter" in query and b"%24format=json" in query and b"%24top=" in query
        assert b"+" not in query  # '+' derrubaria o Olinda com 400
        assert b"baseCalculo%20eq%200" in query  # filtro baseCalculo=0 no servidor
        path = request.url.path
        if path.endswith("ExpectativasMercadoSelic"):
            return httpx.Response(200, json=_SELIC_JSON)
        if path.endswith("ExpectativasMercadoAnuais"):
            if b"IPCA" in query:
                return httpx.Response(200, json=_ANUAIS_IPCA_JSON)
            return httpx.Response(200, json=_ANUAIS_SELIC_JSON)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_ingest_focus_grava_4_reunioes_e_fins_de_ano(monkeypatch) -> None:
    descricoes = _stub_fontes(monkeypatch)
    sess = _SessaoMacro()
    gravados = ingest_focus(sess, hoje=_HOJE, transport=_transport_olinda())
    data_pesquisa = dt.date(2026, 7, 3)

    valores = {codigo: serie.valor for (codigo, _), serie in sess.series.items()}
    # Próxima reunião (R5/2026) e as 3 seguintes; a 5ª (R1/2027) NÃO entra.
    assert valores["FOCUS_SELIC_COPOM"] == 14.75
    assert valores["FOCUS_SELIC_COPOM_2"] == 14.50
    assert valores["FOCUS_SELIC_COPOM_3"] == 14.25
    assert valores["FOCUS_SELIC_COPOM_4"] == 14.00
    # Fins de ano (corrente e seguinte); 2028 é ignorado (abstém, não estima).
    assert valores["FOCUS_SELIC_FIM_ANO"] == 14.50
    assert valores["FOCUS_SELIC_FIM_ANO_SEGUINTE"] == 12.50
    assert valores["FOCUS_IPCA_ANO"] == 4.30
    assert valores["FOCUS_IPCA_ANO_SEGUINTE"] == 4.00
    assert len(sess.series) == 8 and len(gravados) == 8
    # data = Data da PESQUISA (não da reunião/ano de referência).
    assert all(data == data_pesquisa for (_, data) in sess.series)
    # Toda fonte declara expectativa, nunca fato realizado.
    assert descricoes and all("expectativa de mercado" in d for d in descricoes)


def test_ingest_focus_ignora_base_calculo_1_e_pesquisa_antiga(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    sess = _SessaoMacro()
    ingest_focus(sess, hoje=_HOJE, transport=_transport_olinda())
    copom = sess.series[("FOCUS_SELIC_COPOM", dt.date(2026, 7, 3))]
    assert copom.valor == 14.75  # nem 99.99 (baseCalculo=1) nem 15.00 (pesquisa velha)
    assert ("FOCUS_SELIC_COPOM", dt.date(2026, 6, 26)) not in sess.series


def test_ingest_focus_e_idempotente(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    sess = _SessaoMacro()
    transport = _transport_olinda()
    ingest_focus(sess, hoje=_HOJE, transport=transport)
    antes = dict(sess.series)
    ingest_focus(sess, hoje=_HOJE, transport=transport)
    assert len(sess.series) == 8  # upsert por (codigo, data): refresh não duplica
    assert all(sess.series[k] is antes[k] for k in antes)


def test_falha_400_do_olinda_levanta_excecao_limpa(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    transport = httpx.MockTransport(lambda request: httpx.Response(400, text="Bad Request"))
    with pytest.raises(FocusIndisponivel):
        ingest_focus(_SessaoMacro(), hoje=_HOJE, transport=transport)


def test_resposta_nao_json_levanta_excecao_limpa(monkeypatch) -> None:
    _stub_fontes(monkeypatch)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"<html>erro</html>")
    )
    with pytest.raises(FocusIndisponivel):
        ingest_focus(_SessaoMacro(), hoje=_HOJE, transport=transport)


# ---------------------------------------------------------------------------
# CDI — SGS 12 / 4389 mensalizados, janela <=10 anos por consulta
# ---------------------------------------------------------------------------
def test_intervalos_sgs_fatiam_em_ate_10_anos() -> None:
    inicio, fim = dt.date(2014, 1, 1), dt.date(2026, 7, 7)  # ~12,5 anos
    intervalos = _intervalos_sgs(inicio, fim)
    assert len(intervalos) == 2
    assert intervalos[0][0] == inicio and intervalos[-1][1] == fim
    assert all((f - i).days + 1 <= 10 * 365 for i, f in intervalos)
    # contíguos, sem buraco nem sobreposição
    assert intervalos[1][0] == intervalos[0][1] + dt.timedelta(days=1)


def test_ingest_cdi_mensaliza_as_duas_series(monkeypatch) -> None:
    _stub_fontes(monkeypatch)

    def _fake_sgs(codigo: int, ini: dt.date, fim: dt.date) -> list[dict]:
        if codigo == 12:
            return [
                {"data": "15/05/2026", "valor": "0,05"},
                {"data": "29/05/2026", "valor": "0,06"},  # última obs. de maio
                {"data": "10/06/2026", "valor": "0,055"},
            ]
        assert codigo == 4389
        return [
            {"data": "15/05/2026", "valor": "14,90"},
            {"data": "29/05/2026", "valor": "14,90"},
            {"data": "10/06/2026", "valor": "14,65"},
        ]

    monkeypatch.setattr(focus, "bcb_sgs_intervalo", _fake_sgs)
    sess = _SessaoMacro()
    n = ingest_cdi(sess, meses=60, hoje=_HOJE)
    assert n == 4  # 2 meses x 2 séries (última observação de cada mês)
    assert sess.series[("CDI_DIARIO", dt.date(2026, 5, 29))].valor == 0.06
    assert sess.series[("CDI_DIARIO", dt.date(2026, 6, 10))].valor == 0.055
    assert sess.series[("CDI_ANUAL", dt.date(2026, 6, 10))].valor == 14.65
    assert CDI_SERIES["CDI_DIARIO"][0] == 12 and CDI_SERIES["CDI_ANUAL"][0] == 4389


def test_ingest_cdi_falha_de_uma_serie_e_isolada(monkeypatch) -> None:
    _stub_fontes(monkeypatch)

    def _fake_sgs(codigo: int, ini: dt.date, fim: dt.date) -> list[dict]:
        if codigo == 12:
            raise httpx.ConnectError("rede fora")
        return [{"data": "10/06/2026", "valor": "14,65"}]

    monkeypatch.setattr(focus, "bcb_sgs_intervalo", _fake_sgs)
    sess = _SessaoMacro()
    n = ingest_cdi(sess, meses=60, hoje=_HOJE)
    assert n == 1  # CDI_ANUAL persistiu mesmo com o CDI_DIARIO indisponível
    assert ("CDI_ANUAL", dt.date(2026, 6, 10)) in sess.series


# ---------------------------------------------------------------------------
# Rótulos canônicos (padrão A5) — ROTULOS_MACRO, não split de fonte.descricao
# ---------------------------------------------------------------------------
def test_rotulos_das_series_novas_presentes() -> None:
    for codigo in (
        "CDI_DIARIO",
        "CDI_ANUAL",
        "FOCUS_SELIC_COPOM",
        "FOCUS_SELIC_FIM_ANO",
        "FOCUS_SELIC_FIM_ANO_SEGUINTE",
        "FOCUS_IPCA_ANO",
        "FOCUS_IPCA_ANO_SEGUINTE",
    ):
        assert codigo in ROTULOS_MACRO, codigo


def test_rotulos_focus_declaram_expectativa_nao_fato() -> None:
    for codigo, rotulo in ROTULOS_MACRO.items():
        if codigo.startswith("FOCUS_"):
            assert "Expectativa de mercado (Focus/BCB)" in rotulo
            assert "não fato realizado" in rotulo


def test_rotulos_cdi_carregam_unidade_e_serie_sgs() -> None:
    assert rotulo_macro("CDI_DIARIO") == "CDI diário (% a.d.) — BCB SGS 12"
    assert rotulo_macro("CDI_ANUAL") == "CDI anualizado (% a.a.) — BCB SGS 4389"


def test_rotulos_cobrem_as_4_reunioes_persistidas() -> None:
    # ingest_focus grava FOCUS_SELIC_COPOM + _2.._4; todos têm rótulo canônico.
    for sufixo in ("", "_2", "_3", "_4"):
        assert f"FOCUS_SELIC_COPOM{sufixo}" in ROTULOS_MACRO
