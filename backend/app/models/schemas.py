from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJobStatus(str, Enum):
    DRAFT = "draft"  # Created, not started
    READY = "ready"  # Validated, ready to start
    QUEUED = "queued"  # Queued, waiting to start
    PROCESSING = "processing"  # Currently processing
    COMPLETED = "completed"  # All items processed
    FAILED = "failed"  # Batch-level failure
    CANCELLED = "cancelled"  # User cancelled


class ProviderStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    RATE_LIMITED = "rate_limited"
    TIMED_OUT = "timed_out"


class SolutionOption(str, Enum):
    SARVAM_SARVAM = "sarvam_stt_sarvam_llm"
    SARVAM_GROQ = "sarvam_stt_groq_gemma"
    GROQ_SARVAM = "groq_whisper_sarvam_llm"
    GROQ_GROQ = "groq_whisper_groq_gemma"


SOLUTION_LABELS = {
    SolutionOption.SARVAM_SARVAM: "Call Analysis",
    SolutionOption.SARVAM_GROQ: "Sarvam STT + Groq Gemma 4 26B A4B",
    SolutionOption.GROQ_SARVAM: "Groq Whisper + Sarvam LLM",
    SolutionOption.GROQ_GROQ: "Groq Whisper + Groq Gemma 4 26B A4B",
}


class AnalysisResult(BaseModel):
    sentiment: str = ""
    key_issues: list[str] = Field(default_factory=list)
    summary: str = ""
    action_items: list[str] = Field(default_factory=list)
    resolution_status: str = ""
    confidence: float = 0.0
    notes: str = ""
    recommended_action: str = ""
    action_priority: str = ""
    assigned_team: str = ""
    escalation_status: str = ""


class ProviderResult(BaseModel):
    solution_id: str
    label: str
    stt_provider: str
    llm_provider: str
    stt_model: str = ""
    llm_model: str = ""
    status: str = "pending"
    transcript: str = ""
    analysis: AnalysisResult = Field(default_factory=AnalysisResult)
    stt_runtime_seconds: float = 0.0
    llm_runtime_seconds: float = 0.0
    total_runtime_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    error: str | None = None
    parsing_error: str | None = None
    raw_llm_response: str | None = None
    raw_stt_response: str | None = None
    retry_count: int = 0
    sarvam_batch_job_id: str | None = None
    status_message: str | None = None
    stt_language_code: str | None = None
    language_mismatch_warning: str | None = None
    detected_script: str | None = None
    whisper_detected_language: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    overall_score: float = 0.0


class ScoreBreakdown(BaseModel):
    stt_quality: float = 0.0
    llm_analysis_quality: float = 0.0
    latency: float = 0.0
    cost: float = 0.0
    indian_language_suitability: float = 0.0
    compliance_control: float = 0.0
    overall: float = 0.0


class RankingEntry(BaseModel):
    rank: int
    solution_id: str
    label: str
    overall_score: float
    score_breakdown: ScoreBreakdown
    recommendation_reason: str = ""


class ComparisonRanking(BaseModel):
    winner: RankingEntry | None = None
    rankings: list[RankingEntry] = Field(default_factory=list)
    recommendation_summary: str = ""


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    path: str
    metadata: dict = Field(default_factory=dict)


class UploadItemResult(BaseModel):
    file_id: str | None = None
    filename: str
    path: str | None = None
    metadata: dict = Field(default_factory=dict)
    success: bool
    error: str | None = None


class BatchUploadResponse(BaseModel):
    uploaded: list[UploadItemResult] = Field(default_factory=list)
    failed: list[UploadItemResult] = Field(default_factory=list)
    total: int = 0
    success_count: int = 0
    failed_count: int = 0


class UploadUrlRequest(BaseModel):
    audio_url: str = Field(..., min_length=8, description="Direct http(s) link to an audio file")


class RunComparisonRequest(BaseModel):
    file_id: str
    call_reference: str | None = None
    source_type: str | None = None  # upload | url
    source_url: str | None = None
    original_filename: str | None = None
    stored_path: str | None = None  # local path or S3 object key from upload response


class RetryProvidersRequest(BaseModel):
    solution_ids: list[str] | None = None


class ErrorResponse(BaseModel):
    detail: str
    provider: str | None = None
    status_code: int | None = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime | None = None
    completed_at: datetime | None = None
    total_runtime_seconds: float | None = None
    call_reference: str | None = None
    stt_language_code: str | None = None
    audio_filename: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    ingested_at: datetime | None = None
    results: list[ProviderResult] = Field(default_factory=list)
    ranking: ComparisonRanking | None = None
    error: str | None = None
    pending_providers: int = 0
    results_ready: bool = False
    aggregate_status: str = "running"
    provider_groups: dict[str, list[ProviderResult]] = Field(default_factory=dict)
    sarvam_batch_max_wait_seconds: int = 120
    # Canonical final result (one per recording) - source of truth for dashboard
    final_solution_id: str | None = None
    final_sentiment: str | None = None
    final_confidence: float | None = None
    final_overall_score: float | None = None
    final_recommendation: str | None = None
    sentiment_label: str | None = None  # positive | neutral | negative | invalid
    is_valid_call: bool | None = None
    invalid_reason: str | None = None


