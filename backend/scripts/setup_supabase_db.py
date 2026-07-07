#!/usr/bin/env python3
"""
Verify Supabase/Postgres connectivity and apply ORM schema.

Usage (from backend/):
  python -m scripts.setup_supabase_db

Requires DATABASE_URL in backend/.env pointing to Supabase Postgres.
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine, init_db
from app.core.database_url import normalize_database_url
from app.db import database_info


async def main() -> int:
    settings = get_settings()
    if not settings.is_postgres:
        print("ERROR: DATABASE_URL is not Postgres.")
        print("Set DATABASE_URL to your Supabase connection string in backend/.env")
        print("Example:")
        print(
            "  DATABASE_URL=postgresql://postgres.[ref]:[password]@"
            "aws-0-[region].pooler.supabase.com:6543/postgres?pgbouncer=true"
        )
        return 1

    url = normalize_database_url(settings.database_url)
    print(f"Target: ...@{url.split('@')[-1] if '@' in url else url}")
    print(f"Supabase URL: {settings.supabase_url or '(not set — optional)'}")

    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar_one()
            print(f"Connected: {version[:80]}...")
    except Exception as exc:
        print(f"ERROR: Could not connect to Postgres: {exc}")
        return 1

    await init_db()
    info = database_info()
    print("Schema ready.")
    print(f"  backend: {info['backend']}")
    print(f"  dialect: {info['dialect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
