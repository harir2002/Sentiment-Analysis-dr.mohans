import { getCanonicalResult } from './canonicalResult';
import { getRecordingAssessment } from './callValidity';
import {
  getValidConfidence,
  getCanonicalRecommendation,
  isClassifiableRecording,
} from './recordingDisplay';

/** Sentiment → numeric score for trend lines (invalid excluded). */
export function sentimentToScore(sentimentLabel) {
  if (sentimentLabel === 'positive') return 1;
  if (sentimentLabel === 'neutral') return 0.5;
  if (sentimentLabel === 'negative') return 0;
  return null;
}

const URGENT_PRIORITY_PATTERN = /high|urgent|critical/i;
const URGENT_RECOMMENDATION_PATTERN = /urgent|immediate|escalat|asap|complaint|callback/i;

/** Whether a recording needs immediate leadership attention. */
export function isUrgentAction(record) {
  if (!record?.results_ready) return false;

  const { sentimentLabel, isValidCall } = getRecordingAssessment(record);
  if (!isValidCall || sentimentLabel === 'invalid') return false;

  if (sentimentLabel === 'negative') return true;

  const canonical = getCanonicalResult(record);
  const analysis = canonical?.analysis || {};

  if (URGENT_PRIORITY_PATTERN.test(String(analysis.action_priority || ''))) return true;
  if (analysis.resolution_status === 'escalated') return true;

  const recommendation = getCanonicalRecommendation(record) || '';
  if (URGENT_RECOMMENDATION_PATTERN.test(recommendation)) return true;

  const confidence = getValidConfidence(record);
  if (sentimentLabel === 'neutral' && confidence != null && confidence < 0.45) return true;

  return false;
}

/** Full executive KPI layer — one unit per recording, invalid counted separately. */
export function computeDashboardKpis(records = []) {
  let positive = 0;
  let neutral = 0;
  let negative = 0;
  let invalid = 0;
  let urgentAction = 0;
  let totalConfidence = 0;
  let confidenceCount = 0;

  const total = records.length;
  const completed = records.filter((r) => r.aggregate_status === 'completed').length;
  const processing = records.filter(
    (r) => !r.aggregate_status || r.aggregate_status === 'running'
  ).length;
  const failed = records.filter((r) => r.aggregate_status === 'failed').length;

  const recentCount = records.filter((r) => {
    if (!r.created_at) return false;
    const created = new Date(r.created_at);
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return created > oneDayAgo;
  }).length;

  records.forEach((record) => {
    if (!record.results_ready) return;

    const { sentimentLabel, isValidCall } = getRecordingAssessment(record);

    if (!isValidCall || sentimentLabel === 'invalid') {
      invalid++;
      return;
    }

    if (sentimentLabel === 'positive') positive++;
    else if (sentimentLabel === 'neutral') neutral++;
    else if (sentimentLabel === 'negative') negative++;

    if (isUrgentAction(record)) urgentAction++;

    const confidence = getValidConfidence(record);
    if (confidence != null && confidence > 0) {
      totalConfidence += confidence;
      confidenceCount++;
    }
  });

  const callsAnalyzed = positive + neutral + negative;
  const avgConfidence =
    confidenceCount > 0 ? Math.round((totalConfidence / confidenceCount) * 100) : 0;

  const negativeShare =
    callsAnalyzed > 0 ? Math.round((negative / callsAnalyzed) * 100) : 0;

  return {
    total,
    callsAnalyzed,
    completed,
    processing,
    failed,
    positive,
    neutral,
    negative,
    invalid,
    urgentAction,
    avgConfidence,
    recentCount,
    negativeShare,
    callsAnalysed: callsAnalyzed,
  };
}

function dayKey(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function weekKey(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d);
  monday.setDate(diff);
  monday.setHours(0, 0, 0, 0);
  return monday.getTime();
}

function formatDayLabel(timestamp) {
  return new Date(timestamp).toLocaleDateString('en-US', { weekday: 'short' });
}

