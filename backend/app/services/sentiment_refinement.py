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
    r"home visit|home care|blood test|home blood|booked|fixed it for you|"
    r"fixed a home|scheduled|saturday morning|confirm the timing|taking it at home"
    r")\b",
    re.I,
)

_COOPERATIVE_CLOSURE_RE = re.compile(
    r"\b("
    r"no doubts|no other doubts|any other doubts\?\s*no|okay,?\s*alright|"
    r"yes\.?\s*okay|thank you for calling"
    r")\b",
    re.I,
)

_RESOLVED_STATUSES = frozenset({"resolved", "partially_resolved"})


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

        if has_scheduling_success and (
            has_cooperative_closure or resolution == "resolved"
        ):
            return analysis.model_copy(
                update={
                    "sentiment": "positive",
                    "notes": _append_note(
                        analysis.notes,
                        "Sentiment refined to positive: home visit or blood test successfully arranged with cooperative caller.",
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


__all__ = ["refine_sentiment"]
