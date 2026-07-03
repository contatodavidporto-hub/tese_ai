"""Métricas fundamentalistas DERIVADAS de contas CVM — com abstenção estrita.

Regra de ouro (anti-alucinação): uma métrica derivada só é calculada se TODOS os
seus componentes existem. Faltou um componente → devolve `None` (o chamador grava
uma lacuna "dado não encontrado"). NUNCA usa 0 como preenchimento — um 0 implícito
produziria um número errado COM fonte, o pior resultado possível (achado A1/A4).

As funções são puras: recebem `contas = {cd_conta: valor_em_reais}` (já com a escala
aplicada) e devolvem `(valor | None, codigos_usados)`. Para bancos/seguradoras, cujo
plano de contas não tem esses CD_CONTA, as métricas abstêm naturalmente (achado M2).
"""

from __future__ import annotations

# Componentes (CD_CONTA da CVM) de cada métrica derivada. Documentados para a
# fonte composta e para o teste.
COMPONENTES: dict[str, list[str]] = {
    "Dívida bruta": ["2.01.04", "2.02.01"],
    "Caixa e aplicações": ["1.01.01", "1.01.02"],
    # Dívida líquida = dívida bruta − caixa e aplicações (componentes das duas acima).
    "Dívida líquida": ["2.01.04", "2.02.01", "1.01.01", "1.01.02"],
}


def _soma(contas: dict[str, float], codigos: list[str]) -> float | None:
    """Soma se TODOS os `codigos` existem (não-None); senão abstém (None)."""
    valores = [contas.get(c) for c in codigos]
    if any(v is None for v in valores):
        return None
    return float(sum(valores))  # type: ignore[arg-type]


def divida_bruta(contas: dict[str, float]) -> tuple[float | None, list[str]]:
    """Empréstimos circulante + não circulante. Abstém se faltar componente."""
    codigos = COMPONENTES["Dívida bruta"]
    return _soma(contas, codigos), codigos


def caixa_e_aplicacoes(contas: dict[str, float]) -> tuple[float | None, list[str]]:
    codigos = COMPONENTES["Caixa e aplicações"]
    return _soma(contas, codigos), codigos


def divida_liquida(contas: dict[str, float]) -> tuple[float | None, list[str]]:
    """Dívida bruta − (caixa + aplicações). Abstém se qualquer ponta faltar."""
    db, _ = divida_bruta(contas)
    cx, _ = caixa_e_aplicacoes(contas)
    codigos = COMPONENTES["Dívida líquida"]
    if db is None or cx is None:
        return None, codigos
    return db - cx, codigos


# Registro (nome -> função) para o ingestor iterar. EBITDA e FCF livre NÃO entram
# aqui de propósito: EBITDA exige depreciação/amortização (não disponível de forma
# confiável nas demonstrações padronizadas) e FCF livre exige CapEx (sub-linha
# instável de investimento). Sem esses componentes, permanecem como LACUNA explícita
# — nunca estimados. EBIT (3.05) e FCO (6.01) entram como contas factuais diretas.
DERIVADAS = {
    "Dívida bruta (derivado)": divida_bruta,
    "Dívida líquida (derivado)": divida_liquida,
}
