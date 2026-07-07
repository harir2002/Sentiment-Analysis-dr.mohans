"""Tests for database URL normalization."""

from app.core.database_url import is_pgbouncer_url, normalize_database_url


def test_normalize_postgres_uri():
    assert normalize_database_url("postgresql://user:pass@host:5432/db").startswith(
        "postgresql+psycopg://"
    )


def test_normalize_postgres_short_scheme():
    assert normalize_database_url("postgres://user:pass@host/db").startswith(
        "postgresql+psycopg://"
    )


def test_pgbouncer_detection():
    url = "postgresql://u:p@aws.pooler.supabase.com:6543/postgres?pgbouncer=true"
    assert is_pgbouncer_url(url) is True
