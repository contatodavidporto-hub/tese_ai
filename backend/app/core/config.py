"""Configuração da aplicação via pydantic-settings.

Todos os segredos são lidos do `.env` (ou do ambiente). Nada é hardcoded.
Campos sensíveis são `Optional` com default `None` para que a app suba para o
`/health` e os testes mesmo sem `.env` configurado.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    app_base_url: str = "http://localhost:3000"
    # Origens permitidas para CORS (separadas por vírgula).
    cors_origins: str = "http://localhost:3000"

    # Banco (Supabase Postgres + pgvector). None até ser provido no .env.
    database_url: str | None = None

    # Supabase — valores públicos (seguros no cliente).
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    # Segredo — SOMENTE backend. Nunca expor ao frontend.
    supabase_service_role_key: str | None = None

    # LLM (Anthropic) — usado a partir do Estágio 1B.
    anthropic_api_key: str | None = None

    # Observabilidade (Langfuse) — opcional; cliente vira no-op se ausente.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
