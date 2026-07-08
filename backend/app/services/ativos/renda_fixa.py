"""Classe RENDA_FIXA — identidade do Tesouro Direto (gramática TD-* + mapa STN).

Gramática do código de tese: ``TD-<SIGLA>-<ANO>`` (ex.: TD-IPCA-2035). A sigla
identifica a FAMÍLIA do título e o ano identifica o vencimento; a resolução
ano -> ``data_vencimento`` concreta é responsabilidade do serviço do Tesouro
(etapa 8, ``tesouro.py``): SELECT DISTINCT de ``data_vencimento`` em
``titulos_publicos`` (0 -> DadoNaoEncontrado; 2+ vencimentos distintos no ano
-> abstém) e ``max(data_base)`` por (tipo, vencimento) — o CSV da STN NÃO é
cronológico (reconciliação, delta 5). Aqui fica só a IDENTIDADE da classe.

O mapa sigla <-> 'Tipo Titulo' (coluna do CSV da STN) é COMPLETO para os
títulos vivos do Tesouro Direto (verificado no CSV real, recon delta 5) e
testado em ``tests/test_identidade.py``. Tipo fora do mapa -> fora do escopo
(abstém com lacuna; nunca resolve para "o título mais parecido").

Motor pleno da classe (coleta/template/elos) chega na etapa 11 — o contrato
está em ``base.PerfilClasse``. NÃO implementar coleta aqui.
"""

from __future__ import annotations

import re

from app.services.ativos.base import RENDA_FIXA as INFO

CLASSE = INFO.codigo

# Gramática dos códigos aceitos (D4): TD-(sigla)-(ano de 4 dígitos, 19xx/20xx).
# grupo 1 = sigla da família; grupo 2 = ano do vencimento.
TD_CODIGO_RE = re.compile(r"^TD-(PRE|PREJ|SELIC|IPCA|IPCAJ|IGPMJ|RENDA|EDUCA)-((?:19|20)\d{2})$")

# Mapa COMPLETO sigla -> 'Tipo Titulo' (nome oficial no CSV da STN,
# tesourotransparente.gov.br). Fonte de verdade única — o tesouro.py (etapa 8)
# resolve TD-código -> título com ESTE mapa; errar aqui resolveria para o
# título errado (premissa validada no recon delta 5).
SIGLA_PARA_TIPO: dict[str, str] = {
    "PRE": "Tesouro Prefixado",
    "PREJ": "Tesouro Prefixado com Juros Semestrais",
    "SELIC": "Tesouro Selic",
    "IPCA": "Tesouro IPCA+",
    "IPCAJ": "Tesouro IPCA+ com Juros Semestrais",
    "IGPMJ": "Tesouro IGPM+ com Juros Semestrais",
    "RENDA": "Tesouro Renda+ Aposentadoria Extra",
    "EDUCA": "Tesouro Educa+",
}

# Inverso 'Tipo Titulo' -> sigla. Bijeção garantida por teste (nenhum tipo
# oficial duplicado) — usado para rotular/derivar o código a partir do CSV.
TIPO_PARA_SIGLA: dict[str, str] = {tipo: sigla for sigla, tipo in SIGLA_PARA_TIPO.items()}

__all__ = ["CLASSE", "INFO", "SIGLA_PARA_TIPO", "TD_CODIGO_RE", "TIPO_PARA_SIGLA"]
