"""Excel import API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_admin
from app.models.schemas import (
    ExcelImportPreview,
    AudioLinkRecord,
    ExcelImportBatchResponse,
    ExcelImportRequest,
)
from app.services.excel_importer import (
    parse_excel_file,
    create_excel_import_batch,
    add_audio_url_records,
    get_excel_import_batch,
    list_excel_import_batches,
    get_batch_audio_urls,
    get_import_batch_stats,
)
from app.services.batch_processor import process_batch_async
from app.core.observability import obs_logger

router = APIRouter(prefix="/api/excel", tags=["excel"])


@router.post("/preview")
async def preview_excel_file(
    file: UploadFile = File(...),
    _: str = Depends(verify_admin),
):
    """Parse Excel file and preview audio links."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")
    
    # Read file
    content = await file.read()
    
    # Parse
    result = await parse_excel_file(content, file.filename)
    
    if not result['success']:
        raise HTTPException(
            status_code=400,
            detail=result.get('error', 'Failed to parse file'),
        )
    
    return ExcelImportPreview(
        total_rows=result['total_rows'],
        valid_links=result['valid_links'],
        invalid_links=result['invalid_links'],
        duplicate_links=result['duplicate_links'],
        detected_column=result['detected_column'],
        preview_records=[
            AudioLinkRecord(**record) for record in result['preview_records']
        ],
        errors=[] if result['success'] else [result.get('error', 'Unknown error')],
    )


@router.post("/import-and-process")
async def import_and_process_excel(
    request: ExcelImportRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Import Excel links and create batch in draft status (not auto-started)."""
    if not request.audio_link_records:
        raise HTTPException(status_code=400, detail="No valid audio links provided")
    
    valid_records = [r for r in request.audio_link_records if r.status == 'valid']
    if not valid_records:
        raise HTTPException(status_code=400, detail="No valid audio links to process")
    
    try:
        # Create Excel import batch
        import_batch = await create_excel_import_batch(
            db,
            batch_name=request.batch_name,
            filename=request.batch_name,
            total_links=len(request.audio_link_records),
            valid_links=len(valid_records),
        )
        
        # Add audio URL records
        audio_records = await add_audio_url_records(
            db,
            import_batch.id,
            [r.dict() for r in request.audio_link_records],
            request.call_reference_prefix,
        )
        
        obs_logger.info(
            'excel_import_created_draft',
            extra={
                'import_batch_id': import_batch.id,
                'total_records': len(request.audio_link_records),
                'valid_records': len(audio_records),
            },
        )
        
        return ExcelImportBatchResponse(
            import_batch_id=import_batch.id,
            processing_job_id='',  # Set when pipeline is started
            batch_name=request.batch_name,
            total_links=len(request.audio_link_records),
            valid_links=len(valid_records),
            message=f"Import batch created with {len(valid_records)} valid links. Use Start Pipeline to begin processing.",
        )
    
    except Exception as e:
        obs_logger.error(f"Excel import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/batches/{import_batch_id}")
async def get_import_batch_details(
    import_batch_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get details of an import batch."""
    batch = await get_excel_import_batch(db, import_batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    
    stats = await get_import_batch_stats(db, import_batch_id)
    return stats


@router.get("/batches")
async def list_import_batches(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """List all import batches."""
    batches, total = await list_excel_import_batches(db, limit=limit, offset=offset)
    
    result = []
    for batch in batches:
        stats = await get_import_batch_stats(db, batch.id)
        result.append(stats)
    
    return result


@router.get("/batches/{import_batch_id}/records")
async def get_import_batch_records(
    import_batch_id: str,
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Get audio records from import batch."""
    records, total = await get_batch_audio_urls(
        db,
        import_batch_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    
    return [
        {
            'id': r.id,
            'audio_url': r.audio_url,
            'audio_name': r.audio_name,
            'row_number': r.row_number,
            'status': r.status,
            'error': r.error,
            'call_reference': r.call_reference,
            'created_at': r.created_at,
        }
        for r in records
    ]


async def process_imported_urls(
    import_batch_id: str,
    audio_records: list,
):
    """Process imported audio URLs (background task placeholder)."""
    obs_logger.info(
        'processing_imported_urls',
        extra={
            'import_batch_id': import_batch_id,
            'total_records': len(audio_records),
        },
    )
    # TODO: Implement actual URL download and processing
    # This would involve:
    # 1. Download each audio URL
    # 2. Save temporarily
    # 3. Run 4-solution pipeline
    # 4. Save results to DB
    # 5. Update status
