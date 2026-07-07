import { useState, useEffect, useCallback } from 'react';
import { Alert, EmptyState } from './ui';
import { getDashboard, getBatchJob } from '../services/api';
import PipelineControls from './PipelineControls';
import styles from './BatchDashboard.module.css';

const POLL_INTERVAL = 3000;

export default function BatchDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [expandedBatchId, setExpandedBatchId] = useState(null);
  const [pollingJobId, setPollingJobId] = useState(null);

  // Fetch dashboard data
  const fetchDashboard = useCallback(async () => {
    try {
      const data = await getDashboard();
      setDashboard(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to fetch dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Polling for active batch jobs
  useEffect(() => {
    if (!dashboard?.processing_jobs?.length) return;

    const activeJob = dashboard.processing_jobs.find(
      (j) => j.status === 'processing'
    );

    if (!activeJob) {
      setPollingJobId(null);
      return;
    }

    setPollingJobId(activeJob.id);

    const timer = setInterval(() => {
      fetchDashboard();
    }, POLL_INTERVAL);

    return () => clearInterval(timer);
  }, [dashboard, fetchDashboard]);

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>Dashboard</h1>
        </div>
        <div className={styles.loading}>Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>Dashboard</h1>
        </div>
        <Alert type="error" message={error} />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>Dashboard</h1>
        </div>
        <EmptyState
          title="No data available"
          message="No audio files have been processed yet."
        />
      </div>
    );
  }

  const { metrics, recent_jobs, processing_jobs } = dashboard;

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1>Batch Processing Dashboard</h1>
          <p>Local-first batch analysis for 50+ audio files</p>
        </div>
        <button onClick={fetchDashboard} className={styles.refreshBtn}>
          Refresh
        </button>
      </div>

      {/* Metrics Cards */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricCard}>
          <div className={styles.metricValue}>{metrics.total_audios}</div>
          <div className={styles.metricLabel}>Total Audios</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricValue}>{metrics.processed_audios}</div>
          <div className={styles.metricLabel}>Processed</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricValue}>{metrics.failed_audios}</div>
          <div className={styles.metricLabel}>Failed</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricValue}>{metrics.processing_audios}</div>
          <div className={styles.metricLabel}>Processing</div>
        </div>
      </div>

      {/* Sentiment Summary */}
      <div className={styles.sentimentSection}>
        <h2>Sentiment Summary</h2>
        <div className={styles.sentimentGrid}>
          <div className={styles.sentimentCard}>
            <span className={styles.sentimentLabel}>Positive</span>
            <span className={styles.sentimentCount} style={{ color: '#4CAF50' }}>
              {metrics.positive_count}
            </span>
          </div>
          <div className={styles.sentimentCard}>
            <span className={styles.sentimentLabel}>Neutral</span>
            <span className={styles.sentimentCount} style={{ color: '#FF9800' }}>
              {metrics.neutral_count}
            </span>
          </div>
          <div className={styles.sentimentCard}>
            <span className={styles.sentimentLabel}>Negative</span>
            <span className={styles.sentimentCount} style={{ color: '#F44336' }}>
              {metrics.negative_count}
            </span>
          </div>
          <div className={styles.sentimentCard}>
            <span className={styles.sentimentLabel}>Unknown</span>
            <span className={styles.sentimentCount} style={{ color: '#9E9E9E' }}>
              {metrics.unknown_count}
            </span>
          </div>
        </div>
        <div className={styles.metricInfo}>
          <p>Avg Confidence: <strong>{(metrics.average_confidence * 100).toFixed(1)}%</strong></p>
          {metrics.best_solution_id && (
            <p>Best Solution: <strong>{metrics.best_solution_id}</strong></p>
          )}
        </div>
      </div>

      {/* Active Batch Jobs */}
      {processing_jobs && processing_jobs.length > 0 && (
        <div className={styles.batchJobsSection}>
          <h2>Batch Processing Jobs</h2>
          <div className={styles.batchJobsList}>
            {processing_jobs.map((job) => (
              <div key={job.id} className={styles.batchJobCard}>
                <div className={styles.batchJobHeader}>
                  <div>
                    <h3>{job.batch_name || `Batch ${job.id.slice(0, 8)}`}</h3>
                    <p className={styles.batchJobMeta}>
                      Created: {new Date(job.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className={styles.batchJobStatus}>
                    <span className={`${styles.status} ${styles[job.status]}`}>
                      {job.status}
                    </span>
                    <span className={styles.progressPercent}>{job.progress_percent}%</span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className={styles.progressBar}>
                  <div
                    className={styles.progressFill}
                    style={{ width: `${job.progress_percent}%` }}
                  />
                </div>

                {/* Progress Details */}
                <div className={styles.progressDetails}>
                  <span>
                    {job.processed_files + job.failed_files + job.cancelled_files} / {job.total_files} files
                  </span>
                  {job.queued_files > 0 && (
                    <span className={styles.queued}>
                      {job.queued_files} queued
                    </span>
                  )}
                  {job.processing_files > 0 && (
                    <span className={styles.processing}>
                      {job.processing_files} processing
                    </span>
                  )}
                  {job.failed_files > 0 && (
                    <span className={styles.failed}>
                      {job.failed_files} failed
                    </span>
                  )}
                  {job.cancelled_files > 0 && (
                    <span className={styles.cancelled}>
                      {job.cancelled_files} cancelled
                    </span>
                  )}
                  {job.total_runtime_seconds && (
                    <span>
                      {Math.round(job.total_runtime_seconds)}s
                    </span>
                  )}
                </div>

                {job.error && (
                  <Alert type="error" message={job.error} />
                )}

                <button
                  className={styles.expandBtn}
                  onClick={() =>
                    setExpandedBatchId(expandedBatchId === job.id ? null : job.id)
                  }
                >
                  {expandedBatchId === job.id ? 'Hide Details' : 'Show Details'}
                </button>

                {expandedBatchId === job.id && (
                  <div className={styles.batchDetails}>
                    {/* Pipeline Controls */}
                    <PipelineControls
                      job={job}
                      onStatusChange={fetchDashboard}
                    />

                    {/* Job Details */}
                    <div className={styles.detailsGrid}>
                      <p><strong>Job ID:</strong> {job.id}</p>
                      <p><strong>Status:</strong> {job.status}</p>
                      <p><strong>Total Files:</strong> {job.total_files}</p>
                      <p><strong>Processed:</strong> {job.processed_files}</p>
                      <p><strong>Failed:</strong> {job.failed_files}</p>
                      <p><strong>Queued:</strong> {job.queued_files}</p>
                      <p><strong>Processing:</strong> {job.processing_files}</p>
                      {job.cancelled_files > 0 && (
                        <p><strong>Cancelled:</strong> {job.cancelled_files}</p>
                      )}
                      {job.started_at && (
                        <p>
                          <strong>Started:</strong> {new Date(job.started_at).toLocaleString()}
                        </p>
                      )}
                      {job.completed_at && (
                        <p>
                          <strong>Completed:</strong> {new Date(job.completed_at).toLocaleString()}
                        </p>
                      )}
                      {job.cancelled_at && (
                        <p>
                          <strong>Cancelled:</strong> {new Date(job.cancelled_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Results */}
      <div className={styles.recentJobsSection}>
        <h2>Recent Analysis Results ({recent_jobs.length})</h2>
        {recent_jobs.length === 0 ? (
          <EmptyState
            title="No results yet"
            message="Audio files will appear here as they are processed."
          />
        ) : (
          <div className={styles.jobsTable}>
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Call Reference</th>
                  <th>Status</th>
                  <th>Sentiment</th>
                  <th>Confidence</th>
                  <th>Best Solution</th>
                  <th>Runtime (s)</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {recent_jobs.map((job) => (
                  <tr
                    key={job.job_id}
                    className={styles.jobRow}
                    onClick={() => setSelectedJob(job)}
                  >
                    <td title={job.audio_filename}>
                      <span className={styles.filename}>
                        {job.audio_filename?.length > 30
                          ? job.audio_filename.slice(0, 27) + '...'
                          : job.audio_filename}
                      </span>
                    </td>
                    <td>{job.call_reference || '-'}</td>
                    <td>
                      <span className={`${styles.status} ${styles[job.status]}`}>
                        {job.status}
                      </span>
                    </td>
                    <td>
                      {job.sentiment ? (
                        <span
                          className={styles.sentiment}
                          style={{
                            color:
                              job.sentiment === 'positive'
                                ? '#4CAF50'
                                : job.sentiment === 'negative'
                                  ? '#F44336'
                                  : '#FF9800',
                          }}
                        >
                          {job.sentiment}
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td>
                      {job.confidence
                        ? `${(job.confidence * 100).toFixed(0)}%`
                        : '-'}
                    </td>
                    <td className={styles.solution}>
                      {job.winner_solution
                        ? job.winner_solution.split(' + ')[0]
                        : '-'}
                    </td>
                    <td>
                      {job.total_runtime_seconds
                        ? job.total_runtime_seconds.toFixed(1)
                        : '-'}
                    </td>
                    <td className={styles.dateCell}>
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Job Detail Modal */}
      {selectedJob && (
        <div className={styles.modal} onClick={() => setSelectedJob(null)}>
          <div
            className={styles.modalContent}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className={styles.closeBtn}
              onClick={() => setSelectedJob(null)}
            >
              ×
            </button>
            <h2>Analysis Details</h2>
            <div className={styles.detailsGrid}>
              <p>
                <strong>Filename:</strong> {selectedJob.audio_filename}
              </p>
              <p>
                <strong>Call Reference:</strong> {selectedJob.call_reference || '-'}
              </p>
              <p>
                <strong>Status:</strong> {selectedJob.status}
              </p>
              <p>
                <strong>Sentiment:</strong> {selectedJob.sentiment || '-'}
              </p>
              <p>
                <strong>Confidence:</strong>{' '}
                {selectedJob.confidence
                  ? `${(selectedJob.confidence * 100).toFixed(1)}%`
                  : '-'}
              </p>
              <p>
                <strong>Best Solution:</strong> {selectedJob.winner_solution || '-'}
              </p>
              <p>
                <strong>Runtime:</strong>{' '}
                {selectedJob.total_runtime_seconds
                  ? `${selectedJob.total_runtime_seconds.toFixed(1)}s`
                  : '-'}
              </p>
              <p>
                <strong>Created:</strong>{' '}
                {new Date(selectedJob.created_at).toLocaleString()}
              </p>
            </div>
            <a href={`/results/${selectedJob.job_id}`} className={styles.viewBtn}>
              View Full Results
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
