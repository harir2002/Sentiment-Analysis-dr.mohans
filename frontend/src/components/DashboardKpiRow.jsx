import { computeDashboardKpis } from '../utils/dashboardAnalytics';
import styles from './SentimentDashboard.module.css';

function KpiCard({ label, value, insight, variant = 'default', suffix = '' }) {
  return (
    <div className={`${styles['kpi-card']} kpi-card ${styles[`kpi-card-${variant}`]}`}>
      <span className={styles['kpi-label']}>{label}</span>
      <span className={styles['kpi-value']}>
        {value}
        {suffix && <span className={styles['kpi-suffix']}>{suffix}</span>}
      </span>
      {insight && <span className={styles['kpi-insight']}>{insight}</span>}
    </div>
  );
}

export default function DashboardKpiRow({ records }) {
  const kpis = computeDashboardKpis(records);

  return (
    <section className={styles['kpi-section']} aria-label="Executive KPI summary">
      <div className={styles['section-intro']}>
        <h3 className={styles['section-heading']}>Executive Summary</h3>
        <p className={styles['section-subheading']}>
          Simple overview of analysed calls — one result per recording.
        </p>
      </div>
      <div className={styles['kpi-row']}>
        <KpiCard
          label="Calls Analyzed"
          value={kpis.callsAnalyzed}
          insight={kpis.total > kpis.callsAnalyzed ? `${kpis.total - kpis.callsAnalyzed} pending` : 'Classified calls'}
          variant="accent"
        />
        <KpiCard
          label="Positive"
          value={kpis.positive}
          insight="Satisfied customer interactions"
          variant="positive"
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
          insight={kpis.negativeShare > 0 ? `${kpis.negativeShare}% of classified` : 'Needs attention'}
          variant="negative"
        />
        <KpiCard
          label="Unclassified"
          value={kpis.invalid}
          insight="Invalid or unusable audio"
          variant="invalid"
        />
      </div>
    </section>
  );
}
