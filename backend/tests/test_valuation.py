"""Testes offline do valuation determinístico (app.services.valuation).

100% puro — nenhuma rede/DB. Golden tests com contas feitas à mão (documentadas
no docstring de cada teste). Foco anti-alucinação: abstenção rotulada quando
falta insumo; NUNCA ponto único; premissas todas com origem+rótulo; linguagem
dos templates neutra (pré-checagem do gate A5/A6).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import re

import pytest

from app.services.valuation import (
    AVISO_VALUATION,
    Insumo,
    InsumosValuation,
    PeerMultiplo,
    Valuation,
    avaliar,
    valuation_para_envelope,
)

_HOJE = dt.date(2026, 7, 9)


def _insumo(valor: float, fonte: str = "fonte de teste", data: dt.date = _HOJE) -> Insumo:
    return Insumo(valor=valor, fonte=fonte, dt_referencia=data)


def _insumos_acao_golden() -> InsumosValuation:
    """Caso golden da ação genérica: Selic 15%, β ausente (=1), D0=R$2, IPCA Focus 4%."""
    return InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432 — meta Selic (Copom)"),
        ipca_esperado=_insumo(0.04, "Focus/BCB — mediana IPCA ano seguinte"),
        dividendo_por_acao_12m=_insumo(2.00, "B3 — proventos 12m por ação"),
    )


def _insumos_banco_golden() -> InsumosValuation:
    """Caso golden do banco: BVPS=R$20, ROE=18%, Selic 15%, β ausente, IPCA 4%."""
    return InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432 — meta Selic (Copom)"),
        ipca_esperado=_insumo(0.04, "Focus/BCB — mediana IPCA ano seguinte"),
        bvps=_insumo(20.0, "DFP — PL / ações (derivado)"),
        roe=_insumo(0.18, "DFP — LL/PL (RAZAO)"),
    )


def _modelo(v: Valuation, nome: str):
    por_nome = {m.modelo: m for m in v.modelos}
    assert nome in por_nome, f"modelo {nome} ausente: {sorted(por_nome)}"
    return por_nome[nome]


def _cenario(modelo, nome: str):
    por_nome = {c.nome: c for c in modelo.cenarios}
    assert nome in por_nome, f"cenário {nome} ausente: {sorted(por_nome)}"
    return por_nome[nome]


# ---------------------------------------------------------------------------
# Gordon (ação genérica) — golden calculado à mão
# ---------------------------------------------------------------------------


def test_gordon_golden_tres_cenarios() -> None:
    """Conta à mão (Rf=Selic=15%; β=1; ERP 6/5/4%; g=0/3%/4%; D1=D0×(1+g)):

    - conservador: Ke=0,15+0,06=0,21; g=0    → 2,00×1,00/0,21 = 9,5238095...
    - base:        Ke=0,15+0,05=0,20; g=0,03 → 2,00×1,03/0,17 = 12,1176470...
    - otimista:    Ke=0,15+0,04=0,19; g=0,04 → 2,00×1,04/0,15 = 13,8666666...
    """
    v = avaliar("acao", None, None, _insumos_acao_golden())
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert not gordon.omitido
    assert _cenario(gordon, "conservador").valor == pytest.approx(9.523809523809524)
    assert _cenario(gordon, "base").valor == pytest.approx(12.117647058823529)
    assert _cenario(gordon, "otimista").valor == pytest.approx(13.866666666666667)


def test_gordon_faixa_entre_cenarios_nunca_ponto_unico() -> None:
    v = avaliar("acao", None, None, _insumos_acao_golden())
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert gordon.faixa == pytest.approx((9.523809523809524, 13.866666666666667))
    assert gordon.faixa[0] < gordon.faixa[1]  # faixa real, não ponto


def test_gordon_cenario_carrega_todas_as_premissas_rotuladas() -> None:
    """Cada cenário traz Rf, ERP, beta, Ke, g, D0 e D1 — todas com origem+rótulo."""
    v = avaliar("acao", None, None, _insumos_acao_golden())
    assert v is not None
    base = _cenario(_modelo(v, "gordon"), "base")
    nomes = {p.nome for p in base.premissas}
    assert {"Rf", "ERP", "beta", "Ke", "g"}.issubset(nomes)
    assert any(p.nome.startswith("D0") for p in base.premissas)
    assert any(p.nome == "D1" for p in base.premissas)
    for p in base.premissas:
        assert p.origem, f"premissa {p.nome} sem origem"
        assert p.rotulo, f"premissa {p.nome} sem rótulo"
    erp = next(p for p in base.premissas if p.nome == "ERP")
    assert erp.rotulo == "premissa v1, não é previsão"
    rf = next(p for p in base.premissas if p.nome == "Rf")
    assert "Selic" in rf.rotulo and "BCB" in rf.origem


def test_gordon_sensibilidade_ke_g_mais_menos_1pp() -> None:
    """Célula (Ke=0,21; g=0,02): 2,00×1,02/0,19 = 10,7368421...; centro = cenário base."""
    v = avaliar("acao", None, None, _insumos_acao_golden())
    assert v is not None
    sens = _modelo(v, "gordon").sensibilidade
    assert sens is not None
    assert sens.eixo_ke == pytest.approx((0.19, 0.20, 0.21))
    assert sens.eixo_g == pytest.approx((0.02, 0.03, 0.04))
    assert sens.valores[1][1] == pytest.approx(12.117647058823529)  # centro = base
    assert sens.valores[2][0] == pytest.approx(10.736842105263158)  # Ke+1pp × g−1pp
    assert sens.valores[0][2] == pytest.approx(13.866666666666667)  # Ke−1pp × g+1pp


def test_gordon_dividendo_derivado_de_total_e_num_acoes() -> None:
    """D0 = 200 mi / 100 mi ações = R$2,00/ação → mesmo golden do teste acima."""
    insumos = InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432"),
        ipca_esperado=_insumo(0.04, "Focus/BCB"),
        dividendos_12m=_insumo(200_000_000.0, "B3 — proventos 12m (total)"),
        num_acoes=_insumo(100_000_000.0, "DFP — ações emitidas"),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert _cenario(gordon, "base").valor == pytest.approx(12.117647058823529)
    d0 = next(p for p in _cenario(gordon, "base").premissas if p.nome.startswith("D0"))
    assert "÷" in d0.origem  # origem composta declara a derivação


def test_gordon_omitido_sem_dividendos_com_motivo_declarado() -> None:
    insumos = InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432"),
        dividendo_por_acao_12m=_insumo(0.0, "B3 — proventos 12m"),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert gordon.omitido
    assert "não pagou dividendos" in (gordon.motivo_omissao or "")


def test_gordon_omitido_sem_selic_motivo_dado_nao_encontrado() -> None:
    insumos = InsumosValuation(dividendo_por_acao_12m=_insumo(2.0, "B3"))
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert gordon.omitido
    assert "Selic" in (gordon.motivo_omissao or "")
    assert "dado não encontrado" in (gordon.motivo_omissao or "")


def test_gordon_cenario_omitido_quando_ke_menor_igual_g() -> None:
    """Selic 2% (β=1): otimista tem Ke=0,06 ≤ g=0,08 (Focus) → cenário omitido com
    motivo matemático; conservador (Ke=0,08, g=0) e base (Ke=0,07, g=0,03) ficam."""
    insumos = InsumosValuation(
        selic=_insumo(0.02, "BCB/SGS 432"),
        ipca_esperado=_insumo(0.08, "Focus/BCB"),
        dividendo_por_acao_12m=_insumo(2.0, "B3"),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert not gordon.omitido
    assert {c.nome for c in gordon.cenarios} == {"conservador", "base"}
    assert len(gordon.omissoes) == 1
    assert "≤ g" in gordon.omissoes[0] and "otimista" in gordon.omissoes[0]


def test_modelo_omitido_com_menos_de_dois_cenarios() -> None:
    """β=0 → Ke=Selic=2% em TODOS os cenários; g=3% e g=4% matam base e otimista;
    sobra 1 cenário → modelo inteiro omitido (faixa exige ≥2 — nunca ponto único)."""
    insumos = InsumosValuation(
        selic=_insumo(0.02, "BCB/SGS 432"),
        ipca_esperado=_insumo(0.04, "Focus/BCB"),
        beta_aprox=Insumo(valor=0.0, fonte="COTAHIST vs BOVA11"),
        dividendo_por_acao_12m=_insumo(2.0, "B3"),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    gordon = _modelo(v, "gordon")
    assert gordon.omitido
    assert "menos de 2 cenários" in (gordon.motivo_omissao or "")
    assert gordon.faixa is None


def test_beta_ausente_vira_1_com_rotulo_neutro_e_presente_vira_aproximado() -> None:
    v_sem = avaliar("acao", None, None, _insumos_acao_golden())
    assert v_sem is not None
    beta_sem = next(
        p for p in _cenario(_modelo(v_sem, "gordon"), "base").premissas if p.nome == "beta"
    )
    assert beta_sem.valor == 1.0
    assert beta_sem.rotulo == "neutro por ausência de estimativa"

    insumos = InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432"),
        beta_aprox=Insumo(valor=1.2, fonte="COTAHIST vs BOVA11 (252 pregões)"),
        dividendo_por_acao_12m=_insumo(2.0, "B3"),
    )
    v_com = avaliar("acao", None, None, insumos)
    assert v_com is not None
    beta_com = next(
        p for p in _cenario(_modelo(v_com, "gordon"), "base").premissas if p.nome == "beta"
    )
    assert beta_com.valor == 1.2
    assert beta_com.rotulo == "aproximado, preços não ajustados"


# ---------------------------------------------------------------------------
# Banco — P/VP justificado (golden à mão) + nunca EV/EBITDA
# ---------------------------------------------------------------------------


def test_banco_pvp_justificado_golden() -> None:
    """valor = BVPS×(ROE−g)/(Ke−g), BVPS=20, ROE=0,18:

    - conservador: 20×(0,18−0)/(0,21−0)       = 20×0,857142... = 17,1428571...
    - base:        20×(0,18−0,03)/(0,20−0,03) = 20×0,882352... = 17,6470588...
    - otimista:    20×(0,18−0,04)/(0,19−0,04) = 20×0,933333... = 18,6666666...
    """
    v = avaliar("acao", "banco", None, _insumos_banco_golden())
    assert v is not None
    pvp = _modelo(v, "pvp_justificado")
    assert not pvp.omitido
    assert _cenario(pvp, "conservador").valor == pytest.approx(17.142857142857142)
    assert _cenario(pvp, "base").valor == pytest.approx(17.647058823529413)
    assert _cenario(pvp, "otimista").valor == pytest.approx(18.666666666666668)
    assert pvp.faixa == pytest.approx((17.142857142857142, 18.666666666666668))


def test_banco_cenario_omitido_quando_roe_menor_igual_g() -> None:
    """ROE=2%: base (g=3%) e otimista (g=4%) têm ROE ≤ g → sobra só o conservador
    (g=0) → modelo inteiro omitido (regra dos ≥2 cenários) com motivos declarados."""
    insumos = InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432"),
        ipca_esperado=_insumo(0.04, "Focus/BCB"),
        bvps=_insumo(20.0, "DFP"),
        roe=_insumo(0.02, "DFP — LL/PL"),
    )
    v = avaliar("acao", "banco", None, insumos)
    assert v is not None
    pvp = _modelo(v, "pvp_justificado")
    assert pvp.omitido
    assert "ROE" in (pvp.motivo_omissao or "")


def test_banco_nunca_usa_ev_ebitda_e_declara_exclusao() -> None:
    insumos = InsumosValuation(
        selic=_insumo(0.15, "BCB/SGS 432"),
        bvps=_insumo(20.0, "DFP"),
        roe=_insumo(0.18, "DFP"),
        peers_multiplos=(
            PeerMultiplo(nome="JPM", metrica="EV/EBITDA", valor=8.0, fonte="SEC EDGAR"),
            PeerMultiplo(nome="BAC", metrica="EV/EBITDA", valor=9.0, fonte="SEC EDGAR"),
        ),
    )
    v = avaliar("acao", "banco", None, insumos)
    assert v is not None
    assert {m.modelo for m in v.modelos} == {"pvp_justificado", "multiplos_pl", "multiplos_pvp"}
    # EV/EBITDA não vira modelo nem alimenta os múltiplos suportados.
    assert _modelo(v, "multiplos_pl").omitido
    assert _modelo(v, "multiplos_pvp").omitido
    assert any("EV/EBITDA não se aplica a bancos" in c for c in v.contexto)


# ---------------------------------------------------------------------------
# Múltiplos vs pares — golden à mão
# ---------------------------------------------------------------------------


def test_multiplos_pl_golden_faixa_min_max() -> None:
    """LPA = 500 mi / 100 mi = R$5,00; P/L dos pares {8, 10, 12} → faixa implícita
    = (8×5, 12×5) = (R$40, R$60); mediana 10 vai para a observação."""
    insumos = InsumosValuation(
        lucro_liquido_12m=_insumo(500_000_000.0, "DFP — lucro líquido 12m"),
        num_acoes=_insumo(100_000_000.0, "DFP — ações emitidas"),
        peers_multiplos=(
            PeerMultiplo(nome="PEER-A", metrica="P/L", valor=8.0, fonte="SEC EDGAR"),
            PeerMultiplo(nome="PEER-B", metrica="P/L", valor=12.0, fonte="SEC EDGAR"),
            PeerMultiplo(nome="PEER-C", metrica="P/L", valor=10.0, fonte="SEC EDGAR"),
        ),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    mult = _modelo(v, "multiplos_pl")
    assert not mult.omitido
    assert mult.faixa == pytest.approx((40.0, 60.0))
    assert len(mult.premissas) == 3  # um múltiplo rotulado por par
    assert any("mediana 10,00" in o for o in mult.observacoes)


def test_multiplos_omitidos_com_menos_de_dois_pares() -> None:
    insumos = InsumosValuation(
        lucro_liquido_12m=_insumo(500_000_000.0, "DFP"),
        num_acoes=_insumo(100_000_000.0, "DFP"),
        peers_multiplos=(PeerMultiplo(nome="X", metrica="P/L", valor=9.0, fonte="SEC"),),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    mult = _modelo(v, "multiplos_pl")
    assert mult.omitido
    assert "menos de 2 pares" in (mult.motivo_omissao or "")


def test_multiplos_pl_omitido_com_lucro_negativo() -> None:
    insumos = InsumosValuation(
        lucro_liquido_12m=_insumo(-10.0, "DFP"),
        num_acoes=_insumo(100.0, "DFP"),
        peers_multiplos=(
            PeerMultiplo(nome="A", metrica="P/L", valor=8.0, fonte="SEC"),
            PeerMultiplo(nome="B", metrica="P/L", valor=10.0, fonte="SEC"),
        ),
    )
    v = avaliar("acao", None, None, insumos)
    assert v is not None
    mult = _modelo(v, "multiplos_pl")
    assert mult.omitido
    assert "não positivo" in (mult.motivo_omissao or "")


# ---------------------------------------------------------------------------
# Energia — Gordon + RAP como contexto (nunca insumo)
# ---------------------------------------------------------------------------


def test_energia_rap_entra_como_contexto_com_fonte() -> None:
    insumos = dataclasses.replace(
        _insumos_acao_golden(),
        rap=Insumo(
            valor=4_000_000_000.0,
            fonte="ANEEL SIGET — Resolução Homologatória ciclo 2026-27",
            dt_referencia=_HOJE,
            rotulo="RAP agregada das concessões do grupo (mapa curado v1)",
        ),
    )
    v = avaliar("acao", None, "Energia Elétrica", insumos)
    assert v is not None
    assert not _modelo(v, "gordon").omitido
    assert any("RAP" in c and "ANEEL" in c for c in v.contexto)
    assert any("NÃO entra no cálculo" in c for c in v.contexto)


def test_energia_sem_rap_declara_abstencao_no_contexto() -> None:
    v = avaliar("acao", None, "Transmissão de Energia", _insumos_acao_golden())
    assert v is not None
    assert any("RAP não disponível" in c and "dado não encontrado" in c for c in v.contexto)


def test_setor_nao_energia_nao_tem_contexto_rap() -> None:
    v = avaliar("acao", None, "Mineração", _insumos_acao_golden())
    assert v is not None
    assert v.contexto == ()


# ---------------------------------------------------------------------------
# FII — leitura de mercado, sem valor intrínseco (golden à mão)
# ---------------------------------------------------------------------------


def test_fii_leitura_de_mercado_golden() -> None:
    """P/VP = 100/110 = 0,909... ('0,91'); DY = 9,60/100 = 9,60%;
    diferença vs Selic 15% = (0,096−0,15)×100 = −5,40 p.p."""
    insumos = InsumosValuation(
        preco_atual=_insumo(100.0, "B3 COTAHIST — fechamento"),
        vp_cota=_insumo(110.0, "Informe mensal CVM — VP por cota", dt.date(2026, 5, 31)),
        proventos_12m_por_cota=_insumo(9.60, "B3 — rendimentos 12m por cota"),
        selic=_insumo(0.15, "BCB/SGS 432 — meta Selic"),
    )
    v = avaliar("fii", None, None, insumos)
    assert v is not None
    assert v.classe == "fii"
    leitura = _modelo(v, "leitura_mercado_fii")
    assert not leitura.omitido
    assert leitura.cenarios == () and leitura.faixa is None  # sem valor intrínseco
    texto = " | ".join(leitura.observacoes)
    assert "P/VP a mercado: 0,91" in texto
    assert "DY a mercado 12m: 9,60%" in texto
    assert "-5,40 p.p." in texto
    assert "não ajustado" in texto  # rótulo COTAHIST obrigatório
    assert "COTAHIST" in texto and "CVM" in texto  # fontes nas observações


def test_fii_usa_cdi_quando_disponivel() -> None:
    insumos = InsumosValuation(
        preco_atual=_insumo(100.0, "B3 COTAHIST"),
        proventos_12m_por_cota=_insumo(9.60, "B3"),
        selic=_insumo(0.15, "BCB/SGS 432"),
        cdi=_insumo(0.149, "BCB/SGS 4389 — CDI anualizado"),
    )
    v = avaliar("fii", None, None, insumos)
    assert v is not None
    texto = " | ".join(_modelo(v, "leitura_mercado_fii").observacoes)
    assert "CDI" in texto and "14,90%" in texto


def test_fii_componentes_faltantes_viram_omissoes_declaradas() -> None:
    insumos = InsumosValuation(preco_atual=_insumo(100.0, "B3 COTAHIST"))
    v = avaliar("fii", None, None, insumos)
    assert v is not None
    leitura = _modelo(v, "leitura_mercado_fii")
    assert leitura.omitido
    assert "nenhum componente disponível" in (leitura.motivo_omissao or "")
    assert any("VP por cota" in o for o in leitura.omissoes)
    assert any("proventos" in o for o in leitura.omissoes)


# ---------------------------------------------------------------------------
# Roteamento por classe + degradação sem exceção
# ---------------------------------------------------------------------------


def test_renda_fixa_retorna_none_f3_usa_caminho_existente() -> None:
    assert avaliar("renda_fixa", None, None, InsumosValuation()) is None


def test_classe_desconhecida_retorna_none() -> None:
    assert avaliar("cripto", None, None, InsumosValuation()) is None


def test_classe_none_e_tratada_como_acao_legado() -> None:
    v = avaliar(None, None, None, _insumos_acao_golden())
    assert v is not None
    assert v.classe == "acao"


def test_insumos_vazios_degradam_para_abstencao_rotulada_sem_excecao() -> None:
    """Análogo puro da correção A13: SEM dado nenhum, nunca explode — devolve
    modelos omitidos com motivo declarado e o aviso fixo (nunca 500)."""
    v = avaliar("acao", None, None, InsumosValuation())
    assert v is not None
    assert all(m.omitido for m in v.modelos)
    assert all(m.motivo_omissao for m in v.modelos)
    assert v.aviso == AVISO_VALUATION

    v_banco = avaliar("acao", "banco", None, InsumosValuation())
    assert v_banco is not None
    assert all(m.omitido for m in v_banco.modelos)

    v_fii = avaliar("fii", None, None, InsumosValuation())
    assert v_fii is not None
    assert all(m.omitido for m in v_fii.modelos)


def test_taxa_em_escala_percentual_e_erro_de_contrato() -> None:
    """Selic=15.0 (percentual) em vez de 0.15 (fração) → ValueError imediato."""
    insumos = InsumosValuation(selic=_insumo(15.0, "BCB/SGS 432"))
    with pytest.raises(ValueError, match="fração decimal"):
        avaliar("acao", None, None, insumos)


# ---------------------------------------------------------------------------
# Aviso fixo + envelope + linguagem neutra (pré-gate A5/A6)
# ---------------------------------------------------------------------------


def test_aviso_fixo_exato_do_contrato() -> None:
    v = avaliar("acao", None, None, _insumos_acao_golden())
    assert v is not None
    assert v.aviso == (
        "Exercício de sensibilidade sob premissas explícitas — " "NÃO é preço-alvo nem recomendação"
    )


def test_envelope_e_json_serializavel_com_datas_iso() -> None:
    v = avaliar("acao", None, "Energia Elétrica", _insumos_acao_golden())
    assert v is not None
    env = valuation_para_envelope(v)
    dump = json.dumps(env, ensure_ascii=False)  # não pode explodir
    assert "2026-07-09" in dump  # dt.date → ISO
    assert env["aviso"] == AVISO_VALUATION
    assert isinstance(env["modelos"], list)


# Diretivas/termos que o gate (avaliacao.py + R10/R11 da F4) veta em texto livre.
# O AVISO fixo é a única exceção (contém "preço-alvo" em negação — carve-out da F4).
_PROIBIDOS = re.compile(
    r"\bcompre\b|\bcomprar\b|\bvenda\b|\bvender\b|\brecomend\w*|\boportunidad\w*"
    r"|\bbarat\w*|\batrativ\w*|\bupside\b|\bdesconto\b|\bpr[êe]mio\b"
    r"|\bpre[çc]o[\s-]?alvo\b|\bvalor[\s-]?alvo\b|\bpre[çc]o\s+justo\b|\bvalor\s+justo\b"
    r"|\bhora de\b|\bmomento de (compra|venda|comprar|vender)\b|\bsinal de (compra|venda)\b"
    r"|\bpotencial de (alta|valoriza)\w*",
    re.IGNORECASE,
)


def _textos_user_visible(env: dict) -> list[str]:
    """Todas as strings do envelope EXCETO o aviso fixo (carve-out da F4)."""
    textos: list[str] = []

    def _walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, val in obj.items():
                if k == "aviso":
                    continue
                _walk(val)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, str):
            textos.append(obj)

    _walk(env)
    return textos


def test_templates_nao_contem_linguagem_diretiva_em_nenhuma_classe() -> None:
    """Correção A5: todo texto livre user-visible do bloco de valuation (descrições,
    observações, motivos, rótulos, contexto) é neutro — zero linguagem de conselho."""
    casos: list[Valuation | None] = [
        avaliar("acao", None, None, _insumos_acao_golden()),
        avaliar("acao", "banco", None, _insumos_banco_golden()),
        avaliar("acao", None, "Energia Elétrica", _insumos_acao_golden()),
        avaliar("acao", None, None, InsumosValuation()),  # motivos de omissão
        avaliar(
            "fii",
            None,
            None,
            InsumosValuation(
                preco_atual=_insumo(100.0, "B3 COTAHIST"),
                vp_cota=_insumo(110.0, "Informe CVM"),
                proventos_12m_por_cota=_insumo(9.6, "B3"),
                selic=_insumo(0.15, "BCB/SGS 432"),
            ),
        ),
        avaliar(
            "acao",
            "banco",
            None,
            InsumosValuation(
                selic=_insumo(0.15, "BCB"),
                bvps=_insumo(20.0, "DFP"),
                roe=_insumo(0.18, "DFP"),
                peers_multiplos=(
                    PeerMultiplo(nome="JPM", metrica="EV/EBITDA", valor=8.0, fonte="SEC"),
                    PeerMultiplo(nome="A", metrica="P/L", valor=8.0, fonte="SEC"),
                    PeerMultiplo(nome="B", metrica="P/L", valor=10.0, fonte="SEC"),
                ),
                lucro_liquido_12m=_insumo(500.0, "DFP"),
                num_acoes=_insumo(100.0, "DFP"),
            ),
        ),
    ]
    for v in casos:
        assert v is not None
        for texto in _textos_user_visible(valuation_para_envelope(v)):
            m = _PROIBIDOS.search(texto)
            assert m is None, f"linguagem diretiva {m.group(0)!r} em template: {texto!r}"


def test_nenhum_modelo_computado_expoe_ponto_unico() -> None:
    """Todo modelo com cenários tem faixa (mín<máx já coberto no golden); modelos de
    múltiplos expõem faixa mín–máx; leitura FII não expõe valor intrínseco algum."""
    v = avaliar("acao", "banco", None, _insumos_banco_golden())
    assert v is not None
    for m in v.modelos:
        if m.omitido:
            continue
        if m.cenarios:
            assert m.faixa is not None and len(m.faixa) == 2
