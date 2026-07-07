from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.database import Base
from app.main import create_app, lifespan
from app.models.db_models import ComparisonJob
from app.services import health as health_service
from app.services import jobs as jobs_service
from app.services.url_audio_fetch import UrlAudioFetchError, _validate_url_format


def test_settings_reads_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/postgres")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://proj.storage.supabase.co/storage/v1/s3")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET", "call-analytics")

    settings = Settings()

    assert settings.app_env == "production"
    assert settings.is_postgres is True
    assert settings.is_cloud_deployment is True
    assert settings.uses_remote_storage is True


@pytest.mark.asyncio
async def test_lifespan_creates_temp_and_upload_dirs(monkeypatch, tmp_path):
    settings = Settings(
        temp_dir=str(tmp_path / "tmp"),
        upload_dir=str(tmp_path / "uploads"),
        storage_backend="local",
        app_env="development",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    app = create_app()
    init_db_mock = AsyncMock()
    monkeypatch.setattr("app.main.init_db", init_db_mock)

    async with lifespan(app):
        assert Path(settings.temp_dir).exists()
        assert Path(settings.upload_dir).exists()

    init_db_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_cloud_readiness_does_not_require_local_upload_dir(monkeypatch):
    settings = Settings(
        app_env="production",
        database_url="postgresql://user:pass@host:5432/postgres",
        storage_backend="s3",
        s3_endpoint_url="https://proj.storage.supabase.co/storage/v1/s3",
        s3_access_key_id="key",
        s3_secret_access_key="secret",
        s3_bucket="call-analytics",
        sarvam_api_key="sk-live",
    )

    monkeypatch.setattr(health_service, "get_settings", lambda: settings)
    monkeypatch.setattr(health_service, "check_database", AsyncMock(return_value=(True, "ok")))
    monkeypatch.setattr(health_service, "check_temp_directory", lambda: (True, "writable"))
    monkeypatch.setattr(health_service, "check_upload_directory", lambda: (False, "not_writable"))
    monkeypatch.setattr(health_service, "check_storage_config", lambda: (True, "s3_configured"))
    monkeypatch.setattr(health_service, "database_info", lambda: {"backend": "supabase_postgres"})
    monkeypatch.setattr(health_service.metrics, "snapshot", lambda: {"jobs_started": 0})

    report = await health_service.readiness_report()

    assert report["ready"] is True
    assert report["checks"]["upload_dir"] == "not_writable"
    assert report["checks"]["storage"] == "s3_configured"
    assert report["checks"]["persistence"] == "supabase_postgres"


def test_url_ingestion_blocks_localhost_and_private_hosts(monkeypatch):
    monkeypatch.setattr("app.services.url_audio_fetch._is_safe_resolved_host", lambda host: False)

    with pytest.raises(UrlAudioFetchError, match="private or restricted"):
        _validate_url_format("https://10.0.0.5/audio.mp3")

    with pytest.raises(UrlAudioFetchError, match="not allowed"):
        _validate_url_format("http://localhost:8000/audio.mp3")


@pytest.mark.asyncio
async def test_create_job_persists_url_ingestion_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        monkeypatch.setattr(jobs_service, "resolve_audio_path_async", AsyncMock(return_value=None))
        job = await jobs_service.create_job(
            session,
            "file-123",
            None,
            original_filename="call.mp3",
            source_type="url",
            source_url="https://cdn.example.com/call.mp3",
            stored_path=None,
        )

        result = await session.execute(select(ComparisonJob).where(ComparisonJob.id == job.id))
        persisted = result.scalar_one()

    assert persisted.file_id == "file-123"
    assert persisted.audio_filename == "call.mp3"
    assert persisted.source_type == "url"
    assert persisted.source_url == "https://cdn.example.com/call.mp3"

    await engine.dispose()
