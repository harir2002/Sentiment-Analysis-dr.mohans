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
