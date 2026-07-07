import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import AudioValidationError
from app.core.observability import metrics
from app.services.audio_validation import ALLOWED_EXTENSIONS, validate_audio_file
from app.services.storage_backend import StorageBackend
from app.services.storage_local import LocalStorageBackend
from app.services.storage_s3 import S3StorageBackend
from app.services.url_audio_fetch import fetch_audio_from_url

logger = logging.getLogger(__name__)

# Global storage backend instance
_storage_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Get or initialize the global storage backend."""
    global _storage_backend
    
    if _storage_backend is not None:
        return _storage_backend
    
    settings = get_settings()
    
    if settings.storage_backend.lower() == "s3":
        _storage_backend = S3StorageBackend()
        logger.info("Initialized S3 storage backend")
    else:
        _storage_backend = LocalStorageBackend()
        logger.info("Initialized local storage backend")
    
    return _storage_backend


def _ingest_metadata(
    *,
    filename: str,
    stored_path: str,
    validation_meta: dict,
    source_type: str,
    source_url: str | None = None,
) -> dict:
    return {
        **validation_meta,
        "original_filename": filename,
        "source_type": source_type,
        "source_url": source_url,
        "stored_path": stored_path,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


async def save_audio_bytes(
    content: bytes,
    filename: str,
    *,
    content_type: str | None = None,
    source_type: str = "upload",
    source_url: str | None = None,
) -> tuple[str, str, str, dict]:
    """Persist validated audio bytes using the configured storage backend."""
    settings = get_settings()

    if not filename:
        raise AudioValidationError("No filename provided")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AudioValidationError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if len(content) > settings.max_upload_bytes:
        raise AudioValidationError(
            f"File exceeds maximum size of {settings.max_upload_size_mb}MB"
        )
    if len(content) == 0:
        raise AudioValidationError("Audio file is empty")

    if settings.storage_backend.lower() == "s3":
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            validation_meta = validate_audio_file(
                tmp_path,
                size_bytes=len(content),
                content_type=content_type,
            )
        finally:
            Path(tmp_path).unlink()

        storage = get_storage_backend()
        file_id = str(uuid.uuid4())
        upload_result = await storage.upload_file(file_id, content, filename)
        stored_path = upload_result["object_key"]
    else:
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}{ext}"
        file_path = upload_dir / safe_name

        async with __import__("aiofiles").open(file_path, "wb") as out:
            await out.write(content)

        validation_meta = validate_audio_file(
            str(file_path),
            size_bytes=len(content),
            content_type=content_type,
        )
        stored_path = str(file_path)

    if ext == ".m4a":
        logger.info(
            "M4A ingest source=%s filename=%s content_type=%s file_id=%s bytes=%s",
            source_type,
            filename,
            content_type,
            file_id,
            len(content),
        )

    metadata = _ingest_metadata(
        filename=filename,
        stored_path=stored_path,
        validation_meta=validation_meta,
        source_type=source_type,
        source_url=source_url,
    )
    metrics.record_upload(accepted=True)
    return file_id, filename, stored_path, metadata


async def save_upload(file: UploadFile) -> tuple[str, str, str, dict]:
    """Save uploaded file using configured storage backend."""
    if not file.filename:
        raise AudioValidationError("No filename provided")

    content = await file.read()
    return await save_audio_bytes(
        content,
        file.filename,
        content_type=file.content_type,
        source_type="upload",
    )


async def save_from_url(url: str) -> tuple[str, str, str, dict]:
    """Download remote audio and persist it like a local upload."""
    content, filename, content_type = await fetch_audio_from_url(url)
    return await save_audio_bytes(
        content,
        filename,
        content_type=content_type,
        source_type="url",
        source_url=url.strip(),
    )


async def save_uploads(files: list[UploadFile]) -> tuple[list[dict], list[dict]]:
    """Save multiple uploads; failures are isolated per file."""
    uploaded: list[dict] = []
    failed: list[dict] = []

    for file in files:
        filename = file.filename or "unknown"
        try:
            file_id, orig_name, stored_path, metadata = await save_upload(file)
            uploaded.append(
                {
                    "file_id": file_id,
                    "filename": orig_name,
                    "path": stored_path,
                    "metadata": metadata,
                    "success": True,
                    "error": None,
                }
            )
        except AudioValidationError as exc:
            metrics.record_upload(accepted=False)
            failed.append(
                {
                    "file_id": None,
                    "filename": filename,
                    "path": None,
                    "metadata": {},
                    "success": False,
                    "error": str(exc),
                }
            )
        except Exception as exc:
            failed.append(
                {
                    "file_id": None,
                    "filename": filename,
                    "path": None,
                    "metadata": {},
                    "success": False,
                    "error": f"Upload failed: {exc}",
                }
            )

    return uploaded, failed


async def save_from_urls(urls: list[str]) -> tuple[list[dict], list[dict]]:
    """Download and save multiple remote audio URLs."""
    uploaded: list[dict] = []
    failed: list[dict] = []

    for raw_url in urls:
        url = (raw_url or "").strip()
        display_name = url[:80] + ("…" if len(url) > 80 else "")
        try:
            file_id, orig_name, stored_path, metadata = await save_from_url(url)
            uploaded.append(
                {
                    "file_id": file_id,
                    "filename": orig_name,
                    "path": stored_path,
                    "metadata": metadata,
                    "success": True,
                    "error": None,
                }
            )
        except AudioValidationError as exc:
            metrics.record_upload(accepted=False)
            failed.append(
                {
                    "file_id": None,
                    "filename": display_name,
                    "path": None,
                    "metadata": {},
                    "success": False,
                    "error": str(exc),
                }
            )
        except Exception as exc:
            failed.append(
                {
                    "file_id": None,
                    "filename": display_name,
                    "path": None,
                    "metadata": {},
                    "success": False,
                    "error": f"URL ingest failed: {exc}",
                }
            )

    return uploaded, failed


def resolve_audio_path(file_id: str | None, stored_path: str | None = None) -> str | None:
    """Resolve filesystem path or S3 object key for an uploaded file."""
    if stored_path:
        return stored_path

    if not file_id:
        return None

    settings = get_settings()

    if settings.storage_backend.lower() == "s3":
        upload_dir = Path(settings.upload_dir)
        if upload_dir.is_dir():
            matches = list(upload_dir.glob(f"{file_id}.*"))
            if matches:
                return str(matches[0])
        return None

    upload_dir = Path(settings.upload_dir)
    matches = list(upload_dir.glob(f"{file_id}.*"))
    return str(matches[0]) if matches else None


async def resolve_audio_path_async(file_id: str | None, stored_path: str | None = None) -> str | None:
    """Resolve path/key; for S3, discover object key by prefix when needed."""
    if stored_path:
        return stored_path
    if not file_id:
        return None

    settings = get_settings()
    local = resolve_audio_path(file_id)
    if local:
        return local

    if settings.storage_backend.lower() != "s3":
        return None

    storage = get_storage_backend()
    from app.services.storage_s3 import S3StorageBackend

    if isinstance(storage, S3StorageBackend):
        return storage.find_object_key(file_id)
    return None


def delete_audio_file(path: str | None) -> None:
    """Delete audio file (local or cloud)."""
    if not path:
        return
    
    settings = get_settings()
    
    if settings.storage_backend.lower() == "s3":
        # For S3, path is the object_key
        import asyncio
        storage = get_storage_backend()
        try:
            asyncio.run(storage.delete_file(path))
        except Exception as e:
            logger.error(f"Failed to delete S3 object {path}: {e}")
    else:
        # For local storage
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink(missing_ok=True)

