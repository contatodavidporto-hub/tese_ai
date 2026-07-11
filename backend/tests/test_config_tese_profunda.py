"""Testes dos defaults novos de config da Fundação (F0) da Fase "Tese Profunda".

Cobre: kill-switch de consenso (LLM06, desligado por padrão), teto de custo
diário revisado (10 -> 25), parâmetros de validação de consenso (A11) e a
cadência dos jobs de ingest novos (§2.12 do plano). Sem rede/DB — só defaults.
"""

from __future__ import annotations

from app.core.config import Settings


def test_consenso_desligado_por_padrao() -> None:
    # Gasto automático de LLM (web_search) exige autorização expressa (LLM06),
    # mesmo desenho do kill-switch do warm-cache — nunca liga sozinho.
    assert Settings().consenso_enabled is False


def test_teto_de_custo_diario_subiu_para_25() -> None:
    # 10 -> 25: síntese com max_tokens maior + consenso sobem o custo/tese
    # (correção A14); warm-cache frio (12 ativos) precisa caber com folga.
    assert Settings().tese_teto_custo_usd_dia == 25.0


def test_consenso_tem_teto_de_busca_e_staleness_default() -> None:
    s = Settings()
    assert s.consenso_web_search_max_uses == 4
    assert s.consenso_max_page_age_dias == 180


def test_consenso_allowed_domains_default_e_a_lista_curada() -> None:
    s = Settings()
    assert s.consenso_allowed_domains_list == [
        "infomoney.com.br",
        "seudinheiro.com",
        "suno.com.br",
        "moneytimes.com.br",
        "exame.com",
        "valor.globo.com",
        "conteudos.xpi.com.br",
    ]


def test_consenso_allowed_domains_list_normaliza_espacos() -> None:
    s = Settings(consenso_allowed_domains=" infomoney.com.br , exame.com ,, ")
    assert s.consenso_allowed_domains_list == ["infomoney.com.br", "exame.com"]


def test_scheduler_horas_novos_da_tese_profunda() -> None:
    s = Settings()
    assert s.scheduler_cotahist_horas == 24
    assert s.scheduler_anbima_horas == 24
    assert s.scheduler_ifdata_horas == 720
    assert s.scheduler_aneel_horas == 720
