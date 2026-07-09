/** Single active pipeline — Sarvam STT + Sarvam LLM (shown as "Call Analysis" in UI). */
export const SOLUTION_ORDER = [
  {
    id: 'sarvam_stt_sarvam_llm',
    label: 'Call Analysis',
  },
];

export const DISPLAY_LABEL = 'Call Analysis';

export function orderSolutionResults(results = []) {
  const byId = Object.fromEntries((results || []).map((r) => [r.solution_id, r]));
  return SOLUTION_ORDER.map(({ id, label }) => {
    const existing = byId[id];
    if (existing) {
      return { ...existing, label: DISPLAY_LABEL };
    }
    return {
      solution_id: id,
      label: DISPLAY_LABEL,
      status: 'pending',
      transcript: '',
      error: 'No result available',
      analysis: null,
    };
  });
}

export function getPrimaryResult(results = [], ranking = null) {
  const ordered = orderSolutionResults(results);
  const completed = ordered.find((r) => r.status === 'completed' && r.analysis);
  if (completed) return completed;
  return ordered[0] || null;
}
