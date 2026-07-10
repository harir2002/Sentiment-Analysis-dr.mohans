"""Rule-based sentiment refinement for Dr. Mohan's call patterns.

LLM sentiment is the primary signal; this layer corrects systematic mislabels
when transcript evidence is clear (e.g. successful home visit booking marked neutral).
"""
from __future__ import annotations

import re

from app.models.schemas import AnalysisResult

_COMPLAINT_RE = re.compile(
    r"\b("
    r"not working|cannot log in|can't log in|useless|lousy|frustrat|angry|upset|"
    r"complaint|poor service|unsatisfied|never received|still not|four months|"
    r"don't talk about your app|do not talk about your app"
    r")\b",
    re.I,
)

_SCHEDULING_SUCCESS_RE = re.compile(
    r"\b("
    r"home visit|home care|blood test|home blood|hemoglobin injection|injection at home|"
    r"booked|booking|appointment|arrange(?:d|ment)?|fixed it for you|fixed a home|"
    r"scheduled|saturday morning|confirm(?:ing|ed)? details|payment arrangement|"
    r"taking it at home|visit for her|visit for his"
    r")\b",
    re.I,
)

_COOPERATIVE_CLOSURE_RE = re.compile(
    r"\b("
    r"no doubts|no other doubts|any other doubts\?\s*no|okay,?\s*alright|"
    r"yes\.?\s*okay|thank you(?:\s+very\s+much)?(?:\s+for\s+calling)?|"
    r"confirming details|payment arrangement|arranged successfully|"
    r"have a great day|i'll arrange|i will arrange|"
    r"they will come tomorrow|we can give it|okay ma'?am,?\s*thank"
    r")\b",
    re.I,
)

_RESOLVED_STATUSES = frozenset({"resolved", "partially_resolved"})

# Agent confirms patient identity separately from the person on the phone.
_PATIENT_NAME_CONFIRM_RE = re.compile(
    r"\b(?:is\s+(?:the\s+)?)?patient'?s?\s+name\s+(?:is\s+)?([A-Za-z]+)\b",
    re.I,
)
_WRONG_PATIENT_AS_CALLER_RE = re.compile(
    r"^Patient\s+([A-Za-z]+)\s+"
    r"(?:requested|called(?:\s+to)?|arranged|booked)\s+(.+)$",
    re.I | re.S,
)


def _combined_text(analysis: AnalysisResult, transcript: str) -> str:
    parts = [transcript or ""]
    if analysis.summary:
        parts.append(analysis.summary)
    if analysis.notes:
        parts.append(analysis.notes)
    parts.extend(analysis.key_issues or [])
    return " ".join(parts)


def _append_note(existing: str, addition: str) -> str:
    note = (existing or "").strip()
    if not note:
        return addition
    if addition.lower() in note.lower():
        return note
    return f"{note} {addition}".strip()


def _should_upgrade_booking_to_positive(
    *,
    has_complaint: bool,
    has_scheduling_success: bool,
    has_cooperative_closure: bool,
    resolution: str,
) -> bool:
    """Successful home-care booking with no real complaint is positive, not mixed/neutral."""
    if has_complaint or not has_scheduling_success:
        return False
    return has_cooperative_closure or resolution in _RESOLVED_STATUSES


def refine_summary(analysis: AnalysisResult, transcript: str) -> AnalysisResult:
    """Fix summaries that treat a confirmed patient name as if that person called."""
    summary = (analysis.summary or "").strip()
    if not summary or not (transcript or "").strip():
        return analysis

    confirmed = {m.group(1).lower() for m in _PATIENT_NAME_CONFIRM_RE.finditer(transcript)}
    if not confirmed:
        return analysis

    match = _WRONG_PATIENT_AS_CALLER_RE.match(summary)
    if not match:
        return analysis

    name = match.group(1)
    if name.lower() not in confirmed:
        return analysis

    rest = match.group(2).strip().rstrip(".")
    # Prefer a clean relative/patient split for the common home-care booking pattern.
    if "," in rest:
        service, _, after = rest.partition(",")
        new_summary = (
            f"A relative arranged {service.strip()} for patient {name};"
            f"{after.strip()}."
        )
    else:
        new_summary = f"A relative arranged {rest} for patient {name}."

    return analysis.model_copy(
        update={
            "summary": new_summary,
            "notes": _append_note(
                analysis.notes,
                f"Summary refined: {name} is the patient; a relative booked on their behalf.",
            ),
        }
    )


def refine_sentiment(analysis: AnalysisResult, transcript: str) -> AnalysisResult:
    """Adjust LLM sentiment when transcript evidence strongly contradicts the label."""
    sentiment = (analysis.sentiment or "neutral").strip().lower()
    text = _combined_text(analysis, transcript)
    has_complaint = bool(_COMPLAINT_RE.search(text))
    has_scheduling_success = bool(_SCHEDULING_SUCCESS_RE.search(text))
    has_cooperative_closure = bool(_COOPERATIVE_CLOSURE_RE.search(text))
    resolution = (analysis.resolution_status or "").strip().lower()

    if sentiment == "neutral":
        if has_complaint:
            if resolution in _RESOLVED_STATUSES or has_scheduling_success:
                return analysis.model_copy(
                    update={
                        "sentiment": "mixed",
                        "notes": _append_note(
                            analysis.notes,
                            "Sentiment refined to mixed: complaint present with partial resolution.",
                        ),
                    }
                )
            return analysis.model_copy(
                update={
                    "sentiment": "negative",
                    "notes": _append_note(
                        analysis.notes,
                        "Sentiment refined to negative: unresolved complaint detected.",
                    ),
                }
            )

        if _should_upgrade_booking_to_positive(
            has_complaint=has_complaint,
            has_scheduling_success=has_scheduling_success,
            has_cooperative_closure=has_cooperative_closure,
            resolution=resolution,
        ):
            return analysis.model_copy(
                update={
                    "sentiment": "positive",
                    "notes": _append_note(
                        analysis.notes,
                        "Sentiment refined to positive: home visit, injection, or appointment successfully arranged with cooperative caller.",
                    ),
                }
            )

    # LLM often marks successful bookings "mixed" because of hold/transfer or "call back to confirm".
    if sentiment == "mixed" and _should_upgrade_booking_to_positive(
        has_complaint=has_complaint,
        has_scheduling_success=has_scheduling_success,
        has_cooperative_closure=has_cooperative_closure,
        resolution=resolution,
    ):
        return analysis.model_copy(
            update={
                "sentiment": "positive",
                "notes": _append_note(
                    analysis.notes,
                    "Sentiment refined to positive: successful home care/injection booking without service complaint (hold or callback-to-confirm is not mixed).",
                ),
            }
        )

    if sentiment == "positive" and has_complaint and not has_scheduling_success:
        return analysis.model_copy(
            update={
                "sentiment": "mixed",
                "notes": _append_note(
                    analysis.notes,
                    "Sentiment refined to mixed: complaint detected alongside positive closure.",
                ),
            }
        )

    return analysis


def refine_analysis(analysis: AnalysisResult, transcript: str) -> AnalysisResult:
    """Apply sentiment then summary corrections for Dr. Mohan's call patterns."""
    return refine_summary(refine_sentiment(analysis, transcript), transcript)


__all__ = ["refine_sentiment", "refine_summary", "refine_analysis"]
