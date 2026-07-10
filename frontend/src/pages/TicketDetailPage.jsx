import { useEffect, useState } from 'react';
import { getResults, listCalls } from '../services/api';
import { buildTicketFromRecord, findRecordingIndex } from '../utils/ticketModel';
import {
  getCachedTicketRecord,
  navigateToDashboard,
  navigateToResults,
} from '../utils/appNavigation';
import { Alert, Badge, SentimentBadge, PriorityBadge, Skeleton } from '../components/ui';
import styles from './TicketDetailPage.module.css';

const WORKFLOW_PREFIX = 'ticket-workflow:';

function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusVariant(status) {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'running' || status === 'partial') return 'warning';
  return 'neutral';
}

function statusLabel(status) {
  if (status === 'completed') return 'Completed';
  if (status === 'failed') return 'Failed';
  if (status === 'partial') return 'Partial';
  if (status === 'running') return 'Processing';
  return status;
}

function loadWorkflow(jobId) {
  try {
    const raw = sessionStorage.getItem(`${WORKFLOW_PREFIX}${jobId}`);
    return raw ? JSON.parse(raw) : { assigned: false, critical: false, resolved: false };
  } catch {
    return { assigned: false, critical: false, resolved: false };
  }
}

function saveWorkflow(jobId, workflow) {
  try {
    sessionStorage.setItem(`${WORKFLOW_PREFIX}${jobId}`, JSON.stringify(workflow));
  } catch {
    /* ignore */
  }
}

