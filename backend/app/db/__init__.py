"""Database session utilities and persistence backend info."""

from app.core.config import get_settings
from app.core.database import engine
from app.core.database_url import normalize_database_url


def persistence_backend() -> str:
    settings = get_settings()
    if settings.is_postgres:
        return "supabase_postgres"
    return "sqlite_local"


def database_info() -> dict:
    settings = get_settings()
    url = normalize_database_url(settings.database_url)
    safe_url = url.split("@")[-1] if "@" in url else url
    return {
        "backend": persistence_backend(),
        "dialect": engine.dialect.name,
        "host": safe_url,
        "is_postgres": settings.is_postgres,
        "is_cloud_deployment": settings.is_cloud_deployment,
    }
