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

    # pydantic-settings v2: tell it to read from backend/.env
    model_config = SettingsConfigDict(
        env_file="backend/.env",   # relative to where uvicorn is launched (repo root)
        env_file_encoding="utf-8",
        extra="ignore",            # silently ignore any extra keys in .env
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated CORS_ORIGINS string into a Python list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


# Single shared instance imported everywhere else.
settings = Settings()