function SectionCard({ title, subtitle, children, className = '', variant = 'default' }) {
  return (
    <section className={`${styles['section-card']} ${styles[`section-${variant}`]} ${className}`}>
      <div className={styles['section-head']}>
        <h2 className={styles['section-title']}>{title}</h2>
        {subtitle && <p className={styles['section-subtitle']}>{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function MetaRow({ label, value, children }) {
  return (
    <div className={styles['meta-row']}>
      <span className={styles['meta-label']}>{label}</span>
      <span className={styles['meta-value']}>{children || value || '—'}</span>
    </div>
  );
}

export default function TicketDetailPage({ jobId }) {
  const [record, setRecord] = useState(() => getCachedTicketRecord(jobId));
  const [loading, setLoading] = useState(!record);
  const [error, setError] = useState(null);
  const [recordingIndex, setRecordingIndex] = useState(0);
  const [workflow, setWorkflow] = useState(() => loadWorkflow(jobId));

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setError(null);
      try {
        const [job, callsResponse] = await Promise.all([
          getResults(jobId),
          listCalls().catch(() => ({ calls: [] })),
        ]);
        if (cancelled) return;
        setRecordingIndex(findRecordingIndex(callsResponse.calls || [], jobId));
        setRecord(job);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load ticket');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [jobId]);

  const updateWorkflow = (patch) => {
    const next = { ...workflow, ...patch };
    setWorkflow(next);
    saveWorkflow(jobId, next);
  };

  if (loading && !record) {
    return (
      <div className={styles.page}>
        <Skeleton className="ui-skeleton-block ui-skeleton-block-tall" />
        <Skeleton className="ui-skeleton-block ui-skeleton-block-tall" />
      </div>
    );
  }

  if (error && !record) {
    return (
      <div className={styles.page}>
        <button type="button" className={styles['btn-ghost']} onClick={navigateToDashboard}>
          ← Back to Dashboard
        </button>
        <Alert variant="danger" title="Ticket not found">{error}</Alert>
      </div>
    );
  }

  const ticket = buildTicketFromRecord(record, recordingIndex);
  const hasAudio = Boolean(ticket.audioUrl);

  return (
    <div className={`ticket-detail-page ${styles.page}`}>
      {/* ——— Toolbar ——— */}
      <div className={styles.toolbar}>
        <button type="button" className={styles['btn-ghost']} onClick={navigateToDashboard}>
          ← Back to Dashboard
        </button>
        <div className={styles['toolbar-actions']}>
          {hasAudio && (
            <a
              href={ticket.audioUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles['btn-secondary']}
            >
              ▶ Play Audio
            </a>
          )}
          <button
            type="button"
            className={styles['btn-secondary']}
            onClick={() => navigateToResults(jobId, record)}
          >
            View Results
          </button>
          <button
            type="button"
            className={`${styles['btn-secondary']} ${workflow.assigned ? styles['btn-active'] : ''}`}
            onClick={() => updateWorkflow({ assigned: !workflow.assigned })}
          >
            {workflow.assigned ? '✓ Assigned' : 'Assign'}
          </button>
          <button
            type="button"
            className={`${styles['btn-secondary']} ${workflow.critical ? styles['btn-critical'] : ''}`}
            onClick={() => updateWorkflow({ critical: !workflow.critical })}
          >
            {workflow.critical ? '⚠ Critical' : 'Mark Critical'}
          </button>
          <button
            type="button"
            className={`${styles['btn-primary']} ${workflow.resolved ? styles['btn-resolved'] : ''}`}
            onClick={() => updateWorkflow({ resolved: !workflow.resolved })}
          >
            {workflow.resolved ? '✓ Resolved' : 'Resolve'}
          </button>
        </div>
      </div>

      {/* ——— Ticket header ——— */}
      <header className={styles.header}>
        <div className={styles['header-main']}>
          <div className={styles['header-ids']}>
            <span className={styles['ticket-id']}>{ticket.ticketId}</span>
            <span className={styles['recording-id']}>{ticket.recordingId}</span>
          </div>
          <h1 className={styles['header-title']}>{ticket.filename}</h1>
          <p className={styles['header-meta']}>
            Analysed {formatDateTime(ticket.completedAt || ticket.createdAt)}
          </p>
        </div>

        <div className={styles['header-badges']}>
          <Badge variant={statusVariant(ticket.status)}>{statusLabel(ticket.status)}</Badge>
          {workflow.resolved && <Badge variant="success">Resolved</Badge>}
          {workflow.critical && <Badge variant="danger">Critical</Badge>}
          {workflow.assigned && <Badge variant="neutral">Assigned</Badge>}
          {ticket.resultsReady && <SentimentBadge sentiment={ticket.sentiment} />}
          {!ticket.isValidCall && <SentimentBadge sentiment="invalid" />}
          {ticket.actionPriority && ticket.actionPriority !== '—' && (
            <PriorityBadge priority={ticket.actionPriority} />
          )}
          {ticket.needsReview && !workflow.resolved && (
            <Badge variant="danger">Needs Review</Badge>
          )}
        </div>
      </header>

      {hasAudio && (
        <div className={styles['audio-player-wrap']}>
          <audio controls className={styles['audio-player']} src={ticket.audioUrl} preload="metadata">
            Your browser does not support audio playback.
          </audio>
        </div>
      )}

      {/* ——— Primary insight panel ——— */}
      <section className={styles.insight} aria-label="Primary insights">
        <div className={styles['insight-grid']}>
          <div className={styles['insight-sentiment']}>
            <span className={styles['insight-label']}>Final Sentiment</span>
            {ticket.resultsReady ? (
              <SentimentBadge sentiment={ticket.sentiment} />
            ) : (
              <Badge variant="warning">Pending</Badge>
            )}
            {ticket.isUrgent && !workflow.resolved && (
              <span className={styles['urgent-flag']}>Urgent action required</span>
            )}
          </div>

          <div className={styles['insight-recommendation']}>
            <span className={styles['insight-label']}>Next Steps</span>
            {ticket.nextSteps?.length > 0 ? (
              ticket.nextSteps.length === 1 ? (
                <p className={styles['insight-action']}>{ticket.nextSteps[0]}</p>
              ) : (
                <ul className={styles['insight-action-list']}>
                  {ticket.nextSteps.map((step) => (
                    <li key={step} className={styles['insight-action']}>{step}</li>
                  ))}
                </ul>
              )
            ) : (
              <p className={styles['insight-action']}>
                {ticket.recommendation || 'No recommendation available yet.'}
              </p>
            )}
          </div>
        </div>

        {ticket.summary && (
          <p className={styles['insight-summary']}>{ticket.summary}</p>
        )}

        {!ticket.isValidCall && ticket.invalidReason && (
          <div className={styles['insight-invalid']}>
            <strong>Unclassified call</strong> — {ticket.invalidReason}
          </div>
        )}

        {ticket.error && ticket.status === 'failed' && (
          <Alert variant="danger" title="Analysis failed">{ticket.error}</Alert>
        )}
      </section>

      {/* ——— Two-column body ——— */}
      <div className={styles.columns}>
        <div className={styles['col-main']}>
          <SectionCard title="Call Overview" subtitle="What was analysed and where it came from">
            <div className={styles['overview-grid']}>
              <MetaRow label="File name" value={ticket.filename} />
              <MetaRow label="Recording ID" value={ticket.recordingId} />
              <MetaRow label="Uploaded" value={formatDateTime(ticket.createdAt)} />
              <MetaRow label="Source">
                {ticket.sourceType === 'url' ? 'Remote audio URL' : 'File upload'}
              </MetaRow>
              {ticket.sourceUrl && (
                <MetaRow label="Audio URL">
                  <a href={ticket.sourceUrl} target="_blank" rel="noopener noreferrer" className={styles.link}>
                    {ticket.sourceUrl.length > 48 ? `${ticket.sourceUrl.slice(0, 48)}…` : ticket.sourceUrl}
                  </a>
                </MetaRow>
              )}
            </div>
          </SectionCard>

          <SectionCard title="Sentiment & Decision" subtitle="Classification outcome and recommended action">
            <div className={styles['decision-block']}>
              <div className={styles['decision-row']}>
                <span className={styles['decision-label']}>Sentiment</span>
                <SentimentBadge sentiment={ticket.sentiment} />
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Summary" subtitle="What happened and why it matters">
            <p className={styles['body-text']}>
              {ticket.summary || 'Summary will appear once analysis completes.'}
            </p>
            {ticket.keyIssues.length > 0 && (
              <div className={styles['issues-block']}>
                <span className={styles['issues-label']}>Key issues / complaints</span>
                <ul className={styles['issues-list']}>
                  {ticket.keyIssues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
          </SectionCard>

          {ticket.transcript && (
            <SectionCard title="Transcript" subtitle="Full conversation evidence">
              <div className={styles['transcript-panel']}>{ticket.transcript}</div>
            </SectionCard>
          )}
        </div>

        <aside className={styles['col-side']}>
          <SectionCard title="Operational Metadata" subtitle="Status and routing context">
            <MetaRow label="Ticket ID" value={ticket.ticketId} />
            <MetaRow label="Job ID" value={ticket.jobId} />
            <MetaRow label="Status" value={statusLabel(ticket.status)} />
            <MetaRow label="Priority" value={ticket.actionPriority} />
            <MetaRow label="Assigned team" value={ticket.assignedTeam || (workflow.assigned ? 'Assigned (local)' : '—')} />
            <MetaRow label="Processing time">
              {ticket.totalRuntimeSeconds != null ? `${ticket.totalRuntimeSeconds.toFixed(1)}s` : '—'}
            </MetaRow>
            <MetaRow label="Language" value={ticket.sttLanguage} />
            <MetaRow label="Ingested" value={formatDateTime(ticket.ingestedAt || ticket.createdAt)} />
          </SectionCard>

          <SectionCard title="Analysis Details" subtitle="Processing context">
            <MetaRow label="Analysis type" value="Call Analysis" />
            <MetaRow label="Processing time">
              {ticket.totalRuntimeSeconds != null ? `${ticket.totalRuntimeSeconds.toFixed(1)}s` : '—'}
            </MetaRow>
            <MetaRow label="Language" value={ticket.sttLanguage} />
            <MetaRow label="Ingested" value={formatDateTime(ticket.ingestedAt || ticket.createdAt)} />
          </SectionCard>
        </aside>
      </div>
    </div>
  );
}
