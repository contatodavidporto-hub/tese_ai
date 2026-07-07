"""Testes offline do conector SEC EDGAR + seleção de pares (sem rede).

Os testes de mecânica de extração passam `max_idade_meses=0` (sem corte de idade)
para não depender do relógio; o corte de staleness tem testes próprios com `hoje`
fixo (caso real TTE/2017).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from types import SimpleNamespace

from app.services import sec, setores
from app.services.sec import data_corte_pares, extrair_fundamentos, parse_company_tickers


# ---------------------------------------------------------------------------
# company_tickers -> CIK 10 dígitos
# ---------------------------------------------------------------------------
def test_parse_company_tickers_normaliza_cik_para_10_digitos() -> None:
    dados = {
        "0": {"cik_str": 34088, "ticker": "XOM", "title": "EXXON MOBIL CORP"},
        "1": {"cik_str": 93410, "ticker": "cvx", "title": "CHEVRON CORP"},
    }
    mapa = parse_company_tickers(json.dumps(dados).encode())
    assert mapa["XOM"] == "0000034088"
    assert mapa["CVX"] == "0000093410"  # ticker normalizado p/ upper


# ---------------------------------------------------------------------------
# companyfacts -> extração com fallback de taxonomia + abstenção
# ---------------------------------------------------------------------------
def test_extrair_usa_gaap_pega_ultimo_ano() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"end": "2022-12-31", "val": 413680, "form": "10-K", "fp": "FY"},
                            {"end": "2023-12-31", "val": 344582, "form": "10-K", "fp": "FY"},
                        ]
                    }
                }
            }
        }
    }
    achados = extrair_fundamentos(json.dumps(facts).encode(), max_idade_meses=0)
    receita = next(a for a in achados if a["conceito"] == "Receita (us-gaap)")
    assert receita["valor"] == 344582.0  # último ano (2023 > 2022)
    assert receita["moeda"] == "USD"
    assert receita["taxonomia"] == "us-gaap"


def test_extrair_cai_para_ifrs_quando_nao_ha_us_gaap() -> None:
    facts = {
        "facts": {
            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "USD": [{"end": "2023-12-31", "val": 100, "form": "20-F", "fp": "FY"}]
                    }
                }
            }
        }
    }
    achados = extrair_fundamentos(facts, max_idade_meses=0)
    assert len(achados) == 1
    assert achados[0]["conceito"] == "Receita (ifrs-full)"  # rótulo distingue o padrão
    assert achados[0]["taxonomia"] == "ifrs-full"


def test_extrair_omite_conceito_ausente_nao_inventa() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [{"end": "2023-12-31", "val": 10, "form": "10-K", "fp": "FY"}]}
                }
            }
        }
    }
    achados = extrair_fundamentos(facts, max_idade_meses=0)
    conceitos = {a["conceito"] for a in achados}
    assert conceitos == {"Receita (us-gaap)"}  # Lucro/Ativo/PL ausentes -> abstidos


def test_extrair_ignora_fato_nao_anual() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [{"end": "2023-09-30", "val": 5, "form": "10-Q", "fp": "Q3"}]}
                }
            }
        }
    }
    assert extrair_fundamentos(facts, max_idade_meses=0) == []  # trimestral não entra


# ---------------------------------------------------------------------------
# Período mais recente por conceito + corte de staleness (caso real TTE/2017:
# a TotalEnergies abandonou ifrs-full/Revenue em 2017 e migrou para
# RevenueFromContractsWithCustomers — o "primeiro candidato que resolve"
# servia receita de 2017 como atual)
# ---------------------------------------------------------------------------
_HOJE = dt.date(2026, 7, 7)


def _facts_tte() -> dict:
    """Forma real do companyfacts da TTE: tag abandonada (2017) + tag atual (2025)."""
    return {
        "facts": {
            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "USD": [
                            {
                                "end": "2017-12-31",
                                "val": 149_099_000_000,
                                "form": "20-F",
                                "fp": "FY",
                            }
                        ]
                    }
                },
                "RevenueFromContractsWithCustomers": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-12-31",
                                "val": 195_610_000_000,
                                "form": "20-F",
                                "fp": "FY",
                            },
                            {
                                "end": "2025-12-31",
                                "val": 201_200_000_000,
                                "form": "20-F",
                                "fp": "FY",
                            },
                        ]
                    }
                },
            }
        }
    }


def test_extrair_caso_tte_vence_o_periodo_mais_recente_entre_candidatos() -> None:
    achados = extrair_fundamentos(_facts_tte(), max_idade_meses=24, hoje=_HOJE)
    receitas = [a for a in achados if a["conceito"].startswith("Receita")]
    assert len(receitas) == 1
    assert receitas[0]["dt_refer"] == "2025-12-31"  # nunca mais o 2017
    assert receitas[0]["valor"] == 201_200_000_000.0
    assert receitas[0]["tag_xbrl"] == "RevenueFromContractsWithCustomers"


def test_extrair_abstem_quando_o_periodo_mais_recente_e_velho() -> None:
    facts = _facts_tte()
    # Sem a tag atual, o melhor disponível é 2017 -> mais velho que 24 meses -> lacuna.
    del facts["facts"]["ifrs-full"]["RevenueFromContractsWithCustomers"]
    achados = extrair_fundamentos(facts, max_idade_meses=24, hoje=_HOJE)
    assert achados == []  # abstém: número velho nunca sai como atual


def test_extrair_mais_recente_vence_mesmo_cruzando_taxonomia() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [{"end": "2017-12-31", "val": 1, "form": "10-K", "fp": "FY"}]}
                }
            },
            "ifrs-full": {
                "RevenueFromContractsWithCustomers": {
                    "units": {"USD": [{"end": "2025-12-31", "val": 2, "form": "20-F", "fp": "FY"}]}
                }
            },
        }
    }
    achados = extrair_fundamentos(facts, max_idade_meses=0)
    assert len(achados) == 1
    assert achados[0]["valor"] == 2.0  # ifrs 2025 vence us-gaap 2017
    assert achados[0]["taxonomia"] == "ifrs-full"


def test_extrair_empate_de_periodo_mantem_ordem_da_lista() -> None:
    # Caso SHEL: Revenue e RevenueFromContractsWithCustomers ambos no mesmo `end`
    # -> vence o candidato anterior na lista (Revenue = receita total).
    facts = {
        "facts": {
            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "USD": [{"end": "2025-12-31", "val": 266, "form": "20-F", "fp": "FY"}]
                    }
                },
                "RevenueFromContractsWithCustomers": {
                    "units": {
                        "USD": [{"end": "2025-12-31", "val": 257, "form": "20-F", "fp": "FY"}]
                    }
                },
            }
        }
    }
    achados = extrair_fundamentos(facts, max_idade_meses=0)
    assert achados[0]["valor"] == 266.0
    assert achados[0]["tag_xbrl"] == "Revenue"


def test_data_corte_pares_aritmetica_e_desligamento() -> None:
    assert data_corte_pares(24, hoje=_HOJE) == dt.date(2024, 7, 7)
    assert data_corte_pares(6, hoje=dt.date(2026, 3, 31)) == dt.date(2025, 9, 30)  # clamp de dia
    assert data_corte_pares(0, hoje=_HOJE) is None  # 0 desliga


class _FakeSessionPersist:
    def __init__(self) -> None:
        self.deletes = 0
        self.added: list = []

    def execute(self, stmt):
        self.deletes += 1  # único Core DML no fluxo é o delete do snapshot
        return SimpleNamespace()

    def add(self, obj) -> None:
        self.added.append(obj)


def test_persistir_substitui_snapshot_e_grava_dt_referencia(monkeypatch) -> None:
    monkeypatch.setattr(sec, "data_corte_pares", lambda *a, **k: None)
    fonte_fixa = uuid.uuid4()
    descricoes: list[str] = []

    def _fake_fonte(session, url, descricao, dt_referencia):
        descricoes.append(descricao)
        assert dt_referencia is not None  # dt_referencia sempre gravada na fonte
        return fonte_fixa

    monkeypatch.setattr(sec, "get_or_create_fonte", _fake_fonte)
    sess = _FakeSessionPersist()
    par = SimpleNamespace(id=uuid.uuid4(), cik="0000879764", nome_ext="TotalEnergies SE")
    sec._persistir_par_fundamentos(sess, par, json.dumps(_facts_tte()).encode())

    assert sess.deletes == 1  # snapshot anterior removido (re-ingestão = upsert)
    assert len(sess.added) == 1
    linha = sess.added[0]
    assert linha.dt_refer == dt.date(2025, 12, 31)
    assert linha.conceito == "Receita (ifrs-full)"
    assert "RevenueFromContractsWithCustomers" in descricoes[0]  # tag XBRL auditável


# ---------------------------------------------------------------------------
# Seleção de pares (achado A3) — interpretação, com abstenção
# ---------------------------------------------------------------------------
def test_selecionar_pares_petroleo_traz_supermajors() -> None:
    info, motivo = setores.selecionar_pares("Petróleo, Gás e Biocombustíveis")
    assert motivo is None
    assert info["sic"] == "1311"
    tickers = {t for t, _ in info["pares"]}
    assert {"XOM", "CVX", "SHEL"} <= tickers


def test_selecionar_pares_holding_abstem() -> None:
    info, motivo = setores.selecionar_pares("Holdings Diversificadas")
    assert info is None
    assert "ambíguo" in motivo


def test_selecionar_pares_setor_desconhecido_abstem() -> None:
    info, motivo = setores.selecionar_pares("Setor Fictício ZZZ")
    assert info is None
    assert "sem lista curada" in motivo


def test_selecionar_pares_sem_setor_abstem() -> None:
    assert setores.selecionar_pares(None)[0] is None


def test_criterio_selecao_marca_como_interpretacao() -> None:
    rotulo = setores.criterio_selecao("1311")
    assert "interpretação" in rotulo.lower()
    assert "SIC 1311" in rotulo
