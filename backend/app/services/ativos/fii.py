"""Classe FII — identidade (fundo imobiliário via informes CVM).

Identidade: ticker B3 com sufixo 11 (cota) que NÃO consta em ``cvm_cadastro``
(units de ação vencem, D4) e resolve em ``fii_cadastro`` por ticker. O ticker
do cadastro vem de HEURÍSTICA de ISIN rotulada (``ticker_metodo=
'heuristica_isin'``); colisão ou sufixo 12/13 -> ticker NULL e o fundo só
resolve por CNPJ — nesse caso a identidade abstém (``DadoNaoEncontrado``),
nunca chuta.

Dados da classe: indicadores TIPADOS em ``fii_indicadores`` (PL, VP/cota,
cotas emitidas, cotistas, DY do informe — AUTO-DECLARADO pelo administrador,
NUNCA anualizar) e vacância agregada derivada com metodologia declarada
(ponderada por área, recon delta 3). Ingestão na etapa 7 (``fii_dados.py``).

Sem "Pares globais": abstenção ESTRUTURAL (D5) — a seção não existe no
template da classe. Lacunas fixas: P/VP e DY a preço de mercado (preço B3 é
licenciado) — ver ``INFO.lacunas_estruturais``.

Motor pleno da classe (coleta/template/elos) chega na etapa 11 — contrato em
``base.PerfilClasse``. NÃO implementar coleta/template aqui.
"""

from __future__ import annotations

from app.services.ativos.base import FII as INFO

CLASSE = INFO.codigo

__all__ = ["CLASSE", "INFO"]
