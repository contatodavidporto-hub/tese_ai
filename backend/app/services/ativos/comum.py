"""Helpers compartilhados dos perfis de classe (FII/renda fixa) — etapa 11.

Coleta de séries macro FILTRADA por códigos relevantes à classe (a lição da
Fase 2: a tese de FII/RF não pode arrastar TODA `macro_series`, nem a tese de
ação pode ser poluída por séries de renda fixa — por isso `titulos_publicos` é
tabela própria e aqui a seleção é por lista explícita + prefixo `FOCUS_`).

Formatação delega em `tese._fmt_fundamento` (import tardio — fonte única de
verdade do achado B2: valor formatado pela UNIDADE, nunca "R$" por engano).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Fonte, MacroSerie
from app.services import rotulos

# Prefixo das séries de EXPECTATIVA (Focus/BCB) — o rótulo canônico já diz
# "expectativa de mercado, não fato realizado" (rotulos.ROTULOS_MACRO).
PREFIXO_FOCUS = "FOCUS_"


def fmt_por_unidade(valor: float, unidade: str | None) -> str:
    """Formata pela UNIDADE (fonte única: `tese._fmt_fundamento`, achado B2)."""
    # Import tardio: tese.py importa o registry de perfis dentro de gerar_tese;
    # importar tese aqui no topo criaria ciclo em tempo de import.
    from app.services import tese as tese_svc

    return tese_svc._fmt_fundamento(valor, unidade)


def _codigo_relevante(codigo: str, codigos: Sequence[str]) -> bool:
    return codigo in codigos or codigo.startswith(PREFIXO_FOCUS)


def ultimo_ponto_macro(session: Session, codigos: Sequence[str]) -> dict[str, dict]:
    """Último ponto por série macro RELEVANTE: {codigo: {valor, data, fonte_id}}.

    Sempre inclui as séries `FOCUS_*` (expectativas, rotuladas). Série sem valor
    ou fora da lista não entra — nunca poluímos o contexto da classe.
    """
    macro: dict[str, dict] = {}
    for m in session.execute(
        select(MacroSerie).order_by(MacroSerie.codigo, MacroSerie.data.desc())
    ).scalars():
        if m.codigo in macro or m.valor is None:
            continue
        if not _codigo_relevante(m.codigo, codigos):
            continue
        macro[m.codigo] = {"valor": float(m.valor), "data": m.data, "fonte_id": m.fonte_id}
    return macro


def serie_macro(session: Session, codigo: str) -> list[tuple[dt.date, float]]:
    """Histórico (data, valor) de UMA série macro, ascendente — p/ co-movimento."""
    return [
        (m.data, float(m.valor))
        for m in session.execute(
            select(MacroSerie)
            .where(MacroSerie.codigo == codigo, MacroSerie.valor.is_not(None))
            .order_by(MacroSerie.data)
        ).scalars()
    ]


def coletar_macro_docs(session: Session, codigos: Sequence[str]) -> list[tuple[Fonte, str]]:
    """Documentos citáveis das séries macro relevantes (mesmo fraseado do motor
    de ação: rótulo humano CANÔNICO por código — achado A5 —, valor, referência
    e descrição da fonte). Série sem `Fonte` não vira documento (não é fato)."""
    itens: list[tuple[Fonte, str]] = []
    for codigo, ponto in sorted(ultimo_ponto_macro(session, codigos).items()):
        fonte = session.get(Fonte, ponto["fonte_id"]) if ponto["fonte_id"] else None
        if fonte is None:
            continue
        rotulo = rotulos.rotulo_macro(
            codigo,
            fonte.descricao.split(": ", 1)[-1] if fonte.descricao else None,
        )
        texto = (
            f"Indicador macro — {rotulo}: {ponto['valor']} "
            f"(série {codigo}, referência {ponto['data']}; {fonte.descricao})."
        )
        itens.append((fonte, texto))
    return itens
