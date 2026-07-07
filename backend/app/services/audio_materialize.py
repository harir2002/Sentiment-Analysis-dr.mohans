"""Resolve job audio to a local filesystem path for STT/LLM pipelines.

On free-tier cloud hosts (Hugging Face Spaces) local disk is ephemeral.
Audio may live in Supabase Storage (S3-compatible) or be re-fetched from
source_url. This module downloads to a temp file when needed.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.storage import get_storage_backend, resolve_audio_path
from app.services.url_audio_fetch import fetch_audio_from_url

logger = logging.getLogger(__name__)


def _temp_audio_path(suffix: str = ".bin") -> Path:
    settings = get_settings()
    temp_root = Path(settings.temp_dir)
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root / f"job-audio-{uuid.uuid4().hex}{suffix}"


def _suffix_from_key(key: str) -> str:
    if "." in key.rsplit("/", 1)[-1]:
        return "." + key.rsplit(".", 1)[-1].lower()
    return ".bin"


async def materialize_audio_for_analysis(
    *,
    audio_path: str | None,
    file_id: str | None = None,
    source_url: str | None = None,
) -> tuple[str, bool]:
    """Return ``(local_path, is_temporary)`` for pipeline processing."""
    settings = get_settings()

    if audio_path:
        local = Path(audio_path)
        if local.is_file():
            return str(local), False

    if settings.storage_backend.lower() == "s3" and audio_path:
        storage = get_storage_backend()
        suffix = _suffix_from_key(audio_path)
        dest = _temp_audio_path(suffix)
        content = await storage.download_file(audio_path)
        dest.write_bytes(content)
        logger.info("Materialized S3 audio %s -> %s", audio_path, dest)
        return str(dest), True

    resolved = resolve_audio_path(file_id, stored_path=audio_path)
    if resolved:
        local = Path(resolved)
        if local.is_file():
            return str(local), False

        if settings.storage_backend.lower() == "s3":
            storage = get_storage_backend()
            suffix = _suffix_from_key(resolved)
            dest = _temp_audio_path(suffix)
            content = await storage.download_file(resolved)
            dest.write_bytes(content)
            return str(dest), True

    if source_url and source_url.strip():
        content, filename, _content_type = await fetch_audio_from_url(source_url.strip())
        suffix = Path(filename).suffix or ".bin"
        dest = _temp_audio_path(suffix)
        dest.write_bytes(content)
        logger.info("Re-fetched audio from source_url for file_id=%s", file_id)
        return str(dest), True

    raise ValueError(
        "Audio file is not available. On cloud hosting, prefer URL ingestion or "
        "configure Supabase Storage (STORAGE_BACKEND=s3). Uploaded files on local "
        "disk do not survive container restarts."
    )


def cleanup_temporary_audio(path: str | None) -> None:
    if not path:
        return
    settings = get_settings()
    temp_root = Path(settings.temp_dir).resolve()
    try:
        file_path = Path(path).resolve()
        if temp_root in file_path.parents or file_path.parent == temp_root:
            file_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Failed to remove temp audio %s: %s", path, exc)
