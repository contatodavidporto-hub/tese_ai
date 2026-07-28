"""Lógica das lanes de RLS (`app/db/rls.py`) — parte PURA, testável sem Postgres.

Prova comportamental de ISOLAMENTO (dois usuários, SET ROLE, WITH CHECK) roda contra
Postgres real em `test_rls_isolamento.py` (marker `rls`, CI). Aqui: os comandos que o
listener estampa por transação, o fail-closed, e que o `set_config` é PARAMETRIZADO
(nunca interpola claims na string — anti-injeção de impersonação).
"""

from __future__ import annotations

import pytest

from app.db import rls


def test_lane_user_estampa_role_e_claims_parametrizadas() -> None:
    cmds = rls.comandos_rls("user", '{"sub":"abc","role":"authenticated","aal":"aal2"}')
    assert cmds[0] == ("set local role authenticated", ())
    sql, params = cmds[1]
    # Claims vão como PARÂMETRO (%s), jamais interpoladas na string SQL.
    assert "set_config('request.jwt.claims', %s, true)" in sql
    assert params == ('{"sub":"abc","role":"authenticated","aal":"aal2"}',)
    assert "abc" not in sql  # o sub NÃO aparece no texto do comando


def test_lane_anon_so_troca_role() -> None:
    assert rls.comandos_rls("anon", None) == [("set local role anon", ())]


def test_lane_worker_usa_app_worker() -> None:
    assert rls.comandos_rls("worker", None) == [("set local role app_worker", ())]


def test_sem_lane_e_fail_closed() -> None:
    with pytest.raises(rls.RlsSemEscopo):
        rls.comandos_rls(None, None)


def test_lane_desconhecida_e_fail_closed() -> None:
    with pytest.raises(rls.RlsSemEscopo):
        rls.comandos_rls("root", None)  # nunca vira SET ROLE de algo fora da whitelist


def test_lane_user_sem_claims_e_fail_closed() -> None:
    with pytest.raises(rls.RlsSemEscopo):
        rls.comandos_rls("user", None)


def test_role_de_cada_lane_e_da_whitelist_fechada() -> None:
    assert set(rls._LANE_ROLE.values()) == {"authenticated", "anon", "app_worker"}
