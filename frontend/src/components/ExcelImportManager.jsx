import { useState, useRef } from 'react';
import { previewExcelFile, importAndProcessExcel } from '../services/api';
import { Alert, EmptyState } from './ui';
import styles from './ExcelImportManager.module.css';

export default function ExcelImportManager({ onImportStarted }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [batchName, setBatchName] = useState('');
  const [callReferencePrefix, setCallReferencePrefix] = useState('');
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    // Validate file type
    const validTypes = ['.xlsx', '.xls', '.csv'];
    const isValidType = validTypes.some(type => 
      selected.name.toLowerCase().endsWith(type)
    );

    if (!isValidType) {
      setError('Please select an Excel (.xlsx, .xls) or CSV file');
      return;
    }

    setFile(selected);
    setError(null);
    setSuccess(null);
    setPreview(null);
  };

  const handlePreviewExcel = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/api/excel/preview', {
        method: 'POST',
        headers: {
          'Authorization': 'Basic ' + btoa('admin:changeme'),
        },
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to preview file');
      }

      const data = await response.json();
      setPreview(data);
      setSuccess(`Found ${data.total_rows} rows, ${data.valid_links} valid links`);
    } catch (err) {
      setError(err.message || 'Error previewing file');
    } finally {
      setLoading(false);
    }
  };

  const handleImportAndProcess = async () => {
    if (!preview) {
      setError('Preview the file first');
      return;
    }

    if (!batchName.trim()) {
      setError('Batch name is required');
      return;
    }

    if (preview.valid_links === 0) {
      setError('No valid links found in file');
      return;
    }

    setProcessing(true);
    setError(null);

    try {
      // Get only valid records
      const validRecords = preview.preview_records.filter(r => r.status === 'valid');

      const response = await importAndProcessExcel({
        batch_name: batchName.trim(),
        audio_link_records: validRecords,
        call_reference_prefix: callReferencePrefix.trim() || undefined,
      });

      setSuccess(
        `Import batch created! Processing ${preview.valid_links} audio files...`
      );

      if (onImportStarted) {
        onImportStarted(response);
      }

      // Clear form
      setTimeout(() => {
        setFile(null);
        setPreview(null);
        setBatchName('');
        setCallReferencePrefix('');
        fileInputRef.current.value = '';
      }, 2000);
    } catch (err) {
      setError(err.message || 'Failed to start import');
    } finally {
      setProcessing(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    setPreview(null);
    setError(null);
    setSuccess(null);
    setBatchName('');
    setCallReferencePrefix('');
    fileInputRef.current.value = '';
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Import Audio Links from Excel</h2>
        <p>Upload an Excel or CSV file containing audio URLs</p>
      </div>

      {error && <Alert type="error" message={error} />}
      {success && <Alert type="success" message={success} />}

      {/* File Selection */}
      <div className={styles.section}>
        <h3>1. Select Excel or CSV File</h3>
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
          <div className={styles.dropIcon}>📊</div>
          <p>
            Drag and drop your Excel file here or{' '}
            <span className={styles.clickHere}>click to select</span>
          </p>
          <p className={styles.supportedFormats}>
            Supported: .xlsx, .xls, .csv
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {file && (
          <div className={styles.fileSelected}>
            <span className={styles.fileName}>{file.name}</span>
            <span className={styles.fileSize}>
              {(file.size / 1024).toFixed(2)} KB
            </span>
          </div>
        )}
      </div>

      {/* Preview */}
      {file && !preview && (
        <div className={styles.section}>
          <button
            onClick={handlePreviewExcel}
            disabled={loading}
            className={styles.previewBtn}
          >
            {loading ? 'Analyzing...' : 'Preview & Detect Links'}
          </button>
        </div>
      )}

      {/* Preview Results */}
      {preview && (
        <div className={styles.section}>
          <h3>2. Review Detected Links</h3>

          <div className={styles.previewStats}>
            <div className={styles.statBox}>
              <div className={styles.statValue}>{preview.total_rows}</div>
              <div className={styles.statLabel}>Total Rows</div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statValue} style={{ color: '#4CAF50' }}>
                {preview.valid_links}
              </div>
              <div className={styles.statLabel}>Valid Links</div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statValue} style={{ color: '#F44336' }}>
                {preview.invalid_links}
              </div>
              <div className={styles.statLabel}>Invalid</div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statValue} style={{ color: '#FF9800' }}>
                {preview.duplicate_links}
              </div>
              <div className={styles.statLabel}>Duplicates</div>
            </div>
          </div>

          <div className={styles.previewInfo}>
            <p>
              <strong>Detected Column:</strong> {preview.detected_column}
            </p>
          </div>

          {preview.preview_records.length > 0 && (
            <div className={styles.previewTable}>
              <h4>Preview (First 5 Rows)</h4>
              <table>
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Status</th>
                    <th>URL / Error</th>
                    <th>File Name</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_records.map((record, idx) => (
                    <tr key={idx} className={styles[record.status]}>
                      <td>{record.row_number}</td>
                      <td>
                        <span
                          className={styles.badge}
                          style={{
                            backgroundColor:
                              record.status === 'valid'
                                ? '#4CAF50'
                                : '#F44336',
                          }}
                        >
                          {record.status}
                        </span>
                      </td>
                      <td title={record.audio_url || record.error}>
                        {record.audio_url ? (
                          <code className={styles.url}>
                            {record.audio_url.substring(0, 50)}...
                          </code>
                        ) : (
                          <span className={styles.error}>{record.error}</span>
                        )}
                      </td>
                      <td>{record.audio_name || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Configuration */}
          <div className={styles.section}>
            <h3>3. Configure Batch</h3>

            <div className={styles.formGroup}>
              <label>Batch Name</label>
              <input
                type="text"
                placeholder="e.g., Dr Mohans Audio Links - Batch 1"
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
                disabled={processing}
              />
            </div>

            <div className={styles.formGroup}>
              <label>Call Reference Prefix (Optional)</label>
              <input
                type="text"
                placeholder="e.g., CALL (will become CALL_0001, CALL_0002...)"
                value={callReferencePrefix}
                onChange={(e) => setCallReferencePrefix(e.target.value)}
                disabled={processing}
              />
            </div>

            <div className={styles.actions}>
              <button
                onClick={handleImportAndProcess}
                disabled={processing || !batchName}
                className={styles.importBtn}
              >
                {processing
                  ? 'Starting Import...'
                  : `Import & Process ${preview.valid_links} Links`}
              </button>
              <button
                onClick={handleClear}
                disabled={processing}
                className={styles.secondaryBtn}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {!file && !preview && (
        <EmptyState
          title="Ready to import"
          message="Select an Excel or CSV file to get started"
        />
      )}
    </div>
  );
}
