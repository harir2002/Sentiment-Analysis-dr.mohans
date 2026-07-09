import { useState, useEffect, useCallback, useRef } from 'react';

import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import ProcessingState from './components/ProcessingState';
import SolutionComparison from './components/SolutionComparison';
import ExportSection from './components/ExportButtons';
import SentimentDashboard from './components/SentimentDashboard';
import TicketDetailPage from './pages/TicketDetailPage';
import ResultsDetailPage from './pages/ResultsDetailPage';
import { EmptyState, Alert } from './components/ui';

import { checkHealth, uploadAudioFiles, uploadAudioUrl, runComparison, getResults } from './services/api';
import { fileEntryKey } from './constants/sttLanguages';
import {
  parseAppRoute,
  subscribeToRouteChanges,
  navigateToAnalysis,
  navigateToDashboard,
  navigateToCrm,
} from './utils/appNavigation';

const POLL_INTERVAL = 2500;

function getStatusLabel(job, running) {
  if (running) return 'Processing';
  if (!job) return null;
  if (job.results_ready && job.aggregate_status === 'completed') return 'Analysis complete';
  if (job.status === 'failed') return 'Failed';
  if (job.results_ready && job.aggregate_status === 'partial') return 'Partially complete';
  if (job.results_ready) return 'Ready';
  return 'In progress';
}

