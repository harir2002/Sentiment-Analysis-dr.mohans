from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.db.types import JsonType


class AudioFile(Base):
    """Represents an audio file in the batch processing system."""
    __tablename__ = "audio_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), index=True)
    file_path: Mapped[str] = mapped_column(String(512))  # object_key if cloud storage
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64))
    source_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # upload | url
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class ProcessingJob(Base):
    """Represents a processing job for a batch of audio files."""
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft, ready, queued, processing, completed, failed, cancelled
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    queued_files: Mapped[int] = mapped_column(Integer, default=0)
    processing_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_files: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_runtime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_metadata: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # Custom metadata
    __table_args__ = (Index('idx_processing_jobs_status_created', 'status', 'created_at'),)


class ComparisonJob(Base):
    """Represents a single audio file analysis job (4-solution comparison)."""
    __tablename__ = "comparison_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    audio_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)  # Link to AudioFile
    processing_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)  # Link to ProcessingJob (batch)
    file_id: Mapped[str] = mapped_column(String(255), index=True)  # Uploaded file ID
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    audio_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # upload | url
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    call_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stt_language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    results: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # ProviderResult list
    ranking: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # ComparisonRanking
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Canonical final result from winner solution (for dashboard consistency)
    final_solution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    final_sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_valid_call: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_runtime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    export_formats: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # Track which exports were generated
    __table_args__ = (
        Index('idx_comparison_jobs_status_created', 'status', 'created_at'),
        Index('idx_comparison_jobs_processing_job', 'processing_job_id', 'status'),
    )


class JobAuditEvent(Base):
    """Audit trail for job events."""
    __tablename__ = "job_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)  # Batch job reference
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (Index('idx_audit_events_job_created', 'job_id', 'created_at'),)


class ExcelImportBatch(Base):
    """Represents an Excel file import batch."""
    __tablename__ = "excel_import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_name: Mapped[str] = mapped_column(String(255), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    total_links: Mapped[int] = mapped_column(Integer, default=0)
    valid_links: Mapped[int] = mapped_column(Integer, default=0)
    processed_links: Mapped[int] = mapped_column(Integer, default=0)
    failed_links: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending, processing, completed, failed
    processing_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_runtime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (Index('idx_excel_batches_status_created', 'status', 'created_at'),)


class ImportedAudioUrl(Base):
    """Represents an audio URL imported from Excel."""
    __tablename__ = "imported_audio_urls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    import_batch_id: Mapped[str] = mapped_column(String(36), index=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    audio_url: Mapped[str] = mapped_column(String(2048), index=True)
    audio_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    row_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending, queued, processing, completed, failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    call_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    __table_args__ = (
        Index('idx_imported_urls_batch_status', 'import_batch_id', 'status'),
        Index('idx_imported_urls_url', 'audio_url'),
    )


class JobQueue(Base):
    """Durable job queue for background processing (replaces BackgroundTasks)."""
    __tablename__ = "job_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)  # ComparisonJob or processing job reference
    processing_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)  # Batch reference
    job_type: Mapped[str] = mapped_column(String(64))  # "comparison", "batch", "import"
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending, processing, completed, failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # Job parameters
    __table_args__ = (
        Index('idx_job_queue_status', 'status'),
        Index('idx_job_queue_status_created', 'status', 'created_at'),
        Index('idx_job_queue_processing_job', 'processing_job_id', 'status'),
    )

