import { Card, CardHeader, SentimentBadge, Alert } from './ui';
import { getCanonicalResult } from '../utils/canonicalResult';
import {
  getCanonicalRecommendation,
  getDisplaySentiment,
} from '../utils/recordingDisplay';
import { getRecordingAssessment } from '../utils/callValidity';
import { getCanonicalConfidence } from '../utils/canonicalResult';

/**
 * Canonical final result banner for the detailed comparison view.
 * Shows best-performing solution sentiment, recommendation, and invalid status.
 */
export default function CanonicalResultBanner({ results, ranking, jobMeta = null }) {
  const record = jobMeta || { results, ranking, results_ready: true };
  const canonical = getCanonicalResult(record);
  const assessment = getRecordingAssessment(record);
  const sentiment = getDisplaySentiment(record);
  const recommendation = getCanonicalRecommendation(record);
  const confidence = getCanonicalConfidence(record);
  const confidencePct = confidence != null ? Math.round(confidence * 100) : null;

  if (!canonical && !assessment.invalidReason) return null;

  const isInvalid = !assessment.isValidCall || assessment.sentimentLabel === 'invalid';

  return (
    <Card className="canonical-result-banner">
      <CardHeader
        title="Final Result"
        subtitle={
          canonical
            ? `Best-performing solution: ${canonical.label}`
            : 'Canonical assessment for this recording'
        }
      />
      <div className="canonical-result-body">
        <div className="canonical-result-metrics">
          <div className="canonical-metric">
            <span className="canonical-metric-label">Sentiment</span>
            <SentimentBadge sentiment={sentiment} />
          </div>
          {confidencePct != null && (
            <div className="canonical-metric">
              <span className="canonical-metric-label">Confidence</span>
              <strong>{confidencePct}%</strong>
            </div>
          )}
          {canonical?.overall_score != null && (
            <div className="canonical-metric">
              <span className="canonical-metric-label">Score</span>
              <strong>{canonical.overall_score.toFixed(2)}</strong>
            </div>
          )}
        </div>

        {isInvalid && assessment.invalidReason && (
          <Alert variant="info" title="Unclassified Call">
            {assessment.invalidReason}
            {canonical?.transcript && (
              <span> Review the transcript below to inspect raw content.</span>
            )}
          </Alert>
        )}

        {recommendation && (
          <div className="canonical-recommendation">
            <span className="canonical-recommendation-label">Next Step</span>
            <p className="canonical-recommendation-text">{recommendation}</p>
          </div>
        )}

        {!recommendation && !isInvalid && canonical?.analysis?.summary && (
          <p className="canonical-summary-fallback">{canonical.analysis.summary}</p>
        )}
      </div>
    </Card>
  );
}
