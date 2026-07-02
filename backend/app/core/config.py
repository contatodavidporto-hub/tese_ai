"""Configuração da aplicação via pydantic-settings.

Todos os segredos são lidos do `.env` (ou do ambiente). Nada é hardcoded.
Campos sensíveis são `Optional` com default `None` para que a app suba para o
`/health` e os testes mesmo sem `.env` configurado.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
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
    # Modelos do motor de tese (cascata). Opus para a síntese narrada com citações;
    # Haiku para a extração de metadados (etapa 2, sem citações). Sobrepujáveis via .env.
    tese_model_synthesis: str = "claude-opus-4-8"
    tese_model_extraction: str = "claude-haiku-4-5-20251001"

    # Usuário-demo do slice: as teses (RLS owner-only) precisam de um dono real em
    # `auth.users`. Resolvido sob demanda via Admin API do Supabase (service_role).
    demo_user_email: str = "demo@tese-ai.local"

    # Observabilidade (Langfuse) — opcional; cliente vira no-op se ausente.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Conectores premium BEHIND CONFIG (dados de maior frequência). Opcionais: sem
    # a chave, os conectores keyless (fredgraph/World Bank/CVM/BCB) seguem sozinhos
    # e a arquitetura não é bloqueada. Segredo só no .env — nunca no código.
    fred_api_key: str | None = None
    eia_api_key: str | None = None

    # --- Capacidade / anti-abuso (Fase 1 de blindagem) --------------------------
    # Rate limit da criação de tese (endpoint que dispara o LLM caro). Formato
    # slowapi ("N/period"). Vazio desliga (ex.: testes). Chave por IP.
    rate_limit_criar_tese: str = "10/hour"
    rate_limit_global: str = "120/minute"
    # Cap de gerações de tese concorrentes no processo (protege pool de conexões e
    # custo). BackgroundTask além do teto abstém com "sistema ocupado".
    tese_max_concorrencia: int = 2
    # Teto de custo de LLM por dia (USD, por processo — defesa, não contabilidade
    # global). Excedido => a geração abstém em vez de gastar. 0 desliga o teto.
    tese_teto_custo_usd_dia: float = 10.0
    # Tamanho máximo do corpo de requisição (bytes). Acima disso => 413.
    max_request_bytes: int = 64 * 1024

    # --- Cache de tese pública + reaper (Fase 2) --------------------------------
    # Janela em que uma tese `ready` do mesmo ticker é REAPROVEITADA em vez de
    # regenerada via LLM (custo + latência). 0 desliga o cache (sempre regenera).
    tese_cache_horas: int = 24
    # Uma tese presa em `processing` além deste tempo (crash no meio da geração) é
    # marcada `error` pelo reaper (integridade — sem órfãs eternas). 0 desliga.
    tese_processing_timeout_min: int = 15

    @field_validator("database_url")
    @classmethod
    def _normalize_db_driver(cls, v: str | None) -> str | None:
        """Força o driver psycopg (v3) no SQLAlchemy.

        O URI 'Session pooler' do dashboard do Supabase vem como
        `postgresql://...` (ou `postgres://...`), que o SQLAlchemy mapeia para
        psycopg2 (não instalado). O projeto usa psycopg 3 → `postgresql+psycopg://`.
        """
        if not v or v.startswith("postgresql+psycopg://"):
            return v
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
