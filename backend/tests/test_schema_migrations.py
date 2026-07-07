"""Tests for dialect-aware schema migrations."""

from sqlalchemy import create_engine, inspect

from app.core.schema_migrations import apply_schema_patches


def test_schema_patches_idempotent_on_sqlite(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    from app.core.database import Base
    from app.models import db_models  # noqa: F401

    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        apply_schema_patches(conn)
        apply_schema_patches(conn)

    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("comparison_jobs")}
        assert "sentiment_label" in cols
        assert "source_url" in cols
        assert "started_at" in cols
