import React, { useEffect, useState, useCallback } from 'react';
import { fetchProfiles, fetchProfileGraph } from '../services/profileApi';
import { deleteKgItem } from '../services/kgApi';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Durable "facts" WithCare remembers — shown here so the user can review & delete them.
// Plans, reminders and appointments have their own views, so they're excluded.
const FACT_TYPES = {
  note:          { label: 'Remembered notes', icon: 'sticky_note_2', tone: 'text-g-yellow' },
  condition:     { label: 'Conditions',       icon: 'ecg_heart',     tone: 'text-g-red' },
  medication:    { label: 'Medications',      icon: 'medication',    tone: 'text-tertiary' },
  health_metric: { label: 'Health metrics',   icon: 'monitoring',    tone: 'text-g-green' },
  hospital:      { label: 'Hospitals',        icon: 'local_hospital', tone: 'text-primary' },
  scheme:        { label: 'Govt schemes',     icon: 'verified',      tone: 'text-primary' },
  insurance:     { label: 'Insurance',        icon: 'shield',        tone: 'text-g-blue' },
};
const ORDER = Object.keys(FACT_TYPES);

export default function MemoryManager({ userId, onClose }) {
  const [profiles, setProfiles] = useState([]);
  const [pid, setPid] = useState('');
  const [graph, setGraph] = useState(null);   // null = loading
  const [busy, setBusy] = useState({});

  useEffect(() => {
    fetchProfiles(userId).then((ps) => {
      setProfiles(ps);
      if (ps.length) setPid(ps[0].id);
    });
  }, [userId]);

  const load = useCallback(() => {
    if (!pid) return;
    setGraph(null);
    fetchProfileGraph(userId, pid).then(setGraph);
  }, [userId, pid]);
  useEffect(() => { load(); }, [load]);

  async function remove(node) {
    if (!window.confirm(`Forget this? WithCare will no longer remember:\n\n“${node.name}”`)) return;
    setBusy((b) => ({ ...b, [node.id]: true }));
    const ok = await deleteKgItem(userId, node.id);
    if (ok) {
      setGraph((g) => {
        if (!g) return g;
        const nodes = { ...g.nodes };
        for (const t of Object.keys(nodes)) nodes[t] = nodes[t].filter((n) => n.id !== node.id);
        return { ...g, nodes };
      });
    } else {
      setBusy((b) => ({ ...b, [node.id]: false }));
    }
  }

  const nodes = graph?.nodes || {};
  const sections = ORDER.map((t) => ({ t, ...FACT_TYPES[t], items: nodes[t] || [] })).filter((s) => s.items.length);
  const profileConditions = (graph?.profile?.conditions || '').split(/[;,]/).map((s) => s.trim()).filter(Boolean);
  const isEmpty = graph && sections.length === 0 && profileConditions.length === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg max-h-[85vh] flex flex-col bg-surface-container-lowest border border-outline-variant rounded-card elev-4 m3-scale-in overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-outline-variant">
          <div className="w-9 h-9 rounded-xl bg-primary-fixed flex items-center justify-center shrink-0">
            <Sym name="cognition" className="text-primary text-[20px]" fill />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-title-lg text-[16px] text-on-surface">Manage memory</div>
            <div className="text-[12px] text-on-surface-variant">What WithCare remembers about each profile.</div>
          </div>
          <button onClick={onClose} className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container">
            <Sym name="close" className="text-[20px]" />
          </button>
        </div>

        {/* Profile selector */}
        {profiles.length > 1 && (
          <div className="px-5 pt-4">
            <div className="flex gap-2 flex-wrap max-h-[92px] overflow-y-auto">
              {profiles.map((p) => (
                <button key={p.id} onClick={() => setPid(p.id)}
                  className={`px-3 py-1.5 rounded-full text-[12.5px] font-medium border transition-colors
                    ${pid === p.id ? 'border-primary bg-primary-fixed text-primary' : 'border-outline-variant text-on-surface-variant hover:bg-surface-container'}`}>
                  {p.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {graph === null ? (
            <div className="text-[13px] text-on-surface-variant py-8 text-center">Loading…</div>
          ) : isEmpty ? (
            <div className="text-center py-10 text-on-surface-variant">
              <Sym name="psychology_alt" className="text-[32px] opacity-60" />
              <p className="text-[13.5px] mt-2">Nothing remembered yet. As you chat, WithCare will note conditions, medicines, preferences and more here.</p>
            </div>
          ) : (
            <>
              {profileConditions.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-[12px] font-bold uppercase tracking-wide text-on-surface-variant mb-2">
                    <Sym name="badge" className="text-g-yellow text-[16px]" /> Profile conditions
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {profileConditions.map((c, i) => (
                      <span key={i} className="px-3 py-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-[12px]">{c}</span>
                    ))}
                  </div>
                  <div className="text-[11px] text-on-surface-variant/70 mt-1.5">Edit these from the profile’s Edit screen, or ask in chat (“remove arthritis from my conditions”).</div>
                </div>
              )}

              {sections.map((s) => (
                <div key={s.t}>
                  <div className="flex items-center gap-1.5 text-[12px] font-bold uppercase tracking-wide text-on-surface-variant mb-2">
                    <Sym name={s.icon} className={`${s.tone} text-[16px]`} fill /> {s.label}
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {s.items.map((n) => (
                      <div key={n.id} className="flex items-center gap-3 bg-surface-container-low border border-outline-variant/60 rounded-xl px-3.5 py-2.5">
                        <div className="flex-1 min-w-0">
                          <div className="text-[13.5px] text-on-surface truncate">{n.name}</div>
                          {n.data?.detail && <div className="text-[12px] text-on-surface-variant truncate">{n.data.detail}</div>}
                        </div>
                        <button onClick={() => remove(n)} disabled={busy[n.id]} title="Forget this"
                          className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-on-surface-variant hover:bg-error-container/50 hover:text-error transition-colors disabled:opacity-40">
                          <Sym name={busy[n.id] ? 'hourglass_empty' : 'delete'} className="text-[18px]" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        <div className="px-5 py-3 border-t border-outline-variant text-[11.5px] text-on-surface-variant/80">
          Tip: you can also edit memory by chatting — e.g. “remember I’m allergic to penicillin” or “forget my diabetes”.
        </div>
      </div>
    </div>
  );
}
