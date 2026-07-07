"""Derive client-facing recommended actions from analysis signals."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import AnalysisResult

MEDICAL_KEYWORDS = (
    "medical",
    "health",
    "emergency",
    "urgent",
    "critical",
    "doctor",
    "symptom",
    "pain",
    "medication",
    "hospital",
    "clinic",
    "diagnosis",
)

APPOINTMENT_KEYWORDS = (
    "appointment",
    "schedule",
    "scheduling",
    "delay",
    "wait time",
    "waiting",
    "report",
    "lab result",
    "test result",
    "callback",
    "follow-up call",
    "follow up call",
)

COMPLAINT_KEYWORDS = (
    "complaint",
    "repeated issue",
    "repeated service",
    "recurring",
    "multiple times",
    "still not resolved",
    "never received",
    "poor service",
    "unsatisfied",
    "unresolved issue",
)


@dataclass(frozen=True)
class RecommendedActionPlan:
    recommended_action: str
    action_priority: str
    assigned_team: str
    escalation_status: str


def _analysis_text(analysis: AnalysisResult) -> str:
    parts: list[str] = []
    if analysis.summary:
        parts.append(analysis.summary)
    if analysis.notes:
        parts.append(analysis.notes)
    parts.extend(analysis.key_issues or [])
    parts.extend(analysis.action_items or [])
    return " ".join(parts).lower()


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def derive_recommended_action(analysis: AnalysisResult) -> RecommendedActionPlan:
    sentiment = (analysis.sentiment or "neutral").strip().lower()
    text = _analysis_text(analysis)
    confidence = float(analysis.confidence or 0.0)
    issue_count = len(analysis.key_issues or [])

    if _matches_any(text, MEDICAL_KEYWORDS):
        plan = RecommendedActionPlan(
            recommended_action="Mark as critical and assign immediate clinical follow-up.",
            action_priority="Critical",
            assigned_team="Clinical Care Team",
            escalation_status="Critical",
        )
    elif _matches_any(text, COMPLAINT_KEYWORDS) or issue_count >= 2:
        plan = RecommendedActionPlan(
            recommended_action="Create a complaint ticket and route to service recovery.",
            action_priority="High",
            assigned_team="Complaints Desk",
            escalation_status="Escalated",
        )
    elif _matches_any(text, APPOINTMENT_KEYWORDS):
        plan = RecommendedActionPlan(
            recommended_action="Request a callback and confirm appointment or report follow-up.",
            action_priority="High" if sentiment in {"negative", "mixed"} else "Medium",
            assigned_team="Appointment Services",
            escalation_status="Escalated" if sentiment == "negative" else "Standard",
        )
    elif sentiment == "negative":
        plan = RecommendedActionPlan(
            recommended_action="Escalate to the support team for priority follow-up.",
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
    elif sentiment == "neutral":
        plan = RecommendedActionPlan(
            recommended_action="Monitor the case and follow up if needed.",
            action_priority="Low",
            assigned_team="Customer Support",
            escalation_status="None",
        )
    elif sentiment == "positive":
        plan = RecommendedActionPlan(
            recommended_action="No action needed — close the interaction normally.",
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


def enrich_analysis(analysis: AnalysisResult) -> AnalysisResult:
    plan = derive_recommended_action(analysis)
    return analysis.model_copy(
        update={
            "recommended_action": plan.recommended_action,
            "action_priority": plan.action_priority,
            "assigned_team": plan.assigned_team,
            "escalation_status": plan.escalation_status,
        }
    )
