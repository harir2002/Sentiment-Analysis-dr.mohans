#!/usr/bin/env python3
"""Diagnose Supabase connectivity (hostname, IPv6, pooler)."""

from __future__ import annotations

import asyncio
import socket
import sys
from urllib.parse import quote, urlparse, urlunparse

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.database_url import normalize_database_url


def ipv6_literal_for_host(hostname: str, port: int = 5432) -> str | None:
    try:
        infos = socket.getaddrinfo(hostname, port, socket.AF_INET6, socket.SOCK_STREAM)
        return infos[0][4][0]
    except socket.gaierror:
        return None


def with_host(url: str, host: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.split("@")[-1]
    userinfo = parsed.netloc.rsplit("@", 1)[0]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    new_netloc = f"{userinfo}@{host}"
    if parsed.port:
        new_netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=new_netloc))


async def try_url(label: str, url: str) -> bool:
    engine = create_async_engine(normalize_database_url(url), pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print(f"  OK  {label}")
        return True
    except Exception as exc:
        print(f"  FAIL {label}: {type(exc).__name__}: {str(exc)[:120]}")
        return False
    finally:
        await engine.dispose()


async def main() -> int:
    settings = get_settings()
    base = normalize_database_url(settings.database_url)
    parsed = urlparse(base)
    host = parsed.hostname or ""

    print("Supabase connectivity diagnosis")
    print(f"Configured host: {host}")

    if await try_url("configured DATABASE_URL", base):
        return 0

    v6 = ipv6_literal_for_host(host) if host else None
    if v6:
        print(f"IPv6 address for {host}: {v6}")
        ipv6_url = with_host(base, v6)
        if await try_url("IPv6 literal fallback", ipv6_url):
            print("\nUse this in backend/.env DATABASE_URL (same password, IPv6 host):")
            print(ipv6_url.replace(quote(parsed.password or "", safe=""), "***"))
            return 0

    # Common pooler pattern — user should copy exact URI from Supabase dashboard
    project = settings.supabase_project_ref or host.split(".")[0].replace("db.", "")
    password = parsed.password or ""
    if project and password:
        regions = [
            "ap-south-1",
            "ap-southeast-1",
            "us-east-1",
            "eu-west-1",
            "eu-central-1",
        ]
        print(f"\nTrying pooler regions for project ref {project}...")
        for region in regions:
            pooler_host = f"aws-0-{region}.pooler.supabase.com"
            pooler_url = (
                f"postgresql://postgres.{project}:{quote(password, safe='')}"
                f"@{pooler_host}:5432/postgres"
            )
            if await try_url(f"pooler {region} :5432", pooler_url):
                print("\nRecommended DATABASE_URL (Session pooler):")
                print(pooler_url)
                return 0
            pooler_url_6543 = pooler_url.replace(":5432/", ":6543/") + "?pgbouncer=true"
            if await try_url(f"pooler {region} :6543", pooler_url_6543):
                print("\nRecommended DATABASE_URL (Transaction pooler):")
                print(pooler_url_6543)
                return 0

    print("\nCould not connect. In Supabase Dashboard go to:")
    print("  Project Settings → Database → Connection string → URI (Session pooler)")
    print("Paste that exact URI as DATABASE_URL (URL-encode @ in password as %40)")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
