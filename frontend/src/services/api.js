const API_BASE = window.__CONFIG__?.API_URL || import.meta.env.VITE_API_URL || '/api';

function getAuthHeader() {
  const username = import.meta.env.VITE_ADMIN_USERNAME || 'admin';
  const password = import.meta.env.VITE_ADMIN_PASSWORD || 'changeme';
  return 'Basic ' + btoa(`${username}:${password}`);
}

function parseErrorBody(err) {
  if (!err) return 'Request failed';
  if (typeof err.detail === 'string') return err.detail;
  if (Array.isArray(err.detail)) {
    return err.detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
  }
  return JSON.stringify(err);
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: getAuthHeader(),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorBody(err));
  }

  return response.json();
}

export async function checkHealth() {
  return request('/health');
}

export async function listCalls() {
  return request('/calls');
}

export async function uploadAudioFiles(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  return request('/upload', { method: 'POST', body: formData });
}

export async function uploadAudioUrl(audioUrl) {
  return request('/upload/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_url: audioUrl }),
  });
}

export async function runComparison({ fileId, callReference, sourceType, sourceUrl, originalFilename, storedPath }) {
  return request('/run-comparison', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      call_reference: callReference || null,
      source_type: sourceType || null,
      source_url: sourceUrl || null,
      original_filename: originalFilename || null,
      stored_path: storedPath || null,
    }),
  });
}

export async function getResults(jobId) {
  return request(`/results/${jobId}`);
}

export async function deleteRecording(jobId) {
  return request(`/results/${jobId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function retryFailedProviders(jobId, solutionIds = null) {
  return request(`/results/${jobId}/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ solution_ids: solutionIds }),
  });
}

export async function downloadWordReport(jobId) {
  const response = await fetch(`${API_BASE}/results/${jobId}/export/docx`, {
    headers: { Authorization: getAuthHeader() },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorBody(err));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `comparison-${jobId}.docx`;
  a.click();
  URL.revokeObjectURL(url);
}

/** @deprecated Use downloadWordReport */
export async function downloadExport(jobId, format = 'docx') {
  if (format !== 'docx') {
    throw new Error('Only Word (.docx) export is available.');
  }
  return downloadWordReport(jobId);
}

// ============ BATCH PROCESSING API ============

export async function getDashboard() {
  return request('/batch/dashboard');
}

export async function createBatchJob(request) {
  return fetch(`${API_BASE}/batch/jobs`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function getBatchJob(processingJobId) {
  return request(`/batch/jobs/${processingJobId}`);
}

export async function listBatchJobs(limit = 50, offset = 0) {
  return request(`/batch/jobs?limit=${limit}&offset=${offset}`);
}

export async function getBatchAudioFiles(processingJobId, limit = 100, offset = 0) {
  return request(`/batch/jobs/${processingJobId}/audio-files?limit=${limit}&offset=${offset}`);
}

export async function registerAudioFile(fileId, filename, fileSizeBytes, mimeType, durationSeconds = null, batchId = null) {
  const params = new URLSearchParams({
    filename,
    file_size_bytes: fileSizeBytes,
    mime_type: mimeType,
    ...(durationSeconds !== null && { duration_seconds: durationSeconds }),
    ...(batchId && { batch_id: batchId }),
  });
  return request(`/batch/audio-files/${fileId}/register?${params}`);
}

// ============ EXCEL IMPORT API ============

export async function previewExcelFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  return fetch(`${API_BASE}/excel/preview`, {
    method: 'POST',
    headers: { Authorization: getAuthHeader() },
    body: formData,
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function importAndProcessExcel(request) {
  return fetch(`${API_BASE}/excel/import-and-process`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function getImportBatch(importBatchId) {
  return request(`/excel/batches/${importBatchId}`);
}

export async function listImportBatches(limit = 50, offset = 0) {
  return request(`/excel/batches?limit=${limit}&offset=${offset}`);
}

export async function getImportBatchRecords(importBatchId, status = null, limit = 100, offset = 0) {
  const params = new URLSearchParams({
    limit,
    offset,
    ...(status && { status }),
  });
  return request(`/excel/batches/${importBatchId}/records?${params}`);
}

// ============ PIPELINE CONTROL API ============

export async function markBatchReady(processingJobId) {
  return fetch(`${API_BASE}/pipeline/batches/${processingJobId}/ready`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function startPipeline(processingJobId) {
  return fetch(`${API_BASE}/pipeline/batches/${processingJobId}/start`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function cancelPipeline(processingJobId) {
  return fetch(`${API_BASE}/pipeline/batches/${processingJobId}/cancel`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function resumePipeline(processingJobId) {
  return fetch(`${API_BASE}/pipeline/batches/${processingJobId}/resume`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function retryFailedBatch(processingJobId) {
  return fetch(`${API_BASE}/pipeline/batches/${processingJobId}/retry-failed`, {
    method: 'POST',
    headers: {
      Authorization: getAuthHeader(),
      'Content-Type': 'application/json',
    },
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseErrorBody(err));
    }
    return res.json();
  });
}

export async function getBatchProgress(processingJobId) {
  return request(`/pipeline/batches/${processingJobId}/progress`);
}

export async function getBatchStatus(processingJobId) {
  return request(`/pipeline/batches/${processingJobId}/status`);
}
