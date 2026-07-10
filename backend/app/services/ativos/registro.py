"""Registro de PERFIS por classe (etapa 11) — o despacho do motor de tese.

`tese.gerar_tese` resolve o perfil pela classe da `Tese` (``classe_ativo``;
NULL = 'acao', legado byte-idêntico) e conduz o mesmo fluxo para toda classe:
``ensure_ativo -> (precisa_ingest? -> ingest) -> coletar -> system_prompt ->
sintetizar (Opus/Citations) -> montar_elos -> gate``. Cada perfil é um MÓDULO
que cumpre o contrato ``base.PerfilClasse`` (duck typing documentado).

Import: `tese.py` importa este módulo TARDIAMENTE (dentro de gerar_tese) e os
perfis importam `tese` tardiamente dentro das funções — sem ciclo de import.
"""

from __future__ import annotations

from types import ModuleType

from app.services.ativos import acao, fii, renda_fixa

PERFIS: dict[str, ModuleType] = {
    acao.CLASSE: acao,
    fii.CLASSE: fii,
    renda_fixa.CLASSE: renda_fixa,
}


def perfil_da_classe(classe: str | None) -> ModuleType:
    """Perfil da classe ('acao'|'fii'|'renda_fixa'); NULL = 'acao' (legado).

    Classe desconhecida é bug interno (a identidade só grava códigos do
    registry) — ValueError, não abstenção.
    """
    codigo = classe or acao.CLASSE
    try:
        return PERFIS[codigo]
    except KeyError as exc:
        raise ValueError(f"classe de ativo desconhecida: {codigo!r}") from exc


__all__ = ["PERFIS", "perfil_da_classe"]
