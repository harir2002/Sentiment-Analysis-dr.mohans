import { useEffect, useState } from 'react';
import { getResults } from '../services/api';
import { getCachedTicketRecord, navigateToDashboard, navigateToTicket } from '../utils/appNavigation';
import SolutionComparison from '../components/SolutionComparison';
import ExportSection from '../components/ExportButtons';
import { Alert, Skeleton } from '../components/ui';
import styles from './ResultsDetailPage.module.css';

export default function ResultsDetailPage({ jobId }) {
  const [record, setRecord] = useState(() => getCachedTicketRecord(jobId));
  const [loading, setLoading] = useState(!record);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const job = await getResults(jobId);
        if (!cancelled) setRecord(job);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading && !record) {
    return <Skeleton className="ui-skeleton-block ui-skeleton-block-tall" />;
  }

  if (error || !record) {
    return (
      <div className={styles.page}>
        <button type="button" className={styles.back} onClick={navigateToDashboard}>← Dashboard</button>
        <Alert variant="danger" title="Could not load results">{error || 'Not found'}</Alert>
      </div>
    );
  }

  const resultsReady = record.results_ready === true;
  const results = resultsReady ? (record.results || []) : [];

  return (
    <div className={`results-detail-page ${styles.page}`}>
      <div className={styles.toolbar}>
        <button type="button" className={styles.back} onClick={() => navigateToTicket(jobId, record)}>
          ← Back to Ticket
        </button>
        {resultsReady && <ExportSection jobId={jobId} compact />}
      </div>

      <header className={styles.header}>
        <h1 className={styles.title}>Full Analysis Results</h1>
        <p className={styles.sub}>{record.audio_filename || 'Recording'} · 4-solution comparison</p>
      </header>

      {resultsReady ? (
        <SolutionComparison
          results={results}
          ranking={record.ranking}
          audioFilename={record.audio_filename}
          jobMeta={record}
        />
      ) : (
        <Alert variant="info" title="Results not ready">
          Analysis is still in progress or failed. Return to the ticket for status.
        </Alert>
      )}
    </div>
  );
}
