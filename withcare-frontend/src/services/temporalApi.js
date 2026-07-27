const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

async function post(userId, path, body = {}) {
  const res = await fetch(`${BASE}/api/temporal${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId || '' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

// Manual one-tap check-off: status = 'taken' | 'missed' | 'skipped' | 'done'
export const logAdherence      = (userId, body) => post(userId, '/adherence', body);
export const fetchAdherence    = (userId, body) => post(userId, '/adherence-report', body);
export const fetchSummary      = (userId, body) => post(userId, '/summary', body);
export const fetchTrend        = (userId, body) => post(userId, '/trend', body);
export const fetchTimeline     = (userId, body) => post(userId, '/timeline', body);
export const fetchNext         = (userId, body) => post(userId, '/next', body);
export const fetchAttention    = (userId, body) => post(userId, '/attention', body);
