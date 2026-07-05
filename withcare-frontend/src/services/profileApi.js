const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

function headers(userId) {
  return { 'Content-Type': 'application/json', 'x-user-id': userId };
}

export async function fetchProfiles(userId) {
  try {
    const r = await fetch(`${BASE}/api/profiles`, { headers: headers(userId) });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

export async function createProfile(userId, data) {
  const r = await fetch(`${BASE}/api/profiles`, {
    method: 'POST',
    headers: headers(userId),
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error('Could not create profile');
  return r.json();
}

export async function updateProfile(userId, profileId, data) {
  const r = await fetch(`${BASE}/api/profiles/${profileId}`, {
    method: 'PATCH',
    headers: headers(userId),
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error('Could not update profile');
  return r.json();
}

export async function fetchProfileGraph(userId, profileId) {
  try {
    const r = await fetch(`${BASE}/api/profiles/${profileId}/graph`, { headers: headers(userId) });
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
}

export async function deleteProfile(userId, profileId) {
  const r = await fetch(`${BASE}/api/profiles/${profileId}`, {
    method: 'DELETE',
    headers: headers(userId),
  });
  if (!r.ok) throw new Error('Could not delete profile');
  return r.json();
}
