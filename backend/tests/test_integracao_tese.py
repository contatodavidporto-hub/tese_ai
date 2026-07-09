"""Testes offline da integração das 5 dimensões no motor de tese (Estágio 9).

Sem rede/DB real: uma sessão FAKE devolve linhas canônicas para `_coletar`, e o
gate é exercitado com envelopes montados à mão.
"""

from __future__ import annotations

import datetime as dt

from app.models.models import Empresa, Fonte, Fundamento, MacroSerie, Par, ParFundamento
from app.services.avaliacao import avaliar_tese
from app.services.rotulos import rotulo_macro
from app.services.tese import _coletar

_HOJE = dt.date(2026, 6, 22)


class _FakeResult:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return iter(self._rows)

    def all(self):
        return self._rows


class _FakeSession:
    """Devolve fundamentos, macro e pares na ORDEM das 3 chamadas de _coletar."""

    def __init__(self, fundamentos, macro, pares, fontes):
        self._sequencia = [fundamentos, macro, pares]
        self._i = 0
        self._fontes = fontes

    def execute(self, _stmt):
        rows = self._sequencia[self._i]
        self._i += 1
        return _FakeResult(rows)

    def get(self, _model, id_):
        return self._fontes.get(id_)


# ---------------------------------------------------------------------------
# A5 — rótulo canônico por código (não por split frágil)
# ---------------------------------------------------------------------------
def test_rotulo_macro_canonico_e_fallback() -> None:
    assert rotulo_macro("IPCA_MENSAL") == "IPCA - variação mensal (% a.m.)"
    assert rotulo_macro("COMMODITY_BRENT") == "Petróleo Brent (US$/barril)"
    assert rotulo_macro("GLOBAL_TREASURY_10Y").startswith("Juro do Tesouro EUA")
    assert rotulo_macro("DESCONHECIDA", "fallback") == "fallback"


def test_coletar_usa_rotulo_canonico_e_inclui_pares() -> None:
    empresa = Empresa(nome="Petrobras", ticker="PETR4", setor="Petróleo")
    empresa.id = "emp-1"
    fundamentos = [Fundamento(conta="Receita (3.01)", valor=100.0, dt_refer=_HOJE, fonte_id="f1")]
    macro = [MacroSerie(codigo="IPCA_MENSAL", valor=0.5, data=_HOJE, fonte_id="f2")]
    pares = [
        (
            ParFundamento(
                conceito="Receita (us-gaap)",
                valor=1000.0,
                moeda="USD",
                dt_refer=_HOJE,
                fonte_id="f3",
            ),
            Par(nome_ext="Exxon Mobil", ticker_ext="XOM"),
        )
    ]
    fontes = {
        "f1": Fonte(descricao="CVM DFP", url="https://cvm", dt_referencia=_HOJE),
        # descrição propositalmente com múltiplos ": " — o split ingênuo daria rótulo errado.
        "f2": Fonte(
            descricao="Banco Central: SGS 433: IPCA cru", url="https://bcb", dt_referencia=_HOJE
        ),
        "f3": Fonte(descricao="SEC EDGAR", url="https://sec", dt_referencia=_HOJE),
    }
    itens = _coletar(_FakeSession(fundamentos, macro, pares, fontes), empresa)
    textos = [t for _f, t in itens]

    # A5: rótulo canônico do IPCA, não o "SGS 433: IPCA cru" do split.
    assert any("IPCA - variação mensal (% a.m.)" in t for t in textos)
    assert not any("SGS 433: IPCA cru" in t.split("série")[0] for t in textos if "IPCA" in t)
    # D2: par global presente, rotulado como comparável SELECIONADO.
    assert any("XOM" in t and "SELECIONADO" in t for t in textos)
    # os três itens têm fonte
    assert len(itens) == 3


# ---------------------------------------------------------------------------
# Gate estendido — elo sem fonte numa ponta bloqueia (A4)
# ---------------------------------------------------------------------------
def _envelope_base(elos: list[dict]) -> dict:
    # O markdown inclui as seções universais BLOQUEANTES (geopol/Lacunas) da
    # fase 2 — o alvo destes testes é o gate de ELOS, não o de seções.
    return {
        "markdown": (
            "# Tese\n> Não é recomendação de investimento.\n## 1. Fundamentos\nReceita citada.\n"
            "## 4. Camada geopolítica (interpretação)\nSem eventos afirmados.\n"
            "## 8. Lacunas\n- dado não encontrado: exemplo."
        ),
        "citacoes": [{"fonte": {"id": "f1", "url": "https://cvm"}}],
        "fontes": [{"id": "f1", "url": "https://cvm", "descricao": "CVM"}],
        "elos": elos,
    }


def test_gate_bloqueia_elo_sem_fonte_numa_ponta() -> None:
    laudo = avaliar_tese(
        _envelope_base(
            [{"dimensao": "câmbio→empresa", "origem_fonte_id": "f1", "destino_fonte_id": None}]
        )
    )
    assert laudo["bloqueante"] is True
    assert laudo["elos_sem_fonte"] == ["câmbio→empresa"]
    assert any("elo de correlação sem fonte" in m for m in laudo["motivos"])


def test_gate_aprova_elo_com_fonte_nas_duas_pontas() -> None:
    laudo = avaliar_tese(
        _envelope_base(
            [{"dimensao": "câmbio→empresa", "origem_fonte_id": "f1", "destino_fonte_id": "f2"}]
        )
    )
    assert laudo["elos_sem_fonte"] == []
    assert laudo["bloqueante"] is False
    assert laudo["elos_total"] == 1


def test_gate_sem_elos_nao_quebra() -> None:
    laudo = avaliar_tese(_envelope_base([]))
    assert laudo["elos_total"] == 0
    assert laudo["bloqueante"] is False
