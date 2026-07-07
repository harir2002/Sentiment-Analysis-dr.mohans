#!/usr/bin/env python3
"""
Copy all application tables from local SQLite to Supabase Postgres.

Usage (from backend/):
  python -m scripts.migrate_sqlite_to_supabase

Environment:
  SQLITE_DATABASE_URL  — source (default: sqlite:///./data/app.db)
  DATABASE_URL         — target Supabase Postgres (required)

The script is idempotent per primary key: existing rows are skipped (INSERT OR IGNORE style).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.core.database_url import normalize_database_url

# Parent tables first; audit events after comparison_jobs
TABLE_ORDER = [
    "processing_jobs",
    "audio_files",
    "comparison_jobs",
    "job_audit_events",
    "excel_import_batches",
    "imported_audio_urls",
    "job_queue",
]


def _sync_postgres_url(async_url: str) -> str:
    url = normalize_database_url(async_url)
    return url.replace("+psycopg", "")


def _row_to_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    data = dict(zip(columns, row))
    for key, value in list(data.items()):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    data[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
    return data


def _copy_table(
    source: Engine,
    target: Engine,
    table_name: str,
    source_metadata: MetaData,
    target_metadata: MetaData,
) -> tuple[int, int]:
    if table_name not in source_metadata.tables or table_name not in target_metadata.tables:
        return 0, 0

    table = target_metadata.tables[table_name]
    columns = [c.name for c in table.columns]

    with source.connect() as src_conn:
        rows = src_conn.execute(text(f"SELECT * FROM {table_name}")).fetchall()

    if not rows:
        return 0, 0

    inserted = 0
    skipped = 0

    with target.connect() as tgt_conn:
        for row in rows:
            payload = _row_to_dict(row, columns)
            pk_cols = [c.name for c in table.primary_key.columns]
            if pk_cols:
                where = " AND ".join(f"{c} = :{c}" for c in pk_cols)
                exists = tgt_conn.execute(
                    text(f"SELECT 1 FROM {table_name} WHERE {where} LIMIT 1"),
                    {c: payload[c] for c in pk_cols},
                ).first()
                if exists:
                    skipped += 1
                    continue

            tgt_conn.execute(table.insert().values(**payload))
            inserted += 1
        tgt_conn.commit()

    return inserted, skipped


def _reset_serial_sequence(target: Engine, table_name: str, column: str = "id") -> None:
    with target.connect() as conn:
        conn.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', '{column}'),
                    COALESCE((SELECT MAX({column}) FROM {table_name}), 1)
                )
                """
            )
        )
        conn.commit()


def main() -> int:
    settings = get_settings()
    if not settings.is_postgres:
        print("ERROR: DATABASE_URL must be Supabase/Postgres.")
        return 1

    sqlite_url = os.getenv("SQLITE_DATABASE_URL", "sqlite:///./data/app.db")
    if sqlite_url.startswith("sqlite+aiosqlite:"):
        sqlite_url = sqlite_url.replace("sqlite+aiosqlite:", "sqlite:", 1)

    postgres_url = _sync_postgres_url(settings.database_url)

    if not os.path.exists(sqlite_url.replace("sqlite:///", "").split("?")[0]):
        candidate = settings.backend_root / "data" / "app.db"
        if candidate.exists():
            sqlite_url = f"sqlite:///{candidate.as_posix()}"
        else:
            print(f"WARNING: SQLite file not found at {sqlite_url}")
            print("Nothing to migrate.")
            return 0

    print(f"Source:  {sqlite_url}")
    print(f"Target:  ...@{postgres_url.split('@')[-1] if '@' in postgres_url else postgres_url}")

    source_engine = create_engine(sqlite_url)
    target_engine = create_engine(postgres_url)

    if not inspect(source_engine).get_table_names():
        print("Source database has no tables.")
        return 0

    # Ensure target schema exists via setup script
    print("Applying target schema (create_all + patches)...")
    import asyncio

    from app.core.database import Base, init_db
    from app.models import db_models  # noqa: F401

    asyncio.run(init_db())

    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    target_metadata = Base.metadata

    total_inserted = 0
    total_skipped = 0

    for table_name in TABLE_ORDER:
        if table_name not in source_metadata.tables:
            continue
        inserted, skipped = _copy_table(
            source_engine, target_engine, table_name, source_metadata, target_metadata
        )
        total_inserted += inserted
        total_skipped += skipped
        print(f"  {table_name}: inserted={inserted}, skipped={skipped}")

    if inspect(target_engine).has_table("job_audit_events"):
        try:
            _reset_serial_sequence(target_engine, "job_audit_events", "id")
            print("  job_audit_events: serial sequence reset")
        except Exception as exc:
            print(f"  job_audit_events: sequence reset skipped ({exc})")

    print(f"Done. inserted={total_inserted}, skipped={total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
