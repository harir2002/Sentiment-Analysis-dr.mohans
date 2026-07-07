import { useState } from 'react';
import { Alert } from './ui';
import {
  startPipeline,
  cancelPipeline,
  resumePipeline,
  retryFailedBatch,
  getBatchStatus,
} from '../services/api';
import styles from './PipelineControls.module.css';

export default function PipelineControls({ job, onStatusChange }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(job);

  const handleStart = async () => {
    if (!confirm(`Start processing ${job.batch_name || 'batch'}?`)) return;
    setLoading(true);
    setError(null);
    try {
      const result = await startPipeline(job.id);
      setStatus(result);
      onStatusChange?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!confirm('Cancel processing? Already processed items will be preserved.')) return;
    setLoading(true);
    setError(null);
    try {
      const result = await cancelPipeline(job.id);
      setStatus(result);
      onStatusChange?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    if (!confirm(`Resume processing ${job.batch_name || 'batch'}?`)) return;
    setLoading(true);
    setError(null);
    try {
      const result = await resumePipeline(job.id);
      setStatus(result);
      onStatusChange?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!confirm('Retry all failed items in this batch?')) return;
    setLoading(true);
    setError(null);
    try {
      const result = await retryFailedBatch(job.id);
      setStatus(result);
      onStatusChange?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Determine which actions are available
  const canStart = ['draft', 'ready', 'queued'].includes(job.status);
  const canCancel = ['draft', 'ready', 'queued', 'processing'].includes(job.status);
  const canResume = ['cancelled', 'failed'].includes(job.status);
  const canRetry = job.failed_files > 0 || job.cancelled_files > 0;

  return (
    <div className={styles.container}>
      {error && <Alert type="error" message={error} />}

      <div className={styles.controls}>
        {canStart && (
          <button
            className={`${styles.btn} ${styles.primary}`}
            onClick={handleStart}
            disabled={loading}
            title="Start processing this batch"
          >
            ▶ Start Pipeline
          </button>
        )}

        {canCancel && (
          <button
            className={`${styles.btn} ${styles.danger}`}
            onClick={handleCancel}
            disabled={loading}
            title="Stop processing and cancel remaining items"
          >
            ⏹ Cancel Pipeline
          </button>
        )}

        {canResume && (
          <button
            className={`${styles.btn} ${styles.secondary}`}
            onClick={handleResume}
            disabled={loading}
            title="Resume processing cancelled or failed items"
          >
            ↻ Resume Pipeline
          </button>
        )}

        {canRetry && (
          <button
            className={`${styles.btn} ${styles.secondary}`}
            onClick={handleRetry}
            disabled={loading}
            title={`Retry ${job.failed_files} failed + ${job.cancelled_files} cancelled items`}
          >
            🔄 Retry Failed ({job.failed_files + job.cancelled_files})
          </button>
        )}
      </div>

      {/* Status Info */}
      <div className={styles.statusInfo}>
        <div className={styles.statusRow}>
          <span className={styles.label}>Status:</span>
          <span className={`${styles.status} ${styles[job.status]}`}>
            {job.status}
          </span>
        </div>

        {job.queued_files > 0 && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Queued:</span>
            <span className={styles.value}>{job.queued_files}</span>
          </div>
        )}

        {job.processing_files > 0 && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Processing:</span>
            <span className={styles.value}>{job.processing_files}</span>
          </div>
        )}

        {job.processed_files > 0 && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Completed:</span>
            <span className={styles.value}>{job.processed_files}</span>
          </div>
        )}

        {job.failed_files > 0 && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Failed:</span>
            <span className={`${styles.value} ${styles.failed}`}>
              {job.failed_files}
            </span>
          </div>
        )}

        {job.cancelled_files > 0 && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Cancelled:</span>
            <span className={`${styles.value} ${styles.cancelled}`}>
              {job.cancelled_files}
            </span>
          </div>
        )}

        {job.cancelled_at && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Cancelled at:</span>
            <span className={styles.value}>
              {new Date(job.cancelled_at).toLocaleString()}
            </span>
          </div>
        )}

        {job.total_runtime_seconds !== null && (
          <div className={styles.statusRow}>
            <span className={styles.label}>Runtime:</span>
            <span className={styles.value}>
              {Math.round(job.total_runtime_seconds)}s
            </span>
          </div>
        )}
      </div>

      {loading && (
        <div className={styles.loading}>Processing...</div>
      )}
    </div>
  );
}
