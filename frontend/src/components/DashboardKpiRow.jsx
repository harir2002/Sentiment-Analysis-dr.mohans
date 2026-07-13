import { computeDashboardKpis } from '../utils/dashboardAnalytics';
import styles from './SentimentDashboard.module.css';

function KpiCard({
  label,
  value,
  insight,
  variant = 'default',
  suffix = '',
  interactive = false,
  active = false,
  onClick,
}) {
  const className = [
    styles['kpi-card'],
    'kpi-card',
    styles[`kpi-card-${variant}`],
    interactive ? styles['kpi-card-interactive'] : '',
    active ? styles['kpi-card-active'] : '',
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <>
      <span className={styles['kpi-label']}>
        {label}
        {interactive && (
          <span className={styles['kpi-drill-arrow']} aria-hidden="true">
            {active ? '▾' : '→'}
          </span>
        )}
      </span>
      <span className={styles['kpi-value']}>
        {value}
        {suffix && <span className={styles['kpi-suffix']}>{suffix}</span>}
      </span>
      {insight && <span className={styles['kpi-insight']}>{insight}</span>}
    </>
  );

  if (interactive) {
    return (
      <button
        type="button"
        className={className}
        onClick={onClick}
        aria-pressed={active}
        aria-label={`Show ${label.toLowerCase()} calls`}
      >
        {content}
      </button>
    );
  }

  return <div className={className}>{content}</div>;
}

export default function DashboardKpiRow({ records, sentimentFilter = null, onSentimentFilterChange }) {
  const kpis = computeDashboardKpis(records);

  const toggleFilter = (sentiment) => {
    if (!onSentimentFilterChange) return;
    onSentimentFilterChange(sentimentFilter === sentiment ? null : sentiment);
  };

  return (
    <section className={styles['kpi-section']} aria-label="Executive KPI summary">
      <div className={styles['section-intro']}>
        <h3 className={styles['section-heading']}>Executive Summary</h3>
        <p className={styles['section-subheading']}>
          Simple overview of analysed calls — one result per recording. Click Positive or Negative to
          review matching calls.
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
          interactive
          active={sentimentFilter === 'positive'}
          onClick={() => toggleFilter('positive')}
        />
        <KpiCard
          label="Neutral"
          value={kpis.neutral}
          insight="Mixed or informational calls"
          variant="neutral"
        />
        <KpiCard
          label="Negative"
          value={kpis.negative}
          insight={
            kpis.negativeShare > 0 ? `${kpis.negativeShare}% of classified` : 'Needs attention'
          }
          variant="negative"
          interactive
          active={sentimentFilter === 'negative'}
          onClick={() => toggleFilter('negative')}
        />
      </div>
    </section>
  );
}
