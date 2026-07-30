"""LLM-COST-01: orçamento de custo de LLM por usuário/dia (além do teto global)."""

from __future__ import annotations

import pytest

from app.core.limits import CustoDiarioTracker, TetoCustoExcedido, TetoCustoUsuarioExcedido


def test_esgotar_orcamento_de_A_nao_bloqueia_B():
    t = CustoDiarioTracker()
    t.registrar(3.0, user_id="A")
    t.registrar(3.0, user_id="A")  # A = 6.0 >= teto 5.0
    with pytest.raises(TetoCustoUsuarioExcedido):
        t.verificar_usuario("A", 5.0)
    # B nunca gastou -> segue gerando (o cerne do LLM-COST-01)
    t.verificar_usuario("B", 5.0)  # não levanta


def test_teto_usuario_e_subclasse_do_global_para_herdar_abstencao():
    assert issubclass(TetoCustoUsuarioExcedido, TetoCustoExcedido)


def test_desligado_ou_tese_publica_nao_tem_limite_por_usuario():
    t = CustoDiarioTracker()
    t.registrar(100.0, user_id="x")
    t.verificar_usuario("x", 0)  # teto 0 = desligado
    t.verificar_usuario(None, 5.0)  # tese pública/sistema (user_id None)


def test_teto_global_soma_todos_os_usuarios():
    t = CustoDiarioTracker()
    t.registrar(10.0, user_id="x")
    t.registrar(10.0, user_id="y")  # global = 20
    with pytest.raises(TetoCustoExcedido):
        t.verificar(15.0)
    # mas cada usuário isolado ainda está sob o seu teto por-usuário
    t.verificar_usuario("x", 15.0)
