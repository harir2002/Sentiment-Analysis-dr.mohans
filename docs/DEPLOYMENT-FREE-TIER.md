# Free-Tier Deployment Architecture

Deploy this app without paid persistent storage on Hugging Face by using **Supabase** for durable data and **ephemeral container disk** only for temporary audio processing.

## Target stack

| Layer | Service | Role |
|-------|---------|------|
| Frontend | **Vercel** (free) | React SPA, env points to backend |
| Backend | **Hugging Face Spaces** (free CPU Docker) | FastAPI + analysis pipelines |
| Database | **Supabase Postgres** (free) | All structured persistence |
| Object storage | **Supabase Storage** (free tier, optional) | Uploaded audio blobs (S3-compatible) |

## Why Hugging Face local disk is not durable

Hugging Face Spaces free tier runs your backend in a **stateless container**:

- Restarts, redeploys, and sleep/wake cycles **wipe local filesystem**
- SQLite files under `./data/app.db` are **lost**
- Uploaded files under `./data/uploads` are **lost**
- In-memory job state is **lost**

Anything that must survive a restart must live **outside** the container: Supabase Postgres (and optionally Supabase Storage).

## What is stored in Supabase Postgres

All application records are written to Postgres via SQLAlchemy:

| Table | Purpose |
|-------|---------|
| `comparison_jobs` | Recordings, canonical results, sentiment, recommendations, invalid flags, full `results` JSON (4 solutions), transcripts in JSON |
| `job_audit_events` | Processing audit trail |
| `audio_files` | Batch upload registry |
| `processing_jobs` | Batch orchestration |
| `excel_import_batches` / `imported_audio_urls` | Excel URL import workflow |
| `job_queue` | Planned durable worker (schema ready) |

**Dashboard KPIs, ticket detail, and results pages** all read from `comparison_jobs` via existing API routes — no frontend changes required beyond `VITE_API_URL`.

### Denormalized fields (fast dashboard/ticket queries)

On each completed job, the backend persists:

- `final_solution_id`, `final_sentiment`, `final_confidence`, `final_recommendation`
- `sentiment_label`, `is_valid_call`, `invalid_reason`
- `source_type`, `source_url`, `ingested_at`

## What is no longer stored locally (in production)

| Item | Production behavior |
|------|---------------------|
| SQLite `app.db` | **Not used** — set `DATABASE_URL` to Supabase |
| Long-term uploads on HF disk | **Not relied on** — use `STORAGE_BACKEND=s3` or URL ingestion |
| Audio after analysis | Deleted when `CLEANUP_AUDIO_AFTER_JOB=true` (default) |
| Temp processing files | `./data/tmp` or `/tmp/...` — removed after each job |

## File handling strategy

### Preferred: audio URL ingestion

1. User pastes a direct `https://` audio link
2. Backend downloads to temp, validates, optionally uploads to Supabase Storage
3. `source_url` is stored in Postgres
4. After cleanup, **re-analysis can re-fetch** from `source_url`

### File upload (free-tier safe)

1. Upload hits backend → stored in **Supabase Storage** (`uploads/{file_id}.ext`) when `STORAGE_BACKEND=s3`
2. `stored_path` (object key) saved on `comparison_jobs.audio_path`
3. Pipeline **materializes** audio to a temp file for STT/LLM, then deletes temp
4. Optional: delete S3 object after job (`CLEANUP_AUDIO_AFTER_JOB=true`)

### Upload without Supabase Storage (limited)

Works for **same-session** analysis only. If the Space restarts before the job completes, the upload may be lost unless `source_url` was provided.

## Setup steps

### 1. Supabase database

1. Create a project at [supabase.com](https://supabase.com)
2. SQL Editor → run `backend/migrations/001_supabase_schema.sql`
3. Copy **Database → Connection string** (URI)
4. Set `DATABASE_URL` on Hugging Face (pooler port `6543` recommended)

### 2. Supabase Storage (optional but recommended for uploads)

1. Storage → create bucket `call-analytics` (private)
2. Project Settings → Storage → S3 connection → copy endpoint + keys
3. Set `STORAGE_BACKEND=s3` and S3 env vars on Hugging Face

### 3. Hugging Face Space (backend)

1. Create a **Docker** Space pointing at this repo root `Dockerfile`
2. Add secrets from `backend/.env.production.example`
3. Ensure `APP_ENV=production`, `DATABASE_URL`, provider API keys, `CORS_ORIGINS`

### 4. Vercel (frontend)

1. Import repo, set **Root Directory** to `frontend`
2. Add env from `frontend/.env.example`
3. `VITE_API_URL` = your HF Space public URL

## Environment variables

### Backend (Hugging Face Secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | **Yes** | Supabase Postgres URI |
| `APP_ENV` | Yes | `production` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Yes | API basic auth |
| `CORS_ORIGINS` | Yes | Vercel URL(s) |
| `SARVAM_API_KEY` | Yes* | Sarvam pipelines |
| `GROQ_API_KEY` | Yes* | Whisper STT |
| `OPENROUTER_API_KEY` | Yes* | Gemma LLM |
| `STORAGE_BACKEND` | Recommended | `s3` for uploads |
| `S3_ENDPOINT_URL` | If s3 | Supabase Storage S3 API |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | If s3 | Storage keys |
| `S3_BUCKET` | If s3 | e.g. `call-analytics` |
| `TEMP_DIR` | Optional | `/tmp/call-analytics/tmp` |
| `CLEANUP_AUDIO_AFTER_JOB` | Optional | `true` (default) |

\*At least one provider stack must be configured.

### Frontend (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes | HF Space backend URL |
| `VITE_ADMIN_USERNAME` | Yes | Match backend |
| `VITE_ADMIN_PASSWORD` | Yes | Match backend |

## Local development (unchanged)

```bash
# SQLite + local uploads (default)
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
STORAGE_BACKEND=local
```

## Remaining free-tier limitations

1. **HF CPU sleep** — first request after idle may be slow; upgrade or keep-alive ping if needed
2. **Supabase free quotas** — 500 MB database, 1 GB storage, connection limits
3. **No multi-instance job worker** — background tasks run in the single uvicorn process; restarting cancels in-flight jobs (completed results remain in Postgres)
4. **Upload-only without Storage** — not restart-safe; use URLs or Supabase Storage
5. **Play Audio on ticket page** — works for URL-sourced calls (`source_url`); uploaded files need Storage presigned URL (future enhancement)
6. **Batch/excel pipeline** — schema exists; full durable batch worker not yet implemented

## Health checks

- `GET /live` — process alive
- `GET /ready` — Postgres + storage config + provider keys
- `GET /health` — dependency summary including `persistence: supabase_postgres`
