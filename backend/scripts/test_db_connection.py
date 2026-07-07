#!/usr/bin/env python3
"""Test DATABASE_URL from backend/.env without printing secrets."""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.database_url import normalize_database_url
from app.db import database_info


async def main() -> int:
    settings = get_settings()
    url = normalize_database_url(settings.database_url)
    host_hint = url.split("@")[-1] if "@" in url else "(local)"

    print(f"Backend: {database_info()['backend']}")
    print(f"Target:  ...@{host_hint}")

    if not settings.is_postgres:
        print("ERROR: DATABASE_URL is still SQLite. Set Supabase Postgres URL in backend/.env")
        return 1

    try:
        async with engine.connect() as conn:
            one = (await conn.execute(text("SELECT 1"))).scalar_one()
            version = (await conn.execute(text("SELECT version()"))).scalar_one()
            tables = (
                await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'comparison_jobs'"
                    )
                )
            ).scalar_one()
        print(f"Connection OK (SELECT 1 => {one})")
        print(f"Postgres: {str(version)[:70]}...")
        print(f"comparison_jobs table exists: {tables == 1}")
        return 0
    except Exception as exc:
        print(f"Connection FAILED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
