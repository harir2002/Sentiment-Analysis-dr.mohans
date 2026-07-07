import { computeCommonRecommendations } from '../utils/dashboardAnalytics';
import styles from './SentimentDashboard.module.css';

export default function CommonRecommendations({ records }) {
  const items = computeCommonRecommendations(records, 5);

  if (items.length === 0) return null;

  return (
    <div className={styles['common-recommendations']}>
      <h3 className={styles['section-heading']}>Common Next Steps</h3>
      <p className={styles['section-subheading']}>
        Most frequent recommendations across valid analysed calls
      </p>
      <ul className={styles['recommendation-list']}>
        {items.map((item) => (
          <li key={item.text} className={styles['recommendation-item']}>
            <p className={styles['recommendation-text']}>{item.text}</p>
            <span className={styles['recommendation-count']}>
              {item.count} call{item.count !== 1 ? 's' : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
