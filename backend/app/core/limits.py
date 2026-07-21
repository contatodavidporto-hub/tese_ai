"""Guardas de capacidade para a geração de tese (Fase 1 de blindagem).

Duas defesas contra abuso/DoS de custo no endpoint que chama o LLM caro:

- **Cap de concorrência** (`GENERATION_SLOTS`): um `BoundedSemaphore` limita
  quantas gerações rodam ao mesmo tempo no processo. Protege o pool de conexões
  do SQLAlchemy e evita que N BackgroundTasks pesadas subam o custo em paralelo.
- **Teto de custo diário** (`CustoDiarioTracker`): acumula o custo estimado de
  LLM por dia (UTC) e recusa novas gerações quando o teto é atingido — o motor
  ABSTÉM (degradação graciosa) em vez de gastar sem limite.

Ambos são **por processo** (memória): uma defesa pragmática e testável, não uma
contabilidade global multi-worker (isso exigiria Redis/DB — roadmap). O teto real
de custo autoritativo continua no Langfuse quando configurado.
"""

from __future__ import annotations

import datetime as dt
import threading

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConcorrenciaExcedida(RuntimeError):
    """Todas as vagas de geração estão ocupadas — recuar e tentar depois."""


class TetoCustoExcedido(RuntimeError):
    """O teto de custo de LLM do dia foi atingido — abster nesta geração."""


class _SlotGeracao:
    """Semáforo de concorrência com aquisição não-bloqueante (context manager).

    Sem estado Python por-aquisição: o ``BoundedSemaphore`` é a ÚNICA fonte de
    verdade. Um flag de instância (``_adquirido``) seria compartilhado entre
    threads na instância-módulo `GENERATION_SLOTS` e **vazaria vagas** em
    gerações sobrepostas — a 2ª saída veria o flag já zerado pela 1ª e não
    liberaria (o semáforo caía monotonicamente até 0 e travava TODA geração
    até o restart). ``__exit__`` só roda após um ``__enter__`` bem-sucedido
    (contrato do ``with``), então liberar incondicionalmente é balanceado.
    """

    def __init__(self, vagas: int) -> None:
        self._sem = threading.BoundedSemaphore(max(1, vagas))

    def __enter__(self) -> _SlotGeracao:
        # Não-bloqueante: se não há vaga, falha rápido (o caller abstém) em vez de
        # empilhar requisições e travar o processo. Ao levantar aqui, o `with` NÃO
        # chama __exit__ — nenhuma release espúria acontece.
        if not self._sem.acquire(blocking=False):
            raise ConcorrenciaExcedida("limite de gerações simultâneas atingido")
        return self

    def __exit__(self, *exc: object) -> None:
        self._sem.release()


class CustoDiarioTracker:
    """Acumulador thread-safe do custo de LLM por dia (UTC). Reset automático."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dia: dt.date | None = None
        self._acumulado_usd = 0.0

    def _hoje(self) -> dt.date:
        return dt.datetime.now(dt.UTC).date()

    def verificar(self, teto_usd: float) -> None:
        """Levanta `TetoCustoExcedido` se o dia já atingiu o teto. Teto 0 = desligado."""
        if teto_usd <= 0:
            return
        with self._lock:
            hoje = self._hoje()
            if self._dia != hoje:  # virou o dia -> zera
                self._dia = hoje
                self._acumulado_usd = 0.0
            if self._acumulado_usd >= teto_usd:
                raise TetoCustoExcedido(
                    f"teto de custo diário de LLM atingido ({self._acumulado_usd:.2f} "
                    f">= {teto_usd:.2f} USD)"
                )

    def registrar(self, custo_usd: float | None) -> None:
        """Soma o custo de uma geração ao acumulado do dia."""
        if not custo_usd or custo_usd <= 0:
            return
        with self._lock:
            hoje = self._hoje()
            if self._dia != hoje:
                self._dia = hoje
                self._acumulado_usd = 0.0
            self._acumulado_usd += custo_usd
            logger.info("custo_llm_acumulado_dia", dia=str(hoje), usd=round(self._acumulado_usd, 4))


# Instâncias-módulo (por processo). Inicializadas do settings uma vez.
_settings = get_settings()
GENERATION_SLOTS = _SlotGeracao(_settings.tese_max_concorrencia)
CUSTO_DIARIO = CustoDiarioTracker()
