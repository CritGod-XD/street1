import os


def _normalize_db_url(url: str) -> str:
    """Neon (and some other providers) hand out URLs starting with
    'postgres://'. SQLAlchemy + psycopg2 want 'postgresql://'."""
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    _raw_db_url = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(_raw_db_url) or "sqlite:///local.db"
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Neon closes idle connections; recycling avoids "server closed the
        # connection unexpectedly" errors on serverless cold starts.
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
