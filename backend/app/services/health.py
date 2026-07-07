"""Liveness, readiness, and dependency health probes."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.observability import metrics
from app.db import database_info

logger = logging.getLogger(__name__)


async def check_database() -> tuple[bool, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return False, "unavailable"


def check_temp_directory() -> tuple[bool, str]:
    settings = get_settings()
    temp_dir = Path(settings.temp_dir)
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        probe = temp_dir / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, "writable"
    except Exception as exc:
        logger.warning("Temp directory check failed: %s", exc)
        return False, "not_writable"


def check_upload_directory() -> tuple[bool, str]:
    settings = get_settings()
    if settings.uses_remote_storage:
        return True, "remote_s3"
    upload_dir = Path(settings.upload_dir)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        probe = upload_dir / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, "writable"
    except Exception as exc:
        logger.warning("Upload directory check failed: %s", exc)
        return False, "not_writable"


def check_storage_config() -> tuple[bool, str]:
    settings = get_settings()
    if not settings.uses_remote_storage:
        return True, "local"
    missing = [
        name
        for name, value in {
            "S3_ENDPOINT_URL": settings.s3_endpoint_url,
            "S3_ACCESS_KEY_ID": settings.s3_access_key_id,
            "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
            "S3_BUCKET": settings.s3_bucket,
        }.items()
        if not (value or "").strip()
    ]
    if missing:
        return False, f"missing:{','.join(missing)}"
    return True, "s3_configured"


def check_providers() -> dict[str, bool]:
    settings = get_settings()
    return {
        "sarvam": settings.has_sarvam_key(),
        "groq": settings.has_groq_key(),
        "openrouter": settings.has_openrouter_key(),
    }


async def readiness_report() -> dict:
    settings = get_settings()
    db_ok, db_status = await check_database()
    temp_ok, temp_status = check_temp_directory()
    upload_ok, upload_status = check_upload_directory()
    storage_ok, storage_status = check_storage_config()
    providers = check_providers()
    any_provider = any(providers.values())

    if settings.is_cloud_deployment:
        ready = db_ok and temp_ok and storage_ok and any_provider
    else:
        ready = db_ok and upload_ok and any_provider

    checks = {
        "database": db_status,
        "temp_dir": temp_status,
        "upload_dir": upload_status,
        "storage": storage_status,
        "providers": providers,
        "persistence": database_info()["backend"],
    }

    return {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "app_env": settings.app_env,
        "checks": checks,
        "metrics": metrics.snapshot() if settings.metrics_enabled else None,
    }


async def health_report() -> dict:
    settings = get_settings()
    db_ok, db_status = await check_database()
    upload_ok, upload_status = check_upload_directory()
    storage_ok, storage_status = check_storage_config()
    providers = check_providers()

    degraded = not db_ok or not any(providers.values())
    if settings.is_cloud_deployment:
        degraded = degraded or not storage_ok
    else:
        degraded = degraded or not upload_ok

    return {
        "status": "degraded" if degraded else "ok",
        "database": db_status if db_ok else "error",
        "upload_dir": upload_status if upload_ok else "error",
        "storage": storage_status if storage_ok else "error",
        "version": "1.0.0",
        "app_env": settings.app_env,
        "providers": providers,
        "persistence": database_info()["backend"],
        "models": {
            "sarvam_stt": settings.sarvam_stt_model,
            "sarvam_llm": settings.sarvam_llm_model,
            "groq_stt": settings.groq_stt_model,
            "openrouter_llm": settings.openrouter_llm_model,
        },
        "limits": {
            "max_upload_mb": settings.max_upload_size_mb,
            "max_transcript_chars": settings.guardrails_max_transcript_chars,
            "sarvam_llm_max_tokens": settings.sarvam_llm_token_limit,
        },
    }
