/**
 * Client-side invalid-call rules — mirrors backend call_validity.py.
 * API fields (sentiment_label, is_valid_call) take precedence when present.
 */

import { getCanonicalResult } from './canonicalResult';

const MIN_TRANSCRIPT_CHARS = 20;
const MIN_SUMMARY_CHARS = 15;
const LOW_CONFIDENCE_THRESHOLD = 0.15;

const INVALID_SENTIMENT_TOKENS = new Set([
  'invalid',
  'unclassified',
  'unknown',
  'n/a',
  'na',
  'none',
  'unclear',
  'insufficient',
]);

const NOISE_TRANSCRIPT_PATTERNS = [
  /^\[?\s*silence\s*\]?\.?$/i,
  /^no\s+speech/i,
  /^inaudible/i,
  /^unable\s+to\s+transcribe/i,
  /^transcription\s+failed/i,
  /^[\s.\-_,;:!?…]*$/,
];

function normalizeSentimentToken(sentiment) {
  if (!sentiment) return null;
  const value = String(sentiment).trim().toLowerCase();
  if (INVALID_SENTIMENT_TOKENS.has(value)) return null;
  if (value === 'positive' || value === 'pos') return 'positive';
  if (value === 'negative' || value === 'neg') return 'negative';
  if (value === 'neutral' || value === 'mixed' || value === 'neu') return 'neutral';
  return null;
}

function isNoiseTranscript(transcript) {
  const stripped = (transcript || '').trim();
  if (!stripped) return true;
  return NOISE_TRANSCRIPT_PATTERNS.some((pattern) => pattern.test(stripped));
}

function assessProviderResult(result) {
  if (!result || result.status !== 'completed') {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Analysis did not complete successfully',
    };
  }

  const transcript = (result.transcript || '').trim();
  if (!transcript) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Empty transcript — no speech content detected',
    };
  }

  if (transcript.length < MIN_TRANSCRIPT_CHARS) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Transcript too short to classify sentiment reliably',
    };
  }

  if (isNoiseTranscript(transcript)) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Transcript contains only silence or unusable audio content',
    };
  }

  const rawSentiment = (result.analysis?.sentiment || '').trim().toLowerCase();
  if (INVALID_SENTIMENT_TOKENS.has(rawSentiment)) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Insufficient content to infer sentiment',
    };
  }

  const sentimentLabel = normalizeSentimentToken(result.analysis?.sentiment);
  const summary = (result.analysis?.summary || '').trim();
  const confidence = result.analysis?.confidence ?? 0;

  if (!sentimentLabel) {
    if (confidence < LOW_CONFIDENCE_THRESHOLD && summary.length < MIN_SUMMARY_CHARS) {
      return {
        isValidCall: false,
        sentimentLabel: 'invalid',
        invalidReason: 'Low confidence and no useful summary — cannot classify reliably',
      };
    }
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Sentiment could not be classified from available content',
    };
  }

  if (confidence < LOW_CONFIDENCE_THRESHOLD && summary.length < MIN_SUMMARY_CHARS) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'Confidence too low with insufficient summary for reliable classification',
    };
  }

  return { isValidCall: true, sentimentLabel, invalidReason: null };
}

/** Derive validity from a recording when API fields are absent. */
export function deriveRecordingAssessment(record) {
  const aggregateStatus = record?.aggregate_status || record?.status || 'unknown';
  const resultsReady = record?.results_ready === true;
  const canonical = getCanonicalResult(record);

  if (!resultsReady) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: null,
    };
  }

  if (aggregateStatus === 'failed' && !canonical) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: record?.error || 'Analysis failed — no usable result produced',
    };
  }

  if (!canonical) {
    return {
      isValidCall: false,
      sentimentLabel: 'invalid',
      invalidReason: 'No successful analysis output from any solution',
    };
  }

  return assessProviderResult(canonical);
}

/**
 * Unified recording assessment — prefers API-normalized fields, falls back to client derivation.
 */
export function getRecordingAssessment(record) {
  if (record?.sentiment_label != null && record?.is_valid_call != null) {
    return {
      isValidCall: record.is_valid_call,
      sentimentLabel: record.sentiment_label,
      invalidReason: record.invalid_reason || null,
    };
  }
  return deriveRecordingAssessment(record);
}

export function getSentimentLabel(record) {
  return getRecordingAssessment(record).sentimentLabel;
}

export function isValidCall(record) {
  return getRecordingAssessment(record).isValidCall;
}

export function getInvalidReason(record) {
  return getRecordingAssessment(record).invalidReason;
}
