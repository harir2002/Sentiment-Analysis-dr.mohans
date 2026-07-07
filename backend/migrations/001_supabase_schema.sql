-- Supabase Postgres schema for Call Analytics (free-tier deployment)
-- Run once in Supabase SQL Editor or via psql against your project database.
-- Safe to re-run: uses IF NOT EXISTS where supported.

CREATE TABLE IF NOT EXISTS audio_files (
    id VARCHAR(36) PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL UNIQUE,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    duration_seconds DOUBLE PRECISION,
    mime_type VARCHAR(64) NOT NULL,
    source_type VARCHAR(16),
    source_url TEXT,
    uploaded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    batch_id VARCHAR(36)
);
CREATE INDEX IF NOT EXISTS ix_audio_files_file_id ON audio_files (file_id);
CREATE INDEX IF NOT EXISTS ix_audio_files_filename ON audio_files (filename);
CREATE INDEX IF NOT EXISTS ix_audio_files_uploaded_at ON audio_files (uploaded_at);
CREATE INDEX IF NOT EXISTS ix_audio_files_batch_id ON audio_files (batch_id);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id VARCHAR(36) PRIMARY KEY,
    batch_name VARCHAR(255),
    status VARCHAR(20) DEFAULT 'draft' NOT NULL,
    total_files INTEGER DEFAULT 0 NOT NULL,
    queued_files INTEGER DEFAULT 0 NOT NULL,
    processing_files INTEGER DEFAULT 0 NOT NULL,
    processed_files INTEGER DEFAULT 0 NOT NULL,
    failed_files INTEGER DEFAULT 0 NOT NULL,
    cancelled_files INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    cancelled_at TIMESTAMP WITHOUT TIME ZONE,
    total_runtime_seconds DOUBLE PRECISION,
    error TEXT,
    job_metadata JSONB
);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_status ON processing_jobs (status);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_created_at ON processing_jobs (created_at);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status_created ON processing_jobs (status, created_at);

CREATE TABLE IF NOT EXISTS comparison_jobs (
    id VARCHAR(36) PRIMARY KEY,
    audio_file_id VARCHAR(36),
    processing_job_id VARCHAR(36),
    file_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    audio_filename VARCHAR(255),
    audio_path VARCHAR(512),
    source_type VARCHAR(16),
    source_url TEXT,
    ingested_at TIMESTAMP WITHOUT TIME ZONE,
    call_reference VARCHAR(255),
    stt_language_code VARCHAR(16),
    results JSONB,
    ranking JSONB,
    error TEXT,
    final_solution_id VARCHAR(64),
    final_sentiment VARCHAR(32),
    final_confidence DOUBLE PRECISION,
    final_recommendation TEXT,
    sentiment_label VARCHAR(32),
    is_valid_call BOOLEAN,
    invalid_reason TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    total_runtime_seconds DOUBLE PRECISION,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    export_formats JSONB
);
CREATE INDEX IF NOT EXISTS ix_comparison_jobs_file_id ON comparison_jobs (file_id);
CREATE INDEX IF NOT EXISTS ix_comparison_jobs_status ON comparison_jobs (status);
CREATE INDEX IF NOT EXISTS ix_comparison_jobs_created_at ON comparison_jobs (created_at);
CREATE INDEX IF NOT EXISTS ix_comparison_jobs_audio_file_id ON comparison_jobs (audio_file_id);
CREATE INDEX IF NOT EXISTS ix_comparison_jobs_processing_job_id ON comparison_jobs (processing_job_id);
CREATE INDEX IF NOT EXISTS idx_comparison_jobs_status_created ON comparison_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS idx_comparison_jobs_processing_job ON comparison_jobs (processing_job_id, status);
CREATE INDEX IF NOT EXISTS idx_comparison_jobs_sentiment_label ON comparison_jobs (sentiment_label);
CREATE INDEX IF NOT EXISTS idx_comparison_jobs_created_desc ON comparison_jobs (created_at DESC);

CREATE TABLE IF NOT EXISTS job_audit_events (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    processing_job_id VARCHAR(36),
    event_type VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT,
    level VARCHAR(16) DEFAULT 'info' NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_job_audit_events_job_id ON job_audit_events (job_id);
CREATE INDEX IF NOT EXISTS ix_job_audit_events_processing_job_id ON job_audit_events (processing_job_id);
CREATE INDEX IF NOT EXISTS ix_job_audit_events_created_at ON job_audit_events (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_job_created ON job_audit_events (job_id, created_at);

CREATE TABLE IF NOT EXISTS excel_import_batches (
    id VARCHAR(36) PRIMARY KEY,
    batch_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    total_links INTEGER DEFAULT 0 NOT NULL,
    valid_links INTEGER DEFAULT 0 NOT NULL,
    processed_links INTEGER DEFAULT 0 NOT NULL,
    failed_links INTEGER DEFAULT 0 NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    processing_job_id VARCHAR(36),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    total_runtime_seconds DOUBLE PRECISION,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_excel_import_batches_batch_name ON excel_import_batches (batch_name);
CREATE INDEX IF NOT EXISTS ix_excel_import_batches_status ON excel_import_batches (status);
CREATE INDEX IF NOT EXISTS ix_excel_import_batches_created_at ON excel_import_batches (created_at);
CREATE INDEX IF NOT EXISTS idx_excel_batches_status_created ON excel_import_batches (status, created_at);

CREATE TABLE IF NOT EXISTS imported_audio_urls (
    id VARCHAR(36) PRIMARY KEY,
    import_batch_id VARCHAR(36) NOT NULL,
    processing_job_id VARCHAR(36),
    audio_url VARCHAR(2048) NOT NULL,
    audio_name VARCHAR(512),
    row_number INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    error TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    processing_started_at TIMESTAMP WITHOUT TIME ZONE,
    processing_completed_at TIMESTAMP WITHOUT TIME ZONE,
    call_reference VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS ix_imported_audio_urls_import_batch_id ON imported_audio_urls (import_batch_id);
CREATE INDEX IF NOT EXISTS ix_imported_audio_urls_audio_url ON imported_audio_urls (audio_url);
CREATE INDEX IF NOT EXISTS ix_imported_audio_urls_status ON imported_audio_urls (status);
CREATE INDEX IF NOT EXISTS idx_imported_urls_batch_status ON imported_audio_urls (import_batch_id, status);

CREATE TABLE IF NOT EXISTS job_queue (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    processing_job_id VARCHAR(36),
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    max_retries INTEGER DEFAULT 3 NOT NULL,
    error TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    payload JSONB
);
CREATE INDEX IF NOT EXISTS ix_job_queue_job_id ON job_queue (job_id);
CREATE INDEX IF NOT EXISTS ix_job_queue_processing_job_id ON job_queue (processing_job_id);
CREATE INDEX IF NOT EXISTS ix_job_queue_status ON job_queue (status);
CREATE INDEX IF NOT EXISTS idx_job_queue_status_created ON job_queue (status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_queue_processing_job ON job_queue (processing_job_id, status);
