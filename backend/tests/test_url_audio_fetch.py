import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import AudioValidationError
from app.services.url_audio_fetch import (
    UrlAudioFetchError,
    _ensure_allowed_extension,
    _validate_url_format,
    fetch_audio_from_url,
)


def test_validate_url_format_rejects_non_http():
    with pytest.raises(UrlAudioFetchError, match="http and https"):
        _validate_url_format("ftp://example.com/audio.mp3")


def test_validate_url_format_rejects_empty():
    with pytest.raises(UrlAudioFetchError, match="required"):
        _validate_url_format("   ")


def test_validate_url_format_accepts_https():
    url = _validate_url_format(
        "https://s3.ap-south-1.amazonaws.com/bucket/path/recording.mp3"
    )
    assert url.startswith("https://")


def test_ensure_allowed_extension_from_mp3_header():
    name = _ensure_allowed_extension("download", "application/octet-stream", b"ID3\x04")
    assert name.endswith(".mp3")


@pytest.mark.asyncio
async def test_fetch_audio_from_url_rejects_html_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.content = b"<html>not audio</html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.url_audio_fetch.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.services.url_audio_fetch._validate_url_format",
            return_value="https://example.com/a.mp3",
        ):
            with pytest.raises(UrlAudioFetchError, match="non-audio"):
                await fetch_audio_from_url("https://example.com/a.mp3")


@pytest.mark.asyncio
async def test_fetch_audio_from_url_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "audio/mpeg"}
    mock_response.content = b"ID3" + b"\x00" * 512

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.url_audio_fetch.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.services.url_audio_fetch._validate_url_format",
            return_value="https://example.com/recording.mp3",
        ):
            content, filename, content_type = await fetch_audio_from_url(
                "https://example.com/recording.mp3"
            )

    assert content.startswith(b"ID3")
    assert filename.endswith(".mp3")
    assert content_type == "audio/mpeg"
