"""Planos de contas por tipo de emissor — detecção por FILING e extração declarativa.

Bancos e seguradoras reusam os MESMOS CD_CONTA do plano padrão com OUTRO
significado (no ITUB, 2.03 = "Passivos Financeiros ao Custo Amortizado", não
PL) e as posições de lucro/PL VARIAM por emissor (lucro: ITUB=3.09,
BBDC/BBAS/SANB=3.11, seguradoras=3.13; PL: ITUB=2.08, demais bancos=2.07,
seguradoras=2.03). Ground truth: DFP 2025 real (dfp_cia_aberta_2025.zip). Regras:

1. O plano é detectado pelo DS_CONTA normalizado da conta FIXA 3.01 do PRÓPRIO
   filing — SETOR_ATIV do cadastro é só telemetria, nunca decide (decisão D2:
   ITSA4 tem SETOR_ATIV "Intermediação Financeira" e usa plano PADRÃO).
2. Métricas de banco/seguradora são LOCALIZADAS por DS_CONTA normalizada com
   âncoras de prefixo/nível — nunca por CD_CONTA fixo. Match ÚNICO exigido;
   0 ou 2+ candidatos não-hierárquicos → ABSTÉM (jamais soma — somar PDD com
   provisão de contingência seria número errado COM fonte).
3. Preferimos ST_CONTA_FIXA='S'; conta 'N' só entra com match único.
4. VL_CONTA == 0 em métrica de estoque/fluxo de banco/seguradora (intermediação,
   PDD, carteira, depósitos, prêmios) → ABSTÉM com log: idiossincrasia de filing
   (caso real SANB11, que reporta 0 nas contas fixas); zero real é implausível.
   NÃO vale para contas onde 0 é legítimo (ex.: operações descontinuadas).

Fail-safe geral: errar a detecção não produz número errado — a validação
semântica por DS descarta e o motor abstém ("dado não encontrado").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

PLANO_PADRAO = "padrao"
PLANO_BANCO = "banco"
PLANO_SEGURADORA = "seguradora"
PLANOS_FINANCEIROS = frozenset({PLANO_BANCO, PLANO_SEGURADORA})

# Conta e metodologia do ROE derivado (fonte COMPOSTA no ingestor).
ROE_CONTA = "ROE (derivado)"
ROE_METODOLOGIA = "lucro do exercício / patrimônio líquido de fim de período (não é PL médio)"

_RE_PALAVRA = re.compile(r"[a-z0-9]+")


def _normalizar_ds(texto: str) -> str:
    """minúsculas sem acento (comparação estável entre planos de contas)."""
    decomposto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _nivel(cd_conta: str) -> int:
    """Nível hierárquico do CD_CONTA ('2.08' -> 2; '1.02.03.05' -> 4)."""
    return cd_conta.count(".") + 1


def _palavras(ds_normalizado: str) -> list[str]:
    return _RE_PALAVRA.findall(ds_normalizado)


def _grupo_casa(grupo: tuple[str, ...], palavras: list[str]) -> bool:
    """Grupo casa se TODAS as suas palavras aparecem como PREFIXO de alguma
    palavra do DS (qualquer ordem). Necessário porque o DS real do ITUB inverte
    a ordem: "(Perda) de Crédito Esperada com Operações de Crédito..." — um
    substring fixo 'perda esperada' NÃO casaria (e perderia a PDD do ITUB)."""
    return all(any(p.startswith(w) for p in palavras) for w in grupo)


# Tokens ESPECÍFICOS de crédito para a PDD (veredito D1: NUNCA o token nu
# 'provis', que casaria provisão de contingência e somaria número errado).
_PDD_GRUPOS: tuple[tuple[str, ...], ...] = (
    ("perda", "esperada", "cred"),  # BBAS/BBDC 3.04.01 e ITUB 3.02.02 (ordem invertida)
    ("risco", "de", "credito"),
    ("liquidacao", "duvidosa"),
    ("provisao", "para", "cred"),
    ("provisao", "para", "operacoes", "de", "cred"),
)


@dataclass(frozen=True)
class MetricaFinanceira:
    """Especificação DECLARATIVA de uma métrica localizada por DS_CONTA.

    - `cd_exato`: âncora de CD fixo (intermediação 3.01/3.02/3.03) + validação
      semântica por DS; divergiu → descarta (abstém).
    - `prefixos`/`nivel_max`: âncora estrutural quando a POSIÇÃO varia por
      emissor (lucro, PL, PDD, carteira, depósitos).
    - `contem_todos`/`contem_algum`/`ds_exato`/`grupos_palavras`: predicado
      sobre o DS normalizado.
    - `usa_ancestral`: candidato ancestral absorve descendentes (PDD: subtotal
      vence componente; irmãs não-hierárquicas seguem ambíguas → abstém).
    - `zero_abstem`: VL_CONTA == 0 → abstém com log (regra VL=0, caso SANB11).
    """

    papel: str
    demonstracao: str  # 'DRE' | 'BPP' | 'BPA'
    cd_exato: str | None = None
    prefixos: tuple[str, ...] = ()
    nivel_max: int = 99
    contem_todos: tuple[str, ...] = ()
    contem_algum: tuple[str, ...] = ()
    ds_exato: str | None = None
    grupos_palavras: tuple[tuple[str, ...], ...] = field(default=())
    usa_ancestral: bool = False
    zero_abstem: bool = False


ESPEC_POR_PLANO: dict[str, tuple[MetricaFinanceira, ...]] = {
    PLANO_BANCO: (
        MetricaFinanceira(
            "RECEITAS_INTERMEDIACAO",
            "DRE",
            cd_exato="3.01",
            contem_todos=("intermediacao financeira",),
            zero_abstem=True,
        ),
        MetricaFinanceira(
            "DESPESAS_INTERMEDIACAO",
            "DRE",
            cd_exato="3.02",
            contem_todos=("intermediacao financeira",),
            zero_abstem=True,
        ),
        MetricaFinanceira(
            "RESULTADO_BRUTO_INTERMEDIACAO",
            "DRE",
            cd_exato="3.03",
            contem_todos=("resultado bruto", "intermediacao"),
            zero_abstem=True,
        ),
        # Rotulado com o DS REAL ("Resultado antes dos Tributos sobre o Lucro")
        # — NUNCA como 'EBIT' (em banco não existe EBIT de empresa comum).
        MetricaFinanceira(
            "RESULTADO_ANTES_TRIBUTOS",
            "DRE",
            prefixos=("3.",),
            nivel_max=2,
            contem_todos=("antes", "tributos"),
        ),
        # Posição varia: ITUB=3.09, BBDC/BBAS/SANB=3.11 — só o DS decide.
        MetricaFinanceira(
            "LUCRO_CONSOLIDADO",
            "DRE",
            prefixos=("3.",),
            nivel_max=2,
            contem_todos=("consolidado do periodo",),
            contem_algum=("lucro", "prejuizo"),
        ),
        # ITUB=2.08, demais=2.07; em banco 2.03 NÃO é PL (fail-safe por DS).
        MetricaFinanceira(
            "PL_CONSOLIDADO",
            "BPP",
            prefixos=("2.",),
            nivel_max=2,
            contem_todos=("patrimonio liquido consolidado",),
        ),
        MetricaFinanceira(
            "PDD",
            "DRE",
            prefixos=("3.02.", "3.04."),
            nivel_max=4,
            grupos_palavras=_PDD_GRUPOS,
            usa_ancestral=True,
            zero_abstem=True,
        ),
        MetricaFinanceira(
            "CARTEIRA_CREDITO",
            "BPA",
            prefixos=("1.02.",),
            nivel_max=4,
            contem_todos=("operacoes de credito",),
            zero_abstem=True,
        ),
        MetricaFinanceira(
            "DEPOSITOS",
            "BPP",
            prefixos=("2.",),
            nivel_max=4,
            ds_exato="depositos",
            zero_abstem=True,
        ),
    ),
    PLANO_SEGURADORA: (
        # Prêmios/sinistros detalhados (SUSEP) ficam FORA — lacuna explícita.
        MetricaFinanceira(
            "RECEITAS_SEGURADORAS",
            "DRE",
            cd_exato="3.01",
            contem_algum=("seguradora", "resseguradora"),
            zero_abstem=True,  # caso real BBSE3 (holding): 3.01 = 0 -> abstém
        ),
        MetricaFinanceira(
            "DESPESAS_SEGURADORAS",
            "DRE",
            cd_exato="3.02",
            contem_algum=("seguradora", "resseguradora"),
            zero_abstem=True,
        ),
        MetricaFinanceira(
            "RESULTADO_ANTES_TRIBUTOS",
            "DRE",
            prefixos=("3.",),
            nivel_max=2,
            contem_todos=("antes", "tributos"),
        ),
        # IRBR3/BBSE3: lucro consolidado em 3.13 — localizado por DS.
        MetricaFinanceira(
            "LUCRO_CONSOLIDADO",
            "DRE",
            prefixos=("3.",),
            nivel_max=2,
            contem_todos=("consolidado do periodo",),
            contem_algum=("lucro", "prejuizo"),
        ),
        # Seguradoras seguem o balanço padrão: PL em 2.03, mas por DS.
        MetricaFinanceira(
            "PL_CONSOLIDADO",
            "BPP",
            prefixos=("2.",),
            nivel_max=2,
            contem_todos=("patrimonio liquido consolidado",),
        ),
    ),
}


def detectar_plano(linhas_dre: list[dict]) -> str:
    """Detecta o plano de contas pelo DS da conta fixa 3.01 do PRÓPRIO filing.

    'intermediacao financeira' → banco; 'atividades seguradoras'/'resseguradora'
    → seguradora; senão (inclusive DS inventado ou 3.01 ausente) → padrão — o
    fail-safe do plano padrão valida cada conta por DS e abstém no divergente.
    SETOR_ATIV nunca decide (telemetria do chamador).
    """
    descricoes = {
        _normalizar_ds(linha.get("ds_conta", ""))
        for linha in linhas_dre
        if (linha.get("cd_conta") or "").strip() == "3.01"
    }
    if any("intermediacao financeira" in ds for ds in descricoes):
        return PLANO_BANCO
    if any("atividades seguradoras" in ds or "resseguradora" in ds for ds in descricoes):
        return PLANO_SEGURADORA
    return PLANO_PADRAO


def _ds_casa(metrica: MetricaFinanceira, ds_normalizado: str) -> bool:
    if metrica.ds_exato is not None:
        return ds_normalizado == metrica.ds_exato
    if metrica.grupos_palavras:
        palavras = _palavras(ds_normalizado)
        return any(_grupo_casa(g, palavras) for g in metrica.grupos_palavras)
    if metrica.contem_todos and not all(t in ds_normalizado for t in metrica.contem_todos):
        return False
    if metrica.contem_algum and not any(t in ds_normalizado for t in metrica.contem_algum):
        return False
    return bool(metrica.contem_todos or metrica.contem_algum)


def _reduzir_por_ancestral(candidatos: list[dict]) -> list[dict]:
    """Remove candidatos DESCENDENTES de outro candidato (o ancestral já é o
    agregado — usar os dois dobraria a conta). Irmãs não-hierárquicas ficam."""
    return [
        c
        for c in candidatos
        if not any(o is not c and c["cd_conta"].startswith(o["cd_conta"] + ".") for o in candidatos)
    ]


def _match_unico(candidatos: list[dict]) -> dict | None:
    """Match ÚNICO exigido; empate resolve por ST_CONTA_FIXA='S' (preferida);
    'N' só entra sozinha. Persistindo a ambiguidade → None (abstém)."""
    if len(candidatos) == 1:
        return candidatos[0]
    fixas = [c for c in candidatos if (c.get("st_conta_fixa") or "").strip().upper() == "S"]
    if len(fixas) == 1:
        return fixas[0]
    return None


def _localizar(metrica: MetricaFinanceira, linhas: list[dict]) -> dict | None:
    """Localiza a métrica em UM exercício. 0 candidatos → None (lacuna);
    ambíguo → None com log; VL=0 com `zero_abstem` → None com log."""
    candidatos: list[dict] = []
    for linha in linhas:
        cd = linha["cd_conta"]
        if metrica.cd_exato is not None:
            if cd != metrica.cd_exato:
                continue
        else:
            if metrica.prefixos and not any(cd.startswith(p) for p in metrica.prefixos):
                continue
            if _nivel(cd) > metrica.nivel_max:
                continue
        if not _ds_casa(metrica, _normalizar_ds(linha["ds_conta"])):
            continue
        candidatos.append(linha)
    if not candidatos:
        return None
    if metrica.usa_ancestral:
        candidatos = _reduzir_por_ancestral(candidatos)
    escolhido = _match_unico(candidatos)
    if escolhido is None:
        logger.info(
            "metrica_financeira_ambigua_abstida",
            papel=metrica.papel,
            candidatos=[c["cd_conta"] for c in candidatos],
        )
        return None
    if metrica.zero_abstem and float(escolhido["valor"]) == 0.0:
        # Regra VL=0 (caso real SANB11): zero nessas contas é idiossincrasia de
        # filing, não fato — gravar 0 seria número errado COM fonte.
        logger.info(
            "metrica_financeira_zero_abstida",
            papel=metrica.papel,
            cd_conta=escolhido["cd_conta"],
        )
        return None
    return dict(escolhido)


def extrair_financeira(plano: str, linhas_por_demonstracao: dict[str, list[dict]]) -> list[dict]:
    """Extrai as métricas do plano financeiro, por exercício (ULTIMO/PENULTIMO).

    `linhas_por_demonstracao`: {'DRE': [...], 'BPP': [...], 'BPA': [...]} com
    linhas já parseadas ({cd_conta, ds_conta, st_conta_fixa, valor, dt_refer,
    ordem}) e escala aplicada. Devolve achados no formato do ingestor
    ({cd_conta, ds_conta, valor, dt_refer, ordem}) + `papel` (chave estável
    para o ROE derivado). Nunca inventa: só devolve o que casou sem ambiguidade.
    """
    achados: list[dict] = []
    for metrica in ESPEC_POR_PLANO.get(plano, ()):
        linhas = linhas_por_demonstracao.get(metrica.demonstracao, [])
        por_ordem: dict[str, list[dict]] = {}
        for linha in linhas:
            por_ordem.setdefault(linha["ordem"], []).append(linha)
        for _ordem, grupo in sorted(por_ordem.items()):
            achado = _localizar(metrica, grupo)
            if achado is not None:
                achado["papel"] = metrica.papel
                achados.append(achado)
    return achados


def roe_derivado(achados: list[dict]) -> tuple[float | None, list[str]]:
    """ROE = lucro consolidado / PL consolidado, do MESMO exercício ÚLTIMO.

    Puro, no estilo de `derivadas`: devolve (fração decimal | None, contas-base).
    Abstém (None) se faltar componente, se as datas de referência divergirem ou
    se PL <= 0 (ROE sobre PL não-positivo é ininteligível — nunca gravar número
    enganoso). O chamador grava com unidade='RAZAO' e fonte composta declarando
    a metodologia (`ROE_METODOLOGIA`).
    """
    lucro = next(
        (a for a in achados if a.get("papel") == "LUCRO_CONSOLIDADO" and a["ordem"] == "ULTIMO"),
        None,
    )
    pl = next(
        (a for a in achados if a.get("papel") == "PL_CONSOLIDADO" and a["ordem"] == "ULTIMO"),
        None,
    )
    codigos = [a["cd_conta"] for a in (lucro, pl) if a is not None]
    if lucro is None or pl is None:
        return None, codigos
    if lucro["dt_refer"] is None or lucro["dt_refer"] != pl["dt_refer"]:
        logger.info(
            "roe_datas_divergentes_abstido",
            lucro=str(lucro["dt_refer"]),
            pl=str(pl["dt_refer"]),
        )
        return None, codigos
    if float(pl["valor"]) <= 0.0:
        logger.info("roe_pl_nao_positivo_abstido", pl=float(pl["valor"]))
        return None, codigos
    return float(lucro["valor"]) / float(pl["valor"]), codigos
