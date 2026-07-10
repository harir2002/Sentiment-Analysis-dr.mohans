from app.models.schemas import AnalysisResult
from app.services.sentiment_refinement import refine_sentiment

HOME_VISIT_TRANSCRIPT = (
    "Good evening sir, Namaste. We are calling from Dr. Mohan's Diabetes Specialities Centre. "
    "Okay Madam, I have fixed a home visit for you and Madam at home. "
    "Please take a blood test tomorrow and book it for Saturday morning. "
    "Do you have any other doubts? No. Okay, alright? "
    "Okay madam, thank you for calling madam, have a great day."
)

APP_COMPLAINT_TRANSCRIPT = (
    "Chennai lab report will come in two days. "
    "Your app is not working properly, useless app, cannot log in."
)


def test_refine_neutral_home_visit_to_positive():
    analysis = AnalysisResult(
        sentiment="neutral",
        summary="Home visit and blood test scheduled.",
        resolution_status="resolved",
        confidence=0.8,
        notes="",
    )
    refined = refine_sentiment(analysis, HOME_VISIT_TRANSCRIPT)
    assert refined.sentiment == "positive"


def test_refine_neutral_app_complaint_to_mixed():
    analysis = AnalysisResult(
        sentiment="neutral",
        summary="Report timeline shared; app issues raised.",
        resolution_status="partially_resolved",
        confidence=0.75,
        notes="",
    )
    refined = refine_sentiment(analysis, APP_COMPLAINT_TRANSCRIPT)
    assert refined.sentiment == "mixed"


def test_refine_neutral_hemoglobin_home_visit_to_positive():
    analysis = AnalysisResult(
        sentiment="neutral",
        summary=(
            "A relative arranged a home visit for a hemoglobin injection "
            "for patient Bhuvaneshwari, confirming details and payment arrangements."
        ),
        resolution_status="partially_resolved",
        confidence=0.82,
        notes="",
    )
    refined = refine_sentiment(analysis, "")
    assert refined.sentiment == "positive"


def test_refine_negative_complaint_unchanged():
    analysis = AnalysisResult(
        sentiment="negative",
        summary="Caller upset about app.",
        resolution_status="unresolved",
        confidence=0.9,
        notes="",
    )
    refined = refine_sentiment(analysis, APP_COMPLAINT_TRANSCRIPT)
    assert refined.sentiment == "negative"


BHUVANESHWARI_HOME_INJECTION = (
    "Lakshmi from Dr. Mohan Diabetes Speciality Center. "
    "Bhuvaneshwari name. Number 25791. Doctor Parthasarathy. "
    "Hemoglobin injection, triglyceride 500 mg 100 ml. "
    "Can you administer that injection at home? "
    "I will connect you to the Home Care Department. "
    "Is the patient's name Bhuvaneshwari? Yes, Bhuvaneshwari. "
    "Yes, we can give it, sir. They will come tomorrow around 11 to 11:30. "
    "I'll arrange it for you now and then I will call you back in the evening. "
    "Okay, ma'am, thank you very much, thank you very much."
)


def test_refine_mixed_successful_home_injection_to_positive():
    """Hold/transfer + callback-to-confirm must not keep a successful booking as mixed."""
    analysis = AnalysisResult(
        sentiment="mixed",
        summary=(
            "Caller arranged a home hemoglobin injection for patient Bhuvaneshwari; "
            "Home Care will visit tomorrow afternoon and call back to confirm."
        ),
        resolution_status="partially_resolved",
        confidence=0.8,
        notes="Pending evening confirmation callback.",
        key_issues=["home injection scheduling", "payment at home"],
    )
    refined = refine_sentiment(analysis, BHUVANESHWARI_HOME_INJECTION)
    assert refined.sentiment == "positive"


def test_refine_mixed_app_complaint_stays_mixed():
    analysis = AnalysisResult(
        sentiment="mixed",
        summary="App complaint with partial help.",
        resolution_status="partially_resolved",
        confidence=0.7,
        notes="",
    )
    refined = refine_sentiment(analysis, APP_COMPLAINT_TRANSCRIPT)
    assert refined.sentiment == "mixed"


def test_refine_summary_patient_name_not_treated_as_caller():
    from app.services.sentiment_refinement import refine_summary

    analysis = AnalysisResult(
        sentiment="positive",
        summary=(
            "Patient Bhuvaneshwari requested a home hemoglobin injection, was informed "
            "of charges and logistics, and confirmed a home visit for the next day."
        ),
        resolution_status="resolved",
        confidence=0.85,
        notes="",
    )
    refined = refine_summary(analysis, BHUVANESHWARI_HOME_INJECTION)
    assert refined.summary.lower().startswith("a relative arranged")
    assert "patient Bhuvaneshwari" in refined.summary
    assert not refined.summary.lower().startswith("patient bhuvaneshwari requested")
