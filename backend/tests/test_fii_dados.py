"""Testes offline do conector de FIIs (app.services.fii_dados).

Sem rede real (httpx.MockTransport pula a allowlist — padrão de
test_seguranca.py) e sem Postgres: SQLite em memória com as tabelas dos
modelos (server_defaults do Postgres removidos no DDL e preenchidos por
evento de sessão). Fixtures CSV/ZIP inline em latin-1, construídas em memória.

Números das fixtures = ground truth REAL do HGLG11 (informe mensal CVM,
competência 2025-12-01, verificado em 2026-07-08): PL 7.063.626.090,23;
VP/cota 166,576588; cotas 42.404.675; cotistas 525.069; DY mês 0,006635.
Os valores do informe são R$ CRUS (sem ESCALA_MOEDA) — o teste de escala
prova que o PL lê ~7,06 bi e nunca 7,06 tri.
"""

from __future__ import annotations

import datetime as dt
import io
import uuid
import zipfile
from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, event, select
from sqlalchemy.orm import Session

from app.models.models import FiiCadastro, FiiIndicador, Fonte
from app.services import fii_dados
from app.services.dados import DadoNaoEncontrado
from app.services.fii_dados import (
    _ticker_do_isin,
    ensure_fii,
    indicadores_recentes,
    ingest_indicadores,
    ingest_vacancia,
)

HOJE = dt.date(2026, 7, 8)

URL_MENSAL_2026 = fii_dados.CVM_FII_MENSAL_URL.format(ano=2026)
URL_MENSAL_2025 = fii_dados.CVM_FII_MENSAL_URL.format(ano=2025)
URL_TRI_2026 = fii_dados.CVM_FII_TRIMESTRAL_URL.format(ano=2026)
URL_TRI_2025 = fii_dados.CVM_FII_TRIMESTRAL_URL.format(ano=2025)

CNPJ_HGLG = "11.728.688/0001-47"
CNPJ_KNRI = "12.005.956/0001-65"
CNPJ_FALSO = "99.999.999/0001-99"

# --- Fixtures CSV (latin-1, ';') — layout do informe mensal/trimestral FII ---
_GERAL_2025 = (
    "CNPJ_Fundo;Data_Referencia;Versao;Nome_Fundo;Codigo_ISIN;Segmento_Atuacao;"
    "Mandato;Tipo_Gestao;Mercado_Negociacao_Bolsa\n"
    f"{CNPJ_HGLG};2025-11-01;1;PÁTRIA LOG - FII;BRHGLGCTF004;Multicategoria;Renda;Ativa;S\n"
    f"{CNPJ_HGLG};2025-12-01;1;PÁTRIA LOG - FII;BRHGLGCTF004;Multicategoria;Renda;Ativa;S\n"
    f"{CNPJ_KNRI};2025-12-01;1;KINEA RENDA IMOBILIARIA FII RL;BRKNRICTF000;Multicategoria;"
    "Renda;Ativa;S\n"
)

_COMPLEMENTO_2025 = (
    "CNPJ_Fundo;Data_Referencia;Versao;Valor_Ativo;Patrimonio_Liquido;Cotas_Emitidas;"
    "Valor_Patrimonial_Cotas;Total_Numero_Cotistas;Percentual_Dividend_Yield_Mes;"
    "Percentual_Rentabilidade_Efetiva_Mes\n"
    f"{CNPJ_HGLG};2025-11-01;1;7300000000.00;7060000000.00;42404675.00;166.50;524000;"
    "0.006500;0.011000\n"
    f"{CNPJ_HGLG};2025-12-01;1;7300000000.00;7063626090.23;42404675.00;166.576588;525069;"
    "0.006635;0.011383\n"
    # KNRI com Percentual_Rentabilidade_Efetiva_Mes VAZIO -> abstenção só desse campo.
    f"{CNPJ_KNRI};2025-12-01;1;4700000000.00;4602845516.98;28204000.00;163.198052;303496;"
    "0.007648;\n"
)

_GERAL_2026 = (
    "CNPJ_Fundo;Data_Referencia;Versao;Nome_Fundo;Codigo_ISIN;Segmento_Atuacao;"
    "Mandato;Tipo_Gestao;Mercado_Negociacao_Bolsa\n"
    f"{CNPJ_HGLG};2026-06-01;1;PÁTRIA LOG - FII;BRHGLGCTF004;Multicategoria;Renda;Ativa;S\n"
)

