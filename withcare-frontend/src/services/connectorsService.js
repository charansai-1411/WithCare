// Per-user connector state + real Google OAuth consent.
//
// Every user starts with ALL connectors disconnected. Clicking "Connect" requests real Google
// consent (Google Identity Services token model) for that connector's scopes; on approval we mark
// it connected. The connected list is sent with each chat request so the agent can refuse actions
// that need a connector the user hasn't connected yet.

const KEY = 'withcare.connectors';
// Access tokens live in sessionStorage (per-tab, short-lived) — never localStorage.
// Keyed by user so two people signing in on the same browser never share a token.
const TOK_KEY = 'withcare.tokens';

export const CONNECTORS = {
  calendar: { label: 'Google Calendar', scope: 'https://www.googleapis.com/auth/calendar.events' },
  drive:    { label: 'Google Drive',    scope: 'https://www.googleapis.com/auth/drive.file' },
  gmail:    { label: 'Gmail',           scope: 'https://www.googleapis.com/auth/gmail.send' },
  fit:      { label: 'Google Fit',      scope: 'https://www.googleapis.com/auth/fitness.activity.read https://www.googleapis.com/auth/fitness.heart_rate.read https://www.googleapis.com/auth/fitness.blood_pressure.read' },
};

function readAll() {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; }
}
function writeAll(o) {
  try { localStorage.setItem(KEY, JSON.stringify(o)); } catch { /* ignore */ }
}

export function getConnections(userId) {
  return readAll()[userId || 'anon'] || {};
}
export function isConnected(userId, key) {
  return !!getConnections(userId)[key];
}
export function setConnected(userId, key, on) {
  const all = readAll();
  const u = all[userId || 'anon'] || {};
  u[key] = !!on;
  all[userId || 'anon'] = u;
  writeAll(all);
  return u;
}
export function connectedList(userId) {
  const u = getConnections(userId);
  return Object.keys(u).filter((k) => u[k]);
}

// ── Per-user access tokens ──────────────────────────────────────────────────
// Stored in sessionStorage as { [userId]: { [key]: { token, exp } } }.
function readTokens() {
  try { return JSON.parse(sessionStorage.getItem(TOK_KEY) || '{}'); } catch { return {}; }
}
function writeTokens(o) {
  try { sessionStorage.setItem(TOK_KEY, JSON.stringify(o)); } catch { /* ignore */ }
}

export function setToken(userId, key, token, expiresIn) {
  const all = readTokens();
  const u = all[userId || 'anon'] || {};
  // Expire 60s early to avoid using a token that dies mid-request.
  u[key] = { token, exp: Date.now() + (Number(expiresIn) || 3600) * 1000 - 60000 };
  all[userId || 'anon'] = u;
  writeTokens(all);
}

export function clearToken(userId, key) {
  const all = readTokens();
  const u = all[userId || 'anon'];
  if (u && u[key]) { delete u[key]; all[userId || 'anon'] = u; writeTokens(all); }
}

export function getToken(userId, key) {
  const rec = (readTokens()[userId || 'anon'] || {})[key];
  if (!rec || !rec.token) return null;
  if (Date.now() >= rec.exp) { clearToken(userId, key); return null; }  // expired
  return rec.token;
}

// Map of connector → valid access token for this user. Only non-expired tokens.
// The chat request derives its connected-connectors list from these keys, so a
// connector with an expired token is treated as disconnected (agent asks to reconnect)
// instead of silently falling back to a shared account.
export function getValidTokens(userId) {
  const u = readTokens()[userId || 'anon'] || {};
  const out = {};
  for (const key of Object.keys(u)) {
    const t = getToken(userId, key);
    if (t) out[key] = t;
  }
  return out;
}

// Pop the real Google consent screen for a connector's scopes. Resolves with the access token
// on approval, rejects if the library/clientId is unavailable or the user cancels.
export function requestGoogleConsent(clientId, key) {
  return new Promise((resolve, reject) => {
    const scope = CONNECTORS[key]?.scope;
    if (!scope) return reject(new Error(`Unknown connector: ${key}`));
    if (!clientId) return reject(new Error('no_client_id'));
    if (!window.google?.accounts?.oauth2) return reject(new Error('gis_not_loaded'));
    try {
      const client = window.google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope,
        callback: (resp) => {
          if (resp && resp.access_token) resolve({ token: resp.access_token, expiresIn: resp.expires_in });
          else reject(new Error(resp?.error || 'consent_denied'));
        },
        error_callback: (err) => reject(new Error(err?.type || 'consent_cancelled')),
      });
      client.requestAccessToken({ prompt: 'consent' });
    } catch (e) {
      reject(e);
    }
  });
}
