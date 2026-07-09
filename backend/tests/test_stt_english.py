from app.services.stt_english import (
    ENGLISH_TRANSLATION_FAILED,
    is_predominantly_english,
    normalize_english_transcript,
    sarvam_mode_for_english_output,
    validate_english_transcript,
)


def test_sarvam_mode_for_english_output_uses_translate_for_saaras():
    assert sarvam_mode_for_english_output("saaras:v3", "transcribe") == "translate"


def test_sarvam_mode_for_english_output_keeps_config_for_other_models():
    assert sarvam_mode_for_english_output("saarika:v2.5", "transcribe") == "transcribe"


def test_is_predominantly_english_accepts_plain_english():
    assert is_predominantly_english("The patient called about their appointment tomorrow.")


def test_is_predominantly_english_rejects_tamil_script():
    assert not is_predominantly_english("நான் நாளை வருகிறேன்")


def test_validate_english_transcript_returns_error_for_non_english():
    assert validate_english_transcript("நான் நாளை வருகிறேன்") == ENGLISH_TRANSLATION_FAILED


def test_validate_english_transcript_accepts_english():
    assert validate_english_transcript("Please schedule a follow-up call.") is None


def test_normalize_english_transcript_collapses_whitespace():
    assert normalize_english_transcript("Hello   world .") == "Hello world."


def test_normalize_english_transcript_fixes_death_test_homophone():
    raw = "Yesterday my mother's death test was taken and reports have come."
    assert "blood test" in normalize_english_transcript(raw)
    assert "death test" not in normalize_english_transcript(raw).lower()


def test_normalize_english_transcript_fixes_director_specialty_center_mishearing():
    raw = (
        "Good evening sir, Namaste. We are calling from Mohan Director Specialty Center "
        "regarding the mobile number. It is Mohan's Diabetic center, not Director speciality center."
    )
    corrected = normalize_english_transcript(raw)
    assert "Mohan Director Specialty Center" not in corrected
    assert "Director speciality center" not in corrected.lower()
    assert corrected.count("Dr. Mohan's Diabetes Specialities Centre") >= 2
