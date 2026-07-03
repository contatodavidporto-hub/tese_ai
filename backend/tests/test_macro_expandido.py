"""Testa que a camada macro doméstica (D3) foi ampliada com IPCA e IGP-M.

Sem rede: inspeciona o mapa de séries usado por ingest_macro (via introspecção
do código-fonte da função) para garantir os códigos SGS corretos e sem ambiguidade.
"""

from __future__ import annotations

import inspect

from app.services import dados


def test_ingest_macro_inclui_ipca_433_e_igpm_189() -> None:
    fonte = inspect.getsource(dados.ingest_macro)
    # IPCA série 433 e IGP-M série 189 (códigos SGS estáveis do BCB).
    assert '"IPCA_MENSAL": (433,' in fonte
    assert '"IGP_M_MENSAL": (189,' in fonte


def test_ingest_macro_mantem_selic_diaria_separada_da_meta() -> None:
    # Anti-alucinação: a Selic diária (% a.d.) não pode ser confundida com a meta anual.
    fonte = inspect.getsource(dados.ingest_macro)
    assert '"SELIC_DIARIA": (11,' in fonte
    assert '"SELIC_META_ANUAL": (432,' in fonte
