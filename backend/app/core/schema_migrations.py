"""Dialect-aware schema patches applied after create_all."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# comparison_jobs columns added after initial releases
_COMPARISON_JOB_COLUMNS: list[tuple[str, str, str]] = [
    ("stt_language_code", "VARCHAR(16)", "TEXT"),
    ("final_recommendation", "TEXT", "TEXT"),
    ("sentiment_label", "VARCHAR(32)", "TEXT"),
    ("is_valid_call", "BOOLEAN", "BOOLEAN"),
    ("invalid_reason", "TEXT", "TEXT"),
    ("source_type", "VARCHAR(16)", "TEXT"),
    ("source_url", "TEXT", "TEXT"),
    ("ingested_at", "TIMESTAMP WITHOUT TIME ZONE", "DATETIME"),
    ("started_at", "TIMESTAMP WITHOUT TIME ZONE", "DATETIME"),
]

_AUDIO_FILE_COLUMNS: list[tuple[str, str, str]] = [
    ("source_type", "VARCHAR(16)", "TEXT"),
    ("source_url", "TEXT", "TEXT"),
]


def _add_column_postgres(connection: Connection, table: str, name: str, pg_type: str) -> None:
    connection.execute(
        text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_type}")
    )


def _add_column_sqlite(connection: Connection, table: str, name: str, sqlite_type: str) -> None:
    inspector = inspect(connection)
    if not inspector.has_table(table):
        return
    columns = {c["name"] for c in inspector.get_columns(table)}
    if name in columns:
        return
    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqlite_type}"))


def apply_schema_patches(connection: Connection) -> None:
    dialect = connection.dialect.name
    logger.info("Applying schema patches for dialect=%s", dialect)

    if dialect == "postgresql":
        for name, pg_type, _sqlite_type in _COMPARISON_JOB_COLUMNS:
            _add_column_postgres(connection, "comparison_jobs", name, pg_type)
        for name, pg_type, _sqlite_type in _AUDIO_FILE_COLUMNS:
            _add_column_postgres(connection, "audio_files", name, pg_type)

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_comparison_jobs_sentiment_label "
                "ON comparison_jobs (sentiment_label)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_comparison_jobs_created_desc "
                "ON comparison_jobs (created_at DESC)"
            )
        )
        return

    if dialect == "sqlite":
        if not inspect(connection).has_table("comparison_jobs"):
            return
        for name, _pg_type, sqlite_type in _COMPARISON_JOB_COLUMNS:
            _add_column_sqlite(connection, "comparison_jobs", name, sqlite_type)
        for name, _pg_type, sqlite_type in _AUDIO_FILE_COLUMNS:
            _add_column_sqlite(connection, "audio_files", name, sqlite_type)
