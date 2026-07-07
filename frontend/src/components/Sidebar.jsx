import { useState, useRef } from 'react';
import { fileEntryKey } from '../constants/sttLanguages';
import { Button, Alert } from './ui';

const AUDIO_ACCEPT =
  'audio/*,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a,audio/ogg,audio/webm,audio/flac,.wav,.mp3,.mpeg,.m4a,.ogg,.webm,.flac';

const ACCEPTED_LABEL = 'MP3, M4A, WAV, MPEG, FLAC, OGG, WebM';

function isLikelyAudioUrl(value) {
  const trimmed = (value || '').trim();
  if (!trimmed) return true;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export default function Sidebar({
  files,
  onFilesChange,
  audioUrl,
  onAudioUrlChange,
  onRun,
  running,
  health,
  uploadStatus,
  currentPage = 'analysis',
  onPageChange = () => {},
}) {
  const [dragOver, setDragOver] = useState(false);
  const [urlError, setUrlError] = useState(null);
  const inputRef = useRef(null);
  const providersReady =
    health?.providers?.sarvam &&
    health?.providers?.groq &&
    health?.providers?.openrouter;

  const fileCount = files?.length || 0;
  const trimmedUrl = (audioUrl || '').trim();
  const hasUrl = trimmedUrl.length > 0;
  const hasFiles = fileCount > 0;
  const bothProvided = hasFiles && hasUrl;
  const canSubmit = (hasFiles || hasUrl) && !bothProvided && providersReady;

  const handleFiles = (incoming) => {
    const list = Array.from(incoming || []);
    if (list.length) {
      onFilesChange(list);
      onAudioUrlChange('');
      setUrlError(null);
    }
  };

  const handleUrlChange = (value) => {
    onAudioUrlChange(value);
    setUrlError(null);
    if (value.trim()) {
      onFilesChange([]);
    }
  };

  const handleUrlBlur = () => {
    if (!trimmedUrl) {
      setUrlError(null);
      return;
    }
    if (!isLikelyAudioUrl(trimmedUrl)) {
      setUrlError('Enter a valid http or https audio link.');
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true" />
        <div>
          <h1 className="brand-title">Call Analytics</h1>
          <p className="brand-subtitle">Dr. Mohan&apos;s</p>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Primary">
        <button
          type="button"
          className={`sidebar-nav-item ${currentPage === 'analysis' ? 'active' : ''}`}
          onClick={() => onPageChange('analysis')}
        >
          📋 Call Analysis
        </button>
        <button
          type="button"
          className={`sidebar-nav-item ${currentPage === 'dashboard' ? 'active' : ''}`}
          onClick={() => onPageChange('dashboard')}
        >
          📊 Dashboard
        </button>
        <button
          type="button"
          className={`sidebar-nav-item ${currentPage === 'crm' ? 'active' : ''}`}
          onClick={() => onPageChange('crm')}
        >
          🗂 CRM
        </button>
      </nav>

      {currentPage === 'analysis' && (
        <>
          <div className="sidebar-section">
            <h2 className="sidebar-label">Upload recording</h2>
            <div
              className={`file-drop ${dragOver ? 'file-drop-active' : ''} ${hasUrl ? 'file-drop-disabled' : ''}`}
              onDragOver={(e) => {
                if (hasUrl) return;
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => !hasUrl && inputRef.current?.click()}
              onKeyDown={(e) => e.key === 'Enter' && !hasUrl && inputRef.current?.click()}
              role="button"
              tabIndex={hasUrl ? -1 : 0}
              aria-disabled={hasUrl}
            >
              <input
                ref={inputRef}
                type="file"
                multiple
                accept={AUDIO_ACCEPT}
                disabled={hasUrl}
                onChange={(e) => handleFiles(e.target.files)}
              />
              <p className="file-drop-title">
                {fileCount > 0
                  ? `${fileCount} file${fileCount !== 1 ? 's' : ''} selected`
                  : 'Drop audio or browse'}
              </p>
              <p className="file-drop-hint">{ACCEPTED_LABEL} · max 25 MB</p>
            </div>

            {fileCount > 0 && (
              <ul className="file-list">
                {files.map((file) => (
                  <li key={fileEntryKey(file)}>
                    <span className="file-list-name" title={file.name}>{file.name}</span>
                    <span className="file-list-size">{(file.size / 1024).toFixed(0)} KB</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="upload-divider" aria-hidden="true">
              <span>or</span>
            </div>

            <div className="field">
              <label className="sidebar-label" htmlFor="audio-url-input">
                Audio URL
              </label>
              <input
                id="audio-url-input"
                type="url"
                className={`audio-url-input ${urlError ? 'input-invalid' : ''}`}
                placeholder="https://…/recording.mp3"
                value={audioUrl}
                onChange={(e) => handleUrlChange(e.target.value)}
                onBlur={handleUrlBlur}
                disabled={hasFiles || running}
                aria-invalid={Boolean(urlError)}
                aria-describedby="audio-url-hint"
              />
              <p id="audio-url-hint" className="field-hint">
                Paste a direct MP3/WAV/M4A audio file link
              </p>
              {urlError && (
                <p className="field-error" role="alert">{urlError}</p>
              )}
              {hasUrl && (
                <p className="url-preview" title={trimmedUrl}>
                  Remote: {trimmedUrl.length > 48 ? `${trimmedUrl.slice(0, 48)}…` : trimmedUrl}
                </p>
              )}
            </div>

            {bothProvided && (
              <Alert variant="warning">
                Use either file upload or audio URL — not both.
              </Alert>
            )}

            {uploadStatus && (
              <p className="upload-status" role="status">{uploadStatus}</p>
            )}
          </div>

          <div className="sidebar-footer">
            <Button
              variant="primary"
              className="sidebar-run-btn"
              onClick={onRun}
              disabled={running || !canSubmit}
            >
              {running
                ? 'Processing…'
                : hasUrl
                  ? 'Analyze from URL'
                  : fileCount > 1
                    ? `Analyze ${fileCount} calls`
                    : 'Analyze call'}
            </Button>

            {!providersReady && health && (
              <Alert variant="warning">
                Analysis service is temporarily unavailable. Please try again shortly.
              </Alert>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
