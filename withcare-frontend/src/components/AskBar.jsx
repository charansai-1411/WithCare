import React, { useState, useRef } from 'react';
import VoiceButton from './VoiceButton';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

/**
 * Docked composer for the feature pages (Tasks, Plans). Typing a message —
 * or tapping a suggestion, or speaking — opens the chat view and sends it via `onAsk`.
 */
export default function AskBar({ placeholder, suggestions = [], onAsk, userId }) {
  const [val, setVal] = useState('');
  const valRef = useRef(val);
  valRef.current = val; // latest value so an async voice transcript appends correctly
  const submit = () => {
    const t = val.trim();
    if (!t) return;
    onAsk(t);
    setVal('');
  };

  return (
    <div className="shrink-0 px-8 pb-5 pt-3 bg-gradient-to-t from-background via-background to-transparent">
      <div className="max-w-4xl mx-auto">
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2.5">
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => onAsk(s.q)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-outline-variant bg-surface-container-lowest hover:bg-surface-container text-[12.5px] text-on-surface-variant transition-colors">
                <Sym name={s.icon} className="text-primary text-[16px]" />{s.label}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2.5">
          <div className="flex-1 relative">
            <input value={val} onChange={(e) => setVal(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
              placeholder={placeholder}
              className="w-full bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-4 focus:ring-primary/10 rounded-action pl-5 pr-24 py-3.5 shadow-lg text-on-surface outline-none transition-all placeholder:text-on-surface-variant/50" />
            <div className="absolute right-2 top-1/2 -translate-y-1/2">
              <VoiceButton userId={userId}
                onTranscript={(t) => setVal(valRef.current ? `${valRef.current} ${t}` : t)} />
            </div>
          </div>
          <button onClick={submit}
            className="w-12 h-12 rounded-full intelligence-gradient text-white flex items-center justify-center shadow-lg shadow-primary/30 hover:scale-105 active:scale-95 transition-transform shrink-0">
            <Sym name="send" className="text-[22px]" fill />
          </button>
        </div>
        <div className="flex items-center justify-center gap-1.5 mt-2 text-[11px] text-on-surface-variant/70">
          <Sym name="auto_awesome" className="text-[13px]" fill /> Ask WithCare — it opens in chat.
        </div>
      </div>
    </div>
  );
}
