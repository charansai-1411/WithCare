import React, { useState, useRef, useEffect } from 'react';
import { useVoiceInput } from '../hooks/useVoiceInput';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Language hint sent to Gemini ('' = auto-detect). Covers English + major Indian languages.
const LANGS = [
  { code: '', short: 'Auto', label: 'Auto-detect' },
  { code: 'English', short: 'EN', label: 'English' },
  { code: 'Hindi', short: 'HI', label: 'हिन्दी · Hindi' },
  { code: 'Telugu', short: 'TE', label: 'తెలుగు · Telugu' },
  { code: 'Tamil', short: 'TA', label: 'தமிழ் · Tamil' },
  { code: 'Kannada', short: 'KN', label: 'ಕನ್ನಡ · Kannada' },
  { code: 'Malayalam', short: 'ML', label: 'മലയാളം · Malayalam' },
  { code: 'Marathi', short: 'MR', label: 'मराठी · Marathi' },
  { code: 'Bengali', short: 'BN', label: 'বাংলা · Bengali' },
  { code: 'Gujarati', short: 'GU', label: 'ગુજરાતી · Gujarati' },
  { code: 'Punjabi', short: 'PA', label: 'ਪੰਜਾਬੀ · Punjabi' },
  { code: 'Urdu', short: 'UR', label: 'اردو · Urdu' },
];
const KEY = 'withcare-voice-lang';

export default function VoiceButton({ userId, onTranscript }) {
  const [lang, setLang] = useState(() => { try { return localStorage.getItem(KEY) || ''; } catch { return ''; } });
  const [menu, setMenu] = useState(false);
  const wrapRef = useRef(null);

  const { supported, recording, transcribing, error, toggle, clearError } =
    useVoiceInput({ userId, language: lang, onResult: onTranscript });

  useEffect(() => {
    if (!menu) return;
    const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setMenu(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menu]);

  if (!supported) return null; // gracefully hide where the browser can't record

  const current = LANGS.find((l) => l.code === lang) || LANGS[0];
  const chooseLang = (code) => {
    setLang(code); setMenu(false);
    try { localStorage.setItem(KEY, code); } catch {}
  };

  return (
    <div ref={wrapRef} className="relative flex items-center gap-1">
      {/* Error bubble */}
      {error && (
        <div className="absolute bottom-full right-0 mb-2 w-max max-w-[220px] px-3 py-1.5 rounded-xl bg-error-container text-on-error-container text-[11.5px] shadow-lg">
          {error}
        </div>
      )}

      {/* Language picker */}
      <button type="button" onClick={() => { setMenu((m) => !m); clearError(); }} title="Voice language"
        className="px-2 h-7 rounded-full text-[11px] font-semibold text-on-surface-variant hover:bg-surface-container flex items-center gap-0.5">
        <Sym name="language" className="text-[15px]" />{current.short}
      </button>
      {menu && (
        <div className="absolute bottom-full right-0 mb-2 w-48 max-h-72 overflow-y-auto bg-surface-container-lowest border border-outline-variant rounded-2xl elev-4 py-1.5 z-30">
          {LANGS.map((l) => (
            <button key={l.code || 'auto'} type="button" onClick={() => chooseLang(l.code)}
              className={`w-full text-left px-3.5 py-1.5 text-[13px] hover:bg-surface-container flex items-center justify-between
                ${l.code === lang ? 'text-primary font-semibold' : 'text-on-surface'}`}>
              {l.label}
              {l.code === lang && <Sym name="check" className="text-[16px]" />}
            </button>
          ))}
        </div>
      )}

      {/* Mic button */}
      <button type="button" onClick={toggle} disabled={transcribing}
        title={recording ? 'Stop and transcribe' : 'Speak your message'}
        className={`w-10 h-10 rounded-full flex items-center justify-center transition-all shrink-0 disabled:opacity-60
          ${recording ? 'bg-error text-on-error animate-pulse'
            : transcribing ? 'bg-surface-container text-on-surface-variant'
            : 'text-on-surface-variant hover:bg-surface-container'}`}>
        <Sym name={transcribing ? 'progress_activity' : recording ? 'stop' : 'mic'}
             className={`text-[22px] ${transcribing ? 'animate-spin' : ''}`} fill={recording} />
      </button>
    </div>
  );
}
