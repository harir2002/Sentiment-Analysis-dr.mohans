from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import get_settings
from app.core.database_url import is_pgbouncer_url, normalize_database_url
from app.core.schema_migrations import apply_schema_patches
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
database_url = normalize_database_url(settings.database_url)

# Detect if using PostgreSQL and adjust engine parameters accordingly
if settings.is_postgres:
    engine_kwargs: dict = {
        "echo": settings.sql_echo,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    if is_pgbouncer_url(database_url):
        # Supabase transaction pooler (port 6543) — disable prepared statements
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = {"prepare_threshold": None}
        logger.info("Using PostgreSQL via PgBouncer-compatible settings")
    engine = create_async_engine(database_url, **engine_kwargs)
    logger.info("Using Supabase/PostgreSQL database")
else:
    # SQLite with aiosqlite driver (optional local fallback)
    engine = create_async_engine(
        settings.database_url,
        echo=settings.sql_echo,
        connect_args={"timeout": 30},
    )
    logger.info("Using SQLite database (local fallback — set DATABASE_URL for Supabase)")

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from app.models import db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(apply_schema_patches)

    backend = "supabase_postgres" if settings.is_postgres else "sqlite_local"
    logger.info("Database initialized successfully (backend=%s)", backend)
