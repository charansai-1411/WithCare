// Auth: Google Sign-In with a dev-login fallback. The signed-in user is persisted
// in localStorage; user.id is sent as the x-user-id header everywhere.

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const USER_KEY = 'withcare_user';

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

export function signOut() {
  localStorage.removeItem(USER_KEY);
}

export async function fetchAuthConfig() {
  try {
    const r = await fetch(`${BASE}/api/auth/config`);
    return r.ok ? r.json() : { google_enabled: false, dev_login_enabled: true, google_client_id: '' };
  } catch {
    return { google_enabled: false, dev_login_enabled: true, google_client_id: '' };
  }
}

export async function googleLogin(credential) {
  const r = await fetch(`${BASE}/api/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  });
  if (!r.ok) throw new Error('Google sign-in failed');
  return setStoredUser(await r.json());
}

export async function devLogin(name) {
  const r = await fetch(`${BASE}/api/auth/dev`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name || 'Dev User' }),
  });
  if (!r.ok) throw new Error('Dev login failed');
  return setStoredUser(await r.json());
}
