import { getValidTokens } from './connectorsService';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Every call carries the user's valid connector tokens so the backend can create the dose
// reminders on their calendar and send the refill alert from their Gmail.
async function post(userId, path, body = {}) {
  const res = await fetch(`${BASE}/api/medications${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId || '' },
    body: JSON.stringify({ ...body, connector_tokens: getValidTokens(userId) }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const fetchMedications = (userId, profileId) => post(userId, '/list', { profile_id: profileId || null });
export const addMedication    = (userId, med)       => post(userId, '/add', med);
export const refillMedication = (userId, id, quantity) => post(userId, `/${id}/refill`, { quantity });
export const deleteMedication = (userId, id)        => post(userId, `/${id}/delete`);