_COMPLEMENTO_2026 = (
    "CNPJ_Fundo;Data_Referencia;Versao;Valor_Ativo;Patrimonio_Liquido;Cotas_Emitidas;"
    "Valor_Patrimonial_Cotas;Total_Numero_Cotistas;Percentual_Dividend_Yield_Mes;"
    "Percentual_Rentabilidade_Efetiva_Mes\n"
    f"{CNPJ_HGLG};2026-06-01;1;7400000000.00;7100000000.00;42404675.00;167.43;530000;"
    "0.006700;0.010900\n"
)

# Trimestral: trimestre VELHO (2025-09-30) + último (2025-12-31) com os 2 imóveis
# reais do HGLG11 — o agregado deve usar SÓ o último trimestre.
AREA_MASTER_LABS = 14337.0
AREA_CONDOMINIO_SJC = 72487.0
VAC_MASTER_LABS = 0.181971

_TRIMESTRAL_2025 = (
    "CNPJ_Fundo;Data_Referencia;Versao;Nome_Imovel;Percentual_Vacancia;"
    "Percentual_Inadimplencia;Area;Classe\n"
    f"{CNPJ_HGLG};2025-09-30;1;Master Labs;0.150000;0;{AREA_MASTER_LABS};Imóvel\n"
    f"{CNPJ_HGLG};2025-12-31;1;Master Labs;{VAC_MASTER_LABS};0;{AREA_MASTER_LABS};Imóvel\n"
    f"{CNPJ_HGLG};2025-12-31;1;Condomínio SJC;0.0;0;{AREA_CONDOMINIO_SJC};Imóvel\n"
)

_TRIMESTRAL_SEM_VACANCIA = (
    "CNPJ_Fundo;Data_Referencia;Versao;Nome_Imovel;Percentual_Vacancia;"
    "Percentual_Inadimplencia;Area;Classe\n"
    f"{CNPJ_HGLG};2025-12-31;1;Master Labs;{VAC_MASTER_LABS};0;{AREA_MASTER_LABS};Imóvel\n"
    f"{CNPJ_HGLG};2025-12-31;1;Condomínio SJC;;0;{AREA_CONDOMINIO_SJC};Imóvel\n"
)


