"""tests/test_config_urls.py – DATABASE_URL normalisation for hosted Postgres (Neon / Render / Supabase)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.config import Settings

NEON = "ep-cool-name-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://"])
def test_neon_style_urls_keep_ssl_parameters(prefix):
    s = Settings(DATABASE_URL=f"{prefix}user:p%40ss@{NEON}", SECRET_KEY="x" * 32)
    url = s.database_url
    assert url.startswith("postgresql+psycopg://") and not s.is_sqlite
    u = make_url(url)
    assert u.drivername == "postgresql+psycopg"
    assert u.host == "ep-cool-name-123456.eu-central-1.aws.neon.tech" and u.database == "neondb"
    assert u.password == "p@ss"                                   # URL-encoded password survives
    assert dict(u.query) == {"sslmode": "require", "channel_binding": "require"}
    create_engine(url)                                            # builds without connecting


def test_sqlite_and_already_normalised_urls_unchanged():
    assert Settings(DATABASE_URL="sqlite:///./intellipm.db").database_url == "sqlite:///./intellipm.db"
    already = "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert Settings(DATABASE_URL=already, SECRET_KEY="x" * 32).database_url == already


def test_surrounding_whitespace_from_a_pasted_url_is_ignored():
    s = Settings(DATABASE_URL=f"  postgresql://u:p@{NEON}\n", SECRET_KEY="x" * 32)
    assert s.database_url.startswith("postgresql+psycopg://u:p@ep-cool")
