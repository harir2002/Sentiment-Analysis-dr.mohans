const TICKET_CACHE_PREFIX = 'ticket-record:';

export function navigateToTicket(jobId, record = null) {
  if (record?.job_id) {
    try {
      sessionStorage.setItem(`${TICKET_CACHE_PREFIX}${jobId}`, JSON.stringify(record));
    } catch {
      /* ignore quota errors */
    }
  }
  window.location.hash = `#/ticket/${jobId}`;
}

export function navigateToResults(jobId, record = null) {
  if (record?.job_id) {
    try {
      sessionStorage.setItem(`${TICKET_CACHE_PREFIX}${jobId}`, JSON.stringify(record));
    } catch {
      /* ignore */
    }
  }
  window.location.hash = `#/results/${jobId}`;
}

export function parseAppRoute() {
  const raw = (window.location.hash || '').replace(/^#\/?/, '').trim();

  if (raw.startsWith('ticket/')) {
    const jobId = raw.slice('ticket/'.length).split('/')[0];
    if (jobId) return { view: 'ticket', jobId };
  }
  if (raw.startsWith('results/')) {
    const jobId = raw.slice('results/'.length).split('/')[0];
    if (jobId) return { view: 'results', jobId };
  }
  if (raw === 'dashboard') return { view: 'dashboard', jobId: null };
  if (raw === 'crm') return { view: 'crm', jobId: null };
  if (raw === 'analysis' || raw === '') return { view: 'analysis', jobId: null };
  return { view: 'analysis', jobId: null };
}

export function navigateToAnalysis() {
  window.location.hash = '#/analysis';
}

export function navigateToDashboard() {
  window.location.hash = '#/dashboard';
}

export function navigateToCrm() {
  window.location.hash = '#/crm';
}

export function getCachedTicketRecord(jobId) {
  try {
    const raw = sessionStorage.getItem(`${TICKET_CACHE_PREFIX}${jobId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function subscribeToRouteChanges(callback) {
  const handler = () => callback(parseAppRoute());
  window.addEventListener('hashchange', handler);
  return () => window.removeEventListener('hashchange', handler);
}
