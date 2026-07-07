"""Pipeline control service for batch processing lifecycle management."""
import logging
import asyncio
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import ProcessingJob, ComparisonJob, ImportedAudioUrl
from app.core.observability import obs_logger

logger = logging.getLogger(__name__)

# Global set to track which batches are cancelled
# In production, use Redis for distributed systems
_cancelled_batches = set()


async def mark_batch_ready(
    db: AsyncSession,
    processing_job_id: str,
) -> ProcessingJob | None:
    """Mark batch as ready to start (after validation)."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    job = result.scalars().first()
    
    if not job:
        return None
    
    if job.status != "draft":
        logger.warning(f"Cannot mark {job.id} as ready - status is {job.status}")
        return job
    
    job.status = "ready"
    await db.commit()
    await db.refresh(job)
    
    obs_logger.info(
        'batch_marked_ready',
        extra={'processing_job_id': processing_job_id},
    )
    return job


async def start_batch_pipeline(
    db: AsyncSession,
    processing_job_id: str,
) -> ProcessingJob | None:
    """Start batch processing pipeline."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    job = result.scalars().first()
    
    if not job:
        return None
    
    if job.status not in ["draft", "ready"]:
        logger.warning(f"Cannot start {job.id} - status is {job.status}")
        return job
    
    # Mark all comparison jobs as queued
    await db.execute(
        update(ComparisonJob)
        .where(ComparisonJob.processing_job_id == processing_job_id)
        .where(ComparisonJob.status == "pending")
        .values(status="queued")
    )
    
    # Mark all imported URLs as queued
    await db.execute(
        update(ImportedAudioUrl)
        .where(ImportedAudioUrl.import_batch_id == processing_job_id)
        .where(ImportedAudioUrl.status == "pending")
        .values(status="queued")
    )
    
    job.status = "processing"
    job.started_at = datetime.utcnow()
    
    # Remove from cancelled set if it was there
    if processing_job_id in _cancelled_batches:
        _cancelled_batches.discard(processing_job_id)
    
    await db.commit()
    await db.refresh(job)
    
    obs_logger.info(
        'batch_pipeline_started',
        extra={
            'processing_job_id': processing_job_id,
            'total_files': job.total_files,
        },
    )
    return job


async def cancel_batch_pipeline(
    db: AsyncSession,
    processing_job_id: str,
) -> ProcessingJob | None:
    """Cancel batch processing pipeline."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    job = result.scalars().first()
    
    if not job:
        return None
    
    # Mark batch as cancelled
    job.status = "cancelled"
    job.cancelled_at = datetime.utcnow()
    
    if job.started_at:
        job.total_runtime_seconds = (
            job.cancelled_at - job.started_at
        ).total_seconds()
    
    # Mark queued comparison jobs as cancelled
    await db.execute(
        update(ComparisonJob)
        .where(ComparisonJob.processing_job_id == processing_job_id)
        .where(ComparisonJob.status.in_(["pending", "queued"]))
        .values(status="cancelled")
    )
    
    # Mark queued imported URLs as cancelled
    await db.execute(
        update(ImportedAudioUrl)
        .where(ImportedAudioUrl.import_batch_id == processing_job_id)
        .where(ImportedAudioUrl.status.in_(["pending", "queued"]))
        .values(status="cancelled")
    )
    
    # Add to cancelled set to signal running workers
    _cancelled_batches.add(processing_job_id)
    
    await db.commit()
    await db.refresh(job)
    
    # Count cancelled items
    result = await db.execute(
        select(ComparisonJob).where(
            (ComparisonJob.processing_job_id == processing_job_id) &
            (ComparisonJob.status == "cancelled")
        )
    )
    cancelled_count = len(result.scalars().all())
    
    obs_logger.info(
        'batch_pipeline_cancelled',
        extra={
            'processing_job_id': processing_job_id,
            'cancelled_items': cancelled_count,
            'runtime_seconds': job.total_runtime_seconds,
        },
    )
    return job


async def is_batch_cancelled(processing_job_id: str) -> bool:
    """Check if batch has been marked for cancellation."""
    return processing_job_id in _cancelled_batches


async def resume_batch_pipeline(
    db: AsyncSession,
    processing_job_id: str,
) -> ProcessingJob | None:
    """Resume a cancelled or failed batch."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    job = result.scalars().first()
    
    if not job:
        return None
    
    if job.status not in ["cancelled", "failed"]:
        logger.warning(f"Cannot resume {job.id} - status is {job.status}")
        return job
    
    # Mark cancelled/failed comparison jobs as queued again
    await db.execute(
        update(ComparisonJob)
        .where(ComparisonJob.processing_job_id == processing_job_id)
        .where(ComparisonJob.status.in_(["cancelled", "failed"]))
        .values(status="queued")
    )
    
    # Mark cancelled/failed imported URLs as queued again
    await db.execute(
        update(ImportedAudioUrl)
        .where(ImportedAudioUrl.import_batch_id == processing_job_id)
        .where(ImportedAudioUrl.status.in_(["cancelled", "failed"]))
        .values(status="queued")
    )
    
    job.status = "processing"
    job.resumed_at = datetime.utcnow()
    
    # Remove from cancelled set
    if processing_job_id in _cancelled_batches:
        _cancelled_batches.discard(processing_job_id)
    
    await db.commit()
    await db.refresh(job)
    
    obs_logger.info(
        'batch_pipeline_resumed',
        extra={'processing_job_id': processing_job_id},
    )
    return job


