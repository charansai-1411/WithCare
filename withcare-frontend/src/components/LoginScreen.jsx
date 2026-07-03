import React, { useEffect, useRef, useState } from 'react';
import { fetchAuthConfig, googleLogin, devLogin } from '../services/authService';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

export default function LoginScreen({ onLogin }) {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const gbtn = useRef(null);

  useEffect(() => { fetchAuthConfig().then(setCfg); }, []);

  const clientId = cfg?.google_client_id || import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
  const googleEnabled = !!clientId;

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
    <div className="h-screen flex items-center justify-center bg-background font-body-md relative overflow-hidden">
      {/* ambient gradient glow */}
      <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full intelligence-gradient opacity-10 blur-3xl" />
      <div className="absolute -bottom-32 -right-32 w-96 h-96 rounded-full intelligence-gradient opacity-10 blur-3xl" />

      <div className="relative w-[400px] p-9 bg-surface-container-lowest rounded-[24px] border border-outline-variant shadow-2xl text-center">
        <div className="w-16 h-16 rounded-[20px] intelligence-gradient flex items-center justify-center mx-auto mb-5 shadow-lg shadow-primary/20">
          <Sym name="auto_awesome" className="text-white text-[32px]" fill />
        </div>
        <h1 className="font-headline-lg text-[26px] text-on-surface">Welcome to WithCare</h1>
        <p className="text-[14px] text-on-surface-variant mt-1.5 mb-7">Healthcare navigation, <span className="text-gradient font-semibold">with care</span>. Sign in to continue.</p>

        {googleEnabled && (
          <div className="flex justify-center mb-3.5">
            <div ref={gbtn} />
          </div>
        )}

        {cfg && !googleEnabled && (
          <div className="text-[12.5px] text-on-surface-variant mb-3.5 leading-relaxed">
            Google Sign-In isn’t configured yet. Add a Web OAuth Client ID as
            <code className="bg-surface-container px-1.5 py-0.5 rounded mx-1 font-mono text-[11px]">GOOGLE_OAUTH_CLIENT_ID</code>
            in the backend .env to enable it.
          </div>
        )}

        {cfg?.dev_login_enabled && (
          <button onClick={handleDev} disabled={busy}
            className={`w-full py-3 rounded-full text-[14px] font-semibold transition active:scale-[0.98] disabled:opacity-60
              ${googleEnabled
                ? 'border border-outline-variant text-on-surface hover:bg-surface-container'
                : 'intelligence-gradient text-white shadow-md shadow-primary/20 hover:brightness-105'}`}>
            {busy ? 'Signing in…' : 'Continue as guest (dev)'}
          </button>
        )}

        {error && <div className="text-error text-[12.5px] mt-3">{error}</div>}

        <p className="text-[11px] text-on-surface-variant/70 mt-6 flex items-center justify-center gap-1">
          <Sym name="shield" className="text-[14px]" fill /> Your care data stays private. Powered by Gemini.
        </p>
      </div>
    </div>
  );
}
