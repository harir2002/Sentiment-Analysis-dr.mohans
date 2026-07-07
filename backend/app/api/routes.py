from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_admin
from app.core.config import get_settings
from app.core.exceptions import AudioValidationError
from app.models.schemas import (
    UploadItemResult,
    BatchUploadResponse,
    UploadUrlRequest,
    RunComparisonRequest,
    RetryProvidersRequest,
    JobResponse,
    CallsListResponse,
    CallListItem,
    HealthResponse,
)
from app.core.observability import metrics
from app.services.health import health_report, readiness_report, check_database
from app.services.storage import save_uploads, save_from_url, resolve_audio_path_async
from app.services.jobs import (
    create_job,
    get_job,
    list_jobs,
    run_job_background,
    retry_job_background,
    job_to_response,
    delete_job,
)
from app.services.export import (
    export_job_csv,
    export_job_excel,
    export_job_json,
    export_job_pdf,
    export_job_word,
)

router = APIRouter()


async def _list_calls(db: AsyncSession) -> CallsListResponse:
    jobs = await list_jobs(db)
    calls: list[dict] = []
    for job in jobs:
        response = job_to_response(job)
        # Return full JobResponse data including results for dashboard
        calls.append(response.model_dump())
    return CallsListResponse(calls=calls, total=len(calls))


@router.get("/calls", response_model=CallsListResponse, tags=["calls"])
@router.get("/api/calls", response_model=CallsListResponse, tags=["calls"])
async def list_calls(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    return await _list_calls(db)


@router.get("/live")
async def liveness():
    """Process is running (for orchestrator liveness probes)."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """Dependency readiness (DB, upload dir, provider keys)."""
    report = await readiness_report()
    status_code = 200 if report["ready"] else 503
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content=report)


@router.get("/db/status")
async def database_status(_: str = Depends(verify_admin)):
    """Report which persistence backend is active (Supabase vs SQLite fallback)."""
    from app.db import database_info

    info = database_info()
    db_ok, db_status = await check_database()
    return {
        "ok": db_ok,
        "status": db_status,
        **info,
    }


@router.get("/metrics")
async def get_metrics(_: str = Depends(verify_admin)):
    """Operational metrics snapshot for monitoring dashboards."""
    settings = get_settings()
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    return metrics.snapshot()


@router.get("/health", response_model=HealthResponse)
async def health():
    report = await health_report()
    return HealthResponse(
        status=report["status"],
        database=report["database"],
        version=report["version"],
        providers=report["providers"],
        models=report["models"],
    )


@router.post("/upload", response_model=BatchUploadResponse)
async def upload_audio(
    files: list[UploadFile] = File(...),
    _: str = Depends(verify_admin),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one audio file is required")

    uploaded_raw, failed_raw = await save_uploads(files)
    uploaded = [UploadItemResult(**item) for item in uploaded_raw]
    failed = [UploadItemResult(**item) for item in failed_raw]

    if not uploaded and failed:
        raise HTTPException(
            status_code=400,
            detail=f"All {len(failed)} file(s) failed validation",
        )

    return BatchUploadResponse(
        uploaded=uploaded,
        failed=failed,
        total=len(files),
        success_count=len(uploaded),
        failed_count=len(failed),
    )


@router.post("/upload/url", response_model=BatchUploadResponse)
async def upload_audio_url(
    request: UploadUrlRequest,
    _: str = Depends(verify_admin),
):
    url = request.audio_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="audio_url is required")

    try:
        file_id, filename, stored_path, metadata = await save_from_url(url)
    except AudioValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    item = UploadItemResult(
        file_id=file_id,
        filename=filename,
        path=stored_path,
        metadata=metadata,
        success=True,
        error=None,
    )
    return BatchUploadResponse(
        uploaded=[item],
        failed=[],
        total=1,
        success_count=1,
        failed_count=0,
    )


@router.post("/run-comparison", response_model=JobResponse)
async def run_comparison(
    request: RunComparisonRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    if not request.file_id:
        raise HTTPException(status_code=400, detail="file_id is required — upload a real audio file first")

    audio_path = request.stored_path or await resolve_audio_path_async(request.file_id)
    if not audio_path and not request.source_url:
        raise HTTPException(status_code=404, detail="Uploaded audio file not found")

    try:
        job = await create_job(
            db,
            request.file_id,
            request.call_reference,
            original_filename=request.original_filename,
            source_type=request.source_type,
            source_url=request.source_url,
            stored_path=request.stored_path or audio_path,
        )
    except (AudioValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    background_tasks.add_task(run_job_background, job.id)
    return job_to_response(job)


@router.post("/results/{job_id}/retry", response_model=JobResponse)
async def retry_failed_providers(
    job_id: str,
    request: RetryProvidersRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.results:
        raise HTTPException(status_code=400, detail="No results to retry")

    if not job.audio_path:
        raise HTTPException(
            status_code=400,
            detail="Audio file no longer available — re-upload and run a new comparison",
        )

    failed_ids = [
        r["solution_id"]
        for r in job.results
        if r.get("status") != "completed"
    ]
    target_ids = request.solution_ids or failed_ids

    if not target_ids:
        raise HTTPException(status_code=400, detail="No failed providers to retry")

    background_tasks.add_task(retry_job_background, job_id, target_ids)
    job.status = "running"
    await db.commit()
    await db.refresh(job)
    return job_to_response(job)


@router.get("/results/{job_id}", response_model=JobResponse)
async def get_results(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_response(job)


@router.get("/results/{job_id}/export/json")
async def export_results_json(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job_to_response(job)
    content = export_job_json(response)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="comparison-{job_id}.json"'},
    )


@router.get("/results/{job_id}/export/csv")
async def export_results_csv(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job_to_response(job)
    content = export_job_csv(response)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="comparison-{job_id}.csv"'},
    )


@router.get("/results/{job_id}/export/xlsx")
async def export_results_excel(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job_to_response(job)
    content = export_job_excel(response)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="comparison-{job_id}.xlsx"'},
    )


@router.get("/results/{job_id}/export/pdf")
async def export_results_pdf(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job_to_response(job)
    content = export_job_pdf(response)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="comparison-{job_id}.pdf"'},
    )


@router.get("/results/{job_id}/export/docx")
async def export_results_word(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job_to_response(job)
    content = export_job_word(response)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="comparison-{job_id}.docx"'},
    )


@router.delete("/results/{job_id}", response_model=dict)
async def delete_job_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Permanently delete a job and all related database rows."""
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete the job from database
    deleted = await delete_job(db, job_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete job")
    
    return {"message": "Job deleted successfully", "job_id": job_id}
