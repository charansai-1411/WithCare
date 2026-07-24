import { getValidTokens } from './connectorsService';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Every call carries the user's valid connector tokens so the backend can create a routine's
// optional reminder on their own calendar (and email the family member as an attendee).
async function post(userId, path, body = {}) {
  const res = await fetch(`${BASE}/api/routines${path}`, {
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

export const fetchRoutines = (userId, profileId) => post(userId, '/list', { profile_id: profileId || null });
export const draftRoutine  = (userId, body)      => post(userId, '/draft', body);
export const addRoutine    = (userId, body)      => post(userId, '/add', body);
export const deleteRoutine = (userId, id)        => post(userId, `/${id}/delete`);