class CallListItem(BaseModel):
    job_id: str
    status: JobStatus
    audio_filename: str | None = None
    call_reference: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    aggregate_status: str = "running"
    results_ready: bool = False
    total_runtime_seconds: float | None = None
    # Canonical final result (from winner solution) - source of truth for dashboard
    final_solution_id: str | None = None
    final_sentiment: str | None = None
    final_confidence: float | None = None


class CallsListResponse(BaseModel):
    calls: list[JobResponse] = Field(default_factory=list)  # Return full JobResponse for dashboard canonical fields
    total: int = 0


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"
    providers: dict[str, bool] = Field(default_factory=dict)
    models: dict[str, str] = Field(default_factory=dict)


# ============ BATCH PROCESSING SCHEMAS ============

class AudioFileResponse(BaseModel):
    """Response for an audio file in the system."""
    id: str
    file_id: str
    filename: str
    file_size_bytes: int
    duration_seconds: float | None = None
    mime_type: str
    uploaded_at: datetime
    batch_id: str | None = None


class DashboardMetrics(BaseModel):
    """Aggregated metrics for the dashboard."""
    total_audios: int = 0
    processed_audios: int = 0
    failed_audios: int = 0
    processing_audios: int = 0
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    unknown_count: int = 0
    average_confidence: float = 0.0
    best_solution_id: str | None = None
    total_runtime_seconds: float | None = None


class ProcessingJobResponse(BaseModel):
    """Response for a processing/batch job."""
    id: str
    batch_name: str | None = None
    status: ProcessingJobStatus
    total_files: int
    processed_files: int
    failed_files: int
    progress_percent: int  # Calculated: (processed_files + failed_files) / total_files * 100
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_runtime_seconds: float | None = None
    error: str | None = None


class BatchProcessingRequest(BaseModel):
    """Request to start batch processing."""
    batch_name: str | None = None
    audio_file_ids: list[str]  # List of uploaded file IDs to process
    call_reference_prefix: str | None = None  # Optional prefix for call references


class DashboardComparisonItem(BaseModel):
    """Single audio result item for dashboard display."""
    job_id: str
    audio_filename: str
    call_reference: str | None = None
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    sentiment: str | None = None  # Winner sentiment
    confidence: float | None = None  # Winner confidence
    winner_solution: str | None = None
    overall_score: float | None = None  # Winner score
    total_runtime_seconds: float | None = None


class DashboardResponse(BaseModel):
    """Complete dashboard data."""
    metrics: DashboardMetrics
    recent_jobs: list[DashboardComparisonItem] = Field(default_factory=list)
    processing_jobs: list[ProcessingJobResponse] = Field(default_factory=list)
    total_jobs: int = 0


class BatchStartResponse(BaseModel):
    """Response when starting a new batch."""
    processing_job_id: str
    batch_name: str | None = None
    total_files: int
    message: str


# ============ EXCEL IMPORT SCHEMAS ============

class AudioLinkRecord(BaseModel):
    """Single audio link record from Excel."""
    row_number: int
    audio_url: str
    audio_name: str | None = None
    status: str = "pending"  # pending, valid, invalid
    error: str | None = None


class ExcelImportPreview(BaseModel):
    """Preview of parsed Excel file."""
    total_rows: int
    valid_links: int
    invalid_links: int
    duplicate_links: int
    detected_column: str
    preview_records: list[AudioLinkRecord] = Field(default_factory=list)  # First 5 rows
    errors: list[str] = Field(default_factory=list)


class ExcelImportRequest(BaseModel):
    """Request to start Excel import batch."""
    batch_name: str
    audio_link_records: list[AudioLinkRecord]  # All valid records from Excel
    call_reference_prefix: str | None = None


class ExcelImportBatchResponse(BaseModel):
    """Response for Excel import batch creation."""
    import_batch_id: str
    processing_job_id: str
    batch_name: str
    total_links: int
    valid_links: int
    message: str


class ImportedAudioRecord(BaseModel):
    """Record for an imported audio URL."""
    id: str
    audio_url: str
    audio_name: str | None = None
    import_batch_id: str
    processing_job_id: str
    status: str  # pending, processing, completed, failed
    error: str | None = None
    created_at: datetime
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None


class ExcelImportBatchDetails(BaseModel):
    """Details of an Excel import batch."""
    import_batch_id: str
    batch_name: str
    total_links: int
    processed_links: int
    failed_links: int
    pending_links: int
    created_at: datetime
    completed_at: datetime | None = None
    records: list[ImportedAudioRecord] = Field(default_factory=list)
