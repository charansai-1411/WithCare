const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

function headers(userId) {
  return { 'Content-Type': 'application/json', 'x-user-id': userId };
}

export async function fetchConversations(userId) {
  try {
    const r = await fetch(`${BASE}/api/conversations`, { headers: headers(userId) });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

export async function createConversation(userId, { title = 'New conversation', profileName = 'You' } = {}) {
  const r = await fetch(`${BASE}/api/conversations`, {
    method: 'POST',
    headers: headers(userId),
    body: JSON.stringify({ title, profile_name: profileName }),
  });
  return r.json();
}

export async function fetchMessages(userId, convId) {
  try {
    const r = await fetch(`${BASE}/api/conversations/${convId}/messages`, {
      headers: headers(userId),
    });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

export async function saveMessage(userId, convId, { role, content, carePlan = null, title, profileName }) {
  try {
    await fetch(`${BASE}/api/conversations/${convId}/messages`, {
      method: 'POST',
      headers: headers(userId),
      body: JSON.stringify({ role, content, care_plan: carePlan, title, profile_name: profileName }),
    });
  } catch {
    // non-fatal: message still shows in UI even if save fails
  }
}

export async function deleteConversation(userId, convId) {
  await fetch(`${BASE}/api/conversations/${convId}`, {
    method: 'DELETE',
    headers: headers(userId),
  });
}
