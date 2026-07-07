import uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.observability import metrics
from app.services.audit import record_audit_event
from app.models.db_models import AudioFile, ComparisonJob, JobAuditEvent, JobQueue
from app.models.schemas import JobStatus, JobResponse, ProviderResult, ComparisonRanking
from app.services.comparison import run_all_comparisons, retry_solutions, build_provider_groups
from app.services.storage import resolve_audio_path, delete_audio_file, resolve_audio_path_async
from app.services.audio_materialize import materialize_audio_for_analysis, cleanup_temporary_audio
from app.services.audio_validation import validate_audio_file
from app.services.sarvam_batch_worker import schedule_sarvam_batch_followups
from app.providers.sarvam_stt_coordinator import clear_shared_state
from app.services.stt_language import consensus_detected_language
from app.services.stt_english import sanitize_provider_result_for_client
from app.services.call_validity import assess_recording_validity


def _all_providers_completed(results: list[ProviderResult]) -> bool:
    return bool(results) and all(r.status == "completed" for r in results)


def _pending_provider_count(results: list[ProviderResult]) -> int:
    return sum(
        1
        for r in results
        if r.status in {"queued", "running", "timed_out", "pending"}
    )


def _aggregate_status(results: list[ProviderResult], job_status: str) -> str:
    pending = _pending_provider_count(results)
    if pending > 0 or job_status == JobStatus.RUNNING.value:
        return "running"
    if job_status == JobStatus.FAILED.value and not results:
        return "failed"
    completed = sum(1 for r in results if r.status == "completed")
    if results and completed == len(results):
        return "completed"
    if completed > 0:
        return "partial"
    return "failed"


def _results_ready(results: list[ProviderResult], job_status: str) -> bool:
    if job_status == JobStatus.FAILED.value and not results:
        return False
    return bool(results) and _pending_provider_count(results) == 0


def derive_canonical_result(
    results: list[ProviderResult],
    ranking: ComparisonRanking | None,
) -> ProviderResult | None:
    """Pick the single canonical result for a recording.

    Canonical rule: the ranking winner when it has a completed analysis,
    otherwise the completed result with the highest overall_score. Exactly one
    result per recording feeds dashboard KPIs; the other solutions stay
    comparison-only data.
    """
    completed = [r for r in results if r.status == "completed" and r.analysis]
    if not completed:
        return None

    if ranking and ranking.winner:
        winner = next(
            (r for r in completed if r.solution_id == ranking.winner.solution_id),
            None,
        )
        if winner:
            return winner

    return max(completed, key=lambda r: r.overall_score or 0.0)


