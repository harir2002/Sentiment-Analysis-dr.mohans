"""Rules for classifying recordings as valid vs invalid for sentiment KPIs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.schemas import ProviderResult

MIN_TRANSCRIPT_CHARS = 20
MIN_SUMMARY_CHARS = 15
LOW_CONFIDENCE_THRESHOLD = 0.15

INVALID_SENTIMENT_TOKENS = frozenset(
    {
        "invalid",
        "unclassified",
        "unknown",
        "n/a",
        "na",
        "none",
        "unclear",
        "insufficient",
    }
)

NOISE_TRANSCRIPT_PATTERNS = (
    re.compile(r"^\[?\s*silence\s*\]?\.?$", re.I),
    re.compile(r"^no\s+speech", re.I),
    re.compile(r"^inaudible", re.I),
    re.compile(r"^unable\s+to\s+transcribe", re.I),
    re.compile(r"^transcription\s+failed", re.I),
    re.compile(r"^[\s\.\-_,;:!?…]*$"),
)


@dataclass(frozen=True)
class RecordingValidity:
    is_valid_call: bool
    sentiment_label: str  # positive | neutral | negative | invalid
    invalid_reason: str | None = None


def _normalize_sentiment_token(sentiment: str | None) -> str | None:
    if not sentiment:
        return None
    value = sentiment.strip().lower()
    if value in INVALID_SENTIMENT_TOKENS:
        return None
    if value in {"positive", "pos"}:
        return "positive"
    if value in {"negative", "neg"}:
        return "negative"
    if value in {"neutral", "mixed", "neu"}:
        return "neutral"
    return None


def _is_noise_transcript(transcript: str) -> bool:
    stripped = transcript.strip()
    if not stripped:
        return True
    return any(pattern.match(stripped) for pattern in NOISE_TRANSCRIPT_PATTERNS)


def _assess_provider_result(result: ProviderResult) -> RecordingValidity:
    if result.status != "completed":
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Analysis did not complete successfully",
        )

    transcript = (result.transcript or "").strip()
    if not transcript:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Empty transcript — no speech content detected",
        )

    if len(transcript) < MIN_TRANSCRIPT_CHARS:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Transcript too short to classify sentiment reliably",
        )

    if _is_noise_transcript(transcript):
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Transcript contains only silence or unusable audio content",
        )

    raw_sentiment = (result.analysis.sentiment or "").strip().lower()
    if raw_sentiment in INVALID_SENTIMENT_TOKENS:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Insufficient content to infer sentiment",
        )

    sentiment_label = _normalize_sentiment_token(result.analysis.sentiment)
    summary = (result.analysis.summary or "").strip()
    confidence = result.analysis.confidence or 0.0

    if sentiment_label is None:
        if confidence < LOW_CONFIDENCE_THRESHOLD and len(summary) < MIN_SUMMARY_CHARS:
            return RecordingValidity(
                is_valid_call=False,
                sentiment_label="invalid",
                invalid_reason="Low confidence and no useful summary — cannot classify reliably",
            )
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Sentiment could not be classified from available content",
        )

    if confidence < LOW_CONFIDENCE_THRESHOLD and len(summary) < MIN_SUMMARY_CHARS:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="Confidence too low with insufficient summary for reliable classification",
        )

    return RecordingValidity(is_valid_call=True, sentiment_label=sentiment_label)


def assess_recording_validity(
    *,
    aggregate_status: str,
    job_error: str | None,
    canonical: ProviderResult | None,
    results_ready: bool,
) -> RecordingValidity:
    """Assess one recording using its canonical (winner) solution output."""
    if not results_ready:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason=None,
        )

    if aggregate_status == "failed" and canonical is None:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason=job_error or "Analysis failed — no usable result produced",
        )

    if canonical is None:
        return RecordingValidity(
            is_valid_call=False,
            sentiment_label="invalid",
            invalid_reason="No successful analysis output from any solution",
        )

    return _assess_provider_result(canonical)
