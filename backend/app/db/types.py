"""Shared JSON column type — JSONB on Postgres, JSON on SQLite."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JsonType = JSON().with_variant(JSONB, "postgresql")
