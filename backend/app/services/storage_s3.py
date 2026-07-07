"""S3-compatible storage backend (AWS S3, Supabase Storage, DigitalOcean Spaces, etc.)."""

import logging
import mimetypes
from datetime import timedelta
import boto3
from botocore.exceptions import ClientError
from app.services.storage_backend import StorageBackend
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class S3StorageBackend(StorageBackend):
    """Store files on S3-compatible services (AWS S3, Supabase Storage, etc.)."""

    def __init__(self):
        self.settings = get_settings()
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url or None,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
        )
        
        self.bucket = self.settings.s3_bucket
        logger.info(f"S3 storage initialized: bucket={self.bucket}, endpoint={self.settings.s3_endpoint_url}")

    async def upload_file(self, file_id: str, content: bytes, filename: str) -> dict:
        """Upload file to S3."""
        ext = filename.split(".")[-1] if "." in filename else "bin"
        object_key = f"uploads/{file_id}.{ext}"

        # Get MIME type
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "original_filename": filename,
                    "file_id": file_id,
                },
            )

            logger.info(f"Uploaded file {file_id} to S3: s3://{self.bucket}/{object_key}")

            return {
                "file_id": file_id,
                "object_key": object_key,
                "size_bytes": len(content),
                "content_type": content_type,
                "url": await self.get_presigned_url(object_key),
            }

        except ClientError as e:
            logger.error(f"Failed to upload file {file_id} to S3: {e}")
            raise

    async def download_file(self, object_key: str) -> bytes:
        """Download file from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=object_key)
            content = response["Body"].read()
            return content

        except ClientError as e:
            logger.error(f"Failed to download file {object_key} from S3: {e}")
            raise

    async def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for S3 object."""
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=expires_in,
            )
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {object_key}: {e}")
            raise

    async def delete_file(self, object_key: str) -> bool:
        """Delete file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=object_key)
            logger.info(f"Deleted S3 object: s3://{self.bucket}/{object_key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete file {object_key} from S3: {e}")
            return False

    async def file_exists(self, object_key: str) -> bool:
        """Check if file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=object_key)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"Error checking if {object_key} exists in S3: {e}")
            raise

    def find_object_key(self, file_id: str) -> str | None:
        """Find uploads/{file_id}.* object key."""
        prefix = f"uploads/{file_id}."
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=1,
            )
            contents = response.get("Contents") or []
            return contents[0]["Key"] if contents else None
        except ClientError as e:
            logger.error("Failed to list S3 prefix %s: %s", prefix, e)
            return None

    async def cleanup(self):
        """Close S3 client connections."""
        # boto3 client doesn't need explicit cleanup
        pass
