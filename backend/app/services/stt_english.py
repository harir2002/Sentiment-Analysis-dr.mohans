"""English-only STT output validation and client-facing sanitization."""
from __future__ import annotations

import logging
import re

from app.models.schemas import ProviderResult
from app.services.guardrails import safe_log_preview, sanitize_provider_result_for_client
from app.services.stt_language import analyze_transcript_language

logger = logging.getLogger(__name__)

ENGLISH_TRANSLATION_FAILED = (
    "English translation failed. Please try again with a clearer audio recording."
)

# Minimum share of Latin letters for a transcript to be treated as English output.
_MIN_LATIN_RATIO = 0.55
_MIN_LETTERS = 6

_INDIC_SCRIPTS = frozenset(
    {
        "tamil",
        "telugu",
        "kannada",
        "malayalam",
        "devanagari",
        "bengali",
        "gujarati",
        "gurmukhi",
    }
)

# Common Sarvam/Whisper homophone errors in Dr. Mohan's diabetes call-center context.
# Applied on every STT result (not cached) — safe corrections only.
_ORG_NAME = "Dr. Mohan's Diabetes Specialities Centre"
_CLINICAL_STT_CORRECTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdeath tests\b", re.I), "blood tests"),
    (re.compile(r"\bdeath test\b", re.I), "blood test"),
    (
        re.compile(
            r"\bMohan(?:'?s)?\s+Director(?:ate)?\s+Special(?:ty|ities|ity)\s+Cent(?:er|re)\b",
            re.I,
        ),
        _ORG_NAME,
    ),
    (
        re.compile(r"\bDirector(?:ate)?\s+Special(?:ty|ities|ity)\s+Cent(?:er|re)\b", re.I),
        _ORG_NAME,
    ),
    (re.compile(r"\bDr\.?\s*Munda\b", re.I), _ORG_NAME),
    (re.compile(r"\bDoctor\s+Munda\b", re.I), _ORG_NAME),
    # "Eye" is a common STT garble of "Diabetes" / "Speciality" hospital name.
    (
        re.compile(
            r"\b(?:Dr\.?\s*)?Mohan(?:'?s)?\s+Eye\s+Special(?:ty|ities|ity)\s+"
            r"(?:Cent(?:er|re)|Hospital)\b",
            re.I,
        ),
        _ORG_NAME,
    ),
    (
        re.compile(
            r"\bMohan\s+Eye\s+Special(?:ty|ities|ity)\s+(?:Cent(?:er|re)|Hospital)\b",
            re.I,
        ),
        _ORG_NAME,
    ),
    (re.compile(r"\bhome tours?\b", re.I), "home visit"),
    (re.compile(r"\bhome tores?\b", re.I), "home visit"),
    (re.compile(r"\bAdam\s+Baba\s+area\b", re.I), "Adambakkam area"),
    (re.compile(r"\bAdam\s+Baba\b", re.I), "Adambakkam"),
    # Tamil "munnadi" (earlier/before) often misheard as "Mumbai" in scheduling context.
    (re.compile(r"\b(will )?come from Mumbai\b", re.I), r"\1come munnadi"),
    # East Tambaram branch/area — "Conference center" is a common STT garble.
    (
        re.compile(
            r"\bConference\s+cent(?:er|re)\s*[-–,]?\s*East\s+Tambaram\b",
            re.I,
        ),
        "East Tambaram",
    ),
    (re.compile(r"\bConference\s+cent(?:er|re)\s+in\s+East\s+Tambaram\b", re.I), "East Tambaram"),
    (re.compile(r"\bRignesh\b", re.I), "Vignesh"),
    # Trailing digit often dropped: patient/reg number or fee "299" → "2999".
    (
        re.compile(
            r"\b((?:number|id|uhid|mrn|reg(?:istration)?(?:\s+number)?|"
            r"patient\s+(?:id|number)|file\s+number)\s*[:#]?\s*)299\b",
            re.I,
        ),
        r"\g<1>2999",
    ),
    (
        re.compile(
            r"\b((?:rs\.?|inr|rupees?)\s*)299\b",
            re.I,
        ),
        r"\g<1>2999",
    ),
    (
        re.compile(r"\b299(\s*(?:rs\.?|rupees?))\b", re.I),
        r"2999\1",
    ),
    (
        re.compile(
            r"\b((?:charge|charges|fee|amount|cost|payment|service\s+charge)"
            r"\s+(?:of\s+|is\s+|are\s+)?(?:rs\.?\s*)?)299\b",
            re.I,
        ),
        r"\g<1>2999",
    ),
)


def apply_clinical_stt_corrections(text: str) -> str:
    """Fix known healthcare STT mis-hearings in English transcripts."""
    corrected = text or ""
    for pattern, replacement in _CLINICAL_STT_CORRECTIONS:
        corrected = pattern.sub(replacement, corrected)
    return corrected


def sarvam_mode_for_english_output(model: str, configured_mode: str) -> str:
    """Use Sarvam translate mode when supported (saaras) to emit English text."""
    if "saaras" in (model or "").lower():
        return "translate"
    return (configured_mode or "transcribe").strip() or "transcribe"


def is_predominantly_english(text: str) -> bool:
    if not text or not text.strip():
        return False

    letters = [c for c in text if c.isalpha()]
    if len(letters) < _MIN_LETTERS:
        return False

    latin = sum(1 for c in letters if c.isascii())
    if latin / len(letters) < _MIN_LATIN_RATIO:
        return False

    analysis = analyze_transcript_language(text)
    dominant = analysis.get("dominant_script")
    if dominant in _INDIC_SCRIPTS:
        counts = analysis.get("script_counts") or {}
        indic_total = sum(counts.get(s, 0) for s in _INDIC_SCRIPTS)
        latin_count = counts.get("latin", 0)
        if indic_total > latin_count and indic_total >= 3:
            return False

    return True


def validate_english_transcript(text: str) -> str | None:
    """Return an error message when transcript is not usable English output."""
    if not text or not text.strip():
        return ENGLISH_TRANSLATION_FAILED
    if is_predominantly_english(text):
        return None
    logger.warning(
        "Transcript failed English validation (length=%s, preview=%r)",
        len(text),
        safe_log_preview(text),
    )
    return ENGLISH_TRANSLATION_FAILED


def normalize_english_transcript(text: str) -> str:
    """Light cleanup and domain STT corrections before sentiment analysis."""
    cleaned = " ".join((text or "").split())
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = apply_clinical_stt_corrections(cleaned)
    return cleaned.strip()


__all__ = [
    "ENGLISH_TRANSLATION_FAILED",
    "apply_clinical_stt_corrections",
    "is_predominantly_english",
    "normalize_english_transcript",
    "sanitize_provider_result_for_client",
    "sarvam_mode_for_english_output",
    "validate_english_transcript",
]
