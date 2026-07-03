"""Seleção de pares globais por setor — INTERPRETAÇÃO curada, não par oficial.

Achado A3 do red-team: mapear setor B3 -> pares globais é um JULGAMENTO. Por isso:
- é uma configuração VERSIONADA (critério + data), não um dict anônimo;
- cada `Par` grava `criterio_selecao` e uma `Fonte` que aponta para o CRITÉRIO
  interno (não para a URL da SEC), para o motor rotular como interpretação;
- setores AMBÍGUOS (holding/conglomerado/participações) ABSTÊM — não força pares
  enganosos com verniz de fonte.
"""

from __future__ import annotations

CRITERIO_VERSAO = "v1 (2026-06-30)"

# setor B3 (substring, minúsculo) -> {sic, pares: [(ticker_ext, nome_ext)]}.
# Pares = grandes comparáveis globais do setor (US-GAAP 10-K ou IFRS 20-F na SEC).
PARES_POR_SETOR: dict[str, dict] = {
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
    """Rótulo que marca o par como SELEÇÃO interpretativa (não par oficial)."""
    return (
        f"Comparável setorial SELECIONADO (interpretação) — "
        f"critério interno {CRITERIO_VERSAO}, SIC {sic}"
    )
