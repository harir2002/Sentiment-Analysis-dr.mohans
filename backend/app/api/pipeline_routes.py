"""Pipeline control API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_admin
from app.models.schemas import ProcessingJobResponse
from app.services.batch_processor import (
    get_processing_job,
    process_batch_async,
)
from app.services.pipeline_control import (
    mark_batch_ready,
    start_batch_pipeline,
    cancel_batch_pipeline,
    resume_batch_pipeline,
    get_batch_progress,
    mark_batch_complete,
    retry_failed_items,
)
from app.models.db_models import ProcessingJob
from app.core.observability import obs_logger

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/batches/{processing_job_id}/ready")
async def mark_batch_as_ready(
    processing_job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Mark batch as ready to start (after validation/preview)."""
    job = await mark_batch_ready(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return {
        "processing_job_id": job.id,
        "status": job.status,
        "message": "Batch marked as ready. Click Start Pipeline to begin processing.",
    }


@router.post("/batches/{processing_job_id}/start")
async def start_pipeline(
    processing_job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Start batch processing pipeline."""
    job = await get_processing_job(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Mark as started
    job = await start_batch_pipeline(db, processing_job_id)
    
    # Schedule background processing
    background_tasks.add_task(
        process_batch_async,
        db,
        processing_job_id,
        [],  # Will fetch all queued jobs during processing
    )
    
    obs_logger.info(
        'pipeline_start_requested',
        extra={'processing_job_id': processing_job_id},
    )
    
    return {
        "processing_job_id": job.id,
        "status": job.status,
        "total_files": job.total_files,
        "message": "Pipeline started. Processing in progress...",
    }


@router.post("/batches/{processing_job_id}/cancel")
async def cancel_pipeline(
    processing_job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Cancel batch processing pipeline."""
    job = await get_processing_job(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    if job.status not in ["draft", "ready", "queued", "processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel batch with status: {job.status}",
        )
    
    job = await cancel_batch_pipeline(db, processing_job_id)
    
    obs_logger.info(
        'pipeline_cancel_requested',
        extra={
            'processing_job_id': processing_job_id,
            'status': job.status,
        },
    )
    
    return {
        "processing_job_id": job.id,
        "status": job.status,
        "cancelled_at": job.cancelled_at,
        "total_runtime_seconds": job.total_runtime_seconds,
        "message": "Pipeline cancelled. Remaining items have been stopped.",
    }


@router.post("/batches/{processing_job_id}/resume")
async def resume_pipeline(
    processing_job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Resume a cancelled or failed batch."""
    job = await get_processing_job(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    if job.status not in ["cancelled", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume batch with status: {job.status}",
        )
    
    job = await resume_batch_pipeline(db, processing_job_id)
    
    # Schedule background processing
    background_tasks.add_task(
        process_batch_async,
        db,
        processing_job_id,
        [],
    )
    
    obs_logger.info(
        'pipeline_resume_requested',
        extra={'processing_job_id': processing_job_id},
    )
    
    return {
        "processing_job_id": job.id,
        "status": job.status,
        "message": "Pipeline resumed. Processing in progress...",
    }


@router.post("/batches/{processing_job_id}/retry-failed")
async def retry_failed(
    processing_job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Retry failed items in batch."""
    job = await get_processing_job(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Mark batch as processing
    job = await start_batch_pipeline(db, processing_job_id)
    
    # Retry failed items
    retry_count = await retry_failed_items(db, processing_job_id)
    
    if retry_count == 0:
        raise HTTPException(status_code=400, detail="No failed items to retry")
    
    # Schedule background processing
    background_tasks.add_task(
        process_batch_async,
        db,
        processing_job_id,
        [],
    )
    
    obs_logger.info(
        'pipeline_retry_requested',
        extra={
            'processing_job_id': processing_job_id,
            'retry_count': retry_count,
        },
    )
    
    return {
        "processing_job_id": job.id,
        "status": job.status,
        "retried_items": retry_count,
        "message": f"Retrying {retry_count} failed items...",
    }


@router.get("/batches/{processing_job_id}/progress")
async def get_progress(
    processing_job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get detailed batch progress."""
    progress = await get_batch_progress(db, processing_job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Calculate percentage
    total = progress['total_files']
    completed = progress['processed_files'] + progress['failed_files'] + progress['cancelled_files']
    progress_percent = int((completed / max(total, 1)) * 100)
    
    return {
        **progress,
        'progress_percent': progress_percent,
        'remaining_items': progress['queued_files'] + progress['processing_files'],
    }


@router.get("/batches/{processing_job_id}/status")
async def get_status(
    processing_job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get batch status and available actions."""
    job = await get_processing_job(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Determine available actions based on status
    available_actions = {
        "draft": ["ready", "cancel"],
        "ready": ["start", "cancel"],
        "queued": ["start", "cancel"],
        "processing": ["cancel"],
        "completed": ["retry_failed"] if job.failed_files > 0 else [],
        "failed": ["resume", "retry_failed"],
        "cancelled": ["resume", "retry_failed"],
    }
    
    return {
        "processing_job_id": job.id,
        "batch_name": job.batch_name,
        "status": job.status,
        "total_files": job.total_files,
        "queued_files": job.queued_files,
        "processing_files": job.processing_files,
        "processed_files": job.processed_files,
        "failed_files": job.failed_files,
        "cancelled_files": job.cancelled_files,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "cancelled_at": job.cancelled_at,
        "total_runtime_seconds": job.total_runtime_seconds,
        "available_actions": available_actions.get(job.status, []),
        "can_start": job.status in ["draft", "ready", "queued"],
        "can_cancel": job.status in ["draft", "ready", "queued", "processing"],
        "can_resume": job.status in ["cancelled", "failed"],
        "can_retry": job.failed_files > 0,
    }
