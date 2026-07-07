import { getCanonicalResult, getCanonicalConfidence } from './canonicalResult';
import { getRecordingAssessment } from './callValidity';
import {
  getCanonicalRecommendation,
  getDisplaySentiment,
} from './recordingDisplay';
import { isUrgentAction } from './dashboardAnalytics';

function formatTicketId(jobId) {
  if (!jobId) return 'TKT-UNKNOWN';
  return `TKT-${String(jobId).slice(0, 8).toUpperCase()}`;
}

function formatRecordingId(index) {
  return `Recording_ID_${String((index ?? 0) + 1).padStart(3, '0')}`;
}

function derivePriority(record, sentiment, analysis) {
  const explicit = String(analysis?.action_priority || '').trim();
  if (explicit) return explicit;

  if (!getRecordingAssessment(record).isValidCall) return '—';
  if (isUrgentAction(record)) return 'High';
  if (sentiment === 'negative') return 'High';
  if (sentiment === 'neutral') return 'Medium';
  if (sentiment === 'positive') return 'Low';
  return 'Medium';
}

/**
 * Map a job/recording API record to a CRM-style ticket view model.
 * No separate ticket entity — one ticket per recording (job_id).
 */
export function buildTicketFromRecord(record, recordingIndex = 0) {
  const assessment = getRecordingAssessment(record);
  const canonical = getCanonicalResult(record);
  const analysis = canonical?.analysis || {};
  const sentiment = getDisplaySentiment(record);
  const confidence = getCanonicalConfidence(record);

  return {
    ticketId: formatTicketId(record?.job_id),
    jobId: record?.job_id,
    recordingId: formatRecordingId(recordingIndex),
    filename: record?.audio_filename || 'Unknown recording',
    callReference: record?.call_reference || null,
    createdAt: record?.created_at || null,
    completedAt: record?.completed_at || null,
    ingestedAt: record?.ingested_at || null,
    status: record?.aggregate_status || record?.status || 'unknown',
    resultsReady: record?.results_ready === true,
    sentiment,
    confidence,
    confidencePercent: confidence != null ? Math.round(confidence * 100) : null,
    isValidCall: assessment.isValidCall,
    invalidReason: assessment.invalidReason,
    recommendation: getCanonicalRecommendation(record),
    summary: analysis.summary || null,
    keyIssues: analysis.key_issues || [],
    actionItems: analysis.action_items || [],
    actionPriority: derivePriority(record, sentiment, analysis),
    resolutionStatus: analysis.resolution_status || null,
    escalationStatus: analysis.escalation_status || null,
    assignedTeam: analysis.assigned_team || null,
    sourceType: record?.source_type || 'upload',
    sourceUrl: record?.source_url || null,
    transcript: canonical?.transcript || null,
    canonicalResult: canonical,
    canonicalSolutionId: record?.final_solution_id || canonical?.solution_id || null,
    canonicalSolutionLabel: canonical?.label || null,
    overallScore: record?.final_overall_score ?? canonical?.overall_score ?? null,
    results: record?.results || [],
    ranking: record?.ranking || null,
    error: record?.error || null,
    totalRuntimeSeconds: record?.total_runtime_seconds ?? null,
    sttLanguage: record?.stt_language_code || null,
    isUrgent: isUrgentAction(record),
    needsReview: isUrgentAction(record) || sentiment === 'negative',
    audioUrl: record?.source_url || null,
    winnerReason:
      record?.ranking?.winner?.recommendation_reason ||
      record?.ranking?.recommendation_summary ||
      null,
    sttModel: canonical?.stt_model || null,
    llmModel: canonical?.llm_model || null,
  };
}

export function findRecordingIndex(records, jobId) {
  const sorted = [...(records || [])].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );
  const idx = sorted.findIndex((r) => r.job_id === jobId);
  return idx >= 0 ? idx : 0;
}
