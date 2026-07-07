from app.models.schemas import ProviderResult, AnalysisResult
from app.services.call_validity import assess_recording_validity, _assess_provider_result


def _result(
    *,
    status: str = "completed",
    transcript: str = "This is a long enough transcript for sentiment analysis purposes.",
    sentiment: str = "positive",
    confidence: float = 0.9,
    summary: str = "Patient discussed billing concerns in detail.",
    recommended_action: str = "Follow up with billing team within 24 hours.",
) -> ProviderResult:
    return ProviderResult(
        solution_id="groq_whisper_sarvam_llm",
        label="test",
        stt_provider="groq",
        llm_provider="sarvam",
        status=status,
        transcript=transcript,
        analysis=AnalysisResult(
            sentiment=sentiment,
            summary=summary,
            confidence=confidence,
            recommended_action=recommended_action,
        ),
    )


def test_valid_call_classified_positive():
    validity = _assess_provider_result(_result())
    assert validity.is_valid_call is True
    assert validity.sentiment_label == "positive"
    assert validity.invalid_reason is None


def test_empty_transcript_is_invalid():
    validity = _assess_provider_result(_result(transcript=""))
    assert validity.is_valid_call is False
    assert validity.sentiment_label == "invalid"
    assert "Empty transcript" in (validity.invalid_reason or "")


def test_short_transcript_is_invalid():
    validity = _assess_provider_result(_result(transcript="hello"))
    assert validity.is_valid_call is False
    assert validity.sentiment_label == "invalid"


def test_explicit_invalid_sentiment_token():
    validity = _assess_provider_result(_result(sentiment="invalid"))
    assert validity.is_valid_call is False
    assert validity.sentiment_label == "invalid"


def test_low_confidence_and_no_summary_is_invalid():
    validity = _assess_provider_result(
        _result(confidence=0.05, summary="", sentiment="positive")
    )
    assert validity.is_valid_call is False
    assert validity.sentiment_label == "invalid"


def test_failed_job_without_canonical_is_invalid():
    validity = assess_recording_validity(
        aggregate_status="failed",
        job_error="Provider timeout",
        canonical=None,
        results_ready=True,
    )
    assert validity.is_valid_call is False
    assert validity.sentiment_label == "invalid"
    assert "timeout" in (validity.invalid_reason or "").lower()
