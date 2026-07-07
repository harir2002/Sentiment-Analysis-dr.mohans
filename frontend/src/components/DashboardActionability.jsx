import {
  computeCommonRecommendations,
  computeIssueThemes,
  computeCallsNeedingReview,
  computeInvalidReasons,
  computeDashboardKpis,
} from '../utils/dashboardAnalytics';
import { SentimentBadge } from './ui';
import styles from './SentimentDashboard.module.css';

function InsightList({ title, question, items, emptyMessage, renderItem }) {
  return (
    <div className={`${styles['action-card']} action-card`}>
      <h4 className={styles['action-card-title']}>{title}</h4>
      <p className={styles['action-card-question']}>{question}</p>
      {items.length === 0 ? (
        <p className={styles['action-card-empty']}>{emptyMessage}</p>
      ) : (
        <ul className={styles['action-list']}>{items.map(renderItem)}</ul>
      )}
    </div>
  );
}

export default function DashboardActionability({ records, onOpenTicket }) {
  const kpis = computeDashboardKpis(records);
  const recommendations = computeCommonRecommendations(records, 5);
  const issues = computeIssueThemes(records, 6);
  const urgentCalls = computeCallsNeedingReview(records, 6);
  const invalidReasons = computeInvalidReasons(records);

  return (
    <section className={styles['dashboard-story-section']} aria-label="Actionability insights">
      <div className={styles['section-intro']}>
        <h3 className={styles['section-heading']}>Actionability</h3>
        <p className={styles['section-subheading']}>
          What leadership should do next — recommendations, complaint themes, and calls needing review.
        </p>
      </div>

      <div className={styles['action-grid']}>
        <InsightList
          title="Top Next Steps"
          question="What actions appear most often across calls?"
          items={recommendations}
          emptyMessage="Recommendations will appear once valid calls are analysed."
          renderItem={(item) => (
            <li key={item.text} className={`${styles['action-list-item']} dash-action-row`}>
              <p className={styles['action-list-text']}>{item.text}</p>
              <span className={styles['action-list-meta']}>{item.count} call{item.count !== 1 ? 's' : ''}</span>
            </li>
          )}
        />

        <InsightList
          title="Common Complaint Themes"
          question="What issues are customers raising most frequently?"
          items={issues}
          emptyMessage="Issue themes appear when key issues are detected in call summaries."
          renderItem={(item) => (
            <li key={item.theme} className={`${styles['action-list-item']} dash-action-row`}>
              <p className={styles['action-list-text']}>{item.theme}</p>
              <span className={styles['action-list-meta']}>{item.count}×</span>
            </li>
          )}
        />

        <div className={`${styles['action-card']} action-card`}>
          <h4 className={styles['action-card-title']}>Calls Needing Immediate Review</h4>
          <p className={styles['action-card-question']}>
            Which interactions require leadership attention right now?
          </p>
          {urgentCalls.length === 0 ? (
            <p className={styles['action-card-empty']}>
              No urgent calls flagged. Negative or escalated interactions appear here.
            </p>
          ) : (
            <ul className={styles['urgent-list']}>
              {urgentCalls.map((call) => (
                <li key={call.jobId} className={styles['urgent-item']}>
                  <button
                    type="button"
                    className={`${styles['urgent-item-btn']} dash-urgent-btn`}
                    onClick={() => onOpenTicket?.(call.jobId)}
                  >
                    <span className={styles['urgent-filename']}>{call.filename}</span>
                    <span className={styles['urgent-meta']}>
                      <SentimentBadge sentiment={call.sentiment} />
                      {call.confidence != null && (
                        <span className={styles['urgent-confidence']}>
                          {Math.round(call.confidence * 100)}%
                        </span>
                      )}
                    </span>
                    {call.recommendation && (
                      <span className={styles['urgent-rec']}>{call.recommendation}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className={`${styles['action-card']} action-card`}>
          <h4 className={styles['action-card-title']}>Unclassified Calls</h4>
          <p className={styles['action-card-question']}>
            How many calls could not be reliably analysed, and why?
          </p>
          <div className={styles['invalid-summary']}>
            <span className={styles['invalid-count']}>{kpis.invalid}</span>
            <span className={styles['invalid-label']}>
              unclassified call{kpis.invalid !== 1 ? 's' : ''} — excluded from sentiment KPIs
            </span>
          </div>
          {invalidReasons.length === 0 ? (
            <p className={styles['action-card-empty']}>All analysed calls were successfully classified.</p>
          ) : (
            <ul className={styles['action-list']}>
              {invalidReasons.map((item) => (
                <li key={item.reason} className={`${styles['action-list-item']} dash-action-row`}>
                  <p className={styles['action-list-text']}>{item.reason}</p>
                  <span className={styles['action-list-meta']}>{item.count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
