#!/usr/bin/env python3
"""
Delete ALL application data from Supabase Postgres (fresh start).

Keeps tables/schema intact — only removes rows.

Usage (from backend/):
  python -m scripts.reset_supabase_db --confirm

Without --confirm, prints what would be deleted (dry run).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.database_url import normalize_database_url

APP_TABLES = (
    "job_audit_events",
    "job_queue",
    "comparison_jobs",
    "imported_audio_urls",
    "excel_import_batches",
    "audio_files",
    "processing_jobs",
)


async def _table_counts(conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in APP_TABLES:
        row = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        counts[table] = int(row.scalar_one())
    return counts


async def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe all app data from Supabase Postgres")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete data (required)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.is_postgres:
        print("ERROR: DATABASE_URL is not Postgres. This script only wipes Supabase/Postgres.")
        return 1

    url = normalize_database_url(settings.database_url)
    host = url.split("@")[-1] if "@" in url else url
    print(f"Target database: ...@{host}")

    async with engine.connect() as conn:
        before = await _table_counts(conn)
        total = sum(before.values())
        print("\nCurrent row counts:")
        for table, count in before.items():
            print(f"  {table}: {count}")
        print(f"  TOTAL: {total}")

        if total == 0:
            print("\nDatabase is already empty.")
            return 0

        if not args.confirm:
            print("\nDry run only. Re-run with --confirm to delete all rows.")
            return 0

        print("\nDeleting all application data...")
        tables_sql = ", ".join(APP_TABLES)
        await conn.execute(text(f"TRUNCATE TABLE {tables_sql} RESTART IDENTITY CASCADE"))
        await conn.commit()

        after = await _table_counts(conn)
        print("\nAfter reset:")
        for table, count in after.items():
            print(f"  {table}: {count}")
        print("\nDone. Schema is intact; all jobs, results, and uploads metadata removed.")
        print("Re-run analyses after the Sarvam STT cache fix is deployed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
