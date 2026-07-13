import { useMemo, useRef, useState } from 'react';
import { computeDashboardKpis } from '../utils/dashboardAnalytics';
import { getRecordingAssessment } from '../utils/callValidity';
import { getCanonicalResult } from '../utils/canonicalResult';
import {
  getCanonicalRecommendation,
  getValidConfidence,
} from '../utils/recordingDisplay';
import styles from './SentimentDashboard.module.css';

const HOVER_PREVIEW_LIMIT = 4;
const HOVER_CLOSE_DELAY_MS = 140;

function formatCallDate(value) {
  if (!value) return null;
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function truncateText(text, maxLen = 88) {
  if (!text) return null;
  const cleaned = String(text).trim();
  if (!cleaned) return null;
  return cleaned.length > maxLen ? `${cleaned.substring(0, maxLen)}…` : cleaned;
}

function buildSentimentPreviews(records = [], sentiment) {
  return [...records]
    .filter((record) => record.results_ready)
    .filter((record) => {
      const { sentimentLabel, isValidCall } = getRecordingAssessment(record);
      return isValidCall && sentimentLabel === sentiment;
    })
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .map((record) => {
      const canonical = getCanonicalResult(record);
      const confidence = getValidConfidence(record);
      const recommendation = getCanonicalRecommendation(record);
      const summary = canonical?.analysis?.summary;
      return {
        id: record.job_id,
        filename: record.audio_filename || 'Unknown audio',
        sentiment,
        confidence:
          confidence != null && Number.isFinite(confidence)
            ? `${Math.round(confidence * 100)}%`
            : null,
        preview: truncateText(recommendation || summary || 'No summary available.'),
        dateLabel: formatCallDate(record.created_at || record.completed_at),
      };
    });
}

function SentimentHoverCard({ sentiment, items, totalCount }) {
  const label = sentiment.charAt(0).toUpperCase() + sentiment.slice(1);
  const visible = items.slice(0, HOVER_PREVIEW_LIMIT);
  const remaining = Math.max(0, totalCount - visible.length);

  return (
    <div
      className={`${styles['kpi-hover-card']} ${styles[`kpi-hover-card-${sentiment}`]}`}
      role="tooltip"
    >
      <div className={styles['kpi-hover-header']}>
        <span className={styles['kpi-hover-title']}>{label} calls</span>
        <span className={styles['kpi-hover-count']}>{totalCount}</span>
      </div>

      {visible.length === 0 ? (
        <p className={styles['kpi-hover-empty']}>No {sentiment} calls yet.</p>
      ) : (
        <ul className={styles['kpi-hover-list']}>
          {visible.map((item) => (
            <li key={item.id} className={styles['kpi-hover-item']}>
              <div className={styles['kpi-hover-item-top']}>
                <span className={styles['kpi-hover-filename']} title={item.filename}>
                  {item.filename}
                </span>
                {item.dateLabel && (
                  <span className={styles['kpi-hover-date']}>{item.dateLabel}</span>
                )}
              </div>
              <div className={styles['kpi-hover-meta']}>
                <span className={styles[`kpi-hover-sentiment-${item.sentiment}`]}>
                  {label}
                </span>
                {item.confidence && (
                  <span className={styles['kpi-hover-confidence']}>{item.confidence}</span>
                )}
              </div>
              {item.preview && (
                <p className={styles['kpi-hover-preview']}>{item.preview}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {remaining > 0 && (
        <p className={styles['kpi-hover-more']}>
          +{remaining} more {sentiment} call{remaining === 1 ? '' : 's'}
        </p>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  insight,
  variant = 'default',
  suffix = '',
  hoverEnabled = false,
  hoverSentiment = null,
  hoverItems = [],
  hoverTotal = 0,
}) {
  const [open, setOpen] = useState(false);
  const closeTimerRef = useRef(null);

  const clearCloseTimer = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const showHover = () => {
    if (!hoverEnabled) return;
    clearCloseTimer();
    setOpen(true);
  };

  const hideHover = () => {
    if (!hoverEnabled) return;
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => setOpen(false), HOVER_CLOSE_DELAY_MS);
  };

  const className = [
    styles['kpi-card'],
    'kpi-card',
    styles[`kpi-card-${variant}`],
    hoverEnabled ? styles['kpi-card-hoverable'] : '',
    open ? styles['kpi-card-hover-open'] : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={styles['kpi-card-wrap']}
      onMouseEnter={showHover}
      onMouseLeave={hideHover}
      onFocus={showHover}
      onBlur={hideHover}
    >
      <div
        className={className}
        tabIndex={hoverEnabled ? 0 : undefined}
        aria-describedby={
          hoverEnabled && open ? `kpi-hover-${hoverSentiment}` : undefined
        }
      >
        <span className={styles['kpi-label']}>{label}</span>
        <span className={styles['kpi-value']}>
          {value}
          {suffix && <span className={styles['kpi-suffix']}>{suffix}</span>}
        </span>
        {insight && <span className={styles['kpi-insight']}>{insight}</span>}
      </div>

      {hoverEnabled && open && (
        <div id={`kpi-hover-${hoverSentiment}`} className={styles['kpi-hover-anchor']}>
          <SentimentHoverCard
            sentiment={hoverSentiment}
            items={hoverItems}
            totalCount={hoverTotal}
          />
        </div>
      )}
    </div>
  );
}

export default function DashboardKpiRow({ records }) {
  const kpis = computeDashboardKpis(records);

  const previews = useMemo(
    () => ({
      positive: buildSentimentPreviews(records, 'positive'),
      neutral: buildSentimentPreviews(records, 'neutral'),
      negative: buildSentimentPreviews(records, 'negative'),
    }),
    [records]
  );

  return (
    <section className={styles['kpi-section']} aria-label="Executive KPI summary">
      <div className={styles['section-intro']}>
        <h3 className={styles['section-heading']}>Executive Summary</h3>
        <p className={styles['section-subheading']}>
          Simple overview of analysed calls — hover Positive, Neutral, or Negative for a quick
          preview.
        </p>
      </div>
      <div className={styles['kpi-row']}>
        <KpiCard
          label="Calls Analyzed"
          value={kpis.callsAnalyzed}
          insight={
            kpis.total > kpis.callsAnalyzed
              ? `${kpis.total - kpis.callsAnalyzed} pending`
              : 'Classified calls'
          }
          variant="accent"
        />
        <KpiCard
          label="Positive"
          value={kpis.positive}
          insight="Satisfied customer interactions"
          variant="positive"
          hoverEnabled
          hoverSentiment="positive"
          hoverItems={previews.positive}
          hoverTotal={kpis.positive}
        />
        <KpiCard
          label="Neutral"
          value={kpis.neutral}
          insight="Mixed or informational calls"
          variant="neutral"
          hoverEnabled
          hoverSentiment="neutral"
          hoverItems={previews.neutral}
          hoverTotal={kpis.neutral}
        />
        <KpiCard
          label="Negative"
          value={kpis.negative}
          insight={
            kpis.negativeShare > 0 ? `${kpis.negativeShare}% of classified` : 'Needs attention'
          }
          variant="negative"
          hoverEnabled
          hoverSentiment="negative"
          hoverItems={previews.negative}
          hoverTotal={kpis.negative}
        />
      </div>
    </section>
  );
}
