import yaml
from pathlib import Path
from functools import lru_cache
from app.core.config import get_settings


@lru_cache
def load_weights_config() -> dict:
    settings = get_settings()
    config_path = Path(settings.weights_config_path)
    if not config_path.is_absolute():
        config_path = settings.backend_root / config_path

    if not config_path.exists():
        return _default_weights()

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or _default_weights()


def _default_weights() -> dict:
    return {
        "weights": {
            "stt_quality": 0.25,
            "llm_analysis_quality": 0.25,
            "latency": 0.15,
            "cost": 0.10,
            "indian_language_suitability": 0.15,
            "compliance_control": 0.10,
        },
        "cost_per_minute": {
            "sarvam_stt": 0.008,
            "sarvam_llm": 0.003,
            "groq_whisper": 0.005,
            "openrouter_gemma": 0.003,
        },
        "latency_benchmark_seconds": 30,
        "indian_language_scores": {
            "sarvam_stt": 0.95,
            "sarvam_llm": 0.90,
            "groq_whisper": 0.70,
            "openrouter_gemma": 0.65,
        },
        "compliance_scores": {
            "sarvam_stt": 0.90,
            "sarvam_llm": 0.90,
            "groq_whisper": 0.60,
            "openrouter_gemma": 0.55,
        },
    }
