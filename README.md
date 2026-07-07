# Dr. Mohan's Call Sentiment Analysis

Production-ready call analytics platform that compares multiple STT + LLM pipelines, scores sentiment, and surfaces actionable CRM insights from customer call recordings.

**Stack:** React (Vite) · FastAPI · Supabase Postgres · Hugging Face Spaces · Vercel

---

## Features

- **Multi-pipeline comparison** — Run Sarvam, Groq Whisper, and OpenRouter (Gemma) solutions side by side
- **Sentiment dashboard** — KPI cards, quality charts, canonical win tracking, expandable ticket detail
- **CRM view** — Browse all analyzed tickets in one place
- **Batch processing** — Excel URL import, pipeline orchestration, progress tracking
- **Exports** — JSON, CSV, XLSX, PDF, DOCX per job
- **Durable persistence** — Supabase Postgres for jobs, results, and audit events
- **Cloud-ready** — Docker backend for Hugging Face; frontend deploys to Vercel

---

## Architecture

```
┌─────────────┐     HTTPS      ┌──────────────────────┐     SQL      ┌─────────────────┐
│   Vercel    │ ─────────────► │  Hugging Face Space  │ ───────────► │ Supabase Postgres│
│  (React UI) │                │  (FastAPI backend)   │              │  (persistence)   │
└─────────────┘                └──────────────────────┘              └─────────────────┘
                                          │
                                          ▼
                               Sarvam · Groq · OpenRouter APIs
```

| Layer | Service | Role |
|-------|---------|------|
| Frontend | Vercel | React SPA (`frontend/`) |
| Backend | Hugging Face Spaces | FastAPI API (`backend/`) |
| Database | Supabase Postgres | All structured data |
| Storage (optional) | Supabase Storage | Durable audio uploads (`STORAGE_BACKEND=s3`) |

---

## Project structure

```
.
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/             # REST routes
│   │   ├── core/            # Config, database, middleware
│   │   ├── services/        # Jobs, STT/LLM pipelines, storage
│   │   └── main.py
│   ├── migrations/          # Supabase schema SQL
│   ├── tests/
│   └── requirements.txt
├── frontend/                # React + Vite UI
│   ├── src/
│   │   ├── components/      # Dashboard, CRM, charts, sidebar
│   │   └── services/api.js
│   └── vercel.json
├── docs/                    # Deployment & operations guides
├── Dockerfile               # Hugging Face Spaces (port 7860)
├── docker-compose.yml
└── .env.example             # Backend env template (copy to backend/.env)
```

---

## Local development

### Prerequisites

- Python 3.11+
- Node.js 18+
- API keys: Sarvam, Groq, OpenRouter (see `.env.example`)

### 1. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
# Edit .env with your keys and DATABASE_URL (or use SQLite for quick local dev)
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```powershell
cd frontend
npm install
# Create frontend/.env with VITE_API_URL=http://localhost:8000
npm run dev
```

App: http://localhost:5173

### 3. Supabase (recommended for production-like dev)

```powershell
cd backend
python -m scripts.setup_supabase_db
```

See [docs/SUPABASE-MIGRATION.md](docs/SUPABASE-MIGRATION.md) for connection string details.

---

## Environment variables

**Never commit `backend/.env`.** Use the example files:

| File | Purpose |
|------|---------|
| `.env.example` | Full backend template |
| `backend/.env.supabase.example` | Supabase-focused local setup |
| `backend/.env.production.example` | Hugging Face / production |
| `frontend/.env.example` | Vercel frontend variables |

### Backend (required for full functionality)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase Postgres connection string |
| `SARVAM_API_KEY` | Sarvam STT + LLM |
| `GROQ_API_KEY` | Groq Whisper STT |
| `OPENROUTER_API_KEY` | OpenRouter Gemma LLM |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | API basic auth |
| `CORS_ORIGINS` | Comma-separated frontend URLs |

### Frontend (Vercel)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Hugging Face Space URL |
| `VITE_ADMIN_USERNAME` | Must match backend |
| `VITE_ADMIN_PASSWORD` | Must match backend |

---

## Deployment

### Backend → Hugging Face Spaces

1. Create a **Docker** Space (port **7860**)
2. Push `Dockerfile`, `.dockerignore`, and `backend/` (exclude `venv`, `.env`, `data/`)
3. Set **Secrets** on the Space: `APP_ENV`, `DATABASE_URL`, `ADMIN_*`, API keys
4. Set **Variables**: `CORS_ORIGINS` with your Vercel URL

Health checks:

- `/live` — liveness
- `/ready` — readiness
- `/health` — full status
- `/docs` — Swagger UI

> Root `/` returns 404 by design — this is an API-only backend.

See [docs/DEPLOYMENT-FREE-TIER.md](docs/DEPLOYMENT-FREE-TIER.md) for the full free-tier guide.

### Frontend → Vercel

1. Import this repo; set **Root Directory** to `frontend`
2. Add `VITE_API_URL`, `VITE_ADMIN_USERNAME`, `VITE_ADMIN_PASSWORD`
3. Deploy; then add the Vercel URL to backend `CORS_ORIGINS`

---

## API overview

| Endpoint | Description |
|----------|-------------|
| `POST /upload` | Upload audio file |
| `POST /upload/url` | Ingest audio from URL |
| `POST /run-comparison` | Run multi-solution analysis |
| `GET /calls` | List analyzed calls |
| `GET /results/{job_id}` | Job detail + all solution results |
| `DELETE /results/{job_id}` | Delete job from database |
| `GET /api/batch/*` | Batch job management |
| `GET /api/excel/*` | Excel import workflow |

Full interactive docs at `/docs` when the backend is running.

---

## Testing

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/ -q
```

---

## Security notes

- Do **not** commit `.env`, API keys, or database passwords
- Rotate keys if they were ever exposed in logs or chat
- Use strong `ADMIN_PASSWORD` in production
- Prefer Supabase Storage (`STORAGE_BACKEND=s3`) for durable uploads on cloud

---

## Documentation

- [Free-tier deployment](docs/DEPLOYMENT-FREE-TIER.md)
- [Supabase migration](docs/SUPABASE-MIGRATION.md)
- [Operations](docs/OPERATIONS.md)
- [Deployment (general)](docs/DEPLOYMENT.md)

---

## License

Private project — Dr. Mohan's sentiment analysis demo.
