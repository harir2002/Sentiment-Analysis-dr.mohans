import { computeDashboardKpis, computeExecutiveHeadline } from '../utils/dashboardAnalytics';
import styles from './SentimentDashboard.module.css';

export default function ExecutiveDashboardHeader({ records, lastUpdated }) {
  const kpis = computeDashboardKpis(records);
  const headline = computeExecutiveHeadline(records);

  const updatedLabel = lastUpdated
    ? `Updated ${lastUpdated.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`
    : null;

  return (
    <header className={`${styles['executive-header']} executive-header`}>
      <div className={styles['executive-header-main']}>
        <h2 className={styles['dashboard-title']}>Executive Call Analytics</h2>
        <p className={styles['executive-headline']}>{headline}</p>
      </div>
      <div className={styles['executive-header-meta']}>
        {updatedLabel && <span className={styles['executive-updated']}>{updatedLabel}</span>}
        {kpis.processing > 0 && (
          <span className={styles['executive-pill']}>
            {kpis.processing} processing
          </span>
        )}
        {kpis.failed > 0 && (
          <span className={`${styles['executive-pill']} ${styles['executive-pill-danger']}`}>
            {kpis.failed} failed
          </span>
        )}
        <span className={styles['executive-pill']}>
          {kpis.total} total
        </span>
      </div>
    </header>
  );
}
