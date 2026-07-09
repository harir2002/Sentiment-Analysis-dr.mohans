/**
 * Primary analysis result for a recording (single Sarvam pipeline).
 */

/** Completed ProviderResult for the recording, or null. */
export function getCanonicalResult(record) {
  const results = record?.results || [];
  const completed = results.filter((r) => r.status === 'completed' && r.analysis);
  if (completed.length === 0) return null;

  const preferredId = record.final_solution_id || record.ranking?.winner?.solution_id;
  if (preferredId) {
    const preferred = completed.find((r) => r.solution_id === preferredId);
    if (preferred) return preferred;
  }

  return completed[0];
}

/** Normalize a raw sentiment string to 'positive' | 'neutral' | 'negative' | null. */
export function normalizeSentiment(sentiment) {
  if (!sentiment) return null;
  const value = String(sentiment).toLowerCase().trim();
  if (value === 'positive') return 'positive';
  if (value === 'negative') return 'negative';
  if (value === 'neutral' || value === 'mixed') return 'neutral';
  return null;
}

/** Canonical sentiment for a recording (raw string), or null. */
export function getCanonicalSentiment(record) {
  return record?.final_sentiment || getCanonicalResult(record)?.analysis?.sentiment || null;
}

/** @deprecated Confidence hidden from UI — kept for backward compatibility. */
export function getCanonicalConfidence(record) {
  if (record?.final_confidence != null) return record.final_confidence;
  const confidence = getCanonicalResult(record)?.analysis?.confidence;
  return confidence != null ? confidence : null;
}

/** @deprecated Score hidden from UI — kept for backward compatibility. */
export function getCanonicalScore(record) {
  if (record?.final_overall_score != null) return record.final_overall_score;
  const score = getCanonicalResult(record)?.overall_score;
  return score != null ? score : null;
}
