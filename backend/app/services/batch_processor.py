"""Batch processing service for handling 50+ audio files."""
import asyncio
import logging
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import ProcessingJob, ComparisonJob, AudioFile, JobAuditEvent
from app.services.jobs import create_job, run_job_background, job_to_response
from app.core.observability import obs_logger

logger = logging.getLogger(__name__)


async def create_processing_job(
    db: AsyncSession,
    batch_name: str | None = None,
    audio_file_ids: list[str] | None = None,
    job_metadata: dict | None = None,
) -> ProcessingJob:
    """Create a new batch processing job."""
    job = ProcessingJob(
        id=str(uuid4()),
        batch_name=batch_name,
        status="pending",
        total_files=len(audio_file_ids) if audio_file_ids else 0,
        job_metadata=job_metadata or {},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    obs_logger.info(
        "batch_job_created",
        extra={
            "processing_job_id": job.id,
            "batch_name": batch_name,
            "total_files": job.total_files,
        },
    )
    return job


async def get_processing_job(
    db: AsyncSession,
    processing_job_id: str,
) -> ProcessingJob | None:
    """Get a processing job by ID."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.id == processing_job_id)
    )
    return result.scalars().first()


async def list_processing_jobs(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProcessingJob], int]:
    """List all processing jobs with pagination."""
    # Get total count
    count_result = await db.execute(select(ProcessingJob))
    total = len(count_result.scalars().all())
    
    # Get paginated results
    result = await db.execute(
        select(ProcessingJob)
        .order_by(ProcessingJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    jobs = result.scalars().all()
    return jobs, total


async def get_processing_job_audio_files(
    db: AsyncSession,
    processing_job_id: str,
) -> list[AudioFile]:
    """Get all audio files for a processing job."""
    result = await db.execute(
        select(AudioFile).where(AudioFile.batch_id == processing_job_id)
    )
    return result.scalars().all()


async def start_batch_processing(
    db: AsyncSession,
    processing_job_id: str,
    audio_file_ids: list[str],
    call_reference_prefix: str | None = None,
) -> dict:
    """Start processing a batch of audio files."""
    processing_job = await get_processing_job(db, processing_job_id)
    if not processing_job:
        raise ValueError(f"Processing job {processing_job_id} not found")
    
    # Update batch job status
    processing_job.status = "processing"
    processing_job.started_at = datetime.utcnow()
    processing_job.total_files = len(audio_file_ids)
    await db.commit()
    
    # Create comparison jobs for each audio file
    comparison_job_ids = []
    for idx, file_id in enumerate(audio_file_ids):
        try:
            call_reference = None
            if call_reference_prefix:
                call_reference = f"{call_reference_prefix}_{idx + 1:04d}"
            
            job = await create_job(
                db,
                file_id,
                call_reference,
            )
            
            # Link to batch
            job.processing_job_id = processing_job_id
            await db.commit()
            
            comparison_job_ids.append(job.id)
            
            # Log audio file linkage
            audio_file_result = await db.execute(
                select(AudioFile).where(AudioFile.file_id == file_id)
            )
            audio_file = audio_file_result.scalars().first()
            if audio_file:
                audio_file.batch_id = processing_job_id
                await db.commit()
                
        except Exception as e:
            logger.warning(f"Failed to create comparison job for {file_id}: {e}")
            processing_job.failed_files += 1
    
    await db.commit()
    
    obs_logger.info(
        "batch_processing_started",
        extra={
            "processing_job_id": processing_job_id,
            "total_files": len(audio_file_ids),
            "comparison_job_ids": comparison_job_ids,
        },
    )
    
    return {
        "processing_job_id": processing_job_id,
        "comparison_job_ids": comparison_job_ids,
        "total": len(audio_file_ids),
    }


async def process_batch_async(
    db: AsyncSession,
    processing_job_id: str,
    comparison_job_ids: list[str],
    background_tasks=None,
) -> None:
    """Process all comparison jobs in a batch (for background execution)."""
    logger.info(f"Starting async batch processing for {processing_job_id}")
    
    # Process jobs concurrently with a semaphore to limit concurrency
    max_concurrent = 5  # Limit concurrent processing
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(job_id: str):
        from app.services.pipeline_control import is_batch_cancelled
        
        async with semaphore:
            # Check if batch was cancelled
            if await is_batch_cancelled(processing_job_id):
                logger.info(f"Batch {processing_job_id} cancelled, skipping job {job_id}")
                return
            
            try:
                await run_job_background(job_id)
                
                # Update batch progress
                await db.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == processing_job_id)
                    .values(processed_files=ProcessingJob.processed_files + 1)
                )
                await db.commit()
                
            except Exception as e:
                logger.error(f"Error processing job {job_id}: {e}")
                await db.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == processing_job_id)
                    .values(failed_files=ProcessingJob.failed_files + 1)
                )
                await db.commit()
    
    # Execute all jobs concurrently
    tasks = [process_with_semaphore(job_id) for job_id in comparison_job_ids]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Update batch job completion
    from app.services.pipeline_control import mark_batch_complete
    
    processing_job = await get_processing_job(db, processing_job_id)
    if processing_job:
        # Only mark complete if not cancelled
        if processing_job.status != "cancelled":
            await mark_batch_complete(db, processing_job_id)
        
        obs_logger.info(
            "batch_processing_completed",
            extra={
                "processing_job_id": processing_job_id,
                "processed_files": processing_job.processed_files,
                "failed_files": processing_job.failed_files,
                "cancelled_files": processing_job.cancelled_files,
                "total_runtime_seconds": processing_job.total_runtime_seconds,
            },
        )


async def register_audio_file(
    db: AsyncSession,
    file_id: str,
    filename: str,
    file_path: str,
    file_size_bytes: int,
    mime_type: str,
    duration_seconds: float | None = None,
    batch_id: str | None = None,
) -> AudioFile:
    """Register an uploaded audio file in the system."""
    audio_file = AudioFile(
        id=str(uuid4()),
        file_id=file_id,
        filename=filename,
        file_path=file_path,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        duration_seconds=duration_seconds,
        batch_id=batch_id,
        uploaded_at=datetime.utcnow(),
    )
    db.add(audio_file)
    await db.commit()
    await db.refresh(audio_file)
    return audio_file


async def get_audio_file(
    db: AsyncSession,
    file_id: str,
) -> AudioFile | None:
    """Get audio file by file_id."""
    result = await db.execute(
        select(AudioFile).where(AudioFile.file_id == file_id)
    )
    return result.scalars().first()


async def list_audio_files(
    db: AsyncSession,
    batch_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AudioFile], int]:
    """List audio files with optional filtering."""
    query = select(AudioFile)
    
    if batch_id:
        query = query.where(AudioFile.batch_id == batch_id)
    
    # Get total
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Get paginated
    result = await db.execute(
        query.order_by(AudioFile.uploaded_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all(), total


async def get_dashboard_metrics(db: AsyncSession) -> dict:
    """Calculate aggregated dashboard metrics."""
    # Get all comparison jobs
    result = await db.execute(select(ComparisonJob))
    jobs = result.scalars().all()
    
    total_audios = len(jobs)
    processed_audios = sum(1 for j in jobs if j.status in ["completed", "failed"])
    failed_audios = sum(1 for j in jobs if j.status == "failed")
    processing_audios = sum(1 for j in jobs if j.status in ["pending", "running"])
    
    # Count sentiments from completed jobs
    positive_count = 0
    neutral_count = 0
    negative_count = 0
    unknown_count = 0
    confidences = []
    best_solution_id = None
    max_score = 0.0
    
    for job in jobs:
        if job.status == "completed" and job.results:
            # Get winner sentiment
            if job.ranking and job.ranking.get("winner"):
                winner = job.ranking["winner"]
                best_solution_id = winner.get("solution_id", best_solution_id)
                max_score = max(max_score, winner.get("overall_score", 0.0))
                
                # Find sentiment from results
                for result in job.results:
                    if result.get("solution_id") == winner.get("solution_id"):
                        sentiment = result.get("analysis", {}).get("sentiment", "unknown")
                        confidence = result.get("analysis", {}).get("confidence", 0.0)
                        
                        if sentiment.lower() == "positive":
                            positive_count += 1
                        elif sentiment.lower() == "neutral":
                            neutral_count += 1
                        elif sentiment.lower() == "negative":
                            negative_count += 1
                        else:
                            unknown_count += 1
                        
                        if confidence > 0:
                            confidences.append(confidence)
                        break
    
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    total_runtime = sum(j.total_runtime_seconds or 0.0 for j in jobs if j.status == "completed")
    
    return {
        "total_audios": total_audios,
        "processed_audios": processed_audios,
        "failed_audios": failed_audios,
        "processing_audios": processing_audios,
        "positive_count": positive_count,
        "neutral_count": neutral_count,
        "negative_count": negative_count,
        "unknown_count": unknown_count,
        "average_confidence": round(average_confidence, 3),
        "best_solution_id": best_solution_id,
        "total_runtime_seconds": round(total_runtime, 2),
    }
