"""Excel/CSV import service for audio URL batch processing."""
import logging
from io import BytesIO
from urllib.parse import urlparse
from datetime import datetime
from uuid import uuid4

import openpyxl
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import ExcelImportBatch, ImportedAudioUrl
from app.core.observability import obs_logger

logger = logging.getLogger(__name__)

# Common column names to search for
AUDIO_URL_COLUMNS = [
    'audio_file',
    'audiofile',
    'audio_url',
    'audio url',
    'audiourl',
    'file_url',
    'fileurl',
    'file url',
    'recording_url',
    'recordingurl',
    'recording url',
    'url',
    'link',
    'audio_link',
    'audiolink',
    'recording',
    'file',
]


def detect_audio_column(df: pd.DataFrame) -> str | None:
    """Detect the column containing audio URLs."""
    columns = [col.lower().strip() for col in df.columns]
    
    for target in AUDIO_URL_COLUMNS:
        if target in columns:
            original_col = df.columns[columns.index(target)]
            return original_col
    
    return None


def is_valid_url(url: str) -> bool:
    """Validate if string is a valid URL."""
    try:
        result = urlparse(str(url).strip())
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def extract_filename_from_url(url: str) -> str | None:
    """Extract filename from URL."""
    try:
        parsed = urlparse(url)
        path = parsed.path
        filename = path.split('/')[-1] if path else None
        return filename if filename else None
    except Exception:
        return None


async def parse_excel_file(file_content: bytes, filename: str) -> dict:
    """Parse Excel or CSV file and extract audio URLs."""
    try:
        # Determine file type
        is_csv = filename.lower().endswith('.csv')
        
        # Read file
        if is_csv:
            df = pd.read_csv(BytesIO(file_content))
        else:
            df = pd.read_excel(BytesIO(file_content))
        
        # Detect audio URL column
        audio_col = detect_audio_column(df)
        if not audio_col:
            return {
                'success': False,
                'error': f'Could not find audio URL column. Looking for: {", ".join(AUDIO_URL_COLUMNS[:5])}...',
                'detected_column': None,
                'records': [],
                'total_rows': len(df),
            }
        
        # Extract records
        records = []
        seen_urls = set()
        valid_count = 0
        invalid_count = 0
        duplicate_count = 0
        
        for idx, row in df.iterrows():
            row_number = idx + 2  # +2 because Excel is 1-indexed and has header
            
            # Get URL
            url_value = row.get(audio_col)
            if pd.isna(url_value) or url_value == '':
                invalid_count += 1
                records.append({
                    'row_number': row_number,
                    'audio_url': '',
                    'audio_name': None,
                    'status': 'invalid',
                    'error': 'Empty cell',
                })
                continue
            
            url = str(url_value).strip()
            
            # Validate URL
            if not is_valid_url(url):
                invalid_count += 1
                records.append({
                    'row_number': row_number,
                    'audio_url': url,
                    'audio_name': None,
                    'status': 'invalid',
                    'error': 'Invalid URL format',
                })
                continue
            
            # Check for duplicates
            if url in seen_urls:
                duplicate_count += 1
                records.append({
                    'row_number': row_number,
                    'audio_url': url,
                    'audio_name': extract_filename_from_url(url),
                    'status': 'invalid',
                    'error': 'Duplicate URL',
                })
                continue
            
            seen_urls.add(url)
            valid_count += 1
            
            # Extract filename
            audio_name = extract_filename_from_url(url)
            
            records.append({
                'row_number': row_number,
                'audio_url': url,
                'audio_name': audio_name,
                'status': 'valid',
                'error': None,
            })
        
        return {
            'success': True,
            'detected_column': audio_col,
            'total_rows': len(df),
            'valid_links': valid_count,
            'invalid_links': invalid_count,
            'duplicate_links': duplicate_count,
            'records': records,
            'preview_records': records[:5],  # First 5 for preview
        }
    
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        return {
            'success': False,
            'error': f'Error parsing file: {str(e)}',
            'detected_column': None,
            'records': [],
            'total_rows': 0,
        }