function formatDateLabel(timestamp) {
  return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatWeekLabel(timestamp) {
  const start = new Date(timestamp);
  const end = new Date(timestamp);
  end.setDate(end.getDate() + 6);
  const sameMonth = start.getMonth() === end.getMonth();
  if (sameMonth) {
    return `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}–${end.getDate()}`;
  }
  return `${formatDateLabel(start.getTime())} – ${formatDateLabel(end.getTime())}`;
}

/** Donut/pie data for overall sentiment mix (canonical, one per recording). */
export function computeSentimentMix(records = []) {
  const kpis = computeDashboardKpis(records);
  return [
    { name: 'Positive', value: kpis.positive, color: '#22c55e' },
    { name: 'Neutral', value: kpis.neutral, color: '#f59e0b' },
    { name: 'Negative', value: kpis.negative, color: '#ef4444' },
  ].filter((item) => item.value > 0);
}

/** Group canonical sentiments by day for stacked bar chart. */
export function computeSentimentByDay(records = []) {
  const buckets = new Map();

  records.forEach((record) => {
    if (!record.created_at || !record.results_ready) return;

    const { sentimentLabel, isValidCall } = getRecordingAssessment(record);
    if (!isValidCall || sentimentLabel === 'invalid') return;
    if (!['positive', 'neutral', 'negative'].includes(sentimentLabel)) return;

    const key = dayKey(record.created_at);
    if (!buckets.has(key)) {
      buckets.set(key, {
        timestamp: key,
        label: formatDayLabel(key),
        dateLabel: formatDateLabel(key),
        positive: 0,
        neutral: 0,
        negative: 0,
        total: 0,
      });
    }

    const bucket = buckets.get(key);
    bucket[sentimentLabel]++;
    bucket.total++;
  });

  const rows = Array.from(buckets.values()).sort((a, b) => a.timestamp - b.timestamp);
  const spanMs = rows.length > 1 ? rows[rows.length - 1].timestamp - rows[0].timestamp : 0;
  const useWeekdays = spanMs <= 7 * 24 * 60 * 60 * 1000;

  return rows.map((row) => ({
    ...row,
    name: useWeekdays ? row.label : row.dateLabel,
  }));
}

/** Weekly call volume with sentiment breakdown — canonical per recording. */
export function computeWeeklyVolume(records = []) {
  const buckets = new Map();

  records.forEach((record) => {
    if (!record.created_at || !record.results_ready) return;

    const { sentimentLabel, isValidCall } = getRecordingAssessment(record);
    const key = weekKey(record.created_at);

    if (!buckets.has(key)) {
      buckets.set(key, {
        timestamp: key,
        name: formatWeekLabel(key),
        total: 0,
        positive: 0,
        neutral: 0,
        negative: 0,
        invalid: 0,
      });
    }

    const bucket = buckets.get(key);
    bucket.total++;
    if (!isValidCall || sentimentLabel === 'invalid') bucket.invalid++;
    else if (sentimentLabel === 'positive') bucket.positive++;
    else if (sentimentLabel === 'neutral') bucket.neutral++;
    else if (sentimentLabel === 'negative') bucket.negative++;
  });

  return Array.from(buckets.values()).sort((a, b) => a.timestamp - b.timestamp);
}

/** Average sentiment score per day — valid classifiable calls only. */
export function computeSentimentTrend(records = []) {
  const buckets = new Map();

  records.forEach((record) => {
    if (!record.created_at || !record.results_ready) return;

    const { sentimentLabel, isValidCall } = getRecordingAssessment(record);
    if (!isValidCall || sentimentLabel === 'invalid') return;

    const score = sentimentToScore(sentimentLabel);
    if (score == null) return;

    const key = dayKey(record.created_at);
    if (!buckets.has(key)) {
      buckets.set(key, {
        timestamp: key,
        label: formatDayLabel(key),
        dateLabel: formatDateLabel(key),
        scoreSum: 0,
        count: 0,
      });
    }

    const bucket = buckets.get(key);
    bucket.scoreSum += score;
    bucket.count++;
  });

  const spanMs =
    buckets.size > 1 ? Math.max(...buckets.keys()) - Math.min(...buckets.keys()) : 0;
  const useWeekdays = spanMs <= 7 * 24 * 60 * 60 * 1000;

  return Array.from(buckets.values())
    .sort((a, b) => a.timestamp - b.timestamp)
    .map((row) => ({
      name: useWeekdays ? row.label : row.dateLabel,
      score: Math.round((row.scoreSum / row.count) * 100),
      count: row.count,
    }));
}

export function getTrendInsight(trendData = []) {
  if (trendData.length < 2) return null;

  const first = trendData[0].score;
  const last = trendData[trendData.length - 1].score;
  const delta = last - first;

  if (delta >= 8) return 'Customer sentiment is improving over this period.';
  if (delta <= -8) return 'Customer sentiment is declining — review negative drivers.';
  return 'Customer sentiment has remained relatively stable.';
}

/** Aggregate common recommendations from valid canonical results. */
export function computeCommonRecommendations(records = [], limit = 5) {
  const counts = new Map();

  records.forEach((record) => {
    if (!record.results_ready) return;
    const { isValidCall } = getRecordingAssessment(record);
    const text = getCanonicalRecommendation(record);
    if (!text || !isValidCall) return;

    const normalized = text.trim();
    if (normalized.length < 8) return;
    counts.set(normalized, (counts.get(normalized) || 0) + 1);
  });

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([text, count]) => ({ text, count }));
}

