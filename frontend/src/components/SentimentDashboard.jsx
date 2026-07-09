import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardHeader, Badge, Alert, Skeleton, EmptyState, SentimentBadge, ResultField } from './ui';
import { listCalls, deleteRecording } from '../services/api';
import ExecutiveDashboardHeader from './ExecutiveDashboardHeader';
import DashboardKpiRow from './DashboardKpiRow';
import DashboardSentimentStory from './DashboardSentimentStory';
import { StatusBadge } from './SolutionTab';
import {
  getCanonicalResult,
} from '../utils/canonicalResult';
import {
  getDisplaySentiment,
  getCanonicalRecommendation,
  getRecordPreviewText,
  getRecommendationSnippet,
} from '../utils/recordingDisplay';
import { getRecordingAssessment } from '../utils/callValidity';
import { navigateToTicket } from '../utils/appNavigation';
import styles from './SentimentDashboard.module.css';

// Generate stable display ID from current list position (not job_id)
function generateRecordingId(index) {
  return `Recording_ID_${String(index + 1).padStart(3, '0')}`;
}

// Helper function to confirm deletion
function confirmDelete(filename) {
  return window.confirm(
    `Are you sure you want to delete "${filename}"?\n\nThis action cannot be undone. All associated data will be deleted.`
  );
}

// DashboardSummary component - top-level metrics.
function DashboardSummary({ records }) {
  return (
    <div className={styles['dashboard-summary']}>
      <DashboardKpiRow records={records} />
    </div>
  );
}

// Compact result summary inside an expanded recording
function RecordResultSummary({ result }) {
  const completed = result?.status === 'completed' && result?.analysis;

  if (!result) {
    return <p className={styles['results-muted']}>No analysis result available.</p>;
  }

  if (!completed) {
    return (
      <p className={styles['solution-card-summary']}>
        {result.error || result.status_message || 'Awaiting analysis.'}
      </p>
    );
  }

  return (
    <>
      <div className={styles['solution-card-fields']}>
        <ResultField
          label="Sentiment"
          value={<SentimentBadge sentiment={result.analysis.sentiment} />}
        />
        <ResultField label="Status" value={<StatusBadge status={result.status} />} />
      </div>
      <p className={styles['solution-card-summary']}>
        {result.analysis.summary || 'No summary available.'}
      </p>
      {result.analysis.recommended_action && (
        <div className={styles['solution-card-action']}>
          <span className={styles['solution-card-action-label']}>Next Step</span>
          <p className={styles['solution-card-action-text']}>{result.analysis.recommended_action}</p>
        </div>
      )}
    </>
  );
}

