import React, { useEffect, useState, useCallback } from 'react';
import { fetchDocuments } from '../../services/readerApi';
import VisitRecorder from '../VisitRecorder';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function niceDate(iso) {
  if (!iso) return '';
  const d = new Date(iso.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Record Doctor Visit — start a listen-only Gemini Live recording of a consultation, then get a
 * structured summary saved to the Reader. Past visits are listed here; tap one to ask about it.
 */
export default function VisitView({ userId, profile, onAsk }) {
  const [recording, setRecording] = useState(false);
  const [visits, setVisits] = useState(null);

  const load = useCallback(() => {
    if (!userId) return;
    fetchDocuments(userId).then((docs) =>
      setVisits((docs || []).filter((d) => d.kind === 'visit')));
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background">
      <div className="flex-1 overflow-y-auto px-8 py-7">
        <div className="max-w-4xl mx-auto">
          {/* Hero / start */}
          <div className="rounded-3xl border border-outline-variant/60 bg-surface-container-lowest p-6 md:p-7 elev-1">
            <div className="flex items-start gap-4">
              <span className="w-14 h-14 rounded-2xl intelligence-gradient flex items-center justify-center shrink-0">
                <Sym name="stethoscope" className="text-white text-[28px]" fill />
              </span>
              <div className="flex-1 min-w-0">
                <h1 className="font-title-lg text-[19px] text-on-surface">Record a doctor visit</h1>
                <p className="mt-1.5 text-[13.5px] text-on-surface-variant leading-relaxed max-w-2xl">
                  Turn it on during the consultation and WithCare listens quietly — it won’t speak.
                  When you stop, it pulls out the <b className="text-on-surface">medicines, diet, exercise,
                  routines and follow-up</b>, and saves a summary you can search later
                  {profile?.name ? <> for <b className="text-on-surface">{profile.name}</b></> : null}.
                </p>
                <button onClick={() => setRecording(true)}
                  className="press mt-4 inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-primary text-on-primary text-[14px] font-semibold hover:brightness-110">
                  <Sym name="mic" className="text-[20px]" fill /> Start recording
                </button>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { icon: 'hearing', t: 'Listens, never interrupts', d: 'Silent transcription over Gemini Live.' },
                { icon: 'medication', t: 'Extracts the essentials', d: 'Medicines, diet, routines, tests, follow-up.' },
                { icon: 'auto_stories', t: 'Saved & searchable', d: 'Ask “summarise last week’s visit” anytime.' },
              ].map((f) => (
                <div key={f.t} className="rounded-2xl bg-surface-container p-3.5">
                  <Sym name={f.icon} className="text-primary text-[20px]" fill />
                  <div className="mt-1.5 text-[13px] font-semibold text-on-surface">{f.t}</div>
                  <div className="text-[12px] text-on-surface-variant leading-snug">{f.d}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Past visits */}
          <div className="mt-7">
            <h2 className="font-title-lg text-[15px] text-on-surface mb-3">Past visits</h2>
            {visits === null ? (
              <div className="text-[13px] text-on-surface-variant">Loading…</div>
            ) : visits.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-outline-variant/70 p-8 text-center">
                <Sym name="clinical_notes" className="text-on-surface-variant/60 text-[32px]" />
                <div className="mt-2 text-[13.5px] text-on-surface">No recorded visits yet</div>
                <div className="text-[12.5px] text-on-surface-variant">Your saved consultations will appear here.</div>
              </div>
            ) : (
              <div className="rounded-2xl border border-outline-variant/60 divide-y divide-outline-variant/50 overflow-hidden">
                {visits.map((d) => (
                  <button key={d.id} onClick={() => onAsk && onAsk(`Summarise this doctor visit and list the medicines, diet and follow-up: ${d.label}`)}
                    className="w-full flex items-center gap-3.5 px-5 py-4 text-left hover:bg-surface-container/40 transition-colors">
                    <span className="w-10 h-10 rounded-full bg-error-container/50 flex items-center justify-center shrink-0">
                      <Sym name="stethoscope" className="text-error text-[20px]" fill />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[13.5px] font-medium text-on-surface truncate">{d.label || 'Doctor visit'}</div>
                      <div className="text-[12px] text-on-surface-variant">{niceDate(d.created_at)}</div>
                    </div>
                    <Sym name="chat" className="text-on-surface-variant/70 text-[18px] shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {recording && (
        <VisitRecorder userId={userId} profile={profile}
          onClose={() => { setRecording(false); load(); }}
          onSaved={load} />
      )}
    </div>
  );
}
