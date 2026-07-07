"""Batch processing API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_admin
from app.models.schemas import (
    BatchProcessingRequest,
    ProcessingJobResponse,
    DashboardResponse,
    DashboardMetrics,
    DashboardComparisonItem,
    BatchStartResponse,
    AudioFileResponse,
)
from app.services.batch_processor import (
    create_processing_job,
    get_processing_job,
    list_processing_jobs,
    get_processing_job_audio_files,
    start_batch_processing,
    process_batch_async,
    register_audio_file,
    get_audio_file,
    list_audio_files,
    get_dashboard_metrics,
)
from app.services.jobs import get_job, list_jobs, job_to_response
from app.core.observability import obs_logger

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.post("/jobs", response_model=BatchStartResponse)
async def create_batch_job(
    request: BatchProcessingRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Create a new batch processing job in draft status (not auto-started)."""
    if not request.audio_file_ids:
        raise HTTPException(status_code=400, detail="At least one audio file ID is required")
    
    # Create processing job in draft status (do NOT auto-start)
    processing_job = await create_processing_job(
        db,
        batch_name=request.batch_name,
        audio_file_ids=request.audio_file_ids,
        job_metadata={
            "call_reference_prefix": request.call_reference_prefix,
        },
    )
    
    obs_logger.info(
        'batch_job_created_draft',
        extra={
            'processing_job_id': processing_job.id,
            'batch_name': request.batch_name,
            'total_files': len(request.audio_file_ids),
        },
    )
    
    return BatchStartResponse(
        processing_job_id=processing_job.id,
        batch_name=request.batch_name,
        total_files=len(request.audio_file_ids),
        message=f"Batch created with {len(request.audio_file_ids)} files. Use Start Pipeline to begin processing.",
    )


@router.get("/jobs/{processing_job_id}", response_model=ProcessingJobResponse)
async def get_batch_job(
    processing_job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get batch job details."""
    job = await get_processing_job(db, processing_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    processed = job.processed_files + job.failed_files
    progress_percent = int((processed / max(job.total_files, 1)) * 100)
    
    return ProcessingJobResponse(
        id=job.id,
        batch_name=job.batch_name,
        status=job.status,
        total_files=job.total_files,
        processed_files=job.processed_files,
        failed_files=job.failed_files,
        progress_percent=progress_percent,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        total_runtime_seconds=job.total_runtime_seconds,
        error=job.error,
    )


@router.get("/jobs", response_model=list[ProcessingJobResponse])
async def list_batch_jobs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """List all batch processing jobs."""
    jobs, _ = await list_processing_jobs(db, limit=limit, offset=offset)
    
    result = []
    for job in jobs:
        processed = job.processed_files + job.failed_files
        progress_percent = int((processed / max(job.total_files, 1)) * 100)
        result.append(
            ProcessingJobResponse(
                id=job.id,
                batch_name=job.batch_name,
                status=job.status,
                total_files=job.total_files,
                processed_files=job.processed_files,
                failed_files=job.failed_files,
                progress_percent=progress_percent,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                total_runtime_seconds=job.total_runtime_seconds,
                error=job.error,
            )
        )
    
    return result


@router.get("/jobs/{processing_job_id}/audio-files", response_model=list[AudioFileResponse])
async def get_batch_audio_files(
    processing_job_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get audio files in a batch job."""
    files, _ = await list_audio_files(db, batch_id=processing_job_id, limit=limit, offset=offset)
    
    return [
        AudioFileResponse(
            id=f.id,
            file_id=f.file_id,
            filename=f.filename,
            file_size_bytes=f.file_size_bytes,
            duration_seconds=f.duration_seconds,
            mime_type=f.mime_type,
            uploaded_at=f.uploaded_at,
            batch_id=f.batch_id,
        )
        for f in files
    ]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get complete dashboard with metrics and recent jobs."""
    # Get metrics
    metrics_data = await get_dashboard_metrics(db)
    metrics = DashboardMetrics(**metrics_data)
    
    # Get recent comparison jobs (limit to last 50)
    jobs = await list_jobs(db, limit=50)
    
    recent_jobs = []
    for job in jobs:
        response = job_to_response(job)
        
        # Extract winner info
        sentiment = None
        confidence = None
        winner_solution = None
        overall_score = None
        
        if response.ranking and response.ranking.winner:
            winner = response.ranking.winner
            winner_solution = winner.label
            overall_score = winner.overall_score
            
            # Find matching result to get sentiment
            for result in response.results:
                if result.solution_id == winner.solution_id:
                    sentiment = result.analysis.sentiment
                    confidence = result.analysis.confidence
                    break
        
        recent_jobs.append(
            DashboardComparisonItem(
                job_id=response.job_id,
                audio_filename=response.audio_filename or "Unknown",
                call_reference=response.call_reference,
                status=response.status,
                created_at=response.created_at or __import__("datetime").datetime.utcnow(),
                completed_at=response.completed_at,
                sentiment=sentiment,
                confidence=confidence,
                winner_solution=winner_solution,
                overall_score=overall_score,
                total_runtime_seconds=response.total_runtime_seconds,
            )
        )
    
    # Get batch jobs
    processing_jobs, _ = await list_processing_jobs(db, limit=50)
    
    batch_jobs = []
    for job in processing_jobs:
        processed = job.processed_files + job.failed_files
        progress_percent = int((processed / max(job.total_files, 1)) * 100)
        batch_jobs.append(
            ProcessingJobResponse(
                id=job.id,
                batch_name=job.batch_name,
                status=job.status,
                total_files=job.total_files,
                processed_files=job.processed_files,
                failed_files=job.failed_files,
                progress_percent=progress_percent,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                total_runtime_seconds=job.total_runtime_seconds,
                error=job.error,
            )
        )
    
    return DashboardResponse(
        metrics=metrics,
        recent_jobs=recent_jobs,
        processing_jobs=batch_jobs,
        total_jobs=len(jobs),
    )


@router.post("/audio-files/{file_id}/register", response_model=AudioFileResponse)
async def register_audio(
    file_id: str,
    filename: str = Query(...),
    file_size_bytes: int = Query(...),
    mime_type: str = Query(...),
    duration_seconds: float | None = Query(None),
    batch_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Register an uploaded audio file."""
    from app.services.storage import resolve_audio_path
    
    audio_path = resolve_audio_path(file_id)
    if not audio_path:
        raise HTTPException(status_code=404, detail="Audio file not found in uploads")
    
    audio_file = await register_audio_file(
        db,
        file_id=file_id,
        filename=filename,
        file_path=audio_path,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        duration_seconds=duration_seconds,
        batch_id=batch_id,
    )
    
    return AudioFileResponse(
        id=audio_file.id,
        file_id=audio_file.file_id,
        filename=audio_file.filename,
        file_size_bytes=audio_file.file_size_bytes,
        duration_seconds=audio_file.duration_seconds,
        mime_type=audio_file.mime_type,
        uploaded_at=audio_file.uploaded_at,
        batch_id=audio_file.batch_id,
    )