/** Top complaint/issue themes from canonical key_issues. */
export function computeIssueThemes(records = [], limit = 8) {
  const counts = new Map();
  const displayLabels = new Map();

  records.forEach((record) => {
    if (!record.results_ready || !isClassifiableRecording(record)) return;

    const issues = getCanonicalResult(record)?.analysis?.key_issues || [];
    issues.forEach((issue) => {
      const trimmed = String(issue || '').trim();
      if (trimmed.length < 3) return;
      const key = trimmed.toLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
      if (!displayLabels.has(key)) displayLabels.set(key, trimmed);
    });
  });

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([key, count]) => ({ theme: displayLabels.get(key) || key, count }));
}

/** Breakdown of why calls could not be classified. */
export function computeInvalidReasons(records = []) {
  const counts = new Map();

  records.forEach((record) => {
    if (!record.results_ready) return;
    const { isValidCall, invalidReason } = getRecordingAssessment(record);
    if (isValidCall) return;
    const reason = invalidReason || 'Could not classify this call';
    counts.set(reason, (counts.get(reason) || 0) + 1);
  });

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([reason, count]) => ({ reason, count }));
}

/** Calls flagged for immediate leadership review. */
export function computeCallsNeedingReview(records = [], limit = 8) {
  return records
    .filter((r) => r.results_ready && isUrgentAction(r))
    .map((r) => ({
      jobId: r.job_id,
      filename: r.audio_filename || 'Unknown recording',
      sentiment: getRecordingAssessment(r).sentimentLabel,
      recommendation: getCanonicalRecommendation(r),
      confidence: getValidConfidence(r),
      createdAt: r.created_at,
    }))
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, limit);
}

/** One-line executive headline synthesizing KPI + trend. */
export function computeExecutiveHeadline(records = []) {
  const kpis = computeDashboardKpis(records);

  if (kpis.total === 0) {
    return 'Add call recordings one by one to build your executive sentiment report.';
  }

  if (kpis.callsAnalyzed === 0 && kpis.processing > 0) {
    return `${kpis.processing} recording${kpis.processing !== 1 ? 's' : ''} in progress — dashboard will update as analysis completes.`;
  }

  const parts = [];

  if (kpis.callsAnalyzed > 0) {
    parts.push(
      `${kpis.callsAnalyzed} call${kpis.callsAnalyzed !== 1 ? 's' : ''} classified (${kpis.positive} positive, ${kpis.neutral} neutral, ${kpis.negative} negative)`
    );
  }

  if (kpis.urgentAction > 0) {
    parts.push(`${kpis.urgentAction} require immediate action`);
  } else if (kpis.negative > 0) {
    parts.push(`${kpis.negativeShare}% negative sentiment among classified calls`);
  }

  const trend = getTrendInsight(computeSentimentTrend(records));
  if (trend) parts.push(trend);

  return `${parts.join('. ')}.`;
}
