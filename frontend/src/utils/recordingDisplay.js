import {
  getCanonicalResult,
  getCanonicalConfidence,
} from './canonicalResult';
import { getRecordingAssessment } from './callValidity';

/** Canonical recommendation / next step for the winning solution. */
export function getCanonicalRecommendation(record) {
  const fromApi = record?.final_recommendation;
  if (fromApi && String(fromApi).trim()) return String(fromApi).trim();
  const canonical = getCanonicalResult(record);
  const action = canonical?.analysis?.recommended_action;
  return action && String(action).trim() ? String(action).trim() : null;
}

/** Badge-ready sentiment: positive | neutral | negative | invalid */
export function getDisplaySentiment(record) {
  return getRecordingAssessment(record).sentimentLabel;
}

/** Whether this recording has a classifiable sentiment (not invalid). */
export function isClassifiableRecording(record) {
  const { isValidCall, sentimentLabel } = getRecordingAssessment(record);
  return isValidCall && sentimentLabel !== 'invalid';
}

/** Confidence for valid calls only — invalid calls return null for averages. */
export function getValidConfidence(record) {
  if (!isClassifiableRecording(record)) return null;
  return getCanonicalConfidence(record);
}

/** Short preview text for list rows: recommendation first, then summary. */
export function getRecordPreviewText(record, maxLen = 120) {
  const recommendation = getCanonicalRecommendation(record);
  const canonical = getCanonicalResult(record);
  const text =
    recommendation ||
    canonical?.analysis?.summary ||
    getRecordingAssessment(record).invalidReason ||
    '';

  if (!text) return null;
  return text.length > maxLen ? `${text.substring(0, maxLen)}…` : text;
}

/** Truncate recommendation for compact list display. */
export function getRecommendationSnippet(record, maxLen = 80) {
  const text = getCanonicalRecommendation(record);
  if (!text) return null;
  return text.length > maxLen ? `${text.substring(0, maxLen)}…` : text;
}