// ExpandableRecordCard component - individual record with inline expansion
function ExpandableRecordCard({ record, index, onToggleExpand, expanded, onRemove }) {
  const recordId = generateRecordingId(index);

  // Canonical result: the single solution output that represents this recording
  const canonicalResult = getCanonicalResult(record);
  const assessment = getRecordingAssessment(record);
  const resultsReady = record.results_ready === true;
  const hasResults = resultsReady && (canonicalResult != null || assessment.invalidReason);
  const analysis = canonicalResult?.analysis;

  const sentiment = getDisplaySentiment(record);
  const isInvalid = !assessment.isValidCall || assessment.sentimentLabel === 'invalid';
  const recommendation = getCanonicalRecommendation(record);
  const previewText = getRecordPreviewText(record);
  const recommendationSnippet = getRecommendationSnippet(record, 72);
  const summary = analysis?.summary || 'No summary available.';
  const transcript = canonicalResult?.transcript || 'Transcript not available.';
  const status = record.aggregate_status || record.status || 'unknown';

  // Format date
  const createdDate = new Date(record.created_at);
  const formattedDate = createdDate.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
  const formattedTime = createdDate.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

  // Status badge
  let statusVariant = 'neutral';
  let statusLabel = status;
  if (status === 'completed' || status === 'running') statusVariant = 'warning';
  if (resultsReady) statusVariant = 'success';
  if (status === 'failed') statusVariant = 'danger';
  if (status === 'running') statusLabel = 'Processing';

  const truncatedSummary = previewText || (summary.length > 120 ? summary.substring(0, 120) + '…' : summary);

  const handleRemoveClick = async () => {
    if (confirmDelete(record.audio_filename || 'Recording')) {
      onRemove(record.job_id);
    }
  };

  const handleGoToTicket = (e) => {
    e.stopPropagation();
    navigateToTicket(record.job_id, record);
  };

  const panelId = `record-panel-${record.job_id}`;

  return (
    <article
      className={`${styles['record-card']} dash-work-item ${expanded ? `${styles['record-card-expanded']} dash-work-item-expanded` : ''}`}
      id={`record-${record.job_id}`}
    >
      {/* Collapsed header - always visible */}
      <button
        className={styles['record-card-header']}
        onClick={() => onToggleExpand(record.job_id)}
        type="button"
        aria-expanded={expanded}
        aria-controls={panelId}
        aria-label={`${expanded ? 'Collapse' : 'Expand'} details for ${record.audio_filename || 'recording'}`}
      >
        <div className={styles['record-card-header-left']}>
          <div className={styles['record-card-id']}>{recordId}</div>
          <div className={styles['record-card-title-block']}>
            <h4 className={styles['record-card-filename']}>{record.audio_filename || 'Unknown'}</h4>
            <p className={styles['record-card-meta']}>
              {formattedDate} at {formattedTime}
            </p>
          </div>
        </div>

        <div className={styles['record-card-header-right']}>
          {resultsReady && (
            <SentimentBadge sentiment={sentiment} />
          )}
          <Badge variant={statusVariant} className={styles['record-card-status']}>
            {statusLabel}
          </Badge>
          <button
            type="button"
            className={`${styles['ticket-cta-btn']} dash-btn dash-btn-primary`}
            onClick={handleGoToTicket}
          >
            Go to Ticket →
          </button>
          <button
            className={`${styles['record-card-remove-btn']} dash-btn dash-btn-danger`}
            onClick={(e) => {
              e.stopPropagation();
              handleRemoveClick();
            }}
            type="button"
            title="Delete this recording"
            aria-label={`Remove ${record.audio_filename || 'recording'}`}
          >
            Remove
          </button>
          <span
            className={`${styles['record-card-toggle']} ${expanded ? styles['record-card-toggle-open'] : ''}`}
            aria-hidden="true"
          />
        </div>
      </button>

      {/* Quick preview - visible in collapsed state */}
      {!expanded && hasResults && (
        <div className={styles['record-card-preview']}>
          {recommendationSnippet && (
            <p className={styles['record-card-recommendation']}>
              <span className={styles['preview-label']}>Next step:</span> {recommendationSnippet}
            </p>
          )}
          <p className={styles['record-card-summary']}>{truncatedSummary}</p>
        </div>
      )}

      {/* Expanded content — animated panel */}
      <div
        id={panelId}
        className={`${styles['record-expand-panel']} ${expanded ? styles['record-expand-panel-open'] : ''}`}
        aria-hidden={!expanded}
      >
        <div className={styles['record-expand-inner']}>
        {expanded && (
        <div className={styles['record-card-expanded-content']}>
          {!resultsReady && status !== 'failed' && (
            <Alert variant="info" title="Analysis in Progress">
              This recording is being analyzed. Check back soon for results.
            </Alert>
          )}

          {status === 'failed' && (
            <Alert variant="danger" title="Analysis Failed">
              {record.error || 'An error occurred during analysis. Please try again.'}
            </Alert>
          )}

          {hasResults && (
            <>
              {/* Metadata section */}
              <div className={styles['record-expanded-section']}>
                <h5 className={styles['section-title']}>Recording Information</h5>
                <div className={styles['metadata-grid']}>
                  <div className={styles['metadata-item']}>
                    <span className={styles['metadata-label']}>Recording ID</span>
                    <span className={styles['metadata-value']}>{recordId}</span>
                  </div>
                  <div className={styles['metadata-item']}>
                    <span className={styles['metadata-label']}>File Name</span>
                    <span className={styles['metadata-value']}>{record.audio_filename || '—'}</span>
                  </div>
                  <div className={styles['metadata-item']}>
                    <span className={styles['metadata-label']}>Analyzed Date</span>
                    <span className={styles['metadata-value']}>{formattedDate}</span>
                  </div>
                  {record.total_runtime_seconds != null && (
                    <div className={styles['metadata-item']}>
                      <span className={styles['metadata-label']}>Processing Time</span>
                      <span className={styles['metadata-value']}>{record.total_runtime_seconds.toFixed(1)}s</span>
                    </div>
                  )}
                  {record.stt_language_code && (
                    <div className={styles['metadata-item']}>
                      <span className={styles['metadata-label']}>Language</span>
                      <span className={styles['metadata-value']}>{record.stt_language_code}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Analysis result */}
              <div className={styles['record-expanded-section']}>
                <h5 className={styles['section-title']}>Call Analysis</h5>

                {isInvalid && assessment.invalidReason && (
                  <Alert variant="info" title="Unclassified Call">
                    {assessment.invalidReason}
                  </Alert>
                )}

                <RecordResultSummary result={canonicalResult} />
              </div>

              {/* Next Step */}
              {recommendation && (
                <div className={styles['record-expanded-section']}>
                  <h5 className={styles['section-title']}>Next Steps</h5>
                  <div className={styles['action-box']}>
                    <p className={styles['action-text']}>{recommendation}</p>
                  </div>
                </div>
              )}

              {/* Summary section */}
              <div className={styles['record-expanded-section']}>
                <h5 className={styles['section-title']}>Summary</h5>
                <p className={styles['record-summary-text']}>{summary}</p>
              </div>

              {/* Transcript */}
              <div className={styles['record-expanded-section']}>
                <h5 className={styles['section-title']}>Transcript</h5>
                <div className={styles['transcript-box']}>
                  <p className={styles['transcript-text']}>{transcript}</p>
                </div>
              </div>
            </>
          )}
        </div>
        )}
        </div>
      </div>
    </article>
  );
}

// Main SentimentDashboard component
const POLL_INTERVAL_MS = 12000;

export default function SentimentDashboard({ mode = 'dashboard' }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedIds, setExpandedIds] = useState(new Set());
  const [deleting, setDeleting] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const recordsListRef = useRef(null);

  const fetchRecords = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const response = await listCalls();
      setRecords(response.calls || []);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecords();
    const interval = setInterval(() => fetchRecords(true), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchRecords]);

  const toggleExpand = (jobId) => {
    const newSet = new Set(expandedIds);
    if (newSet.has(jobId)) {
      newSet.delete(jobId);
    } else {
      newSet.add(jobId);
    }
    setExpandedIds(newSet);
  };

  const handleRemoveRecording = async (jobId) => {
    setDeleting(jobId);
    try {
      await deleteRecording(jobId);
      // Remove from local state - this triggers re-sequencing because indices change
      setRecords(records.filter(r => r.job_id !== jobId));
      // Remove from expanded set if it was expanded
      const newSet = new Set(expandedIds);
      newSet.delete(jobId);
      setExpandedIds(newSet);
    } catch (err) {
      setError(`Failed to delete recording: ${err.message}`);
    } finally {
      setDeleting(null);
    }
  };

  if (loading) {
    return (
      <div className={styles['sentiment-dashboard']}>
        {mode === 'dashboard' && <ExecutiveDashboardHeader records={[]} />}
        {mode === 'dashboard' && <DashboardKpiRow records={[]} />}
        <div className={styles['records-section']}>
          <Card>
            <CardHeader title={mode === 'crm' ? 'Loading tickets…' : 'Loading recordings…'} />
            <Skeleton className="ui-skeleton-block ui-skeleton-block-tall" />
            <Skeleton className="ui-skeleton-block ui-skeleton-block-tall" />
          </Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles['sentiment-dashboard']}>
        <Alert variant="danger" title="Error Loading Dashboard">
          {error}
        </Alert>
      </div>
    );
  }

  if (!records || records.length === 0) {
    return (
      <div className={styles['sentiment-dashboard']}>
        {mode === 'dashboard' && <ExecutiveDashboardHeader records={[]} lastUpdated={lastUpdated} />}
        {mode === 'dashboard' && <DashboardKpiRow records={[]} />}
        {mode === 'dashboard' && <DashboardSentimentStory records={[]} />}
        <div className={styles['records-section']} ref={recordsListRef}>
          <EmptyState
            icon={mode === 'crm' ? '🗂' : '📊'}
            title={mode === 'crm' ? 'No Tickets Yet' : 'No Recordings Yet'}
            description={
              mode === 'crm'
                ? 'Tickets will appear here after calls are analysed.'
                : 'Upload audio files or paste direct audio links one by one. The dashboard updates automatically as each call is analysed.'
            }
          />
        </div>
      </div>
    );
  }

  // Sort records by created_at (newest first)
  const sortedRecords = [...records].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  return (
    <div className={styles['sentiment-dashboard']}>
      {mode === 'dashboard' && <ExecutiveDashboardHeader records={records} lastUpdated={lastUpdated} />}

      {mode === 'dashboard' && <DashboardSummary records={records} />}

      {mode === 'dashboard' && <DashboardSentimentStory records={records} />}

      <div className={styles['records-section']} ref={recordsListRef}>
        <Card className={`${styles['records-header-card']} records-header-card`}>
          <CardHeader
            title={mode === 'crm' ? 'CRM Ticket Explorer' : 'Record Explorer'}
            subtitle={
              mode === 'crm'
                ? `${records.length} ticket${records.length !== 1 ? 's' : ''} — open any ticket or expand a row for CRM details`
                : `${records.length} recording${records.length !== 1 ? 's' : ''} — click any row to expand details, or open the full ticket`
            }
          />
        </Card>

        <div className={styles['records-list']}>
          {sortedRecords.map((record, index) => (
            <ExpandableRecordCard
              key={record.job_id}
              record={record}
              index={index}
              onToggleExpand={toggleExpand}
              expanded={expandedIds.has(record.job_id)}
              onRemove={handleRemoveRecording}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
