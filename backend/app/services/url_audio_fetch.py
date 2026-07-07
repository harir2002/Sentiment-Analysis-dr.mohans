"""Download and validate remote audio files from HTTP(S) URLs."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from app.core.config import get_settings
from app.core.exceptions import AudioValidationError
from app.services.audio_validation import (
    ALLOWED_EXTENSIONS,
    EXTENSION_MIME,
    _has_mp4_container_signature,
    _normalize_mime_type,
)

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
    }
)

# Non-audio Content-Types that clearly indicate a wrong resource.
BLOCKED_CONTENT_TYPES = frozenset(
    {
        "text/html",
        "text/plain",
        "text/css",
        "text/javascript",
        "application/javascript",
        "application/json",
        "application/xml",
        "text/xml",
        "image/",
        "video/mp4",  # video container without audio intent
    }
)

MP3_SIGNATURES = (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
WAV_SIGNATURE = b"RIFF"
OGG_SIGNATURE = b"OggS"
FLAC_SIGNATURE = b"fLaC"


class UrlAudioFetchError(AudioValidationError):
    """Raised when a remote audio URL cannot be fetched or validated."""


def _validate_url_format(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise UrlAudioFetchError("Audio URL is required")

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise UrlAudioFetchError("Only http and https URLs are supported")

    if not parsed.netloc:
        raise UrlAudioFetchError("Invalid URL format")

    if parsed.username or parsed.password:
        raise UrlAudioFetchError("URLs with embedded credentials are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UrlAudioFetchError("Invalid URL hostname")

    lowered = hostname.lower().rstrip(".")
    if lowered in BLOCKED_HOSTNAMES or lowered.endswith(".local"):
        raise UrlAudioFetchError("This URL host is not allowed")

    if not _is_safe_resolved_host(lowered):
        raise UrlAudioFetchError("URL points to a private or restricted network address")

    return cleaned


def _is_safe_resolved_host(hostname: str) -> bool:
    try:
        addr_infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return False
        if ip == ipaddress.ip_address("169.254.169.254"):
            return False
    return True


def _filename_from_url(url: str, content_disposition: str | None = None) -> str:
    if content_disposition:
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";\n]+)"?', content_disposition, re.I)
        if match:
            name = unquote(match.group(1).strip())
            if name:
                return Path(name).name

    path_name = Path(unquote(urlparse(url).path)).name
    if path_name and "." in path_name:
        return path_name
    return "remote-audio.mp3"


def _extension_from_content_type(content_type: str | None) -> str | None:
    normalized = _normalize_mime_type(content_type)
    if not normalized:
        return None
    for ext, mime in EXTENSION_MIME.items():
        if normalized == mime or normalized.startswith(mime.split("/")[0] + "/"):
            if ext in ALLOWED_EXTENSIONS:
                return ext
    if normalized in {"audio/mpeg", "audio/mp3"}:
        return ".mp3"
    if normalized in {"audio/mp4", "audio/x-m4a", "audio/m4a"}:
        return ".m4a"
    if normalized == "audio/wav":
        return ".wav"
    return None


def _guess_extension_from_bytes(header: bytes) -> str | None:
    if header.startswith(WAV_SIGNATURE):
        return ".wav"
    if header.startswith(MP3_SIGNATURES):
        return ".mp3"
    if header.startswith(OGG_SIGNATURE):
        return ".ogg"
    if header.startswith(FLAC_SIGNATURE):
        return ".flac"
    if _has_mp4_container_signature(header):
        return ".m4a"
  # WebM uses EBML header 0x1A45DFA3
    if len(header) >= 4 and header[0:4] == b"\x1a\x45\xdf\xa3":
        return ".webm"
    return None


def _ensure_allowed_extension(filename: str, content_type: str | None, header: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = _extension_from_content_type(content_type) or _guess_extension_from_bytes(header)
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise UrlAudioFetchError(
            "Remote file is not a supported audio format. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    stem = Path(filename).stem or "remote-audio"
    return f"{stem}{ext}"


def _validate_response_content_type(content_type: str | None) -> None:
    normalized = _normalize_mime_type(content_type)
    if not normalized:
        return
    for blocked in BLOCKED_CONTENT_TYPES:
        if blocked.endswith("/"):
            if normalized.startswith(blocked):
                raise UrlAudioFetchError(f"URL returned non-audio content ({normalized})")
        elif normalized == blocked:
            raise UrlAudioFetchError(f"URL returned non-audio content ({normalized})")
    if normalized.startswith("audio/") or normalized in {
        "application/ogg",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        return
    raise UrlAudioFetchError(f"URL returned unsupported content type: {normalized}")


async def fetch_audio_from_url(url: str) -> tuple[bytes, str, str | None]:
    """Download remote audio. Returns (content, filename, content_type)."""
    settings = get_settings()
    safe_url = _validate_url_format(url)
    timeout = httpx.Timeout(
        connect=min(15.0, settings.url_download_timeout_seconds),
        read=settings.url_download_timeout_seconds,
        write=15.0,
        pool=15.0,
    )

    headers = {"User-Agent": "CallAnalytics/1.0 (+audio-ingest)"}

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
    ) as client:
        try:
            response = await client.get(safe_url, headers=headers)
        except httpx.TimeoutException as exc:
            raise UrlAudioFetchError(
                f"Timed out fetching audio URL after {settings.url_download_timeout_seconds:.0f}s"
            ) from exc
        except httpx.TooManyRedirects as exc:
            raise UrlAudioFetchError("Too many redirects while fetching audio URL") from exc
        except httpx.RequestError as exc:
            raise UrlAudioFetchError(f"Could not fetch audio URL: {exc}") from exc

        if response.status_code == 404:
            raise UrlAudioFetchError("Audio URL not found (404)")
        if response.status_code == 403:
            raise UrlAudioFetchError("Access denied for audio URL (403)")
        if response.status_code >= 400:
            raise UrlAudioFetchError(
                f"Failed to download audio (HTTP {response.status_code})"
            )

        content_type = response.headers.get("content-type")
        _validate_response_content_type(content_type)

        content = response.content
        if not content:
            raise UrlAudioFetchError("Downloaded file is empty")

        if len(content) > settings.max_upload_bytes:
            raise UrlAudioFetchError(
                f"Remote file exceeds maximum size of {settings.max_upload_size_mb}MB"
            )

        filename = _filename_from_url(
            safe_url,
            response.headers.get("content-disposition"),
        )
        filename = _ensure_allowed_extension(filename, content_type, content[:16])

        logger.info(
            "Fetched remote audio url=%s filename=%s bytes=%s content_type=%s",
            safe_url,
            filename,
            len(content),
            content_type,
        )
        return content, filename, content_type


def build_url_ingest_metadata(source_url: str) -> dict:
    return {
        "source_type": "url",
        "source_url": source_url,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
