# Supabase Postgres Migration Guide

This application uses **SQLAlchemy** with a single `DATABASE_URL`. Point it at Supabase Postgres and all features (upload, analysis, dashboard, tickets) persist in the cloud database.

## What was replaced

| Before | After |
|--------|-------|
| `backend/data/app.db` (SQLite) | Supabase `comparison_jobs` + related tables |
| Local-only job/results storage | Postgres JSONB for `results` / `ranking` |
| Ad-hoc `ALTER TABLE` in `init_db` | Dialect-aware `schema_migrations.py` |

**SQLite remains** as an optional fallback when `DATABASE_URL` is not set to Postgres (default in `.env.example`). For production and pre-deployment testing, use Supabase.

## Tables in Supabase

| Table | Stores |
|-------|--------|
| `comparison_jobs` | **Primary** — recordings, canonical result, sentiment, recommendation, invalid flags, confidence, full 4-solution `results` JSON, transcripts, source URL, timestamps |
| `job_audit_events` | Processing audit trail |
| `audio_files` | Batch upload registry |
| `processing_jobs` | Batch orchestration |
| `excel_import_batches` | Excel import metadata |
| `imported_audio_urls` | Imported URL rows |
| `job_queue` | Durable worker queue (schema ready) |

### Dashboard & ticket fields (`comparison_jobs`)

- `audio_filename`, `file_id`, `call_reference`, `source_type`, `source_url`, `ingested_at`
- `final_solution_id`, `final_sentiment`, `final_confidence`, `final_recommendation`
- `sentiment_label`, `is_valid_call`, `invalid_reason`
- `status`, `results`, `ranking`, `error`, `created_at`, `completed_at`

## Environment variables

### Required (backend `backend/.env`)

```env
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?pgbouncer=true
```

The app auto-converts `postgresql://` and `postgres://` to `postgresql+psycopg://` for async SQLAlchemy.

### Optional

```env
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_ROLE_KEY=...   # backend-only; not required for SQLAlchemy CRUD
```

`SUPABASE_SERVICE_ROLE_KEY` is reserved for future admin/storage automation. **All current CRUD uses `DATABASE_URL` only.**

Copy `backend/.env.supabase.example` as a starting point.

## Setup steps

### 1. Create schema in Supabase

**Option A — ORM (recommended)**

```bash
cd backend
# Set DATABASE_URL in .env first
python -m scripts.setup_supabase_db
```

**Option B — SQL Editor**

Run `backend/migrations/001_supabase_schema.sql` in Supabase SQL Editor.

### 2. Run backend against Supabase locally

```bash
cd backend
# .env has DATABASE_URL pointing to Supabase
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

### 3. Verify connection

```bash
curl -u admin:changeme http://localhost:8000/db/status
```

Expected:

```json
{
  "ok": true,
  "status": "ok",
  "backend": "supabase_postgres",
  "dialect": "postgresql",
  "is_postgres": true
}
```

Also check `GET /ready` and `GET /health`.

## Migrate existing SQLite data

If you have data in `backend/data/app.db`:

```bash
cd backend
# DATABASE_URL = Supabase (target)
# Optional: SQLITE_DATABASE_URL=sqlite:///./data/app.db
python -m scripts.migrate_sqlite_to_supabase
```

- Copies all 7 tables in dependency order
- Skips rows that already exist (by primary key)
- Resets `job_audit_events` serial sequence after copy

If SQLite is empty, skip this step.

## Code paths using the database

All persistence goes through SQLAlchemy async sessions:

| Module | Operations |
|--------|------------|
| `app/services/jobs.py` | Create/run/delete comparison jobs |
| `app/api/routes.py` | `/calls`, `/results`, `/run-comparison` |
| `app/api/batch_routes.py` | Batch jobs, dashboard |
| `app/api/excel_routes.py` | Excel imports |
| `app/services/audit.py` | Audit events |

No raw SQLite file access outside the migration script.

## Local DB usage still remaining

| Component | When used |
|-----------|-----------|
| SQLite (`sqlite+aiosqlite`) | Only if `DATABASE_URL` is default/unset |
| `backend/data/app.db` | Created automatically in SQLite mode |
| `scripts/migrate_sqlite_to_supabase.py` | One-time migration tool |

Set `DATABASE_URL` to Supabase to eliminate local DB usage entirely.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `could not connect` | Check password, IP allowlist (Supabase allows all by default), use pooler URL |
| `prepared statement` errors | Use port `6543` pooler URL; app sets `prepare_threshold=None` |
| Empty dashboard | Confirm `/db/status` shows `supabase_postgres`; run migration script if needed |
| JSON errors | Postgres uses JSONB via `app/db/types.py` |

## Next step

After verifying locally against Supabase, proceed to hosting (Vercel + Hugging Face) per `docs/DEPLOYMENT-FREE-TIER.md`.