async def update_batch_progress(
    db: AsyncSession,
    processing_job_id: str,
    queued: int = 0,
    processing: int = 0,
    processed: int = 0,
    failed: int = 0,
    cancelled: int = 0,
) -> None:
    """Update batch progress counters."""
    await db.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == processing_job_id)
        .values(
            queued_files=queued,
            processing_files=processing,
            processed_files=processed,
            failed_files=failed,
            cancelled_files=cancelled,
        )
    )
    await db.commit()


async def get_batch_progress(
    db: AsyncSession,
    processing_job_id: str,
) -> dict | None:
    """Get detailed batch progress."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    job = result.scalars().first()
    
    if not job:
        return None
    
    return {
        'processing_job_id': job.id,
        'batch_name': job.batch_name,
        'status': job.status,
        'total_files': job.total_files,
        'queued_files': job.queued_files,
        'processing_files': job.processing_files,
        'processed_files': job.processed_files,
        'failed_files': job.failed_files,
        'cancelled_files': job.cancelled_files,
        'created_at': job.created_at,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'cancelled_at': job.cancelled_at,
        'total_runtime_seconds': job.total_runtime_seconds,
        'error': job.error,
    }


async def mark_batch_complete(
    db: AsyncSession,
    processing_job_id: str,
) -> ProcessingJob | None:
    """Mark batch as complete."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    job = result.scalars().first()
    
    if not job:
        return None
    
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    
    if job.started_at:
        job.total_runtime_seconds = (
            job.completed_at - job.started_at
        ).total_seconds()
    
    # Remove from cancelled set
    if processing_job_id in _cancelled_batches:
        _cancelled_batches.discard(processing_job_id)
    
    await db.commit()
    await db.refresh(job)
    
    obs_logger.info(
        'batch_pipeline_completed',
        extra={
            'processing_job_id': processing_job_id,
            'total_runtime_seconds': job.total_runtime_seconds,
            'processed': job.processed_files,
            'failed': job.failed_files,
            'cancelled': job.cancelled_files,
        },
    )
    return job


async def retry_failed_items(
    db: AsyncSession,
    processing_job_id: str,
) -> int:
    """Retry failed items in a batch."""
    # Mark failed comparison jobs as queued
    result = await db.execute(
        select(ComparisonJob).where(
            (ComparisonJob.processing_job_id == processing_job_id) &
            (ComparisonJob.status == "failed")
        )
    )
    failed_jobs = result.scalars().all()
    
    for job in failed_jobs:
        job.status = "queued"
        job.retry_count += 1
    
    # Mark failed imported URLs as queued
    result = await db.execute(
        select(ImportedAudioUrl).where(
            (ImportedAudioUrl.import_batch_id == processing_job_id) &
            (ImportedAudioUrl.status == "failed")
        )
    )
    failed_urls = result.scalars().all()
    
    for url_record in failed_urls:
        url_record.status = "queued"
    
    await db.commit()
    
    obs_logger.info(
        'retry_failed_items',
        extra={
            'processing_job_id': processing_job_id,
            'failed_jobs': len(failed_jobs),
            'failed_urls': len(failed_urls),
        },
    )
    
    return len(failed_jobs) + len(failed_urls)
