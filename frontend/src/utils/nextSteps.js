function normalizeStep(text) {
  return String(text || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

function isDuplicateStep(a, b) {
  const left = normalizeStep(a);
  const right = normalizeStep(b);
  if (!left || !right) return false;
  if (left === right) return true;
  return left.includes(right) || right.includes(left);
}

/** Merged, deduplicated next steps for display. */
export function getNextStepsFromAnalysis(analysis) {
  if (!analysis) return [];

  const steps = [];
  const primary = analysis.recommended_action?.trim();
  if (primary) steps.push(primary);

  (analysis.action_items || []).forEach((item) => {
    const text = String(item || '').trim();
    if (!text) return;
    if (!steps.some((step) => isDuplicateStep(step, text))) {
      steps.push(text);
    }
  });

  return steps;
}

export function getPrimaryNextStep(analysis) {
  const steps = getNextStepsFromAnalysis(analysis);
  return steps[0] || null;
}
