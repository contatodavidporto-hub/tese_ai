"""Classe ACAO — identidade (legado byte-idêntico).

Identidade: ticker B3 (raiz de 4 alfanuméricos iniciada por letra + 1-2
dígitos + sufixo 'B' opcional de balcão). Sufixos numéricos 11-13 são
AMBÍGUOS (units SANB11/TAEE11/BPAC11 vs cotas de FII): a identidade consulta
``cvm_cadastro`` PRIMEIRO — units vencem (D4) — ver
``identidade.resolver_classe``. A autoridade final do cadastro na geração
segue sendo ``cvm_cadastro.resolve_ticker`` (com seed offline).

Semântica de persistência: ``teses.classe_ativo`` NULL = 'acao' (migração
0005) — o caminho legado da ação permanece byte-idêntico.

Planos de contas 'banco'/'seguradora' são variações DENTRO desta classe (D4:
'financeira' não é classe); as lacunas do plano (ex.: Índice de Basileia) são
declaradas pelo plano no template, não pela classe.

Motor pleno da classe (coleta DFP/ITR, template, elos D5 com pares globais)
chega na etapa 11 — contrato em ``base.PerfilClasse``. NÃO implementar aqui.
"""

from __future__ import annotations

from app.services.ativos.base import ACAO as INFO

CLASSE = INFO.codigo

__all__ = ["CLASSE", "INFO"]
