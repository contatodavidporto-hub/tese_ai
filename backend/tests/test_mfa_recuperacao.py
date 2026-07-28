"""2FA — códigos de recuperação (cofre) + gate aal2 (`services/mfa.py`, `routers/conta.py`).

O cofre roda em SQLite real (subset schema); o break-glass/exclusão (Admin API httpx) e
o `tem_fator_totp_verified` (função SECURITY DEFINER do Postgres) são mockados — a prova
comportamental da policy aal2 contra Postgres real está em `test_rls_isolamento.py`.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import Session

from app.core.auth import Identidade
from app.models.models import CodigoRecuperacao
from app.routers import conta
from app.services import mfa

USER_A = uuid.uuid4()
USER_B = uuid.uuid4()


@pytest.fixture()
def sessao():
    engine = create_engine("sqlite://")
    meta = MetaData()
    copia = CodigoRecuperacao.__table__.to_metadata(meta)
    for col in copia.columns:
        col.server_default = None  # gen_random_uuid()/now() não existem no SQLite
    meta.create_all(engine)
    with Session(engine) as s:

        @event.listens_for(s, "before_flush")
        def _defaults(sess, _ctx, _instances) -> None:
            for obj in sess.new:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()
                if getattr(obj, "criado_em", None) is None:
                    obj.criado_em = dt.datetime.now(dt.UTC)

        yield s


def _ident(*, aal: str = "aal1", amr=None) -> Identidade:
    return Identidade(
        user_id=str(USER_A),
        session_id="s",
        role="authenticated",
        aal=aal,
        amr=amr,
        email="a@t",
        claims={},
    )


# --- Cofre de códigos --------------------------------------------------------
def test_hash_ignora_hifen_e_caixa() -> None:
    assert mfa._hash("ABCD-1234-EF56") == mfa._hash("abcd1234ef56")


def test_gerar_10_codigos_formatados(sessao) -> None:
    codigos = mfa.gerar_codigos(sessao, USER_A)
    assert len(codigos) == 10
    assert all(len(c) == 24 and c.count("-") == 4 for c in codigos)  # 20 hex + 4 hífens
    assert mfa.contar_codigos_ativos(sessao, USER_A) == 10


def test_regerar_apaga_lote_anterior(sessao) -> None:
    mfa.gerar_codigos(sessao, USER_A)
    mfa.gerar_codigos(sessao, USER_A)
    assert mfa.contar_codigos_ativos(sessao, USER_A) == 10  # não 20


def test_consumir_single_use(sessao) -> None:
    codigos = mfa.gerar_codigos(sessao, USER_A)
    assert mfa.consumir_codigo(sessao, USER_A, codigos[0]) is True
    assert mfa.consumir_codigo(sessao, USER_A, codigos[0]) is False  # já usado
    assert mfa.contar_codigos_ativos(sessao, USER_A) == 9


def test_consumir_aceita_com_ou_sem_hifen(sessao) -> None:
    codigos = mfa.gerar_codigos(sessao, USER_A)
    sem_hifen = codigos[0].replace("-", "").lower()
    assert mfa.consumir_codigo(sessao, USER_A, sem_hifen) is True


def test_consumir_codigo_invalido(sessao) -> None:
    mfa.gerar_codigos(sessao, USER_A)
    assert mfa.consumir_codigo(sessao, USER_A, "0000-0000-0000-0000-0000") is False


def test_codigo_de_outro_usuario_nao_consome(sessao) -> None:
    codigos_a = mfa.gerar_codigos(sessao, USER_A)
    mfa.gerar_codigos(sessao, USER_B)
    assert mfa.consumir_codigo(sessao, USER_B, codigos_a[0]) is False
    assert mfa.contar_codigos_ativos(sessao, USER_A) == 10  # o lote de A intacto


# --- Gate aal2 ---------------------------------------------------------------
def test_exigir_aal2_com_aal2_passa() -> None:
    conta.exigir_aal2(_ident(aal="aal2"), session=None)  # nem toca a sessão


def test_exigir_aal2_aal1_sem_fator_passa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conta.mfa, "tem_fator_totp_verificado", lambda _s, _u: False)
    conta.exigir_aal2(_ident(aal="aal1"), session="fake")


def test_exigir_aal2_aal1_com_fator_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conta.mfa, "tem_fator_totp_verificado", lambda _s, _u: True)
    with pytest.raises(HTTPException) as exc:
        conta.exigir_aal2(_ident(aal="aal1"), session="fake")
    assert exc.value.status_code == 403


# --- Reautenticação para break-glass -----------------------------------------
def test_senha_recente() -> None:
    agora = dt.datetime.now(dt.UTC).timestamp()
    assert conta._senha_recente(_ident(amr=[{"method": "password", "timestamp": int(agora)}]))
    assert not conta._senha_recente(
        _ident(amr=[{"method": "password", "timestamp": int(agora) - 3600}])
    )  # 1h atrás
    assert not conta._senha_recente(_ident(amr=[{"method": "otp"}]))  # sem password
    assert not conta._senha_recente(_ident(amr=None))
