"""Testes offline dos planos de contas de financeiras (Bloco B da Fase 2).

Fixtures CSV latin-1 inline com números REAIS da DFP 2025 (ground truth
verificado): a posição de lucro/PL VARIA por emissor (ITUB=3.09/2.08,
BBAS=3.11/2.07, seguradoras=3.13/2.03) e a localização é por DS_CONTA
normalizada — nunca CD fixo. Cobre também a regra VL=0 (caso real SANB11),
a PDD por tokens específicos de crédito (nunca soma; ambíguo abstém), o ROE
derivado (unidade='RAZAO') e a formatação por unidade no coletor da tese.
Sem rede/DB: ZIPs em memória e sessões fake.
"""

from __future__ import annotations

import datetime as dt
import io
import uuid
import zipfile

from app.models.models import Empresa, Fonte, Fundamento
from app.services import dados as dados_svc
from app.services.dados import _ds_conta_valida, _ler_linhas_membro
from app.services.planos_contas import (
    ROE_CONTA,
    detectar_plano,
    extrair_financeira,
    roe_derivado,
)
from app.services.tese import _coletar, _fmt_fundamento, _fmt_reais

_HOJE = dt.date(2025, 12, 31)

_CAB = "CD_CVM;CD_CONTA;DS_CONTA;ST_CONTA_FIXA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC\n"

_MEMBRO_DRE = "dfp_cia_aberta_DRE_con_2025.csv"
_MEMBRO_BPP = "dfp_cia_aberta_BPP_con_2025.csv"
_MEMBRO_BPA = "dfp_cia_aberta_BPA_con_2025.csv"


