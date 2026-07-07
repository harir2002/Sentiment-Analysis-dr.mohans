/**
 * Canonical result normalization.
 *
 * Each recording carries 4 per-solution outputs (results[]). Dashboard KPIs
 * must count every recording exactly once, so all summary metrics read the
 * single canonical result resolved here — never the raw per-solution list.
 *
 * Canonical rule (mirrors backend derive_canonical_result):
 *   1. the solution referenced by record.final_solution_id (backend winner),
 *   2. else the ranking winner if it completed,
 *   3. else the completed solution with the highest overall_score.
 */

/** Full ProviderResult for the canonical solution, or null if none completed. */
export function getCanonicalResult(record) {
  const results = record?.results || [];
  const completed = results.filter((r) => r.status === 'completed' && r.analysis);
  if (completed.length === 0) return null;

  const preferredId = record.final_solution_id || record.ranking?.winner?.solution_id;
  if (preferredId) {
    const preferred = completed.find((r) => r.solution_id === preferredId);
    if (preferred) return preferred;
  }

  return completed.reduce((best, r) =>
    (r.overall_score || 0) > (best.overall_score || 0) ? r : best
  );
}

/** Normalize a raw sentiment string to 'positive' | 'neutral' | 'negative' | null. */
export function normalizeSentiment(sentiment) {
  if (!sentiment) return null;
  const value = String(sentiment).toLowerCase().trim();
  if (value === 'positive') return 'positive';
  if (value === 'negative') return 'negative';
  // "mixed" counts as neutral for dashboard aggregation
  if (value === 'neutral' || value === 'mixed') return 'neutral';
  return null;
}

/** Canonical sentiment for a recording (raw string), or null. */
export function getCanonicalSentiment(record) {
  return record?.final_sentiment || getCanonicalResult(record)?.analysis?.sentiment || null;
}

/** Canonical confidence as a 0–1 fraction, or null. */
export function getCanonicalConfidence(record) {
  if (record?.final_confidence != null) return record.final_confidence;
  const confidence = getCanonicalResult(record)?.analysis?.confidence;
  return confidence != null ? confidence : null;
}

/** Canonical overall score (0–1), or null. */
export function getCanonicalScore(record) {
  if (record?.final_overall_score != null) return record.final_overall_score;
  const score = getCanonicalResult(record)?.overall_score;
  return score != null ? score : null;
}
