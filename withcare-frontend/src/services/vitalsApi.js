const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export async function fetchVitals(userId, profileId, metric) {
  const q = new URLSearchParams();
  if (profileId) q.set('profile_id', profileId);
  if (metric) q.set('metric', metric);
  try {
    const res = await fetch(`${BASE}/api/vitals?${q.toString()}`, { headers: { 'x-user-id': userId || '' } });
    return res.ok ? res.json() : [];
  } catch { return []; }
}

export async function logVital(userId, payload) {
  const res = await fetch(`${BASE}/api/vitals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId || '' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || 'Could not log the reading.');
  }
  return res.json();
}

export async function deleteVital(userId, id) {
  const res = await fetch(`${BASE}/api/vitals/${id}`, { method: 'DELETE', headers: { 'x-user-id': userId || '' } });
  return res.ok;
}
