"""
config.py – Application settings loaded from backend/.env via pydantic-settings.

We use pydantic-settings so every value is type-checked at startup.
If a required key is missing from .env, the app fails fast with a clear message.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./intellipm.db"

    # ── JWT / Auth ────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins, e.g. "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173"

    # ── LLM (primary: Groq) ───────────────────────────────────────────────────
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "openai/gpt-oss-120b"

    # ── LLM (fallback: Gemini) ────────────────────────────────────────────────
    LLM_FALLBACK_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_MODEL: str = "gemini-flash-latest"

    # ── Feature flags ─────────────────────────────────────────────────────────
    USE_CACHED_PLAN_ONLY: bool = False

    # ── Estimation ────────────────────────────────────────────────────────────
    HOURS_PER_STORY_POINT: int = 3

    # pydantic-settings v2: look for .env in backend/ (when run from repo root)
    # OR in ./ (when run from backend/ directory). First match wins.
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),  # tuple = try both paths
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        DATABASE_URL in the form SQLAlchemy + psycopg 3 needs.

        Hosts (Render, Neon, Supabase) hand out `postgres://...` or `postgresql://...`;
        SQLAlchemy would pick the old psycopg2 driver for those, so we name psycopg 3
        explicitly.  SQLite URLs are returned unchanged.  This is the ONLY thing that
        differs between development and deployment: you change DATABASE_URL, nothing else.
        """
        url = self.DATABASE_URL.strip()
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated CORS_ORIGINS string into a Python list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


# Single shared instance imported everywhere else.
settings = Settings()

# Fail fast: a deployed (non-SQLite) database must never run with the public default secret,
# because anyone could then forge login tokens.
if not settings.is_sqlite and settings.SECRET_KEY.startswith(("change-me", "CHANGE_ME")):
    raise RuntimeError(
        "SECRET_KEY is still the default. Set a long random SECRET_KEY "
        "(e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`) before using PostgreSQL."
    )
