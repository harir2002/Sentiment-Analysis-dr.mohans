"""Derive client-facing recommended actions for Dr. Mohan's Diabetes Specialities Centre."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.schemas import AnalysisResult

_CLINICAL_URGENT_RE = re.compile(
    r"\b("
    r"emergency|severe pain|chest pain|unconscious|life[- ]threatening|"
    r"critical condition|urgent doctor|immediate (?:medical|clinical)"
    r")\b",
    re.I,
)

_BOOKING_SUCCESS_RE = re.compile(
    r"\b("
    r"home visit|home care|home blood|blood test|blood collection|hemoglobin injection|"
    r"injection at home|appointment|booked|booking|scheduled|arrange(?:d|ment)?|"
    r"confirm(?:ing|ed)? details|payment arrangement|fixed (?:it )?for|visit for"
    r")\b",
    re.I,
)

_APP_SUPPORT_RE = re.compile(
    r"\b("
    r"mobile app|app (?:not working|issue|problem|login)|cannot log in|can't log in|"
    r"login (?:issue|problem|fail)|password|otp|digital report|online report|"
    r"report (?:on|in) (?:the )?app"
    r")\b",
    re.I,
)

_LAB_REPORT_RE = re.compile(
    r"\b("
    r"lab report|blood report|test report|report delay|report not received|"
    r"outstation|chennai lab|report status|death test|pending report|"
    r"waiting for (?:the )?report"
    r")\b",
    re.I,
)

_COMPLAINT_RE = re.compile(
    r"\b("
    r"complaint|repeated (?:issue|service|failure)|recurring|multiple times|"
    r"still not resolved|never received|poor service|unsatisfied|unresolved issue|"
    r"frustrat|angry|upset|escalat|four months|useless|lousy"
    r")\b",
    re.I,
)

_GENERIC_COMPLAINT_PHRASE = "create a complaint ticket and route to service recovery"

_RESOLVED_STATUSES = frozenset({"resolved", "partially_resolved"})


@dataclass(frozen=True)
class RecommendedActionPlan:
    recommended_action: str
    action_priority: str
    assigned_team: str
    escalation_status: str


def _analysis_text(analysis: AnalysisResult, transcript: str = "") -> str:
    parts: list[str] = [transcript or ""]
    if analysis.summary:
        parts.append(analysis.summary)
    if analysis.notes:
        parts.append(analysis.notes)
    parts.extend(analysis.key_issues or [])
    parts.extend(analysis.action_items or [])
    return " ".join(parts)


def _is_generic_complaint(text: str) -> bool:
    lowered = text.lower()
    return "complaint ticket" in lowered or "service recovery" in lowered


def _normalize_step(text: str) -> str:
    return " ".join(text.lower().split())


def _is_duplicate_step(a: str, b: str) -> bool:
    left, right = _normalize_step(a), _normalize_step(b)
    if not left or not right:
        return False
    if left == right:
        return True
    return left in right or right in left


def _clean_action_items(recommended_action: str, action_items: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for item in action_items or []:
        text = str(item).strip()
        if not text:
            continue
        if _is_duplicate_step(text, recommended_action):
            continue
        if _is_generic_complaint(text) and not _is_generic_complaint(recommended_action):
            continue
        if any(_is_duplicate_step(text, existing) for existing in cleaned):
            continue
        cleaned.append(text)
    return cleaned


def derive_recommended_action(
    analysis: AnalysisResult,
    *,
    transcript: str = "",
) -> RecommendedActionPlan:
    sentiment = (analysis.sentiment or "neutral").strip().lower()
    text = _analysis_text(analysis, transcript)
    confidence = float(analysis.confidence or 0.0)
    resolution = (analysis.resolution_status or "").strip().lower()
    resolved = resolution in _RESOLVED_STATUSES

    has_booking = bool(_BOOKING_SUCCESS_RE.search(text))
    has_complaint = bool(_COMPLAINT_RE.search(text))
    has_app_issue = bool(_APP_SUPPORT_RE.search(text))
    has_lab_issue = bool(_LAB_REPORT_RE.search(text))
    has_clinical_urgent = bool(_CLINICAL_URGENT_RE.search(text))

    if has_clinical_urgent:
        plan = RecommendedActionPlan(
            recommended_action="Mark as critical and arrange immediate clinical callback.",
            action_priority="Critical",
            assigned_team="Clinical Care Team",
            escalation_status="Critical",
        )
    elif has_booking and sentiment == "positive" and (resolved or not has_complaint):
        plan = RecommendedActionPlan(
            recommended_action=(
                "Send confirmation SMS or WhatsApp with visit date, time, patient name, "
                "and service type (home visit, blood test, or injection)."
            ),
            action_priority="Medium",
            assigned_team="Home Care / Appointment Desk",
            escalation_status="None",
        )
    elif has_booking and resolved and sentiment in {"positive", "neutral", "mixed"}:
        plan = RecommendedActionPlan(
            recommended_action=(
                "Send confirmation message with booked date, time, and any payment or "
                "preparation instructions discussed on the call."
            ),
            action_priority="Medium",
            assigned_team="Home Care / Appointment Desk",
            escalation_status="Standard" if sentiment == "mixed" else "None",
        )
    elif has_app_issue:
        plan = RecommendedActionPlan(
            recommended_action=(
                "Route to App Support, fix login or digital report access, and call the "
                "patient back once the app issue is resolved."
            ),
            action_priority="High" if sentiment in {"negative", "mixed"} else "Medium",
            assigned_team="App Support",
            escalation_status="Escalated" if sentiment == "negative" else "Standard",
        )
    elif has_lab_issue and sentiment in {"negative", "mixed"} and not resolved:
        plan = RecommendedActionPlan(
            recommended_action=(
                "Follow up with the lab or Chennai branch on report status and call the "
                "patient back with the expected delivery timeline."
            ),
            action_priority="High",
            assigned_team="Lab / Branch Ops",
            escalation_status="Escalated" if sentiment == "negative" else "Standard",
        )
    elif has_lab_issue and resolved:
        plan = RecommendedActionPlan(
            recommended_action=(
                "Notify the patient when the lab report is ready via SMS, WhatsApp, or app alert."
            ),
            action_priority="Medium",
            assigned_team="Lab / Branch Ops",
            escalation_status="None",
        )
    elif has_complaint and sentiment in {"negative", "mixed"} and not (
        has_booking and resolved and sentiment == "mixed"
    ):
        plan = RecommendedActionPlan(
            recommended_action="Create a complaint ticket and route to service recovery.",
            action_priority="High",
            assigned_team="Complaints Desk",
            escalation_status="Escalated",
        )
    elif has_booking and sentiment in {"negative", "mixed"}:
        plan = RecommendedActionPlan(
            recommended_action=(
                "Call the patient back to confirm or complete the home visit or appointment booking."
            ),
            action_priority="High",
            assigned_team="Home Care / Appointment Desk",
            escalation_status="Standard",
        )
    elif has_booking:
        plan = RecommendedActionPlan(
            recommended_action=(
                "Send confirmation SMS or WhatsApp with the arranged visit or appointment details."
            ),
            action_priority="Medium",
            assigned_team="Home Care / Appointment Desk",
            escalation_status="None",
        )
    elif sentiment == "negative":
        plan = RecommendedActionPlan(
            recommended_action="Call the patient back for priority follow-up on the unresolved issue.",
            action_priority="High",
            assigned_team="Customer Support",
            escalation_status="Escalated",
        )
    elif sentiment == "mixed":
        plan = RecommendedActionPlan(
            recommended_action="Review unresolved items and assign targeted follow-up.",
            action_priority="Medium",
            assigned_team="Customer Support",
            escalation_status="Standard",
        )
    elif sentiment == "positive":
        plan = RecommendedActionPlan(
            recommended_action="No further action needed — close the interaction normally.",
            action_priority="Low",
            assigned_team="Customer Support",
            escalation_status="None",
        )
    elif sentiment == "neutral":
        plan = RecommendedActionPlan(
            recommended_action="Monitor the case and follow up only if the patient does not receive promised updates.",
            action_priority="Low",
            assigned_team="Customer Support",
            escalation_status="None",
        )
    else:
        plan = RecommendedActionPlan(
            recommended_action="Review the call and determine appropriate follow-up.",
            action_priority="Medium",
            assigned_team="Customer Support",
            escalation_status="Standard",
        )

    if confidence < 0.5 and plan.action_priority != "Critical":
        return RecommendedActionPlan(
            recommended_action=f"Manual review recommended. {plan.recommended_action}",
            action_priority="Medium" if plan.action_priority == "Low" else plan.action_priority,
            assigned_team=plan.assigned_team,
            escalation_status=plan.escalation_status,
        )

    return plan


def enrich_analysis(analysis: AnalysisResult, *, transcript: str = "") -> AnalysisResult:
    plan = derive_recommended_action(analysis, transcript=transcript)
    cleaned_items = _clean_action_items(plan.recommended_action, analysis.action_items)
    return analysis.model_copy(
        update={
            "recommended_action": plan.recommended_action,
            "action_priority": plan.action_priority,
            "assigned_team": plan.assigned_team,
            "escalation_status": plan.escalation_status,
            "action_items": cleaned_items,
        }
    )
