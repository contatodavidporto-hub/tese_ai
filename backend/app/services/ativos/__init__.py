"""Pacote de classes de ativo — registry + identidade + perfis (D4/D5/D8).

- ``base``: dataclass de metadados, ``CLASSES`` (registry) e o contrato
  ``PerfilClasse`` que os perfis cumprem (etapa 11).
- ``identidade``: ``resolver_classe(codigo, session)`` — classifica o código
  pedido em 'acao'|'fii'|'renda_fixa' sem rede (só ORM).
- ``acao``/``fii``/``renda_fixa``: PERFIS do motor por classe (ensure/ingest/
  coletar/template/elos; o mapa STN sigla<->'Tipo Titulo' vive em ``renda_fixa``).
- ``registro``: ``perfil_da_classe(classe)`` — despacho usado por gerar_tese
  (importado TARDIAMENTE por tese.py; não importar aqui para não criar ciclo).
"""

from app.services.ativos.base import CLASSES, ClasseAtivo, PerfilClasse, obter_classe
from app.services.ativos.identidade import resolver_classe

__all__ = ["CLASSES", "ClasseAtivo", "PerfilClasse", "obter_classe", "resolver_classe"]