async def create_excel_import_batch(
    db: AsyncSession,
    batch_name: str,
    filename: str,
    total_links: int,
    valid_links: int,
) -> ExcelImportBatch:
    """Create a new Excel import batch."""
    batch = ExcelImportBatch(
        id=str(uuid4()),
        batch_name=batch_name,
        file_name=filename,
        total_links=total_links,
        valid_links=valid_links,
        status='pending',
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    
    obs_logger.info(
        'excel_import_batch_created',
        extra={
            'import_batch_id': batch.id,
            'batch_name': batch_name,
            'total_links': total_links,
            'valid_links': valid_links,
        },
    )
    return batch


async def add_audio_url_records(
    db: AsyncSession,
    import_batch_id: str,
    records: list[dict],
    call_reference_prefix: str | None = None,
) -> list[ImportedAudioUrl]:
    """Add imported audio URL records."""
    imported_records = []
    
    for idx, record in enumerate(records):
        if record['status'] != 'valid':
            continue  # Skip invalid records
        
        call_reference = None
        if call_reference_prefix:
            call_reference = f"{call_reference_prefix}_{idx + 1:04d}"
        
        audio_record = ImportedAudioUrl(
            id=str(uuid4()),
            import_batch_id=import_batch_id,
            audio_url=record['audio_url'],
            audio_name=record['audio_name'],
            row_number=record['row_number'],
            status='pending',
            call_reference=call_reference,
        )
        db.add(audio_record)
        imported_records.append(audio_record)
    
    await db.commit()
    return imported_records


async def get_excel_import_batch(
    db: AsyncSession,
    import_batch_id: str,
) -> ExcelImportBatch | None:
    """Get Excel import batch by ID."""
    result = await db.execute(
        select(ExcelImportBatch).where(ExcelImportBatch.id == import_batch_id)
    )
    return result.scalars().first()


async def list_excel_import_batches(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ExcelImportBatch], int]:
    """List Excel import batches."""
    result = await db.execute(select(ExcelImportBatch))
    total = len(result.scalars().all())
    
    result = await db.execute(
        select(ExcelImportBatch)
        .order_by(ExcelImportBatch.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all(), total


async def get_batch_audio_urls(
    db: AsyncSession,
    import_batch_id: str,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ImportedAudioUrl], int]:
    """Get audio URLs from import batch."""
    query = select(ImportedAudioUrl).where(
        ImportedAudioUrl.import_batch_id == import_batch_id
    )
    
    if status:
        query = query.where(ImportedAudioUrl.status == status)
    
    result = await db.execute(query)
    total = len(result.scalars().all())
    
    result = await db.execute(
        query.order_by(ImportedAudioUrl.row_number)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all(), total


async def get_import_batch_stats(
    db: AsyncSession,
    import_batch_id: str,
) -> dict:
    """Get statistics for import batch."""
    batch = await get_excel_import_batch(db, import_batch_id)
    if not batch:
        return None
    
    # Count by status
    result = await db.execute(
        select(ImportedAudioUrl.status)
        .where(ImportedAudioUrl.import_batch_id == import_batch_id)
    )
    statuses = result.scalars().all()
    
    status_counts = {}
    for status in ['pending', 'processing', 'completed', 'failed']:
        status_counts[status] = sum(1 for s in statuses if s == status)
    
    return {
        'import_batch_id': batch.id,
        'batch_name': batch.batch_name,
        'total_links': batch.total_links,
        'valid_links': batch.valid_links,
        'pending': status_counts['pending'],
        'processing': status_counts['processing'],
        'completed': status_counts['completed'],
        'failed': status_counts['failed'],
        'status': batch.status,
        'created_at': batch.created_at,
        'completed_at': batch.completed_at,
    }