def _zip_com(membros: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, texto in membros.items():
            z.writestr(nome, texto.encode("latin-1"))
    return buf.getvalue()


def _linhas(csv_corpo: str, cd_cvm: int, membro: str = _MEMBRO_DRE) -> list[dict]:
    return _ler_linhas_membro(_zip_com({membro: _CAB + csv_corpo}), cd_cvm, membro)


# ---------------------------------------------------------------------------
# Detecção do plano — pelo DS da conta fixa 3.01 do PRÓPRIO filing (D2)
# ---------------------------------------------------------------------------
def test_detecta_banco_itub_e_bbas() -> None:
    # Variação 'da'/'de' na descrição real (ITUB vs BBAS) — ambas são banco.
    itub = _linhas(
        "19348;3.01;Receitas da Intermediação Financeira;S;387118000;MIL;ÚLTIMO;2025-12-31\n",
        19348,
    )
    bbas = _linhas(
        "1023;3.01;Receitas de Intermediação Financeira;S;300000000;MIL;ÚLTIMO;2025-12-31\n",
        1023,
    )
    assert detectar_plano(itub) == "banco"
    assert detectar_plano(bbas) == "banco"


def test_detecta_seguradora_irbr_e_bbse_mesmo_com_vl_zero() -> None:
    irbr = _linhas(
        "24180;3.01;Receitas das Atividades Seguradoras/Resseguradoras;S;"
        "5210000;MIL;ÚLTIMO;2025-12-31\n",
        24180,
    )
    # BBSE3 (holding) reporta 3.01 = 0: a DETECÇÃO ainda vê a seguradora
    # (a regra VL=0 abstém só a métrica, não a detecção do plano).
    bbse = _linhas(
        "23159;3.01;Receitas das Atividades Seguradoras/Resseguradoras;S;0;MIL;ÚLTIMO;2025-12-31\n",
        23159,
    )
    assert detectar_plano(irbr) == "seguradora"
    assert detectar_plano(bbse) == "seguradora"


def test_detecta_padrao_para_holdings_e_nao_financeiras() -> None:
    # ITSA4/PSSA3/B3SA3/PETR4: 3.01 = 'Receita de Venda de Bens e/ou Serviços'
    # no filing REAL (ground truth) — plano padrão, mesmo com SETOR_ATIV
    # 'Intermediação Financeira' (ITSA4) ou 'Seguradoras' (PSSA3).
    for cd_cvm in (7617, 16659, 21610, 9512):
        linhas = _linhas(
            f"{cd_cvm};3.01;Receita de Venda de Bens e/ou Serviços;S;100;MIL;ÚLTIMO;2025-12-31\n",
            cd_cvm,
        )
        assert detectar_plano(linhas) == "padrao"


def test_ds_inventado_ou_sem_3_01_cai_no_padrao_fail_safe() -> None:
    inventado = _linhas("999;3.01;Faturamento Bruto Consolidado;S;100;MIL;ÚLTIMO;2025-12-31\n", 999)
    assert detectar_plano(inventado) == "padrao"
    assert detectar_plano([]) == "padrao"


# ---------------------------------------------------------------------------
# Fixtures ITUB4 — números REAIS da DFP 2025 (escala MIL, regra A1)
# ---------------------------------------------------------------------------
_ITUB_DRE = (
    "19348;3.01;Receitas da Intermediação Financeira;S;387118000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.02;Despesas da Intermediação Financeira;S;-248171000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.02.02;(Perda) de Crédito Esperada com Operações de Crédito e Arrendamento "
    "Mercantil Financeiro;N;-32617000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.03;Resultado Bruto da Intermediação Financeira;S;138947000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.05;Resultado antes dos Tributos sobre o Lucro;S;58548000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.06;Imposto de Renda e Contribuição Social sobre o Lucro;S;"
    "-12699000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.09;Lucro/Prejuízo Consolidado do Período;S;45849000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.10;Atribuído a Sócios da Empresa Controladora;S;44900000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;3.09;Lucro/Prejuízo Consolidado do Período;S;41000000;MIL;PENÚLTIMO;2024-12-31\n"
)
_ITUB_BPP = (
    # Em banco, 2.03 NÃO é PL — é passivo financeiro (o CD fixo 2.03 gravaria
    # número errado COM fonte; a localização por DS não pode cair nele).
    "19348;2.03;Passivos Financeiros ao Custo Amortizado;S;1500000000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;2.03.01;Depósitos;N;1114480000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;2.07;Provisões;S;30000000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;2.08;Patrimônio Líquido Consolidado;S;215076000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;2.08.01;Capital Social Realizado;S;90000000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;2.08;Patrimônio Líquido Consolidado;S;200000000;MIL;PENÚLTIMO;2024-12-31\n"
)
_ITUB_BPA = (
    "19348;1.02;Ativo Realizável a Longo Prazo;S;5000000000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;1.02.03;Ativos Financeiros ao Custo Amortizado;S;2000000000;MIL;ÚLTIMO;2025-12-31\n"
    "19348;1.02.03.05;Operações de Crédito e Arrendamento Mercantil Financeiro;N;"
    "1083798000;MIL;ÚLTIMO;2025-12-31\n"
)


def _extrai_itub() -> list[dict]:
    return extrair_financeira(
        "banco",
        {
            "DRE": _linhas(_ITUB_DRE, 19348),
            "BPP": _linhas(_ITUB_BPP, 19348, _MEMBRO_BPP),
            "BPA": _linhas(_ITUB_BPA, 19348, _MEMBRO_BPA),
        },
    )


def test_itub_localiza_lucro_e_pl_por_ds_nao_por_cd_fixo() -> None:
    achados = _extrai_itub()
    ultimo = {a["papel"]: a for a in achados if a["ordem"] == "ULTIMO"}
    # Lucro do ITUB está em 3.09 (não em 3.11 como BBDC/BBAS) — DS decide.
    assert ultimo["LUCRO_CONSOLIDADO"]["cd_conta"] == "3.09"
    assert ultimo["LUCRO_CONSOLIDADO"]["valor"] == 45_849_000_000.0  # 45.849.000 MIL (A1)
    # PL do ITUB está em 2.08; 2.03 ('Passivos Financeiros...') NÃO pode casar.
    assert ultimo["PL_CONSOLIDADO"]["cd_conta"] == "2.08"
    assert ultimo["PL_CONSOLIDADO"]["valor"] == 215_076_000_000.0
    # PENÚLTIMO também entra (tendência ano-contra-ano), separado por exercício.
    penultimo = [a for a in achados if a["ordem"] == "PENULTIMO"]
    assert {a["papel"] for a in penultimo} == {"LUCRO_CONSOLIDADO", "PL_CONSOLIDADO"}


def test_itub_intermediacao_pdd_carteira_e_depositos() -> None:
    ultimo = {a["papel"]: a for a in _extrai_itub() if a["ordem"] == "ULTIMO"}
    assert ultimo["RECEITAS_INTERMEDIACAO"]["valor"] == 387_118_000_000.0
    assert ultimo["RESULTADO_BRUTO_INTERMEDIACAO"]["valor"] == 138_947_000_000.0
    # PDD do ITUB é conta N (3.02.02), ordem das palavras INVERTIDA no DS.
    assert ultimo["PDD"]["cd_conta"] == "3.02.02"
    assert ultimo["PDD"]["valor"] == -32_617_000_000.0
    # Carteira em nível 4 (1.02.03.05), conta N, match único.
    assert ultimo["CARTEIRA_CREDITO"]["cd_conta"] == "1.02.03.05"
    assert ultimo["CARTEIRA_CREDITO"]["valor"] == 1_083_798_000_000.0
    assert ultimo["DEPOSITOS"]["cd_conta"] == "2.03.01"
    assert ultimo["DEPOSITOS"]["valor"] == 1_114_480_000_000.0
    # Rótulo do resultado antes dos tributos = DS REAL, nunca 'EBIT'.
    assert "antes dos Tributos" in ultimo["RESULTADO_ANTES_TRIBUTOS"]["ds_conta"]
    assert "EBIT" not in " ".join(a["ds_conta"] for a in _extrai_itub())


def test_bbas_localiza_nas_posicoes_proprias_e_pdd_ignora_contingencia() -> None:
    dre = (
        "1023;3.01;Receitas de Intermediação Financeira;S;300000000;MIL;ÚLTIMO;2025-12-31\n"
        "1023;3.04.01;Despesa de Provisão para Perda Esperada para Risco de Crédito;S;"
        "-66633285;MIL;ÚLTIMO;2025-12-31\n"
        # Contingência no MESMO subtree 3.04.*: NÃO pode casar nem somar (o token
        # nu 'provis' somaria contingência + PDD = número errado COM fonte).
        "1023;3.04.02;Provisões para Contingências Cíveis, Fiscais e Trabalhistas;S;"
        "-9000000;MIL;ÚLTIMO;2025-12-31\n"
        "1023;3.05;Resultado antes dos Tributos sobre o Lucro;S;21000000;MIL;ÚLTIMO;2025-12-31\n"
        "1023;3.11;Lucro ou Prejuízo Líquido Consolidado do Período;S;"
        "16781938;MIL;ÚLTIMO;2025-12-31\n"
    )
    bpp = (
        "1023;2.02.01;Depósitos;S;897940000;MIL;ÚLTIMO;2025-12-31\n"
        "1023;2.07;Patrimônio Líquido Consolidado;S;193567416;MIL;ÚLTIMO;2025-12-31\n"
    )
    bpa = "1023;1.02.04.04;Operações de Crédito;S;1133070000;MIL;ÚLTIMO;2025-12-31\n"
    achados = extrair_financeira(
        "banco",
        {
            "DRE": _linhas(dre, 1023),
            "BPP": _linhas(bpp, 1023, _MEMBRO_BPP),
            "BPA": _linhas(bpa, 1023, _MEMBRO_BPA),
        },
    )
    ultimo = {a["papel"]: a for a in achados}
    assert ultimo["LUCRO_CONSOLIDADO"]["cd_conta"] == "3.11"  # ≠ ITUB (3.09)
    assert ultimo["LUCRO_CONSOLIDADO"]["valor"] == 16_781_938_000.0
    assert ultimo["PL_CONSOLIDADO"]["cd_conta"] == "2.07"  # ≠ ITUB (2.08)
    assert ultimo["PL_CONSOLIDADO"]["valor"] == 193_567_416_000.0
    assert ultimo["PDD"]["cd_conta"] == "3.04.01"
    assert ultimo["PDD"]["valor"] == -66_633_285_000.0  # contingência ficou fora
    assert ultimo["DEPOSITOS"]["cd_conta"] == "2.02.01"
    assert ultimo["CARTEIRA_CREDITO"]["cd_conta"] == "1.02.04.04"


# ---------------------------------------------------------------------------
# PDD — ambiguidade e hierarquia (nunca soma; veredito D1)
# ---------------------------------------------------------------------------
def test_pdd_duas_irmas_nao_hierarquicas_abstem_nunca_soma() -> None:
    dre = (
        "906;3.04.01;Provisão para Créditos de Liquidação Duvidosa;S;-100;MIL;ÚLTIMO;2025-12-31\n"
        "906;3.04.02;Perda Esperada para Risco de Crédito;S;-50;MIL;ÚLTIMO;2025-12-31\n"
    )
    achados = extrair_financeira("banco", {"DRE": _linhas(dre, 906)})
    assert not [a for a in achados if a["papel"] == "PDD"]  # abstém — jamais -150


def test_pdd_ancestral_absorve_descendente() -> None:
    dre = (
        "906;3.04.01;Provisão para Créditos de Liquidação Duvidosa;S;-80;MIL;ÚLTIMO;2025-12-31\n"
        "906;3.04.01.01;Provisão para Créditos de Liquidação Duvidosa - Varejo;N;"
        "-50;MIL;ÚLTIMO;2025-12-31\n"
    )
    achados = extrair_financeira("banco", {"DRE": _linhas(dre, 906)})
    pdd = [a for a in achados if a["papel"] == "PDD"]
    assert len(pdd) == 1
    assert pdd[0]["cd_conta"] == "3.04.01"  # subtotal vence componente
    assert pdd[0]["valor"] == -80_000.0  # nunca -130 (dupla contagem)


def test_regra_vl_zero_sanb_abstem_pdd_carteira_e_depositos() -> None:
    # Caso real SANB11: contas fixas casam mas reportam 0 (idiossincrasia de
    # filing). Gravar 0 seria número errado COM fonte -> abstém.
    dre = (
        "20532;3.01;Receitas de Intermediação Financeira;S;50000000;MIL;ÚLTIMO;2025-12-31\n"
        "20532;3.04.01;Despesa de Provisão para Perda Esperada para Risco de Crédito;S;"
        "0;MIL;ÚLTIMO;2025-12-31\n"
        "20532;3.11;Lucro ou Prejuízo Líquido Consolidado do Período;S;"
        "13000000;MIL;ÚLTIMO;2025-12-31\n"
    )
    bpp = (
        "20532;2.02.01;Depósitos;S;0;MIL;ÚLTIMO;2025-12-31\n"
        "20532;2.07;Patrimônio Líquido Consolidado;S;126550000;MIL;ÚLTIMO;2025-12-31\n"
    )
    bpa = "20532;1.02.04.04;Operações de Crédito;S;0;MIL;ÚLTIMO;2025-12-31\n"
    achados = extrair_financeira(
        "banco",
        {
            "DRE": _linhas(dre, 20532),
            "BPP": _linhas(bpp, 20532, _MEMBRO_BPP),
            "BPA": _linhas(bpa, 20532, _MEMBRO_BPA),
        },
    )
    papeis = {a["papel"] for a in achados}
    assert "PDD" not in papeis
    assert "CARTEIRA_CREDITO" not in papeis
    assert "DEPOSITOS" not in papeis
    # Onde 0 não é a regra, os fatos legítimos permanecem.
    assert {"RECEITAS_INTERMEDIACAO", "LUCRO_CONSOLIDADO", "PL_CONSOLIDADO"} <= papeis


def test_escala_milhar_tambem_multiplica_por_mil_nas_financeiras() -> None:
    dre = "19348;3.01;Receitas da Intermediação Financeira;S;387118000;MILHAR;ÚLTIMO;2025-12-31\n"
    achados = extrair_financeira("banco", {"DRE": _linhas(dre, 19348)})
    assert achados[0]["valor"] == 387_118_000_000.0  # padrão A1


# ---------------------------------------------------------------------------
# Seguradora — IRBR3 (valores reais) e BBSE3 (holding com 3.01 = 0)
# ---------------------------------------------------------------------------
def test_irbr_seguradora_lucro_em_3_13_e_pl_em_2_03() -> None:
    dre = (
        "24180;3.01;Receitas das Atividades Seguradoras/Resseguradoras;S;"
        "5210000;MIL;ÚLTIMO;2025-12-31\n"
        "24180;3.05;Resultado antes dos Tributos sobre o Lucro;S;400000;MIL;ÚLTIMO;2025-12-31\n"
        "24180;3.13;Lucro/Prejuízo Consolidado do Período;S;300000;MIL;ÚLTIMO;2025-12-31\n"
    )
    bpp = "24180;2.03;Patrimônio Líquido Consolidado;S;2000000;MIL;ÚLTIMO;2025-12-31\n"
    achados = extrair_financeira(
        "seguradora",
        {"DRE": _linhas(dre, 24180), "BPP": _linhas(bpp, 24180, _MEMBRO_BPP)},
    )
    ultimo = {a["papel"]: a for a in achados}
    assert ultimo["RECEITAS_SEGURADORAS"]["valor"] == 5_210_000_000.0
    assert ultimo["LUCRO_CONSOLIDADO"]["cd_conta"] == "3.13"  # posição de seguradora
    assert ultimo["PL_CONSOLIDADO"]["cd_conta"] == "2.03"  # balanço padrão
    roe, componentes = roe_derivado(achados)
    assert roe == 0.15  # 300.000 / 2.000.000
    assert componentes == ["3.13", "2.03"]


def test_bbse_holding_com_3_01_zero_abstem_receitas_mas_mantem_lucro() -> None:
    dre = (
        "23159;3.01;Receitas das Atividades Seguradoras/Resseguradoras;S;0;MIL;ÚLTIMO;2025-12-31\n"
        "23159;3.13;Lucro/Prejuízo Consolidado do Período;S;5340000;MIL;ÚLTIMO;2025-12-31\n"
    )
    achados = extrair_financeira("seguradora", {"DRE": _linhas(dre, 23159)})
    papeis = {a["papel"] for a in achados}
    assert "RECEITAS_SEGURADORAS" not in papeis  # VL=0 -> abstém
    assert "LUCRO_CONSOLIDADO" in papeis


# ---------------------------------------------------------------------------
# ROE derivado — guardas de abstenção
# ---------------------------------------------------------------------------
def _achado(papel: str, cd: str, valor: float, data=_HOJE, ordem: str = "ULTIMO") -> dict:
    return {
        "papel": papel,
        "cd_conta": cd,
        "ds_conta": papel,
        "valor": valor,
        "dt_refer": data,
        "ordem": ordem,
    }


def test_roe_itub_e_21_32_por_cento() -> None:
    achados = [a for a in _extrai_itub() if a["ordem"] == "ULTIMO"]
    roe, componentes = roe_derivado(achados)
    assert roe is not None
    assert round(roe, 4) == 0.2132  # 45.849.000 / 215.076.000 (ground truth)
    assert componentes == ["3.09", "2.08"]
    assert _fmt_fundamento(roe, "RAZAO") == "21,32%"


def test_roe_abstem_sem_componente_datas_divergentes_ou_pl_nao_positivo() -> None:
    lucro = _achado("LUCRO_CONSOLIDADO", "3.09", 100.0)
    assert roe_derivado([lucro])[0] is None  # falta PL
    assert roe_derivado([_achado("PL_CONSOLIDADO", "2.08", 500.0)])[0] is None  # falta lucro
    divergente = _achado("PL_CONSOLIDADO", "2.08", 500.0, data=dt.date(2024, 12, 31))
    assert roe_derivado([lucro, divergente])[0] is None  # exercícios diferentes
    pl_negativo = _achado("PL_CONSOLIDADO", "2.08", -500.0)
    assert roe_derivado([lucro, pl_negativo])[0] is None  # PL <= 0
    penultimo = _achado("PL_CONSOLIDADO", "2.08", 500.0, ordem="PENULTIMO")
    assert roe_derivado([lucro, penultimo])[0] is None  # só o MESMO exercício ÚLTIMO


# ---------------------------------------------------------------------------
# _ds_conta_valida parametrizada — default global preservado (suite antiga)
# ---------------------------------------------------------------------------
def test_ds_conta_valida_default_global_preservado_e_parametrizavel() -> None:
    # Default global (plano padrão) intocado: 3.05 de banco diverge (caso M2).
    assert _ds_conta_valida("3.05", "Resultado Antes do Resultado Financeiro e dos Tributos")
    assert not _ds_conta_valida("3.05", "Resultado antes dos Tributos sobre o Lucro")
    # Parametrizada: outra especificação muda o veredito sem tocar o default.
    espec = {"3.05": ("antes dos tributos",)}
    assert _ds_conta_valida("3.05", "Resultado antes dos Tributos sobre o Lucro", espec)


# ---------------------------------------------------------------------------
# Formatação por unidade (achado B2) — ROE nunca vira 'R$ 0,21'
# ---------------------------------------------------------------------------
def test_fmt_fundamento_por_unidade() -> None:
    assert _fmt_fundamento(0.2132, "RAZAO") == "21,32%"
    assert "R$" not in _fmt_fundamento(0.2132, "RAZAO")
    assert _fmt_fundamento(0.006635, "PCT") == "0,66%"  # DY mensal HGLG11
    assert _fmt_fundamento(525069, "UN") == "525.069"  # cotistas, sem 'R$'
    assert _fmt_fundamento(166.576588, "BRL_POR_COTA") == "R$ 166,58 por cota"
    # NULL e 'BRL' -> byte-idênticos ao legado (_fmt_reais).
    assert _fmt_fundamento(110605000000.0, None) == _fmt_reais(110605000000.0)
    assert _fmt_fundamento(110605000000.0, "BRL") == "R$ 110.605.000.000,00"
    # Unidade desconhecida: nunca 'R$' por engano — valor cru rotulado.
    assert _fmt_fundamento(1.5, "X_NOVA") == "1.5 (X_NOVA)"


# ---------------------------------------------------------------------------
# _coletar formata por unidade; legado (unidade NULL) byte-idêntico
# ---------------------------------------------------------------------------
class _FakeResult:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return iter(self._rows)

    def all(self):
        return self._rows


class _FakeSession:
    """Devolve fundamentos, macro e pares na ORDEM das 3 chamadas de _coletar."""

    def __init__(self, fundamentos, fontes):
        self._sequencia = [fundamentos, [], []]
        self._i = 0
        self._fontes = fontes

    def execute(self, _stmt):
        rows = self._sequencia[self._i]
        self._i += 1
        return _FakeResult(rows)

    def get(self, _model, id_):
        return self._fontes.get(id_)


def test_coletar_formata_roe_como_percentual_e_legado_byte_identico() -> None:
    empresa = Empresa(nome="Itaú Unibanco", ticker="ITUB4")
    empresa.id = "emp-1"
    legado = Fundamento(
        conta="Receita de Venda de Bens e/ou Serviços (3.01)",
        valor=110605000000.0,
        dt_refer=_HOJE,
        fonte_id="f1",
    )
    roe = Fundamento(conta=ROE_CONTA, valor=0.2132, unidade="RAZAO", dt_refer=_HOJE, fonte_id="f2")
    fontes = {
        "f1": Fonte(descricao="CVM DFP", url="https://cvm", dt_referencia=_HOJE),
        "f2": Fonte(descricao="CVM DFP — ROE derivado", url="https://cvm", dt_referencia=_HOJE),
    }
    itens = _coletar(_FakeSession([legado, roe], fontes), empresa)
    textos = {t for _f, t in itens}

    # Legado (unidade NULL): byte-idêntico ao formato de sempre.
    assert (
        "Fundamento de Itaú Unibanco (ITUB4): "
        "Receita de Venda de Bens e/ou Serviços (3.01) = R$ 110.605.000.000,00 "
        "(exercício/ref. 2025-12-31)."
    ) in textos
    texto_roe = next(t for t in textos if ROE_CONTA in t)
    assert "= 21,32%" in texto_roe
    assert "R$" not in texto_roe  # nunca 'R$ 0,21'


# ---------------------------------------------------------------------------
# ingest_fundamentos multi-plano — dispatch banco + ROE persistido (offline)
# ---------------------------------------------------------------------------
class _ResultadoVazio:
    def scalar_one_or_none(self):
        return None


class _SessaoGravadora:
    """Sessão fake mínima: todo lookup falha (força criação) e `add` registra."""

    def __init__(self) -> None:
        self.adicionados: list = []

    def execute(self, _stmt) -> _ResultadoVazio:
        return _ResultadoVazio()

    def add(self, obj) -> None:
        self.adicionados.append(obj)

    def flush(self) -> None:
        for o in self.adicionados:
            if getattr(o, "id", None) is None:
                o.id = uuid.uuid4()


def test_ingest_fundamentos_banco_persiste_plano_roe_e_abstem_derivadas(monkeypatch) -> None:
    zip_2025 = _zip_com(
        {
            _MEMBRO_DRE: _CAB + _ITUB_DRE,
            _MEMBRO_BPP: _CAB + _ITUB_BPP,
            _MEMBRO_BPA: _CAB + _ITUB_BPA,
        }
    )
    monkeypatch.setattr(dados_svc, "_baixar_dfp_zip", lambda _ano: zip_2025)

    empresa = Empresa(nome="Itaú Unibanco Holding S.A.", ticker="ITUB4", setor="Bancos")
    empresa.id = uuid.uuid4()
    empresa.cd_cvm = 19348
    sessao = _SessaoGravadora()

    gravados = dados_svc.ingest_fundamentos(sessao, empresa)

    # Plano detectado pelo filing e persistido na empresa.
    assert empresa.plano_contas == "banco"

    # ROE derivado: unidade='RAZAO', fração decimal, fonte composta com a
    # metodologia declarada (não é PL médio).
    roes = [f for f in gravados if f.conta == ROE_CONTA]
    assert len(roes) == 1
    assert roes[0].unidade == "RAZAO"
    assert round(float(roes[0].valor), 4) == 0.2132
    assert roes[0].dt_refer == _HOJE
    fontes = [o for o in sessao.adicionados if isinstance(o, Fonte)]
    fonte_roe = [f for f in fontes if "metodologia" in (f.descricao or "")]
    assert len(fonte_roe) == 1
    assert "não é PL médio" in fonte_roe[0].descricao
    assert "3.09+2.08" in fonte_roe[0].descricao  # fonte COMPOSTA (contas-base)

    # Fatos BRL: unidade NULL (legado byte-idêntico) + fonte + dt em todos.
    for f in gravados:
        if f.conta != ROE_CONTA:
            assert f.unidade is None
        assert f.fonte_id is not None
        assert f.dt_refer is not None

    # Derivadas do plano padrão NÃO rodam em banco (abstenção estrutural).
    contas = " ".join(f.conta for f in gravados)
    assert "Dívida" not in contas
    assert "EBITDA" not in contas
    assert "EBIT" not in contas
    # Métricas de banco presentes, rotuladas pelo DS real.
    assert "Lucro/Prejuízo Consolidado do Período (3.09)" in contas
    assert "Patrimônio Líquido Consolidado (2.08)" in contas
