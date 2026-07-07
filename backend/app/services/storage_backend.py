"""Abstract storage backend interface for audio file persistence."""

from abc import ABC, abstractmethod
from typing import Optional


class StorageBackend(ABC):
    """Abstract base class for storage backends (local, S3, etc.)."""

    @abstractmethod
    async def upload_file(self, file_id: str, content: bytes, filename: str) -> dict:
        """
        Upload a file to storage.
        
        Returns: {
            'file_id': str,
            'object_key': str,  # Path/key in storage
            'size_bytes': int,
            'content_type': str,
            'url': str,  # Presigned URL if applicable
        }
        """
        pass

    @abstractmethod
    async def download_file(self, object_key: str) -> bytes:
        """Download file content from storage by object key."""
        pass

    @abstractmethod
    async def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Get a presigned URL for downloading the file."""
        pass

    @abstractmethod
    async def delete_file(self, object_key: str) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, object_key: str) -> bool:
        """Check if a file exists in storage."""
        pass

    @abstractmethod
    async def cleanup(self):
        """Close any connections or cleanup resources."""
        pass