export default function App() {
  const [files, setFiles] = useState([]);
  const [audioUrl, setAudioUrl] = useState('');
  const [batchItems, setBatchItems] = useState([]);
  const [activeBatchIndex, setActiveBatchIndex] = useState(0);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [health, setHealth] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') return 'dark';
    return window.localStorage.getItem('theme') || 'dark';
  });
  const [currentPage, setCurrentPage] = useState('analysis'); // 'analysis' | 'dashboard' | 'crm'
  const [ticketJobId, setTicketJobId] = useState(null);
  const [resultsJobId, setResultsJobId] = useState(null);

  const batchItemsRef = useRef(batchItems);

  useEffect(() => {
    const syncRoute = () => {
      const route = parseAppRoute();
      if (route.view === 'ticket' && route.jobId) {
        setTicketJobId(route.jobId);
        setResultsJobId(null);
        setCurrentPage('dashboard');
        return;
      }
      if (route.view === 'results' && route.jobId) {
        setResultsJobId(route.jobId);
        setTicketJobId(null);
        setCurrentPage('dashboard');
        return;
      }
      setTicketJobId(null);
      setResultsJobId(null);
      setCurrentPage(route.view === 'dashboard' ? 'dashboard' : route.view === 'crm' ? 'crm' : 'analysis');
    };

    syncRoute();
    return subscribeToRouteChanges(syncRoute);
  }, []);

  const handlePageChange = (page) => {
    if (page === 'dashboard') navigateToDashboard();
    else if (page === 'crm') navigateToCrm();
    else navigateToAnalysis();
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    window.localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    batchItemsRef.current = batchItems;
  }, [batchItems]);

  useEffect(() => {
    checkHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const isJobTerminal = useCallback((data) => {
    if (data.status === 'failed' && data.error) return true;
    return data.results_ready === true;
  }, []);

  useEffect(() => {
    if (!running) return undefined;

    const interval = setInterval(async () => {
      const items = batchItemsRef.current;
      if (items.length === 0) return;

      try {
        const updates = await Promise.all(items.map((item) => getResults(item.job.job_id)));
        const newItems = items.map((item, i) => ({ ...item, job: updates[i] }));
        setBatchItems(newItems);

        if (updates.every(isJobTerminal)) {
          setRunning(false);
          setUploadStatus(null);
          clearInterval(interval);
        }
      } catch (e) {
        setError(e.message);
        setRunning(false);
        setUploadStatus(null);
        clearInterval(interval);
      }
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [running, isJobTerminal]);

  const handleFilesChange = (newFiles) => {
    setFiles(newFiles);
    setUploadStatus(null);
    setError(null);
  };

  const handleAudioUrlChange = (url) => {
    setAudioUrl(url);
    setUploadStatus(null);
    setError(null);
  };

  const handleRun = async () => {
    const trimmedUrl = audioUrl.trim();
    const hasFiles = files.length > 0;
    const hasUrl = trimmedUrl.length > 0;

    if (hasFiles && hasUrl) {
      setError('Choose either a file upload or an audio URL, not both.');
      return;
    }
    if (!hasFiles && !hasUrl) {
      setError('Upload an audio file or paste a direct audio URL.');
      return;
    }

    setError(null);
    setRunning(true);
    setBatchItems([]);
    setActiveBatchIndex(0);

    try {
      let batch;

      if (hasUrl) {
        setUploadStatus('Downloading remote audio…');
        batch = await uploadAudioUrl(trimmedUrl);
      } else {
        setUploadStatus(`Uploading ${files.length} file${files.length !== 1 ? 's' : ''}…`);
        batch = await uploadAudioFiles(files);
      }

      if (batch.failed?.length) {
        const failedSummary = batch.failed
          .map((f) => `${f.filename}: ${f.error}`)
          .join('; ');
        if (batch.success_count === 0) {
          setError(`Upload failed: ${failedSummary}`);
          setRunning(false);
          setUploadStatus(null);
          return;
        }
        setError(`Some files could not be uploaded (${batch.failed_count}/${batch.total}): ${failedSummary}`);
      }

      setUploadStatus('Transcribing and analyzing…');

      const startedJobs = await Promise.all(
        batch.uploaded.map(async (item) => {
          const job = await runComparison({
            fileId: item.file_id,
            sourceType: item.metadata?.source_type,
            sourceUrl: item.metadata?.source_url,
            originalFilename: item.filename,
            storedPath: item.path,
          });
          return {
            fileId: item.file_id,
            filename: item.filename,
            uploadMeta: item.metadata,
            job,
          };
        }),
      );

      setBatchItems(startedJobs);
      if (hasUrl) {
        setAudioUrl('');
      }

      if (startedJobs.every((item) => isJobTerminal(item.job))) {
        setRunning(false);
        setUploadStatus(null);
      }
    } catch (e) {
      setError(e.message);
      setRunning(false);
      setUploadStatus(null);
    }
  };

  const activeItem = batchItems[activeBatchIndex] || null;
  const job = activeItem?.job || null;
  const resultsReady = job?.results_ready === true;
  const results = resultsReady ? (job?.results || []) : [];
  const showActiveProcessing = !job ? running : !job.results_ready;
  const multiFile = batchItems.length > 1;
  const completedBatchCount = batchItems.filter((item) => item.job?.results_ready).length;
  const statusLabel = getStatusLabel(job, showActiveProcessing);
  const canExport = job?.job_id && resultsReady;

  const pageSubtitle = activeItem?.filename
    ? activeItem.filename
    : 'Upload a call recording to begin';

  return (
    <div className="app-shell">
      <Sidebar
        files={files}
        onFilesChange={handleFilesChange}
        audioUrl={audioUrl}
        onAudioUrlChange={handleAudioUrlChange}
        onRun={handleRun}
        running={running}
        health={health}
        uploadStatus={uploadStatus}
        currentPage={currentPage}
        onPageChange={handlePageChange}
      />

      <div className="main-column">
        <TopBar
          title={
            resultsJobId
              ? 'Analysis Results'
              : ticketJobId
                ? 'Call Ticket'
                : currentPage === 'dashboard'
                  ? 'Sentiment Analysis Dashboard'
                  : currentPage === 'crm'
                    ? 'CRM Tickets'
                  : 'Call Analysis'
          }
          subtitle={
            resultsJobId
              ? 'Full call analysis for this recording'
              : ticketJobId
                ? 'CRM-style call detail and recommended actions'
                : currentPage === 'dashboard'
                  ? 'Overview of all analyzed recordings'
                  : currentPage === 'crm'
                    ? 'All analyzed recordings in a ticket-first CRM view'
                  : activeItem?.filename || 'Upload a call recording to begin'
          }
          status={ticketJobId || resultsJobId || currentPage === 'dashboard' || currentPage === 'crm' ? null : (job?.aggregate_status || job?.status)}
          statusLabel={ticketJobId || resultsJobId || currentPage === 'dashboard' || currentPage === 'crm' ? null : statusLabel}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
          exportSlot={
            !ticketJobId && !resultsJobId && currentPage !== 'dashboard' && currentPage !== 'crm' && canExport ? (
              <ExportSection jobId={job.job_id} />
            ) : null
          }
        />

        <main className="main-content">
          {ticketJobId && <TicketDetailPage jobId={ticketJobId} />}

          {resultsJobId && <ResultsDetailPage jobId={resultsJobId} />}

          {!ticketJobId && !resultsJobId && currentPage === 'dashboard' && <SentimentDashboard />}

          {!ticketJobId && !resultsJobId && currentPage === 'crm' && <SentimentDashboard mode="crm" />}

          {!ticketJobId && !resultsJobId && currentPage === 'analysis' && (
            <>
              {error && (
                <Alert variant="danger" title="Something went wrong">
                  {error}
                </Alert>
              )}

              {!showActiveProcessing && batchItems.length === 0 && !error && (
                <EmptyState
                  icon="📋"
                  title="No analysis yet"
                  description="Upload a call recording or paste a direct audio URL using the panel on the left, then run analysis to view the transcript, sentiment, and key highlights."
                />
              )}

              {showActiveProcessing && (
                <ProcessingState
                  uploadStatus={uploadStatus}
                  job={job}
                  running={running}
                  multiFile={multiFile}
                  completedBatchCount={completedBatchCount}
                  batchTotal={batchItems.length}
                />
              )}

              {multiFile && batchItems.length > 0 && (
                <div className="batch-switcher">
                  {batchItems.map((item, i) => {
                    const ready = item.job?.results_ready;
                    const failed = item.job?.status === 'failed';
                    return (
                      <button
                        key={item.fileId || fileEntryKey({ name: item.filename })}
                        type="button"
                        className={`batch-pill ${i === activeBatchIndex ? 'active' : ''} ${ready ? 'ready' : ''} ${failed ? 'failed' : ''}`}
                        onClick={() => setActiveBatchIndex(i)}
                      >
                        <span className="batch-pill-name">{item.filename}</span>
                        <span className="batch-pill-dot" aria-hidden="true" />
                      </button>
                    );
                  })}
                </div>
              )}

              {job?.status === 'failed' && job?.error && !resultsReady && (
                <Alert variant="danger" title="Analysis failed">
                  {job.error}
                </Alert>
              )}

              {resultsReady && !showActiveProcessing && (
                <SolutionComparison
                  results={results}
                  ranking={job?.ranking}
                  audioFilename={job?.audio_filename || activeItem?.filename}
                  jobMeta={job}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
