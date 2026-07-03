"""Resolve o usuário-dono das teses do slice (RLS owner-only exige dono real).

As tabelas `teses`/`tese_versoes` têm FK para `auth.users` e RLS `auth.uid() =
user_id`. Como o slice ainda não tem login, criamos/recuperamos um usuário-demo
via Admin API do Supabase (com a `service_role`, só no backend). Quando o login
real entrar, basta passar o `user_id` autenticado em vez deste.
"""

from __future__ import annotations

from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_or_create_demo_user() -> str:
    """Devolve o UUID do usuário-demo (idempotente por e-mail). Cacheado por processo."""
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_role_key):
        raise RuntimeError("Supabase URL/service_role ausentes — não há como resolver o dono.")

    base = s.supabase_url.rstrip("/")
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    email = s.demo_user_email

    # Cria (idempotente). Se já existir, o GoTrue responde 4xx → buscamos na lista.
    created = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "email_confirm": True},
        timeout=30.0,
    )
    if created.status_code in (200, 201):
        uid = created.json()["id"]
        logger.info("demo_user_criado", email=email)
        return uid

    listed = httpx.get(
        f"{base}/auth/v1/admin/users",
        headers=headers,
        params={"page": 1, "per_page": 200},
        timeout=30.0,
    )
    listed.raise_for_status()
    for user in listed.json().get("users", []):
        if user.get("email") == email:
            return user["id"]

    created.raise_for_status()  # superfície o erro original se não achamos o usuário
    raise RuntimeError("Não foi possível resolver o usuário-demo.")
