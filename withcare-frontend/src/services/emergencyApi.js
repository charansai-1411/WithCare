import { getValidTokens } from './connectorsService';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export async function fetchEmergencySummary(userId, profileId) {
  if (!profileId) return null;
  try {
    const res = await fetch(`${BASE}/api/emergency/summary?profile_id=${encodeURIComponent(profileId)}`,
      { headers: { 'x-user-id': userId || '' } });
    return res.ok ? res.json() : null;
  } catch { return null; }
}

// Emails the person's emergency summary to their family members + the caregiver.
export async function sendSos(userId, profileId, location, coordinates) {
  const res = await fetch(`${BASE}/api/emergency/sos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId || '' },
    body: JSON.stringify({
      profile_id: profileId,
      location: location || '',
      coordinates: coordinates || null,
      connector_tokens: getValidTokens(userId),
    }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || 'Could not send the SOS alert.');
  }
  return res.json();
}
