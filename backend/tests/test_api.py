from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import routes
from app.core.database import get_db
from app.core.exceptions import AudioValidationError
from app.core.security import verify_admin
from app.main import app
from app.models.db_models import ComparisonJob
from app.models.schemas import AnalysisResult, ComparisonRanking, JobStatus, ProviderResult, RankingEntry, ScoreBreakdown
from app.services.jobs import job_to_response


@pytest.fixture
def api_app():
    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[verify_admin] = lambda: "test-admin"
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def api_client(api_app):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _make_result(solution_id: str, *, sentiment: str = "neutral", overall_score: float = 80.0) -> dict:
    return ProviderResult(
        solution_id=solution_id,
        label=solution_id,
        stt_provider="groq_stt",
        stt_model="whisper-large-v3",
        llm_provider="openrouter",
        llm_model="gemma-test",
        status="completed",
        transcript="Patient discussed appointment scheduling and billing follow-up.",
        analysis=AnalysisResult(
            sentiment=sentiment,
            summary="Customer called about appointment scheduling.",
            resolution_status="resolved",
            confidence=0.92,
            recommended_action="Confirm the scheduled appointment with the customer.",
        ),
        stt_runtime_seconds=1.2,
        llm_runtime_seconds=0.8,
        total_runtime_seconds=2.0,
        estimated_cost_usd=0.01,
        overall_score=overall_score,
    ).model_dump()


def _make_job(job_id: str = "job-123") -> ComparisonJob:
    winner = RankingEntry(
        rank=1,
        solution_id="groq_whisper_groq_gemma",
        label="Groq Whisper + Groq Gemma",
        overall_score=88.0,
        score_breakdown=ScoreBreakdown(overall=88.0),
    )
    return ComparisonJob(
        id=job_id,
        status=JobStatus.COMPLETED.value,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        total_runtime_seconds=8.5,
        audio_filename="call.mp3",
        source_type="url",
        source_url="https://cdn.example.com/call.mp3",
        ingested_at=datetime.utcnow(),
        results=[
            _make_result("groq_whisper_groq_gemma", sentiment="positive", overall_score=88.0),
            _make_result("sarvam_stt_groq_gemma", sentiment="neutral", overall_score=75.0),
        ],
        ranking=ComparisonRanking(winner=winner, rankings=[winner]).model_dump(),
    )


@pytest.mark.asyncio
async def test_health_endpoint(api_client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "health_report",
        AsyncMock(
            return_value={
                "status": "ok",
                "database": "ok",
                "version": "1.0.0",
                "providers": {"sarvam": True, "groq": True, "openrouter": True},
                "models": {
                    "sarvam_stt": "saaras:v3",
                    "sarvam_llm": "sarvam-30b",
                    "groq_stt": "whisper-large-v3",
                    "openrouter_llm": "google/gemma-4-26b-a4b-it",
                },
            }
        ),
    )

    response = await api_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["providers"]["sarvam"] is True
    assert data["models"]["openrouter_llm"] == "google/gemma-4-26b-a4b-it"


@pytest.mark.asyncio
async def test_list_calls_endpoints_return_dashboard_payload(api_client, monkeypatch):
    job = _make_job("job-list-1")
    monkeypatch.setattr(routes, "list_jobs", AsyncMock(return_value=[job]))

    response = await api_client.get("/api/calls")
    alias_response = await api_client.get("/calls")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["calls"][0]["job_id"] == "job-list-1"
    assert data["calls"][0]["final_solution_id"] == "groq_whisper_groq_gemma"
    assert data["calls"][0]["results_ready"] is True
    assert alias_response.status_code == 200
    assert alias_response.json()["total"] == 1


@pytest.mark.asyncio
async def test_upload_audio_url_success(api_client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "save_from_url",
        AsyncMock(
            return_value=(
                "file-1",
                "call.mp3",
                "./data/uploads/file-1.mp3",
                {"source_type": "url", "source_url": "https://cdn.example.com/call.mp3"},
            )
        ),
    )

    response = await api_client.post("/upload/url", json={"audio_url": "https://cdn.example.com/call.mp3"})

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 1
    assert data["uploaded"][0]["file_id"] == "file-1"
    assert data["uploaded"][0]["metadata"]["source_type"] == "url"


@pytest.mark.asyncio
async def test_upload_audio_url_invalid_returns_400(api_client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "save_from_url",
        AsyncMock(side_effect=AudioValidationError("Only http and https URLs are supported")),
    )

    response = await api_client.post("/upload/url", json={"audio_url": "ftp://bad.example.com/file.mp3"})

    assert response.status_code == 400
    assert "http and https" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_comparison_requires_file_id(api_client):
    response = await api_client.post("/run-comparison", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_run_comparison_missing_uploaded_audio_returns_404(api_client, monkeypatch):
    monkeypatch.setattr(routes, "resolve_audio_path_async", AsyncMock(return_value=None))

    response = await api_client.post(
        "/run-comparison",
        json={"file_id": "missing-file", "original_filename": "call.mp3"},
    )

    assert response.status_code == 404
    assert "Uploaded audio file not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_comparison_queues_job_and_returns_job_response(api_client, monkeypatch):
    job = _make_job("job-run-1")
    monkeypatch.setattr(routes, "resolve_audio_path_async", AsyncMock(return_value="./data/uploads/call.mp3"))
    monkeypatch.setattr(routes, "create_job", AsyncMock(return_value=job))
    monkeypatch.setattr(routes, "run_job_background", AsyncMock())

    response = await api_client.post(
        "/run-comparison",
        json={
            "file_id": "file-123",
            "original_filename": "call.mp3",
            "source_type": "url",
            "source_url": "https://cdn.example.com/call.mp3",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-run-1"
    assert data["audio_filename"] == "call.mp3"
    assert data["source_url"] == "https://cdn.example.com/call.mp3"


@pytest.mark.asyncio
async def test_get_results_returns_ticket_detail_payload(api_client, monkeypatch):
    job = _make_job("job-results-1")
    monkeypatch.setattr(routes, "get_job", AsyncMock(return_value=job))

    response = await api_client.get("/results/job-results-1")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-results-1"
    assert data["results_ready"] is True
    assert data["aggregate_status"] == "completed"
    assert data["final_solution_id"] == "groq_whisper_groq_gemma"
    assert data["source_type"] == "url"
    assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_db_status_uses_dependency_health_data(api_client, monkeypatch):
    monkeypatch.setattr(routes, "check_database", AsyncMock(return_value=(True, "ok")))
    monkeypatch.setattr(
        "app.db.database_info",
        lambda: {"backend": "supabase_postgres", "dialect": "postgresql"},
    )

    response = await api_client.get("/db/status")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["backend"] == "supabase_postgres"
    assert data["dialect"] == "postgresql"
