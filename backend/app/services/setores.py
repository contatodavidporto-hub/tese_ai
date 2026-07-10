"""Seleção de pares globais por setor — INTERPRETAÇÃO curada, não par oficial.

Achado A3 do red-team: mapear setor B3 -> pares globais é um JULGAMENTO. Por isso:
- é uma configuração VERSIONADA (critério + data), não um dict anônimo;
- cada `Par` grava `criterio_selecao` e uma `Fonte` que aponta para o CRITÉRIO
  interno (não para a URL da SEC), para o motor rotular como interpretação;
- setores AMBÍGUOS (holding/conglomerado/participações) ABSTÊM — não força pares
  enganosos com verniz de fonte.
"""

from __future__ import annotations

# Versão do critério de seleção (D9): v2 adiciona 'bancos' (SIC 6021) com a
# ressalva US-GAAP × IFRS explícita no rótulo do critério.
CRITERIO_VERSAO = "v2 (2026-07-08)"

# Fonte do CRITÉRIO (não dos dados): a classificação setorial vem do código SIC
# atribuído pela SEC a cada registrante (EDGAR company facts/submissions,
# https://www.sec.gov/cgi-bin/browse-edgar) — a lista de pares por SIC é uma
# CURADORIA interna versionada, não um índice oficial.
CRITERIO_FONTE = "classificação SIC da SEC (EDGAR) + curadoria interna versionada"

# setor B3 (substring, minúsculo) -> {sic, pares: [(ticker_ext, nome_ext)]}.
# Pares = grandes comparáveis globais do setor (US-GAAP 10-K ou IFRS 20-F na SEC).
PARES_POR_SETOR: dict[str, dict] = {
    # D9 — bancos (SIC 6021, National Commercial Banks): os 4 grandes bancos
    # comerciais dos EUA, via SEC companyfacts (já integrado). Comparação sempre
    # com ressalva US-GAAP × IFRS (bancos BR reportam em IFRS/BRGAAP-BCB).
    "banco": {
        "sic": "6021",
        "pares": [
            ("JPM", "JPMorgan Chase & Co."),
            ("BAC", "Bank of America Corporation"),
            ("C", "Citigroup Inc."),
            ("WFC", "Wells Fargo & Company"),
        ],
    },
    "petróleo": {
        "sic": "1311",
        "pares": [
            ("XOM", "Exxon Mobil Corporation"),
            ("CVX", "Chevron Corporation"),
            ("COP", "ConocoPhillips"),
            ("SHEL", "Shell plc"),
            ("BP", "BP p.l.c."),
            ("TTE", "TotalEnergies SE"),
        ],
    },
    "mineração": {
        "sic": "1000",
        "pares": [
            ("BHP", "BHP Group Limited"),
            ("RIO", "Rio Tinto Group"),
            ("FCX", "Freeport-McMoRan Inc."),
        ],
    },
    "siderurgia": {
        "sic": "3310",
        "pares": [
            ("NUE", "Nucor Corporation"),
            ("MT", "ArcelorMittal S.A."),
            ("TS", "Tenaris S.A."),
        ],
    },
    "bebidas": {
        "sic": "2080",
        "pares": [
            ("KO", "The Coca-Cola Company"),
            ("PEP", "PepsiCo, Inc."),
            ("BUD", "Anheuser-Busch InBev SA/NV"),
        ],
    },
    "aviação": {
        "sic": "4512",
        "pares": [
            ("DAL", "Delta Air Lines, Inc."),
            ("UAL", "United Airlines Holdings"),
            ("LUV", "Southwest Airlines Co."),
        ],
    },
}

# Setores sem par global inequívoco -> ABSTÉM (não compara maçã com laranja).
_SETORES_AMBIGUOS = ("holding", "conglomerad", "diversos", "participaç", "outros")


def selecionar_pares(setor: str | None) -> tuple[dict | None, str | None]:
    """Devolve ({sic, pares}, None) OU (None, motivo_da_abstenção).

    Nunca "chuta" pares: se o setor é ambíguo ou não tem lista curada, abstém.
    """
    if not setor:
        return None, "setor não informado — pares abstidos"
    s = setor.lower()
    if any(t in s for t in _SETORES_AMBIGUOS):
        return None, f"setor ambíguo ('{setor}') — pares abstidos (holding/conglomerado)"
    for chave, info in PARES_POR_SETOR.items():
        if chave in s:
            return info, None
    return None, f"sem lista curada de pares para o setor '{setor}' — abstém"


def criterio_selecao(sic: str) -> str:
    """Rótulo que marca o par como SELEÇÃO interpretativa (não par oficial).

    Gravado em `pares.criterio_selecao` e na `Fonte` do critério: inclui a
    versão datada, a fonte do critério (D9) e a ressalva US-GAAP × IFRS — a
    comparação nunca é apresentada como equivalência contábil.
    """
    return (
        f"Comparável setorial SELECIONADO (interpretação) — "
        f"critério interno {CRITERIO_VERSAO}, SIC {sic}; "
        f"fonte do critério: {CRITERIO_FONTE}; "
        f"ressalva: padrão contábil US-GAAP × IFRS e moeda podem diferir"
    )
