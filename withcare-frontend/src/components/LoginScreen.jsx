import React, { useEffect, useRef, useState } from 'react';
import { fetchAuthConfig, googleLogin, devLogin } from '../services/authService';

const ACCENT = '#1C7A6A';

export default function LoginScreen({ onLogin }) {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const gbtn = useRef(null);

  useEffect(() => { fetchAuthConfig().then(setCfg); }, []);

  // Client ID: backend config wins; fall back to a frontend build-time env var.
  const clientId = cfg?.google_client_id || import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
  const googleEnabled = !!clientId;

  // Render the Google Sign-In button once config + GIS script are ready.
  useEffect(() => {
    if (!googleEnabled) return;
    let tries = 0;
    const t = setInterval(() => {
      tries++;
      if (window.google?.accounts?.id && gbtn.current) {
        clearInterval(t);
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async ({ credential }) => {
            setBusy(true); setError('');
            try { onLogin(await googleLogin(credential)); }
            catch { setError('Google sign-in failed. Try again.'); setBusy(false); }
          },
        });
        window.google.accounts.id.renderButton(gbtn.current, {
          theme: 'outline', size: 'large', width: 300, text: 'continue_with',
        });
      }
      if (tries > 40) clearInterval(t);
    }, 150);
    return () => clearInterval(t);
  }, [googleEnabled, clientId, onLogin]);

  async function handleDev() {
    setBusy(true); setError('');
    try { onLogin(await devLogin('Dev User')); }
    catch { setError('Dev login failed — is the backend running?'); setBusy(false); }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#F6F2EC', fontFamily: "'Hanken Grotesk', system-ui, sans-serif" }}>
      <div style={{ width: 380, padding: '40px 36px', background: '#fff', borderRadius: 22,
        border: '1px solid #E6DFD2', boxShadow: '0 10px 40px rgba(40,30,20,0.08)', textAlign: 'center' }}>
        <div style={{ width: 56, height: 56, borderRadius: 16, background: ACCENT, color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px',
          fontSize: 24, fontWeight: 800 }}>W</div>
        <div style={{ fontFamily: "'Newsreader', serif", fontSize: 26, fontWeight: 600, color: '#26322F' }}>
          Welcome to WithCare
        </div>
        <div style={{ fontSize: 14, color: '#9A9485', marginTop: 6, marginBottom: 26 }}>
          Healthcare navigation, with care. Sign in to continue.
        </div>

        {googleEnabled && (
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
            <div ref={gbtn} />
          </div>
        )}

        {cfg && !googleEnabled && (
          <div style={{ fontSize: 12.5, color: '#B0A797', marginBottom: 14, lineHeight: 1.5 }}>
            Google Sign-In isn’t configured yet. Add a Web OAuth Client ID as
            <code style={{ background: '#F2EEE6', padding: '1px 5px', borderRadius: 4, margin: '0 3px' }}>
              GOOGLE_OAUTH_CLIENT_ID</code>
            in the backend .env to enable it.
          </div>
        )}

        {cfg?.dev_login_enabled && (
          <button onClick={handleDev} disabled={busy}
            style={{ width: '100%', padding: '11px', borderRadius: 12, cursor: 'pointer',
              border: `1px solid ${ACCENT}`, background: googleEnabled ? '#fff' : ACCENT,
              color: googleEnabled ? ACCENT : '#fff', fontSize: 14, fontWeight: 600 }}>
            {busy ? 'Signing in…' : 'Continue as guest (dev)'}
          </button>
        )}

        {error && <div style={{ color: '#C0492E', fontSize: 12.5, marginTop: 12 }}>{error}</div>}
      </div>
    </div>
  );
}
