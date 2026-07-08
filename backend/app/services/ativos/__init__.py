"""Pacote de classes de ativo — registry + identidade (BLOCO C, D4/D5).

- ``base``: dataclass de metadados, ``CLASSES`` (registry) e o contrato
  ``PerfilClasse`` que o motor por classe cumprirá (etapa 11).
- ``identidade``: ``resolver_classe(codigo, session)`` — classifica o código
  pedido em 'acao'|'fii'|'renda_fixa' sem rede (só ORM).
- ``acao``/``fii``/``renda_fixa``: constantes de identidade de cada classe
  (o mapa STN sigla<->'Tipo Titulo' vive em ``renda_fixa``).
"""

from app.services.ativos.base import CLASSES, ClasseAtivo, PerfilClasse, obter_classe
from app.services.ativos.identidade import resolver_classe

__all__ = ["CLASSES", "ClasseAtivo", "PerfilClasse", "obter_classe", "resolver_classe"]
