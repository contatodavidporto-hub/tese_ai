"""Testes offline da ingestão concorrente (app.services.paralelo)."""

from __future__ import annotations

import threading
import time

from app.services.paralelo import Resultado, host_de_url, map_concorrente


def test_preserva_ordem_de_entrada() -> None:
    itens = [1, 2, 3, 4, 5]
    res = map_concorrente(itens, lambda x: x * 10, max_workers=4)
    assert [r.valor for r in res] == [10, 20, 30, 40, 50]
    assert all(r.ok for r in res)


def test_lista_vazia_devolve_vazio() -> None:
    assert map_concorrente([], lambda x: x) == []


def test_falha_de_um_item_nao_derruba_o_lote() -> None:
    def fn(x: int) -> int:
        if x == 3:
            raise ValueError("boom")
        return x

    res = map_concorrente([1, 2, 3, 4], fn, max_workers=4)
    assert [r.ok for r in res] == [True, True, False, True]
    falha = res[2]
    assert isinstance(falha, Resultado)
    assert falha.valor is None
    assert "ValueError" in (falha.erro or "") and "boom" in (falha.erro or "")


def test_nunca_excede_max_workers() -> None:
    ativos = 0
    pico = 0
    trava = threading.Lock()

    def fn(_x: int) -> int:
        nonlocal ativos, pico
        with trava:
            ativos += 1
            pico = max(pico, ativos)
        time.sleep(0.02)
        with trava:
            ativos -= 1
        return _x

    map_concorrente(list(range(20)), fn, max_workers=4)
    assert pico <= 4


def test_semaforo_por_host_limita_concorrencia_por_host() -> None:
    ativos_por_host: dict[str, int] = {}
    pico_por_host: dict[str, int] = {}
    trava = threading.Lock()

    urls = [f"https://data.sec.gov/{i}" for i in range(6)] + [
        f"https://api.worldbank.org/{i}" for i in range(6)
    ]

    def fn(url: str) -> str:
        host = host_de_url(url)
        with trava:
            ativos_por_host[host] = ativos_por_host.get(host, 0) + 1
            pico_por_host[host] = max(pico_por_host.get(host, 0), ativos_por_host[host])
        time.sleep(0.02)
        with trava:
            ativos_por_host[host] -= 1
        return url

    map_concorrente(urls, fn, max_workers=12, host_de=host_de_url, por_host_limite=2)
    assert pico_por_host["data.sec.gov"] <= 2
    assert pico_por_host["api.worldbank.org"] <= 2


def test_host_de_url_extrai_netloc() -> None:
    assert host_de_url("https://data.sec.gov/api/xbrl/companyfacts/CIK000.json") == "data.sec.gov"
