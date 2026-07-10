"""Tests for recommended action mapping."""
from app.models.schemas import AnalysisResult
from app.services.recommended_action import derive_recommended_action, enrich_analysis


def test_positive_sentiment_no_action():
    plan = derive_recommended_action(
        AnalysisResult(sentiment="positive", confidence=0.9, summary="Customer was satisfied.")
    )
    assert "No further action needed" in plan.recommended_action
    assert plan.action_priority == "Low"
    assert plan.escalation_status == "None"


def test_negative_sentiment_escalates():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="negative",
            confidence=0.85,
            summary="Customer was unhappy with billing.",
            key_issues=["billing error"],
        )
    )
    assert "priority follow-up" in plan.recommended_action.lower()
    assert plan.action_priority == "High"
    assert plan.escalation_status == "Escalated"


def test_neutral_sentiment_monitor():
    plan = derive_recommended_action(
        AnalysisResult(sentiment="neutral", confidence=0.8, summary="Routine inquiry.")
    )
    assert "Monitor" in plan.recommended_action
    assert plan.action_priority == "Low"


def test_medical_concern_critical():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="negative",
            confidence=0.9,
            summary="Patient reported severe pain and needs urgent doctor callback.",
            key_issues=["medical concern"],
        )
    )
    assert plan.action_priority == "Critical"
    assert plan.assigned_team == "Clinical Care Team"
    assert plan.escalation_status == "Critical"


def test_appointment_issue_callback():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="negative",
            confidence=0.88,
            summary="Appointment was delayed again.",
            key_issues=["appointment delay"],
        )
    )
    assert "call the patient back" in plan.recommended_action.lower()
    assert plan.assigned_team == "Home Care / Appointment Desk"


def test_repeated_issues_complaint_ticket():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="negative",
            confidence=0.9,
            summary="Customer complained about repeated service failures.",
            key_issues=["missed callback", "unresolved billing"],
        )
    )
    assert "complaint ticket" in plan.recommended_action.lower()
    assert plan.assigned_team == "Complaints Desk"


def test_home_visit_booking_sends_confirmation():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="positive",
            confidence=0.9,
            summary="Home visit for hemoglobin injection arranged for Saturday morning.",
            resolution_status="resolved",
            key_issues=["home visit arrangement", "payment confirmation"],
        ),
        transcript="We fixed a home visit for her on Saturday morning. Any other doubts? No.",
    )
    assert "confirmation" in plan.recommended_action.lower()
    assert "complaint ticket" not in plan.recommended_action.lower()
    assert plan.assigned_team == "Home Care / Appointment Desk"


def test_multiple_issues_do_not_force_complaint_for_booking():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="positive",
            confidence=0.88,
            summary="Blood test home collection booked with payment arrangement confirmed.",
            resolution_status="partially_resolved",
            key_issues=["home blood collection", "payment arrangement"],
        )
    )
    assert "complaint ticket" not in plan.recommended_action.lower()
    assert "confirmation" in plan.recommended_action.lower()


def test_app_issue_routes_to_app_support():
    plan = derive_recommended_action(
        AnalysisResult(
            sentiment="mixed",
            confidence=0.86,
            summary="Patient cannot log in to the mobile app to view reports.",
            key_issues=["app login failure"],
        )
    )
    assert plan.assigned_team == "App Support"
    assert "app" in plan.recommended_action.lower()


def test_low_confidence_adds_manual_review():
    plan = derive_recommended_action(
        AnalysisResult(sentiment="positive", confidence=0.4, summary="Short call.")
    )
    assert "Manual review recommended" in plan.recommended_action


def test_enrich_analysis_populates_fields():
    enriched = enrich_analysis(AnalysisResult(sentiment="neutral", confidence=0.8))
    assert enriched.recommended_action
    assert enriched.action_priority
    assert enriched.assigned_team
    assert enriched.escalation_status


def test_enrich_analysis_strips_duplicate_generic_complaint_items():
    enriched = enrich_analysis(
        AnalysisResult(
            sentiment="positive",
            confidence=0.9,
            summary="Home visit booked for blood test on Saturday.",
            resolution_status="resolved",
            action_items=[
                "Create a complaint ticket and route to service recovery.",
                "Confirm patient address before dispatch.",
            ],
        )
    )
    assert "complaint ticket" not in enriched.recommended_action.lower()
    assert all("complaint ticket" not in item.lower() for item in enriched.action_items)
    assert any("address" in item.lower() for item in enriched.action_items)
