"""Normalize DATABASE_URL for SQLAlchemy async + Supabase Postgres."""

from __future__ import annotations

import re
import socket
from urllib.parse import quote, unquote, urlparse, urlunparse


def _sanitize_password_brackets(url: str) -> str:
    """Fix postgres://user:[pass@word]@host — brackets break URL parsing."""
    match = re.match(
        r"^(postgresql(?:\+psycopg)?://)([^:]+):\[([^\]]+)\]@(.+)$",
        url,
        flags=re.IGNORECASE,
    )
    if not match:
        return url
    prefix, user, password, rest = match.groups()
    encoded = quote(unquote(password), safe="")
    return f"{prefix}{user}:{encoded}@{rest}"


def normalize_database_url(url: str) -> str:
    """Convert common Postgres URLs to the async psycopg driver form."""
    raw = (url or "").strip()
    if not raw:
        return raw

    raw = _sanitize_password_brackets(raw)

    if raw.startswith("postgresql+psycopg://") or raw.startswith("postgresql+asyncpg://"):
        return resolve_supabase_ipv6_host(raw)

    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw[len("postgres://") :]

    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]

    return resolve_supabase_ipv6_host(raw)


def resolve_supabase_ipv6_host(url: str) -> str:
    """On Windows, db.*.supabase.co is often IPv6-only — use literal address."""
    parsed = urlparse(url)
    host = parsed.hostname
    if not host or not host.startswith("db.") or not host.endswith(".supabase.co"):
        return url

    port = parsed.port or 5432
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET6, socket.SOCK_STREAM)
        ipv6 = infos[0][4][0]
    except OSError:
        return url

    netloc = parsed.netloc.rsplit("@", 1)[0] + f"@[{ipv6}]"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def is_pgbouncer_url(url: str) -> bool:
    lowered = (url or "").lower()
    return ":6543" in lowered or "pgbouncer=true" in lowered or "pooler.supabase.com" in lowered

