"""Validação do access token do GoTrue (`app/core/auth.py`).

Hermético: gera um par ES256 local e faz monkeypatch da resolução de chave — nunca
toca a rede/JWKS. Cobre o caminho feliz e os ataques que a allowlist ES256 tem de
barrar (confusão HS256-com-chave-pública, `alg: none`), além dos claims estruturais
obrigatórios (exp/aud/iss/session_id).
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import types
from typing import Annotated

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.core import auth

ISSUER_BASE = "https://proj.supabase.co"
ISSUER = f"{ISSUER_BASE}/auth/v1"
KID = "test-kid"

_PRIV = ec.generate_private_key(ec.SECP256R1())
_PUB = _PRIV.public_key()
_PUB_PEM = _PUB.public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)


@pytest.fixture(autouse=True)
def _config_e_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings com o supabase_url do teste + resolução de chave local (sem rede)."""
    fake = types.SimpleNamespace(
        supabase_url=ISSUER_BASE,
        supabase_jwt_audience="authenticated",
        jwt_leeway_segundos=30,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: fake)
    # Seam: qualquer token válido resolve para a nossa chave pública local.
    monkeypatch.setattr(auth, "_chave_de_assinatura", lambda _token: _PUB)


def _claims(**over: object) -> dict:
    agora = dt.datetime.now(dt.UTC)
    base = {
        "iss": ISSUER,
        "aud": "authenticated",
        "sub": "11111111-1111-1111-1111-111111111111",
        "session_id": "22222222-2222-2222-2222-222222222222",
        "role": "authenticated",
        "aal": "aal1",
        "amr": [{"method": "password", "timestamp": int(agora.timestamp())}],
        "email": "user@example.com",
        "iat": agora,
        "exp": agora + dt.timedelta(minutes=10),
    }
    base.update(over)
    return base


def _es256(**over: object) -> str:
    return jwt.encode(_claims(**over), _PRIV, algorithm="ES256", headers={"kid": KID})


# --- Caminho feliz ----------------------------------------------------------
def test_token_valido_extrai_identidade_completa() -> None:
    ident = auth.validar_token(_es256())
    assert ident.user_id == "11111111-1111-1111-1111-111111111111"
    assert ident.session_id == "22222222-2222-2222-2222-222222222222"
    assert ident.role == "authenticated"
    assert ident.aal == "aal1"
    assert ident.email == "user@example.com"


def test_claims_rls_inclui_aal_session_amr_nao_so_sub() -> None:
    ident = auth.validar_token(_es256(aal="aal2"))
    rls = ident.claims_rls()
    assert rls["sub"] == ident.user_id
    assert rls["role"] == "authenticated"
    assert rls["aal"] == "aal2"  # sem isto o gate de 2FA falha (correção do red-team)
    assert rls["session_id"] == ident.session_id
    assert "amr" in rls


def _b64u(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


# --- Ataques que a allowlist ES256 barra -------------------------------------
def test_confusao_hs256_com_chave_publica_e_recusada() -> None:
    # Ataque clássico de confusão de algoritmo: forjar um token HS256 usando a chave
    # PÚBLICA (PEM) como segredo HMAC. A PyJWT recusa fazer isso no `encode` (guarda
    # própria), então forjamos o token à mão — como um atacante real faria.
    agora = dt.datetime.now(dt.UTC)
    header = _b64u(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
    payload = _b64u(
        json.dumps(
            {
                "iss": ISSUER,
                "aud": "authenticated",
                "sub": "11111111-1111-1111-1111-111111111111",
                "session_id": "22222222-2222-2222-2222-222222222222",
                "role": "authenticated",
                "exp": int((agora + dt.timedelta(minutes=10)).timestamp()),
            }
        ).encode()
    )
    entrada = header + b"." + payload
    sig = _b64u(hmac.new(_PUB_PEM, entrada, hashlib.sha256).digest())
    forjado = (entrada + b"." + sig).decode()
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(forjado)


def test_alg_none_e_recusado() -> None:
    inseguro = jwt.encode(_claims(), key="", algorithm="none")
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(inseguro)


# --- Claims estruturais obrigatórios ----------------------------------------
def test_token_expirado_recusado() -> None:
    passado = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(_es256(exp=passado, iat=passado))


def test_audiencia_errada_recusada() -> None:
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(_es256(aud="anon"))


def test_issuer_errado_recusado() -> None:
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(_es256(iss="https://evil.example/auth/v1"))


def test_sem_session_id_recusado() -> None:
    claims = _claims()
    del claims["session_id"]
    tok = jwt.encode(claims, _PRIV, algorithm="ES256", headers={"kid": KID})
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(tok)


def test_assinatura_de_outra_chave_recusada(monkeypatch: pytest.MonkeyPatch) -> None:
    # Token assinado por uma chave DIFERENTE da que o servidor conhece.
    outra = ec.generate_private_key(ec.SECP256R1())
    tok = jwt.encode(_claims(), outra, algorithm="ES256", headers={"kid": KID})
    with pytest.raises(auth.TokenInvalido):
        auth.validar_token(tok)  # _chave_de_assinatura ainda devolve _PUB


# --- Dependency FastAPI ------------------------------------------------------
def _app_protegido() -> FastAPI:
    app = FastAPI()

    @app.get("/protegido")
    def protegido(ident: Annotated[auth.Identidade, Depends(auth.usuario_atual)]) -> dict:
        return {"user_id": ident.user_id}

    @app.get("/talvez")
    def talvez(request: Request) -> dict:
        ident = auth.usuario_opcional(request)
        return {"user_id": ident.user_id if ident else None}

    return app


def test_dependency_aceita_bearer_valido() -> None:
    client = TestClient(_app_protegido())
    r = client.get("/protegido", headers={"Authorization": f"Bearer {_es256()}"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "11111111-1111-1111-1111-111111111111"


def test_dependency_sem_header_e_nao_autorizado() -> None:
    client = TestClient(_app_protegido())
    # HTTPBearer(auto_error=True) nesta versão do FastAPI devolve 401 quando o
    # header Authorization está ausente (credencial não apresentada).
    assert client.get("/protegido").status_code == 401


def test_dependency_token_invalido_e_401() -> None:
    client = TestClient(_app_protegido())
    r = client.get("/protegido", headers={"Authorization": "Bearer nao.e.um.jwt"})
    assert r.status_code == 401


def test_usuario_opcional_sem_header_e_anonimo() -> None:
    client = TestClient(_app_protegido())
    assert client.get("/talvez").json()["user_id"] is None


def test_usuario_opcional_token_ruim_vira_anonimo() -> None:
    client = TestClient(_app_protegido())
    r = client.get("/talvez", headers={"Authorization": "Bearer lixo"})
    assert r.status_code == 200
    assert r.json()["user_id"] is None


def test_usuario_opcional_bearer_valido_identifica() -> None:
    client = TestClient(_app_protegido())
    r = client.get("/talvez", headers={"Authorization": f"Bearer {_es256()}"})
    assert r.json()["user_id"] == "11111111-1111-1111-1111-111111111111"
