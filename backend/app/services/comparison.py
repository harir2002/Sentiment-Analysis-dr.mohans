import asyncio
import logging

from app.core.observability import metrics, obs_logger
from app.models.schemas import SolutionOption, ProviderResult
from app.services.pipeline import run_full_pipeline, make_failed_result
from app.services.scoring import score_all_results, build_ranking

logger = logging.getLogger(__name__)

# Groq Whisper + LLM pipelines ("open-source" group in the UI)
OPEN_SOURCE_SOLUTIONS = (
    SolutionOption.GROQ_SARVAM,
    SolutionOption.GROQ_GROQ,
)

# Sarvam STT + LLM pipelines
SARVAM_SOLUTIONS = (
    SolutionOption.SARVAM_SARVAM,
    SolutionOption.SARVAM_GROQ,
)


async def _run_solution(
    solution: SolutionOption,
    audio_path: str,
    language_code: str | None = None,
) -> ProviderResult:
    try:
        return await run_full_pipeline(audio_path, solution, language_code=language_code)
    except Exception as exc:
        logger.exception("Pipeline %s failed", solution.value)
        return make_failed_result(solution, str(exc))


async def get_all_results(
    audio_path: str,
    language_code: str | None = None,
) -> tuple[list[ProviderResult], dict]:
    """
    Run all provider pipelines concurrently.
    Open-source (Groq) and Sarvam tasks start at the same time via create_task.
    """
    open_source_tasks = [
        asyncio.create_task(
            _run_solution(solution, audio_path, language_code),
            name=f"pipeline-{solution.value}",
        )
        for solution in OPEN_SOURCE_SOLUTIONS
    ]
    sarvam_tasks = [
        asyncio.create_task(
            _run_solution(solution, audio_path, language_code),
            name=f"pipeline-{solution.value}",
        )
        for solution in SARVAM_SOLUTIONS
    ]

    all_tasks = open_source_tasks + sarvam_tasks
    raw_results = await asyncio.gather(*all_tasks, return_exceptions=True)

    results: list[ProviderResult] = []
    all_solutions = list(OPEN_SOURCE_SOLUTIONS) + list(SARVAM_SOLUTIONS)
    for solution, item in zip(all_solutions, raw_results):
        if isinstance(item, Exception):
            results.append(make_failed_result(solution, str(item)))
            metrics.record_provider_error(solution.value)
        else:
            results.append(item)
            if item.status in {"failed", "rate_limited"}:
                metrics.record_provider_error(item.solution_id)
                obs_logger.warning(
                    "provider_pipeline_failed",
                    solution_id=item.solution_id,
                    status=item.status,
                    runtime_seconds=item.total_runtime_seconds,
                )
            elif item.analysis and item.status == "completed":
                obs_logger.info(
                    "provider_pipeline_completed",
                    solution_id=item.solution_id,
                    sentiment=item.analysis.sentiment,
                    confidence=item.analysis.confidence,
                    runtime_seconds=item.total_runtime_seconds,
                )

    scored = score_all_results(results, audio_path)
    ranking = build_ranking(scored)
    return scored, ranking


async def run_all_comparisons(
    audio_path: str,
    language_code: str | None = None,
) -> tuple[list[ProviderResult], dict]:
    """Backward-compatible entry point used by the job runner."""
    return await get_all_results(audio_path, language_code=language_code)


def build_provider_groups(results: list[ProviderResult]) -> dict[str, list[ProviderResult]]:
    open_source_ids = {s.value for s in OPEN_SOURCE_SOLUTIONS}
    sarvam_ids = {s.value for s in SARVAM_SOLUTIONS}
    return {
        "open_source": [r for r in results if r.solution_id in open_source_ids],
        "sarvam": [r for r in results if r.solution_id in sarvam_ids],
    }


async def retry_solutions(
    audio_path: str,
    solution_ids: list[str],
    existing_results: list[ProviderResult],
    language_code: str | None = None,
) -> tuple[list[ProviderResult], dict]:
    by_id = {r.solution_id: r for r in existing_results}
    tasks: list[asyncio.Task] = []
    solutions: list[SolutionOption] = []

    for solution_id in solution_ids:
        try:
            solution = SolutionOption(solution_id)
        except ValueError:
            continue
        solutions.append(solution)
        tasks.append(
            asyncio.create_task(
                _run_solution(solution, audio_path, language_code),
                name=f"retry-{solution.value}",
            )
        )

    if not tasks:
        scored = score_all_results(existing_results, audio_path)
        return scored, build_ranking(scored)

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    for solution, item in zip(solutions, raw_results):
        if isinstance(item, Exception):
            by_id[solution.value] = make_failed_result(solution, str(item))
        else:
            by_id[solution.value] = item

    merged = [by_id[s.value] for s in SolutionOption if s.value in by_id]
    scored = score_all_results(merged, audio_path)
    ranking = build_ranking(scored)
    return scored, ranking
