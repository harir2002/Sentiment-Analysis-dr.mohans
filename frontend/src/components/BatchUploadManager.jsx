import { useState, useRef } from 'react';
import { uploadAudioFiles, createBatchJob, registerAudioFile } from '../services/api';
import { Alert, EmptyState } from './ui';
import styles from './BatchUploadManager.module.css';

export default function BatchUploadManager({ onBatchCreated }) {
  const [files, setFiles] = useState([]);
  const [batchName, setBatchName] = useState('');
  const [callReferencePrefix, setCallReferencePrefix] = useState('');
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length === 0) return;

    setFiles((prev) => [...prev, ...selected]);
    setError(null);
    setSuccess(null);
  };

  const handleRemoveFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const clearAll = () => {
    setFiles([]);
    setUploadedFiles([]);
    setBatchName('');
    setCallReferencePrefix('');
    setError(null);
    setSuccess(null);
  };

  const handleUploadFiles = async () => {
    if (files.length === 0) {
      setError('Select at least one audio file');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      // Upload all files
      const uploadResponse = await uploadAudioFiles(files);

      if (uploadResponse.uploaded.length === 0) {
        throw new Error('No files uploaded successfully');
      }

      // Register uploaded files
      const fileIds = [];
      for (const uploadedFile of uploadResponse.uploaded) {
        try {
          await registerAudioFile(
            uploadedFile.file_id,
            uploadedFile.filename,
            uploadedFile.metadata?.file_size_bytes || 0,
            uploadedFile.metadata?.mime_type || 'audio/mpeg',
            uploadedFile.metadata?.duration_seconds,
            null
          );
          fileIds.push(uploadedFile.file_id);
        } catch (err) {
          console.warn(`Failed to register ${uploadedFile.filename}:`, err);
        }
      }

      setUploadedFiles(uploadResponse.uploaded);
      setUploadProgress(100);
      setSuccess(
        `Uploaded ${uploadResponse.uploaded.length}/${uploadResponse.total} files`
      );

      if (uploadResponse.failed.length > 0) {
        setError(
          `${uploadResponse.failed.length} file(s) failed validation: ${uploadResponse.failed
            .map((f) => `${f.filename} (${f.error})`)
            .join(', ')}`
        );
      }

      setFiles([]);
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleStartBatch = async () => {
    if (uploadedFiles.length === 0) {
      setError('No files uploaded. Upload files first.');
      return;
    }

    if (!batchName.trim()) {
      setError('Batch name is required');
      return;
    }

    setProcessing(true);
    setError(null);

    try {
      const fileIds = uploadedFiles.map((f) => f.file_id);

      const batchResponse = await createBatchJob({
        batch_name: batchName.trim(),
        audio_file_ids: fileIds,
        call_reference_prefix: callReferencePrefix.trim() || undefined,
      });

      setSuccess(
        `Batch "${batchName}" created with ${fileIds.length} files. Processing started.`
      );

      // Notify parent
      if (onBatchCreated) {
        onBatchCreated(batchResponse);
      }

      // Clear form
      setTimeout(() => {
        clearAll();
      }, 2000);
    } catch (err) {
      setError(err.message || 'Failed to start batch processing');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Batch Upload & Processing</h2>
        <p>Upload 50+ audio files and process them in a single batch</p>
      </div>

      {/* Alerts */}
      {error && <Alert type="error" message={error} />}
      {success && <Alert type="success" message={success} />}

      {/* File Selection Section */}
      <div className={styles.section}>
        <h3>1. Select Audio Files</h3>
        <div
          className={styles.dropZone}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFileSelect({
              target: { files: e.dataTransfer.files },
            });
          }}
        >
          <div className={styles.dropIcon}>📁</div>
          <p>
            Drag and drop audio files here or{' '}
            <span className={styles.clickHere}>click to select</span>
          </p>
          <p className={styles.supportedFormats}>
            Supported: MP3, WAV, M4A, FLAC, OGG, WebM (Max 25 MB each)
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="audio/*"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {files.length > 0 && (
          <div className={styles.fileList}>
            <div className={styles.fileListHeader}>
              <h4>Selected Files ({files.length})</h4>
              <button
                onClick={() => setFiles([])}
                className={styles.clearBtn}
              >
                Clear
              </button>
            </div>
            <div className={styles.files}>
              {files.map((file, idx) => (
                <div key={idx} className={styles.fileItem}>
                  <div className={styles.fileInfo}>
                    <span className={styles.fileName}>{file.name}</span>
                    <span className={styles.fileSize}>
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </span>
                  </div>
                  <button
                    onClick={() => handleRemoveFile(idx)}
                    className={styles.removeBtn}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {files.length > 0 && (
          <button
            onClick={handleUploadFiles}
            disabled={uploading}
            className={styles.uploadBtn}
          >
            {uploading
              ? `Uploading (${uploadProgress}%)...`
              : `Upload ${files.length} File(s)`}
          </button>
        )}
      </div>

      {/* Uploaded Files Section */}
      {uploadedFiles.length > 0 && (
        <div className={styles.section}>
          <h3>2. Configure Batch</h3>

          <div className={styles.formGroup}>
            <label htmlFor="batchName">Batch Name</label>
            <input
              id="batchName"
              type="text"
              placeholder="e.g., Dr Mohans Calls - Batch 1"
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              disabled={processing}
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="callRefPrefix">Call Reference Prefix (Optional)</label>
            <input
              id="callRefPrefix"
              type="text"
              placeholder="e.g., CALL (will auto-increment to CALL_0001, CALL_0002, ...)"
              value={callReferencePrefix}
              onChange={(e) => setCallReferencePrefix(e.target.value)}
              disabled={processing}
            />
            <small>If blank, calls will be numbered sequentially</small>
          </div>

          <div className={styles.uploadedSummary}>
            <h4>Files Ready for Batch:</h4>
            <div className={styles.summaryStats}>
              <div className={styles.stat}>
                <span className={styles.statValue}>{uploadedFiles.length}</span>
                <span className={styles.statLabel}>Files</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue}>
                  {(
                    uploadedFiles.reduce(
                      (sum, f) => sum + (f.metadata?.file_size_bytes || 0),
                      0
                    ) /
                    1024 /
                    1024
                  ).toFixed(1)}
                </span>
                <span className={styles.statLabel}>MB Total</span>
              </div>
            </div>

            <div className={styles.uploadedFiles}>
              {uploadedFiles.slice(0, 5).map((file) => (
                <div key={file.file_id} className={styles.uploadedFile}>
                  <span className={styles.fileName}>{file.filename}</span>
                  <span className={styles.status}>✓ Ready</span>
                </div>
              ))}
              {uploadedFiles.length > 5 && (
                <div className={styles.more}>
                  ... and {uploadedFiles.length - 5} more
                </div>
              )}
            </div>
          </div>

          <div className={styles.actions}>
            <button
              onClick={handleStartBatch}
              disabled={processing || uploadedFiles.length === 0}
              className={styles.startBtn}
            >
              {processing ? 'Starting Batch...' : `Start Batch Processing (${uploadedFiles.length} files)`}
            </button>
            <button
              onClick={clearAll}
              disabled={processing}
              className={styles.secondaryBtn}
            >
              Cancel & Clear
            </button>
          </div>
        </div>
      )}

      {uploadedFiles.length === 0 && files.length === 0 && (
        <EmptyState
          title="No files selected"
          message="Upload audio files to get started with batch processing"
        />
      )}
    </div>
  );
}
