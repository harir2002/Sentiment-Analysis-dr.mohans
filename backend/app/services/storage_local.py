"""Local filesystem storage backend (for development)."""

import logging
from pathlib import Path
import aiofiles
import mimetypes
from app.services.storage_backend import StorageBackend
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """Store files on local filesystem. Use for development only."""

    def __init__(self):
        self.settings = get_settings()
        self.upload_dir = Path(self.settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_id: str, content: bytes, filename: str) -> dict:
        """Upload file to local storage."""
        ext = Path(filename).suffix or ".bin"
        safe_name = f"{file_id}{ext}"
        file_path = self.upload_dir / safe_name

        # Write file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Get MIME type
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        logger.info(f"Uploaded file {file_id} to local storage: {file_path}")

        return {
            "file_id": file_id,
            "object_key": safe_name,  # Relative path
            "size_bytes": len(content),
            "content_type": content_type,
            "url": f"/downloads/{safe_name}",  # Local URL (not used in async context)
        }

    async def download_file(self, object_key: str) -> bytes:
        """Download file from local storage."""
        file_path = self.upload_dir / object_key

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        return content

    async def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Get URL for local file (not presigned, just the path)."""
        if not await self.file_exists(object_key):
            raise FileNotFoundError(f"File not found: {object_key}")
        return f"/api/downloads/{object_key}"

    async def delete_file(self, object_key: str) -> bool:
        """Delete file from local storage."""
        file_path = self.upload_dir / object_key

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted local file: {file_path}")
            return True

        return False

    async def file_exists(self, object_key: str) -> bool:
        """Check if file exists in local storage."""
        file_path = self.upload_dir / object_key
        return file_path.exists()

    async def cleanup(self):
        """No cleanup needed for local storage."""
        pass
