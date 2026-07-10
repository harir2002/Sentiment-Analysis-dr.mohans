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


def test_normalize_english_transcript_fixes_directorate_and_home_tour():
    raw = (
        "We are calling from Mohan Directorate Specialty Center. "
        "I have fixed a home tour for you tomorrow."
    )
    corrected = normalize_english_transcript(raw)
    assert "Directorate Specialty Center" not in corrected
    assert "home tour" not in corrected.lower()
    assert "Dr. Mohan's Diabetes Specialities Centre" in corrected
    assert "home visit" in corrected.lower()


def test_normalize_english_transcript_fixes_adambakkam_area():
    raw = "The patient lives in Adam Baba area near Velachery."
    corrected = normalize_english_transcript(raw)
    assert "Adambakkam area" in corrected
    assert "Adam Baba" not in corrected


def test_normalize_english_transcript_fixes_mumbai_to_munnadi():
    raw = (
        "We are in the Adambakkam area. They have come early. "
        "They will come from Mumbai for the blood test tomorrow."
    )
    corrected = normalize_english_transcript(raw)
    assert "come munnadi" in corrected.lower()
    assert "from mumbai" not in corrected.lower()


def test_normalize_english_transcript_fixes_conference_center_east_tambaram():
    raw = "Please visit the Conference center-East Tambaram for the blood test."
    corrected = normalize_english_transcript(raw)
    assert "East Tambaram" in corrected
    assert "Conference center" not in corrected


def test_normalize_english_transcript_fixes_rignesh_to_vignesh():
    raw = "The caller Rignesh asked about the home visit tomorrow."
    corrected = normalize_english_transcript(raw)
    assert "Vignesh" in corrected
    assert "Rignesh" not in corrected


def test_normalize_english_transcript_fixes_dr_munda_to_mohans():
    raw = "We are calling from Dr. Munda regarding the blood test report."
    corrected = normalize_english_transcript(raw)
    assert "Dr. Mohan's Diabetes Specialities Centre" in corrected
    assert "Munda" not in corrected


def test_normalize_english_transcript_fixes_mohan_eye_to_diabetes():
    raw = "Lakshmi from Mohan Eye Speciality Center. Hello."
    corrected = normalize_english_transcript(raw)
    assert "Dr. Mohan's Diabetes Specialities Centre" in corrected
    assert "Eye" not in corrected
