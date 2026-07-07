import wave
import contextlib
from pathlib import Path

from app.core.weights import load_weights_config
from app.models.schemas import (
    ProviderResult,
    ComparisonRanking,
    RankingEntry,
    ScoreBreakdown,
)


def _estimate_audio_minutes(audio_path: str | None) -> float:
    if not audio_path or not Path(audio_path).exists():
        return 2.0
    try:
        with contextlib.closing(wave.open(audio_path, "r")) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return max(frames / float(rate) / 60.0, 0.5)
    except Exception:
        return 2.0


def _stt_quality_score(result: ProviderResult) -> float:
    if result.status != "completed":
        return 0.0
    text = result.transcript.strip()
    if not text:
        return 0.0
    length_score = min(len(text.split()) / 80.0, 1.0)
    structure_score = 0.3 if ":" in text or "\n" in text else 0.15
    return round(min(length_score * 0.7 + structure_score + 0.1, 1.0), 3)


def _llm_quality_score(result: ProviderResult) -> float:
    if result.status != "completed":
        return 0.0
    a = result.analysis
    score = 0.0
    if a.summary:
        score += 0.25
    if a.key_issues:
        score += 0.20
    if a.action_items:
        score += 0.20
    if a.sentiment and a.sentiment != "unknown":
        score += 0.15
    if a.resolution_status and a.resolution_status != "unknown":
        score += 0.10
    if a.notes:
        score += 0.05
    score += min(a.confidence, 1.0) * 0.10
    return round(min(score, 1.0), 3)


def _latency_score(runtime: float, benchmark: float) -> float:
    if runtime <= 0:
        return 0.0
    ratio = runtime / benchmark
    return round(max(0.0, min(1.0, 1.0 - (ratio - 0.5) * 0.5)), 3)


def _cost_score(estimated_cost: float, max_cost: float) -> float:
    if max_cost <= 0:
        return 1.0
    return round(max(0.0, min(1.0, 1.0 - (estimated_cost / max_cost))), 3)


def estimate_cost(stt_provider: str, llm_provider: str, audio_minutes: float) -> float:
    cfg = load_weights_config()
    costs = cfg.get("cost_per_minute", {})
    stt_cost = costs.get(stt_provider, 0.005) * audio_minutes
    llm_cost = costs.get(llm_provider, 0.002) * audio_minutes
    return round(stt_cost + llm_cost, 5)


def score_result(result: ProviderResult, audio_path: str | None, all_costs: list[float]) -> ProviderResult:
    cfg = load_weights_config()
    weights = cfg.get("weights", {})
    benchmark = cfg.get("latency_benchmark_seconds", 30)
    indian_scores = cfg.get("indian_language_scores", {})
    compliance_scores = cfg.get("compliance_scores", {})

    audio_minutes = _estimate_audio_minutes(audio_path)
    result.estimated_cost_usd = estimate_cost(
        result.stt_provider, result.llm_provider, audio_minutes
    )

    stt_q = _stt_quality_score(result)
    llm_q = _llm_quality_score(result)
    latency = _latency_score(result.total_runtime_seconds, benchmark)
    max_cost = max(all_costs) if all_costs else result.estimated_cost_usd or 0.01
    cost = _cost_score(result.estimated_cost_usd, max_cost)
    indian = (
        indian_scores.get(result.stt_provider, 0.7) * 0.6
        + indian_scores.get(result.llm_provider, 0.7) * 0.4
    )
    compliance = (
        compliance_scores.get(result.stt_provider, 0.6) * 0.5
        + compliance_scores.get(result.llm_provider, 0.6) * 0.5
    )

    overall = (
        stt_q * weights.get("stt_quality", 0.25)
        + llm_q * weights.get("llm_analysis_quality", 0.25)
        + latency * weights.get("latency", 0.15)
        + cost * weights.get("cost", 0.10)
        + indian * weights.get("indian_language_suitability", 0.15)
        + compliance * weights.get("compliance_control", 0.10)
    )

    result.scores = {
        "stt_quality": stt_q,
        "llm_analysis_quality": llm_q,
        "latency": latency,
        "cost": cost,
        "indian_language_suitability": round(indian, 3),
        "compliance_control": round(compliance, 3),
    }
    result.overall_score = round(overall, 3)
    return result


def score_all_results(results: list[ProviderResult], audio_path: str | None = None) -> list[ProviderResult]:
    costs = [
        estimate_cost(r.stt_provider, r.llm_provider, _estimate_audio_minutes(audio_path))
        for r in results
    ]
    return [score_result(r, audio_path, costs) for r in results]


def _reason_text(entry: RankingEntry) -> str:
    b = entry.score_breakdown
    parts = []
    if b.stt_quality >= 0.7:
        parts.append("strong transcription quality")
    if b.llm_analysis_quality >= 0.7:
        parts.append("rich analysis output")
    if b.latency >= 0.7:
        parts.append("fast processing")
    if b.cost >= 0.7:
        parts.append("lower estimated cost")
    if b.indian_language_suitability >= 0.8:
        parts.append("excellent Indian language fit")
    if b.compliance_control >= 0.8:
        parts.append("strong compliance posture")
    if not parts:
        parts.append("balanced overall performance")
    return ", ".join(parts)


def build_ranking(results: list[ProviderResult]) -> dict:
    sorted_results = sorted(results, key=lambda r: r.overall_score, reverse=True)

    rankings: list[RankingEntry] = []
    for i, r in enumerate(sorted_results, start=1):
        breakdown = ScoreBreakdown(
            stt_quality=r.scores.get("stt_quality", 0),
            llm_analysis_quality=r.scores.get("llm_analysis_quality", 0),
            latency=r.scores.get("latency", 0),
            cost=r.scores.get("cost", 0),
            indian_language_suitability=r.scores.get("indian_language_suitability", 0),
            compliance_control=r.scores.get("compliance_control", 0),
            overall=r.overall_score,
        )
        entry = RankingEntry(
            rank=i,
            solution_id=r.solution_id,
            label=r.label,
            overall_score=r.overall_score,
            score_breakdown=breakdown,
        )
        entry.recommendation_reason = _reason_text(entry)
        rankings.append(entry)

    winner = rankings[0] if rankings else None
    summary = ""
    if winner:
        summary = (
            f"Recommended: {winner.label} (score {winner.overall_score:.2f}). "
            f"Key strengths: {winner.recommendation_reason}."
        )

    ranking = ComparisonRanking(
        winner=winner,
        rankings=rankings,
        recommendation_summary=summary,
    )
    return ranking.model_dump()
