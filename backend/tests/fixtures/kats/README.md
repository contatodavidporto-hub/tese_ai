# KATs (Known-Answer Tests) — indicadores técnicos

Fixtures de validação numérica do `app/services/tecnica.py` (testes 100% offline).

## Conjunto 1 — CSVs `cs-*.csv` (bukosabino/ta, licença MIT)

Arquivos copiados do diretório de dados de teste do projeto
[bukosabino/ta](https://github.com/bukosabino/ta) (Technical Analysis Library in
Python, © 2020 Darío López Padial), distribuídos sob licença MIT — texto integral
em `ta_LICENSE.txt` neste diretório. Os CSVs derivam das planilhas educacionais da
StockCharts (prefixo `cs-`), com colunas intermediárias publicadas:

| Arquivo | Indicador | Convenção do KAT |
|---|---|---|
| `cs-rsi.csv` | RSI(14) | suavização Wilder (α=1/14, adjust=False) com seed=0 na 1ª barra |
| `cs-macd.csv` | MACD(12,26,9) | EMAs com seed=primeiro valor (ewm adjust=False); a coluna `MACD_signal` usa semente própria da planilha (EMA(9) desde a 1ª linha da `MACD_line`) — o teste compara a cauda (linha ≥ 80), onde o esquecimento exponencial (α=0,2) reduz o efeito da semente a < 2e-6 |
| `cs-bbands.csv` | Bollinger(20,2) | desvio-padrão POPULACIONAL (ddof=0) |
| `cs-soo.csv` | Estocástico %K(14) + %D=SMA(3) | fast |
| `cs-percentr.csv` | Williams %R(14) | padrão (−100..0) |
| `cs-accum.csv` | A/D line (MFM, MFV, acumulado) | MFM=0 quando High==Low |

## Conjunto 2 — números transcritos do Tulip Indicators

Os casos numéricos de `sma`, `ema`, `rsi`, `macd`, `bbands`, `stoch`, `willr` e
`ad` do arquivo de smoke-tests do [Tulip Indicators](https://tulipindicators.org/)
foram transcritos como `parametrize` diretamente em `tests/test_tecnica.py`
(APENAS os vetores de entrada/saída publicados, precisão de 3 casas decimais —
nenhum código LGPL foi copiado).

Convenções que diferem entre produção e KAT são validadas pelo modo
correspondente do helper (ex.: EMA `seed="primeiro"`), documentado em cada teste.
Validação cruzada: os DOIS conjuntos devem passar.
