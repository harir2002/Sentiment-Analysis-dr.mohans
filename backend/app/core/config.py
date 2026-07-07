from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv
import os

from app.core.database_url import normalize_database_url

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"

# Load .env before Settings is first instantiated (database.py calls get_settings at import time)
load_dotenv(_ENV_FILE, override=True)
load_dotenv(_BACKEND_ROOT.parent / ".env", override=True)

PLACEHOLDER_KEYS = {
    "",
    "your_sarvam_api_key_here",
    "your_groq_api_key_here",
    "your_openrouter_api_key_here",
    "changeme",
}

# Sarvam LLM max_tokens caps by subscription tier (sarvam-30b).
SARVAM_LLM_TIER_MAX_TOKENS: dict[str, int] = {
    "starter": 4096,
    "growth": 8192,
    "enterprise": 8192,
}
SARVAM_LLM_DEFAULT_MAX_TOKENS = 4096


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ============ APP CONFIG ============
    app_env: str = "development"
    log_level: str = "INFO"
    sql_echo: bool = False
    access_log: bool = True
    api_max_retries: int = 3
    api_retry_base_seconds: float = 1.0
    admin_username: str = "admin"
    admin_password: str = "changeme"

    # ============ DATABASE CONFIG ============
    # Primary persistence: Supabase Postgres via DATABASE_URL.
    # SQLite remains as optional local fallback when DATABASE_URL is unset/default.
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # Supabase project metadata (optional — used for docs/integrations; DB uses DATABASE_URL)
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # ============ STORAGE CONFIG ============
    # "local" for dev only. Use "s3" with Supabase Storage on cloud (HF Spaces).
    storage_backend: str = "local"

    # Local upload path — ephemeral on Hugging Face; not for long-term persistence
    upload_dir: str = "./data/uploads"

    # Temp processing dir — safe for cloud; cleaned after each job when possible
    temp_dir: str = "./data/tmp"
    
    # S3/Supabase Storage configuration
    s3_endpoint_url: str = ""  # For Supabase Storage, use https://PROJECT_ID.supabase.co/storage/v1/s3
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = "call-analytics"
    s3_region: str = "us-east-1"
    
    # File upload limits
    max_upload_size_mb: int = 25
    url_download_timeout_seconds: float = 60.0
    min_sample_rate_hz: int = 8000
    max_sample_rate_hz: int = 48000
    cleanup_audio_after_job: bool = True

    # ============ JOB PROCESSING CONFIG ============
    job_worker_enabled: bool = True  # Enable durable job worker
    job_worker_poll_interval: float = 5.0  # Check for queued jobs every N seconds
    job_worker_max_concurrent: int = 5  # Concurrent jobs in worker
    job_timeout_seconds: int = 3600  # 1 hour max per job
    job_max_retries: int = 3

    # ============ SARVAM CONFIG ============
    sarvam_api_key: str = ""
    sarvam_stt_url: str = "https://api.sarvam.ai/speech-to-text"
    sarvam_stt_model: str = "saaras:v3"
    sarvam_stt_mode: str = "transcribe"
    sarvam_stt_language: str = "unknown"
    sarvam_rest_max_seconds: float = 30.0
    sarvam_batch_max_wait_seconds: float = 120.0
    sarvam_batch_poll_interval: float = 5.0
    sarvam_batch_absolute_max_seconds: float = 3600.0
    sarvam_batch_blocking_poll_seconds: float = 0.0
    sarvam_chunk_stt_enabled: bool = True
    sarvam_chunk_seconds: float = 25.0
    sarvam_llm_url: str = "https://api.sarvam.ai/v1/chat/completions"
    sarvam_llm_model: str = "sarvam-30b"
    sarvam_llm_plan_tier: str = "starter"
    sarvam_llm_max_tokens: int = 2048  # Output token budget; capped by plan tier and context window
    sarvam_llm_context_window_tokens: int = 8192  # Total context for input + output
    sarvam_llm_content_retries: int = 3
    sarvam_llm_max_transcript_chars: int = 6000
    # Sarvam-30B enables internal reasoning by default, which consumes max_tokens.
    # Use "none" for structured JSON tasks; or "low"/"medium"/"high" with a larger max_tokens.
    sarvam_llm_reasoning_effort: str = "none"

    # ============ GUARDRAILS CONFIG ============
    guardrails_max_transcript_chars: int = 8000  # Reduced to match LLM limit
    guardrails_pii_masking_enabled: bool = True

    # ============ LOGGING & MONITORING ============
    log_format: str = "text"
    expose_error_details: bool = False
    metrics_enabled: bool = True
    slow_request_threshold_ms: float = 5000.0
    request_id_header: str = "X-Request-ID"

    # ============ GROQ CONFIG ============
    groq_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3"
    groq_stt_url: str = "https://api.groq.com/openai/v1/audio/transcriptions"

    @property
    def groq_stt_translate_url(self) -> str:
        if self.groq_stt_url.rstrip("/").endswith("/transcriptions"):
            return self.groq_stt_url.rstrip("/").replace("/transcriptions", "/translations")
        return "https://api.groq.com/openai/v1/audio/translations"

    # ============ OPENROUTER CONFIG ============
    openrouter_api_key: str = ""
    openrouter_llm_model: str = "google/gemma-4-26b-a4b-it"
    openrouter_llm_url: str = "https://openrouter.ai/api/v1/chat/completions"
    openrouter_app_name: str = "Call Analytics Lab"

    # ============ CORS CONFIG ============
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    weights_config_path: str = "config/weights.yaml"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sarvam_llm_token_limit(self) -> int:
        """Effective max_tokens cap for the configured Sarvam plan tier."""
        tier = (self.sarvam_llm_plan_tier or "starter").strip().lower()
        tier_cap = SARVAM_LLM_TIER_MAX_TOKENS.get(tier, SARVAM_LLM_DEFAULT_MAX_TOKENS)
        requested = self.sarvam_llm_max_tokens or SARVAM_LLM_DEFAULT_MAX_TOKENS
        return max(256, min(requested, tier_cap))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def backend_root(self) -> Path:
        return _BACKEND_ROOT

    @property
    def is_production(self) -> bool:
        return (self.app_env or "").strip().lower() in {"production", "prod"}

    @property
    def is_postgres(self) -> bool:
        """Detect if using PostgreSQL."""
        url = normalize_database_url(self.database_url).lower()
        return "postgresql" in url or "postgres" in url

    @property
    def is_cloud_deployment(self) -> bool:
        """True when running on stateless cloud (production + Postgres)."""
        return self.is_production and self.is_postgres

    @property
    def uses_supabase(self) -> bool:
        """True when DATABASE_URL points to Postgres (Supabase)."""
        return self.is_postgres

    @property
    def supabase_project_ref(self) -> str | None:
        url = (self.supabase_url or "").strip()
        if not url:
            return None
        host = url.replace("https://", "").replace("http://", "").split("/")[0]
        return host.split(".")[0] if host else None

    @property
    def uses_remote_storage(self) -> bool:
        return self.storage_backend.strip().lower() == "s3"

    @property
    def show_error_details(self) -> bool:
        if self.is_production:
            return False
        return self.expose_error_details

    def has_sarvam_key(self) -> bool:
        return self.sarvam_api_key.strip() not in PLACEHOLDER_KEYS

    def has_groq_key(self) -> bool:
        return self.groq_api_key.strip() not in PLACEHOLDER_KEYS

    def has_openrouter_key(self) -> bool:
        return self.openrouter_api_key.strip() not in PLACEHOLDER_KEYS

    def require_sarvam_key(self) -> str:
        key = self.sarvam_api_key.strip()
        if key in PLACEHOLDER_KEYS:
            raise ValueError(
                "SARVAM_API_KEY is missing or not configured. "
                "Set a valid key in your .env file."
            )
        return key

    def require_groq_key(self) -> str:
        key = self.groq_api_key.strip()
        if key in PLACEHOLDER_KEYS:
            raise ValueError(
                "GROQ_API_KEY is missing or not configured. "
                "Set a valid key in your .env file (used for Whisper STT)."
            )
        return key

    def require_openrouter_key(self) -> str:
        key = self.openrouter_api_key.strip()
        if key in PLACEHOLDER_KEYS:
            raise ValueError(
                "OPENROUTER_API_KEY is missing or not configured. "
                "Set a valid key in your .env file (used for Gemma 4 26B LLM via OpenRouter)."
            )
        return key


def get_settings() -> Settings:
    # Re-load on each access so .env edits apply without a full server restart
    load_dotenv(_ENV_FILE, override=True)
    load_dotenv(_BACKEND_ROOT.parent / ".env", override=True)
    return Settings()

