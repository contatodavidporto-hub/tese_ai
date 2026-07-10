"""Identidade de ativo (D4): classifica o código pedido em 'acao'|'fii'|'renda_fixa'.

SEM REDE: só a gramática dos códigos + consultas ORM na ``session``. Ordem de
decisão (determinística, testada em ``tests/test_identidade.py``):

1. Gramática TD-* (``renda_fixa.TD_CODIGO_RE``) -> 'renda_fixa'. Aqui só se
   classifica e devolve família+ano; a resolução ano -> ``data_vencimento``
   (SELECT DISTINCT em ``titulos_publicos``) é do serviço do Tesouro (etapa 8).
2. Ticker B3 com sufixo numérico 11-13 (AMBÍGUO: unit de ação x cota de FII):
   consulta ``cvm_cadastro`` PRIMEIRO — units (SANB11/TAEE11/BPAC11) vencem ->
   'acao'; em seguida o seed offline ``TICKER_CD_CVM`` (mesma autoridade do
   ``resolve_ticker``); senão ``fii_cadastro`` por ticker -> 'fii'; nenhum ->
   ``DadoNaoEncontrado`` (mensagem estável — abstém, nunca chuta).
3. Demais sufixos B3 -> 'acao' direto (3-8 é o caso típico; BDRs 31-39,
   direitos e recibos seguem o comportamento legado: tudo era ação, e
   ``cvm_cadastro.resolve_ticker`` permanece a autoridade final na geração).

Código fora das duas gramáticas também levanta ``DadoNaoEncontrado`` (defesa
em profundidade — o schema da API já rejeita com 422 antes de chegar aqui).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import CvmCadastro, FiiCadastro
from app.services.ativos import renda_fixa
from app.services.dados import TICKER_CD_CVM, DadoNaoEncontrado

# Mesmo padrão B3 do schema/cvm_cadastro, com o SUFIXO numérico capturado —
# é ele que desambigua unit (ação) x cota de FII.
_TICKER_B3_RE = re.compile(r"^([A-Z][A-Z0-9]{3})([0-9]{1,2})B?$")

# Sufixos ambíguos na B3: 11 = unit OU cota de FII; 12/13 = recibos/sobras de
# cota (só existem no universo de fundos/units) — exigem consulta ao cadastro.
_SUFIXOS_AMBIGUOS = frozenset({"11", "12", "13"})


def resolver_classe(codigo: str, session: Session | None) -> tuple[str, dict[str, object]]:
    """Resolve o código pedido para (classe, payload de identidade).

    ``payload`` documenta COMO a classe foi decidida (rastreabilidade):
    - renda_fixa: {codigo, sigla, familia, ano} — família = 'Tipo Titulo' STN.
    - acao: {codigo, metodo: 'sufixo_b3'|'cvm_cadastro'|'seed_cvm', cd_cvm?}.
    - fii: {codigo, metodo: 'fii_cadastro', cnpj, nome}.

    ``session=None`` pula as consultas (útil em teste/offline): códigos que
    exigiriam cadastro (sufixo 11-13) abstêm — nunca inventa.
    """
    alvo = (codigo or "").strip().upper()

    m_td = renda_fixa.TD_CODIGO_RE.fullmatch(alvo)
    if m_td is not None:
        sigla, ano = m_td.group(1), int(m_td.group(2))
        return "renda_fixa", {
            "codigo": alvo,
            "sigla": sigla,
            "familia": renda_fixa.SIGLA_PARA_TIPO[sigla],
            "ano": ano,
        }

    m_b3 = _TICKER_B3_RE.fullmatch(alvo)
    if m_b3 is None:
        raise DadoNaoEncontrado(
            f"código {alvo} não reconhecido (nem ticker B3 nem código TD) — dado não encontrado"
        )

    sufixo = m_b3.group(2)
    if sufixo not in _SUFIXOS_AMBIGUOS:
        return "acao", {"codigo": alvo, "metodo": "sufixo_b3"}

    # Sufixo 11-13: cvm_cadastro VENCE (protege units SANB11/TAEE11/BPAC11).
    if session is not None:
        unit = (
            session.execute(select(CvmCadastro).where(CvmCadastro.comneg == alvo).limit(1))
            .scalars()
            .first()
        )
        if unit is not None:
            return "acao", {"codigo": alvo, "metodo": "cvm_cadastro", "cd_cvm": unit.cd_cvm}

    seed = TICKER_CD_CVM.get(alvo)
    if seed is not None:
        return "acao", {"codigo": alvo, "metodo": "seed_cvm", "cd_cvm": seed[0]}

    if session is not None:
        fundo = (
            session.execute(select(FiiCadastro).where(FiiCadastro.ticker == alvo).limit(1))
            .scalars()
            .first()
        )
        if fundo is not None:
            return "fii", {
                "codigo": alvo,
                "metodo": "fii_cadastro",
                "cnpj": fundo.cnpj,
                "nome": fundo.nome,
            }

    raise DadoNaoEncontrado(
        f"código {alvo} (sufixo {sufixo}) não consta em cvm_cadastro nem em "
        "fii_cadastro — dado não encontrado"
    )


__all__ = ["resolver_classe"]