async def create_job(
    db: AsyncSession,
    file_id: str,
    call_reference: str | None,
    original_filename: str | None = None,
    *,
    source_type: str | None = None,
    source_url: str | None = None,
    stored_path: str | None = None,
) -> ComparisonJob:
    audio_path = stored_path or await resolve_audio_path_async(file_id, stored_path)
    if not audio_path and not source_url:
        raise ValueError("Uploaded audio file not found")

    if audio_path and Path(audio_path).is_file():
        validate_audio_file(audio_path)

    from datetime import datetime, timezone

    job = ComparisonJob(
        id=str(uuid.uuid4()),
        status=JobStatus.PENDING.value,
        file_id=file_id,
        audio_filename=original_filename or file_id,
        audio_path=audio_path,
        call_reference=call_reference,
        stt_language_code=None,
        source_type=source_type or "upload",
        source_url=source_url,
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    metrics.record_job_started()
    await record_audit_event(
        db,
        job_id=job.id,
        event_type="job_created",
        message="Comparison job created",
        metadata={
            "filename": original_filename or file_id,
            "status": job.status,
        },
    )
    return job


async def get_job(db: AsyncSession, job_id: str) -> ComparisonJob | None:
    result = await db.execute(select(ComparisonJob).where(ComparisonJob.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(db: AsyncSession, *, limit: int = 100) -> list[ComparisonJob]:
    result = await db.execute(
        select(ComparisonJob).order_by(ComparisonJob.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _save_job_results(
    db: AsyncSession,
    job: ComparisonJob,
    results: list[ProviderResult],
    ranking: dict,
    audio_path: str | None,
) -> None:
    settings = get_settings()
    job.results = [r.model_dump() for r in results]
    job.ranking = ranking
    job.error = None
    detected = consensus_detected_language([r.stt_language_code for r in results])
    if detected:
        job.stt_language_code = detected
    job.completed_at = datetime.utcnow()
    if results:
        job.total_runtime_seconds = max(r.total_runtime_seconds for r in results)

    pending = _pending_provider_count(results)
    job.status = JobStatus.RUNNING.value if pending > 0 else JobStatus.COMPLETED.value

    # Persist the canonical result so DB-level aggregations count each
    # recording exactly once (never once per solution).
    canonical = derive_canonical_result(
        results,
        ComparisonRanking(**ranking) if ranking else None,
    )
    if canonical:
        job.final_solution_id = canonical.solution_id
        job.final_sentiment = canonical.analysis.sentiment or None
        job.final_confidence = canonical.analysis.confidence
        job.final_recommendation = canonical.analysis.recommended_action or None
        validity = assess_recording_validity(
            aggregate_status=_aggregate_status(results, job.status),
            job_error=job.error,
            canonical=canonical,
            results_ready=True,
        )
        job.sentiment_label = validity.sentiment_label
        job.is_valid_call = validity.is_valid_call
        job.invalid_reason = validity.invalid_reason

    await db.commit()

    completed_count = sum(1 for r in results if r.status == "completed")
    failed_count = sum(1 for r in results if r.status not in {"completed", "queued", "running", "timed_out", "pending"})
    await record_audit_event(
        db,
        job_id=job.id,
        event_type="job_results_saved",
        message="Provider results persisted",
        metadata={
            "status": job.status,
            "pending_providers": pending,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "runtime_seconds": job.total_runtime_seconds,
        },
    )

    if pending == 0:
        success = completed_count > 0 and failed_count == 0
        metrics.record_job_finished(success=success, runtime_seconds=job.total_runtime_seconds)
        await record_audit_event(
            db,
            job_id=job.id,
            event_type="job_finished" if success else "job_partial",
            message="Job processing finished",
            level="info" if success else "warning",
            metadata={
                "status": job.status,
                "completed_count": completed_count,
                "failed_count": failed_count,
            },
        )

    if pending > 0:
        await schedule_sarvam_batch_followups(job.id, audio_path or job.audio_path or "", results)
    elif settings.cleanup_audio_after_job and audio_path and _all_providers_completed(results):
        delete_audio_file(audio_path)
        refreshed = await get_job(db, job.id)
        if refreshed:
            refreshed.audio_path = None
            await db.commit()

    clear_shared_state(audio_path or "")


async def run_job_background(job_id: str):
    from app.core.database import AsyncSessionLocal

    audio_path = None
    temp_audio = False

    async with AsyncSessionLocal() as db:
        job = await get_job(db, job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING.value
        await db.commit()
        await record_audit_event(
            db,
            job_id=job_id,
            event_type="job_started",
            message="Background analysis started",
        )

        try:
            local_path, temp_audio = await materialize_audio_for_analysis(
                audio_path=job.audio_path,
                file_id=job.file_id,
                source_url=job.source_url,
            )
            audio_path = local_path
            validate_audio_file(audio_path)
            results, ranking = await run_all_comparisons(audio_path)
            await _save_job_results(db, job, results, ranking, job.audio_path)

        except Exception as e:
            job.status = JobStatus.FAILED.value
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            await db.commit()
            metrics.record_job_finished(success=False)
            await record_audit_event(
                db,
                job_id=job_id,
                event_type="job_failed",
                message="Job failed during processing",
                level="error",
                metadata={"error_type": type(e).__name__},
            )
        finally:
            if temp_audio:
                cleanup_temporary_audio(audio_path)


async def retry_job_background(job_id: str, solution_ids: list[str] | None = None):
    from app.core.database import AsyncSessionLocal

    temp_audio = False
    local_path = None

    async with AsyncSessionLocal() as db:
        job = await get_job(db, job_id)
        if not job:
            return

        if not job.audio_path and not job.source_url:
            job.error = "Audio file no longer available — re-upload or provide a source URL"
            await db.commit()
            return

        existing = [ProviderResult(**r) for r in (job.results or [])]
        targets = solution_ids or [
            r.solution_id
            for r in existing
            if r.status not in {"completed"}
        ]

        if not targets:
            return

        job.status = JobStatus.RUNNING.value
        await db.commit()

        try:
            local_path, temp_audio = await materialize_audio_for_analysis(
                audio_path=job.audio_path,
                file_id=job.file_id,
                source_url=job.source_url,
            )
            validate_audio_file(local_path)
            clear_shared_state(local_path)
            results, ranking = await retry_solutions(local_path, targets, existing)
            await _save_job_results(db, job, results, ranking, job.audio_path)
        except Exception as e:
            job.status = JobStatus.FAILED.value
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            await db.commit()
            metrics.record_job_finished(success=False)
            await record_audit_event(
                db,
                job_id=job_id,
                event_type="job_retry_failed",
                message="Job retry failed",
                level="error",
                metadata={"error_type": type(e).__name__},
            )
        finally:
            if temp_audio:
                cleanup_temporary_audio(local_path)


def sanitize_ranking_for_client(ranking: ComparisonRanking) -> ComparisonRanking:
    data = ranking.model_dump()
    data["recommendation_summary"] = ""
    if data.get("winner"):
        data["winner"]["recommendation_reason"] = ""
    data["rankings"] = [
        {**entry, "recommendation_reason": ""} for entry in data.get("rankings", [])
    ]
    return ComparisonRanking(**data)


def job_to_response(job: ComparisonJob) -> JobResponse:
    settings = get_settings()
    results: list[ProviderResult] = []
    if job.results:
        results = [
            sanitize_provider_result_for_client(ProviderResult(**r))
            for r in job.results
        ]

    pending = _pending_provider_count(results)
    ready = _results_ready(results, job.status)
    aggregate = _aggregate_status(results, job.status)
    groups = build_provider_groups(results) if ready else {"open_source": [], "sarvam": []}

    ranking = None
    if job.ranking and ready:
        ranking = sanitize_ranking_for_client(ComparisonRanking(**job.ranking))

    # Canonical final result: exactly one solution represents this recording
    # in dashboard KPIs; only expose it once all providers are terminal so
    # partial runs never leak a provisional winner.
    final_solution_id = None
    final_sentiment = None
    final_confidence = None
    final_overall_score = None
    final_recommendation = None
    sentiment_label = None
    is_valid_call = None
    invalid_reason = None

    if ready:
        canonical = derive_canonical_result(results, ranking)
        if canonical:
            final_solution_id = canonical.solution_id
            final_sentiment = canonical.analysis.sentiment or None
            final_confidence = canonical.analysis.confidence
            final_overall_score = canonical.overall_score
            final_recommendation = canonical.analysis.recommended_action or None

        validity = assess_recording_validity(
            aggregate_status=aggregate,
            job_error=job.error,
            canonical=canonical,
            results_ready=ready,
        )
        sentiment_label = validity.sentiment_label
        is_valid_call = validity.is_valid_call
        invalid_reason = validity.invalid_reason

    return JobResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        created_at=job.created_at,
        completed_at=job.completed_at,
        total_runtime_seconds=job.total_runtime_seconds,
        call_reference=job.call_reference,
        stt_language_code=None,
        audio_filename=job.audio_filename,
        source_type=job.source_type,
        source_url=job.source_url,
        ingested_at=job.ingested_at,
        results=results if ready else [],
        ranking=ranking if ready else None,
        error=job.error,
        pending_providers=pending,
        results_ready=ready,
        aggregate_status=aggregate,
        provider_groups=groups,
        sarvam_batch_max_wait_seconds=int(settings.sarvam_batch_max_wait_seconds),
        final_solution_id=final_solution_id,
        final_sentiment=final_sentiment,
        final_confidence=final_confidence,
        final_overall_score=final_overall_score,
        final_recommendation=final_recommendation,
        sentiment_label=sentiment_label,
        is_valid_call=is_valid_call,
        invalid_reason=invalid_reason,
    )


async def delete_job(db: AsyncSession, job_id: str) -> bool:
    """Delete a job and all associated rows from Postgres plus stored audio."""
    job = await get_job(db, job_id)
    if not job:
        return False

    if job.audio_path:
        delete_audio_file(job.audio_path)

    await db.execute(delete(JobAuditEvent).where(JobAuditEvent.job_id == job_id))
    await db.execute(delete(JobQueue).where(JobQueue.job_id == job_id))

    if job.audio_file_id:
        await db.execute(delete(AudioFile).where(AudioFile.id == job.audio_file_id))
    if job.file_id:
        await db.execute(delete(AudioFile).where(AudioFile.file_id == job.file_id))

    await db.delete(job)
    await db.commit()
    return True
