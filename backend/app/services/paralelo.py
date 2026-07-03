"""Ingestão concorrente com falha isolada por item.

Corrige a lacuna de paralelismo (auditoria de fidelidade): os conectores de rede
(CVM, BCB, SEC, World Bank) podem buscar em paralelo. Contrato de segurança
(achado M4 do red-team): os workers fazem **apenas I/O** e devolvem dados; a
PERSISTÊNCIA (Session do SQLAlchemy, que não é thread-safe) fica no orquestrador,
fora daqui. Um item que falha vira `Resultado(ok=False, ...)` — nunca derruba o lote.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass
class Resultado[T, R]:
    """Resultado de um item: sucesso com `valor` OU falha isolada com `erro`."""

    item: T
    ok: bool
    valor: R | None = None
    erro: str | None = None


def map_concorrente[T, R](
    itens: Sequence[T],
    fn: Callable[[T], R],
    *,
    max_workers: int = 8,
    host_de: Callable[[T], str] | None = None,
    por_host_limite: int = 4,
) -> list[Resultado[T, R]]:
    """Aplica `fn` a cada item concorrentemente, preservando a ORDEM de entrada.

    - `max_workers`: teto global de threads.
    - `host_de` + `por_host_limite`: se informado, limita a concorrência por host
      (ex.: respeitar 10 req/s de data.sec.gov usando um semáforo por host).
    - Exceção de um item é capturada em `Resultado.erro`; o lote continua.
    """
    if not itens:
        return []

    semaforos: dict[str, threading.Semaphore] = {}
    trava_semaforos = threading.Lock()

    def _semaforo(host: str) -> threading.Semaphore:
        with trava_semaforos:
            sem = semaforos.get(host)
            if sem is None:
                sem = threading.Semaphore(por_host_limite)
                semaforos[host] = sem
            return sem

    def _executar(item: T) -> Resultado[T, R]:
        try:
            if host_de is not None:
                sem = _semaforo(host_de(item))
                with sem:
                    valor = fn(item)
            else:
                valor = fn(item)
            return Resultado(item=item, ok=True, valor=valor)
        except Exception as exc:  # falha isolada — não propaga
            return Resultado(item=item, ok=False, erro=f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # executor.map preserva a ordem de entrada nos resultados.
        return list(executor.map(_executar, itens))


def host_de_url(url: str) -> str:
    """Extrai o host de uma URL (para o semáforo por host)."""
    return urlsplit(url).netloc
