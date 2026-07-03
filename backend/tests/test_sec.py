"""Testes offline do conector SEC EDGAR + seleção de pares (sem rede)."""

from __future__ import annotations

import json

from app.services import setores
from app.services.sec import extrair_fundamentos, parse_company_tickers


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
    achados = extrair_fundamentos(json.dumps(facts).encode())
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
    achados = extrair_fundamentos(facts)
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
    achados = extrair_fundamentos(facts)
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
    assert extrair_fundamentos(facts) == []  # trimestral não entra


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