# --- Helpers de fixture ------------------------------------------------------
def _zip_bytes(membros: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, texto in membros.items():
            z.writestr(nome, texto.encode("latin-1"))
    return buf.getvalue()


def _zip_mensal(ano: int, geral: str, complemento: str) -> bytes:
    return _zip_bytes(
        {
            f"inf_mensal_fii_geral_{ano}.csv": geral,
            f"inf_mensal_fii_complemento_{ano}.csv": complemento,
            f"inf_mensal_fii_ativo_passivo_{ano}.csv": "CNPJ_Fundo;Data_Referencia\n",
        }
    )


def _zip_trimestral(ano: int, imovel_csv: str) -> bytes:
    return _zip_bytes({f"inf_trimestral_fii_imovel_{ano}.csv": imovel_csv})


def _transport(mapa: dict[str, bytes], chamadas: list[str] | None = None) -> httpx.MockTransport:
    """Serve os ZIPs por URL exata; fora do mapa -> 404 (exercita a cascata)."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if chamadas is not None:
            chamadas.append(url)
        corpo = mapa.get(url)
        if corpo is None:
            return httpx.Response(404, text="nao existe")
        return httpx.Response(200, content=corpo)

    return httpx.MockTransport(handler)


def _mapa_mensal_2025() -> dict[str, bytes]:
    return {URL_MENSAL_2025: _zip_mensal(2025, _GERAL_2025, _COMPLEMENTO_2025)}


# --- Sessão SQLite em memória -------------------------------------------------
@pytest.fixture()
def sessao() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    meta = MetaData()
    for tabela in (Fonte.__table__, FiiCadastro.__table__, FiiIndicador.__table__):
        copia = tabela.to_metadata(meta)
        for col in copia.columns:
            col.server_default = None  # gen_random_uuid()/now() não existem no SQLite
    meta.create_all(engine)
    with Session(engine) as s:

        @event.listens_for(s, "before_flush")
        def _defaults(sess, _ctx, _instances) -> None:
            for obj in sess.new:
                if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()
                if hasattr(obj, "criado_em") and getattr(obj, "criado_em", None) is None:
                    obj.criado_em = dt.datetime.now(dt.UTC)

        yield s
    engine.dispose()


def _fii_manual(sessao: Session, cnpj: str = CNPJ_HGLG, ticker: str | None = "HGLG11"):
    fii = FiiCadastro(cnpj=cnpj, nome="PÁTRIA LOG - FII", ticker=ticker)
    sessao.add(fii)
    sessao.flush()
    return fii


def _indicador(sessao: Session, fii, codigo: str) -> list[FiiIndicador]:
    return list(
        sessao.execute(
            select(FiiIndicador)
            .where(FiiIndicador.fii_id == fii.id, FiiIndicador.indicador == codigo)
            .order_by(FiiIndicador.dt_referencia)
        )
        .scalars()
        .all()
    )


def _seed_indicador(sessao: Session, fii, codigo: str, valor: float, data: dt.date) -> None:
    fonte = Fonte(url="https://dados.cvm.gov.br/x", descricao="seed", dt_referencia=data)
    sessao.add(fonte)
    sessao.flush()
    sessao.add(
        FiiIndicador(
            fii_id=fii.id,
            indicador=codigo,
            valor=valor,
            unidade="BRL",
            dt_referencia=data,
            fonte_id=fonte.id,
        )
    )
    sessao.flush()


# ---------------------------------------------------------------------------
# Heurística ISIN -> ticker
# ---------------------------------------------------------------------------
def test_heuristica_isin_hglg() -> None:
    assert _ticker_do_isin("BRHGLGCTF004") == "HGLG11"


def test_heuristica_isin_normaliza_caixa_e_espacos() -> None:
    assert _ticker_do_isin("  brhglgctf004 ") == "HGLG11"


@pytest.mark.parametrize(
    "malformado",
    [
        None,
        "",
        "HGLG",  # curto demais
        "BRHGLGCTF04",  # 11 chars
        "BRHGLGCTF0045",  # 13 chars
        "1RHGLGCTF004",  # país não começa com letra
        "BRHGLGCTF00X",  # dígito verificador não numérico
    ],
)
def test_heuristica_isin_malformado_vira_none(malformado: str | None) -> None:
    assert _ticker_do_isin(malformado) is None


# ---------------------------------------------------------------------------
# ensure_fii — cadastro, cascata de ano e abstenção
# ---------------------------------------------------------------------------
def test_ensure_fii_resolve_hglg11_com_heuristica_rotulada(sessao: Session) -> None:
    fii = ensure_fii(sessao, "hglg11", hoje=HOJE, transport=_transport(_mapa_mensal_2025()))
    assert fii.cnpj == CNPJ_HGLG
    assert fii.nome == "PÁTRIA LOG - FII"
    assert fii.ticker == "HGLG11"
    assert fii.ticker_metodo == "heuristica_isin"  # heurística NUNCA vira fato oficial
    assert fii.isin == "BRHGLGCTF004"
    assert fii.segmento == "Multicategoria"
    assert fii.mandato == "Renda"
    assert fii.tipo_gestao == "Ativa"
    assert fii.mercado_bolsa == "S"
    assert fii.dt_referencia == dt.date(2025, 12, 1)  # ÚLTIMA Data_Referencia do fundo
    assert fii.fonte_id is not None  # sem fonte não é fato


def test_ensure_fii_cascata_tenta_ano_corrente_antes_do_anterior(sessao: Session) -> None:
    chamadas: list[str] = []
    ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=_transport(_mapa_mensal_2025(), chamadas))
    assert chamadas[0] == URL_MENSAL_2026  # 2026 primeiro (404 na fixture)...
    assert URL_MENSAL_2025 in chamadas  # ...fallback ano-1 resolve


def test_ensure_fii_idempotente_nao_duplica_cadastro(sessao: Session) -> None:
    transport = _transport(_mapa_mensal_2025())
    ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=transport)
    fii = ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=transport)
    linhas = (
        sessao.execute(select(FiiCadastro).where(FiiCadastro.cnpj == CNPJ_HGLG)).scalars().all()
    )
    assert len(linhas) == 1
    assert fii.ticker == "HGLG11"  # segunda rodada não zera o ticker do próprio fundo


def test_ensure_fii_ticker_inexistente_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado, match="dado não encontrado"):
        ensure_fii(sessao, "XXXX11", hoje=HOJE, transport=_transport(_mapa_mensal_2025()))


def test_ensure_fii_sem_zip_em_nenhum_ano_abstem(sessao: Session) -> None:
    with pytest.raises(DadoNaoEncontrado):
        ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=_transport({}))


# ---------------------------------------------------------------------------
# Colisão de raiz ISIN -> ticker NULL para AMBOS, sem abortar o ingest
# ---------------------------------------------------------------------------
_GERAL_COLISAO = (
    "CNPJ_Fundo;Data_Referencia;Versao;Nome_Fundo;Codigo_ISIN;Segmento_Atuacao;"
    "Mandato;Tipo_Gestao;Mercado_Negociacao_Bolsa\n"
    f"{CNPJ_HGLG};2025-12-01;1;PÁTRIA LOG - FII;BRHGLGCTF004;Multicategoria;Renda;Ativa;S\n"
    f"{CNPJ_FALSO};2025-12-01;1;FUNDO SÓSIA FII;BRHGLGABC123;Logística;Renda;Passiva;S\n"
)


def test_colisao_no_mesmo_lote_zera_ambos_sem_abortar(sessao: Session) -> None:
    mapa = {URL_MENSAL_2025: _zip_mensal(2025, _GERAL_COLISAO, _COMPLEMENTO_2025)}
    # A raiz HGLG colide entre 2 CNPJs -> heurística some para os DOIS e o
    # ticker não resolve (abstenção)...
    with pytest.raises(DadoNaoEncontrado):
        ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=_transport(mapa))
    # ...mas o ingest do lote NÃO aborta: os dois fundos ficam persistidos
    # (acessíveis por CNPJ), ambos com ticker NULL.
    linhas = sessao.execute(select(FiiCadastro)).scalars().all()
    por_cnpj = {linha.cnpj: linha for linha in linhas}
    assert {CNPJ_HGLG, CNPJ_FALSO} <= set(por_cnpj)
    assert por_cnpj[CNPJ_HGLG].ticker is None
    assert por_cnpj[CNPJ_FALSO].ticker is None
    assert por_cnpj[CNPJ_HGLG].ticker_metodo is None


def test_colisao_com_ticker_ja_persistido_zera_ambos(sessao: Session) -> None:
    # 1ª rodada: só o HGLG11 existe e ganha o ticker pela heurística.
    ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=_transport(_mapa_mensal_2025()))
    # 2ª rodada: outro CNPJ chega com a MESMA raiz de ISIN (unique de ticker
    # no banco). O conector zera o ticker de AMBOS sem abortar.
    geral_b = (
        "CNPJ_Fundo;Data_Referencia;Versao;Nome_Fundo;Codigo_ISIN;Segmento_Atuacao;"
        "Mandato;Tipo_Gestao;Mercado_Negociacao_Bolsa\n"
        f"{CNPJ_FALSO};2025-12-01;1;FUNDO SÓSIA FII;BRHGLGABC123;Logística;Renda;Passiva;S\n"
    )
    mapa_b = {URL_MENSAL_2025: _zip_mensal(2025, geral_b, _COMPLEMENTO_2025)}
    with pytest.raises(DadoNaoEncontrado):
        ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=_transport(mapa_b))
    linhas = sessao.execute(select(FiiCadastro)).scalars().all()
    por_cnpj = {linha.cnpj: linha for linha in linhas}
    assert {CNPJ_HGLG, CNPJ_FALSO} <= set(por_cnpj)  # ninguém foi descartado
    assert por_cnpj[CNPJ_HGLG].ticker is None  # o dono anterior também perde
    assert por_cnpj[CNPJ_HGLG].ticker_metodo is None
    assert por_cnpj[CNPJ_FALSO].ticker is None


# ---------------------------------------------------------------------------
# ingest_indicadores — números REAIS do HGLG11, R$ CRUS (sem reescala)
# ---------------------------------------------------------------------------
def test_indicadores_reais_hglg_persistidos_sem_reescala(sessao: Session) -> None:
    transport = _transport(_mapa_mensal_2025())
    fii = ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=transport)
    ingest_indicadores(sessao, fii, hoje=HOJE, transport=transport)

    pl = _indicador(sessao, fii, "PL")[-1]
    assert float(pl.valor) == pytest.approx(7_063_626_090.23)
    # Regra de escala do informe FII: R$ CRUS. Se alguém aplicar a escala MIL
    # da DFP aqui, o PL viraria 7,06 TRILHÕES — este guarda pega a regressão.
    assert float(pl.valor) < 1e10
    assert pl.unidade == "BRL"
    assert pl.dt_referencia == dt.date(2025, 12, 1)
    assert pl.fonte_id is not None

    vp = _indicador(sessao, fii, "VP_COTA")[-1]
    assert float(vp.valor) == pytest.approx(166.576588)
    assert vp.unidade == "BRL_POR_COTA"

    cotas = _indicador(sessao, fii, "COTAS_EMITIDAS")[-1]
    assert float(cotas.valor) == pytest.approx(42_404_675.0)
    assert cotas.unidade == "UN"

    cotistas = _indicador(sessao, fii, "COTISTAS")[-1]
    assert float(cotistas.valor) == pytest.approx(525_069.0)
    assert cotistas.unidade == "UN"

    dy = _indicador(sessao, fii, "DY_MES_INFORME")[-1]
    assert float(dy.valor) == pytest.approx(0.006635)  # fração decimal, como no CSV
    assert dy.unidade == "PCT"
    assert dy.metodologia == "auto-declarado pelo administrador; informe mensal CVM"
    assert dy.fonte_id is not None

    rent = _indicador(sessao, fii, "RENT_EFETIVA_MES")[-1]
    assert float(rent.valor) == pytest.approx(0.011383)


def test_indicadores_gravam_serie_historica_por_competencia(sessao: Session) -> None:
    transport = _transport(_mapa_mensal_2025())
    fii = ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=transport)
    ingest_indicadores(sessao, fii, hoje=HOJE, transport=transport)
    datas = [ind.dt_referencia for ind in _indicador(sessao, fii, "PL")]
    assert datas == [dt.date(2025, 11, 1), dt.date(2025, 12, 1)]  # TODAS as competências


def test_indicadores_ingere_zip_do_ano_corrente_e_do_anterior(sessao: Session) -> None:
    mapa = {
        URL_MENSAL_2026: _zip_mensal(2026, _GERAL_2026, _COMPLEMENTO_2026),
        URL_MENSAL_2025: _zip_mensal(2025, _GERAL_2025, _COMPLEMENTO_2025),
    }
    transport = _transport(mapa)
    fii = ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=transport)
    ingest_indicadores(sessao, fii, hoje=HOJE, transport=transport)
    datas = [ind.dt_referencia for ind in _indicador(sessao, fii, "PL")]
    assert datas == [dt.date(2025, 11, 1), dt.date(2025, 12, 1), dt.date(2026, 6, 1)]


def test_indicador_campo_vazio_abstem_sem_derrubar_os_demais(sessao: Session) -> None:
    transport = _transport(_mapa_mensal_2025())
    fii = ensure_fii(sessao, "KNRI11", hoje=HOJE, transport=transport)
    ingest_indicadores(sessao, fii, hoje=HOJE, transport=transport)
    assert _indicador(sessao, fii, "RENT_EFETIVA_MES") == []  # campo vazio -> não grava
    pl = _indicador(sessao, fii, "PL")
    assert len(pl) == 1 and float(pl[0].valor) == pytest.approx(4_602_845_516.98)


def test_ingest_indicadores_idempotente(sessao: Session) -> None:
    transport = _transport(_mapa_mensal_2025())
    fii = ensure_fii(sessao, "HGLG11", hoje=HOJE, transport=transport)
    ingest_indicadores(sessao, fii, hoje=HOJE, transport=transport)
    antes = len(sessao.execute(select(FiiIndicador)).scalars().all())
    ingest_indicadores(sessao, fii, hoje=HOJE, transport=transport)
    depois = len(sessao.execute(select(FiiIndicador)).scalars().all())
    assert antes == depois  # rodar 2x não duplica (upsert por fii+indicador+dt)


def test_ingest_indicadores_sem_zip_em_nenhum_ano_abstem(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    with pytest.raises(DadoNaoEncontrado):
        ingest_indicadores(sessao, fii, hoje=HOJE, transport=_transport({}))


# ---------------------------------------------------------------------------
# ingest_vacancia — média ponderada pela ÁREA + abstenção estrita
# ---------------------------------------------------------------------------
def test_vacancia_ponderada_por_area_do_ultimo_trimestre(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    mapa = {URL_TRI_2025: _zip_trimestral(2025, _TRIMESTRAL_2025)}
    ind = ingest_vacancia(sessao, fii, hoje=HOJE, transport=_transport(mapa))
    assert ind is not None
    esperado = (VAC_MASTER_LABS * AREA_MASTER_LABS + 0.0 * AREA_CONDOMINIO_SJC) / (
        AREA_MASTER_LABS + AREA_CONDOMINIO_SJC
    )
    assert float(ind.valor) == pytest.approx(esperado)
    assert ind.unidade == "PCT"
    assert ind.dt_referencia == dt.date(2025, 12, 31)  # último trimestre, não 2025-09-30
    assert ind.metodologia == (
        "média ponderada pela área (m²) dos imóveis; "
        "vacância auto-declarada por imóvel no informe trimestral CVM"
    )
    assert ind.fonte_id is not None


def test_vacancia_imovel_sem_percentual_aborta_agregado(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    mapa = {URL_TRI_2025: _zip_trimestral(2025, _TRIMESTRAL_SEM_VACANCIA)}
    assert ingest_vacancia(sessao, fii, hoje=HOJE, transport=_transport(mapa)) is None
    assert _indicador(sessao, fii, "VACANCIA_AGREGADA") == []  # nada gravado (lacuna)


@pytest.mark.parametrize("area_ruim", ["", "0", "0.0"])
def test_vacancia_area_vazia_ou_zero_aborta_agregado(sessao: Session, area_ruim: str) -> None:
    fii = _fii_manual(sessao)
    csv_area = (
        "CNPJ_Fundo;Data_Referencia;Versao;Nome_Imovel;Percentual_Vacancia;"
        "Percentual_Inadimplencia;Area;Classe\n"
        f"{CNPJ_HGLG};2025-12-31;1;Master Labs;{VAC_MASTER_LABS};0;{AREA_MASTER_LABS};Imóvel\n"
        f"{CNPJ_HGLG};2025-12-31;1;Sem Área;0.05;0;{area_ruim};Imóvel\n"
    )
    mapa = {URL_TRI_2025: _zip_trimestral(2025, csv_area)}
    assert ingest_vacancia(sessao, fii, hoje=HOJE, transport=_transport(mapa)) is None
    assert _indicador(sessao, fii, "VACANCIA_AGREGADA") == []


def test_vacancia_idempotente(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    mapa = {URL_TRI_2025: _zip_trimestral(2025, _TRIMESTRAL_2025)}
    ingest_vacancia(sessao, fii, hoje=HOJE, transport=_transport(mapa))
    ingest_vacancia(sessao, fii, hoje=HOJE, transport=_transport(mapa))
    assert len(_indicador(sessao, fii, "VACANCIA_AGREGADA")) == 1


def test_vacancia_sem_informe_devolve_none(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    assert ingest_vacancia(sessao, fii, hoje=HOJE, transport=_transport({})) is None


# ---------------------------------------------------------------------------
# indicadores_recentes — staleness de 90 dias com 'hoje' injetável
# ---------------------------------------------------------------------------
def test_staleness_90_dias_exclui_competencia_velha(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    _seed_indicador(sessao, fii, "PL", 7_100_000_000.0, dt.date(2026, 6, 1))  # 37 dias
    _seed_indicador(sessao, fii, "DY_MES_INFORME", 0.006635, dt.date(2025, 12, 1))  # 219 dias
    recentes = indicadores_recentes(sessao, fii, hoje=HOJE)
    assert "PL" in recentes
    assert "DY_MES_INFORME" not in recentes  # mais velho que 90 dias -> excluído


def test_staleness_limite_de_90_dias_e_inclusivo(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    _seed_indicador(sessao, fii, "PL", 7_000_000_000.0, HOJE - dt.timedelta(days=90))
    _seed_indicador(sessao, fii, "VP_COTA", 166.0, HOJE - dt.timedelta(days=91))
    recentes = indicadores_recentes(sessao, fii, hoje=HOJE)
    assert "PL" in recentes  # exatamente 90 dias -> entra (<= 90)
    assert "VP_COTA" not in recentes  # 91 dias -> sai


def test_indicadores_recentes_devolve_o_mais_novo_por_indicador(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    _seed_indicador(sessao, fii, "PL", 7_000_000_000.0, dt.date(2026, 5, 1))
    _seed_indicador(sessao, fii, "PL", 7_100_000_000.0, dt.date(2026, 6, 1))
    recentes = indicadores_recentes(sessao, fii, hoje=HOJE)
    assert float(recentes["PL"].valor) == pytest.approx(7_100_000_000.0)
    assert recentes["PL"].dt_referencia == dt.date(2026, 6, 1)


def test_indicadores_recentes_staleness_customizavel(sessao: Session) -> None:
    fii = _fii_manual(sessao)
    _seed_indicador(sessao, fii, "PL", 7_100_000_000.0, dt.date(2026, 6, 1))  # 37 dias
    assert "PL" not in indicadores_recentes(sessao, fii, hoje=HOJE, staleness_dias=30)
    assert "PL" in indicadores_recentes(sessao, fii, hoje=HOJE, staleness_dias=90)
