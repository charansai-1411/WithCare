import React, { useEffect, useRef, useState } from 'react';
import { saveVisit, timingToTimes } from '../services/visitApi';
import { addMedication } from '../services/medicationApi';
import { addRoutine } from '../services/routineApi';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const WS_URL = API.replace(/^http/, 'ws') + '/ws/scribe';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Float32 [-1,1] -> Int16 PCM (16 kHz mono, what Gemini Live expects)
function floatTo16(f32) {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function mmss(sec) {
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/**
 * Record Doctor Visit — a listen-only Gemini Live session that transcribes the consultation
 * (the assistant stays silent), then on Stop extracts medicines / diet / routines / follow-up
 * and saves a searchable record to the Reader. Extracted items are surfaced as one-tap adds.
 */
export default function VisitRecorder({ userId, profile, onClose, onSaved }) {
  const [status, setStatus] = useState('connecting'); // connecting | recording | saving | done | error
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [hospital, setHospital] = useState('');
  const [doctor, setDoctor] = useState('');
  const [result, setResult] = useState(null); // { doc_id, label, visit }

  const wsRef = useRef(null);
  const inCtxRef = useRef(null);
  const streamRef = useRef(null);
  const procRef = useRef(null);
  const transcriptRef = useRef('');
  const hospitalRef = useRef('');
  const doctorRef = useRef('');
  const savingRef = useRef(false);

  useEffect(() => { hospitalRef.current = hospital; }, [hospital]);
  useEffect(() => { doctorRef.current = doctor; }, [doctor]);

  // Tear down mic + socket (used on stop and unmount).
  function teardownAudio() {
    try { wsRef.current?.send(JSON.stringify({ type: 'end' })); } catch { /* noop */ }
    try { wsRef.current?.close(); } catch { /* noop */ }
    try { procRef.current?.disconnect(); } catch { /* noop */ }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    try { inCtxRef.current?.close(); } catch { /* noop */ }
  }

  // Timer while recording.
  useEffect(() => {
    if (status !== 'recording') return undefined;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [status]);

  useEffect(() => {
    let closed = false;

    async function startMic() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        });
        streamRef.current = stream;
        const AC = window.AudioContext || window.webkitAudioContext;
        const inCtx = new AC({ sampleRate: 16000 });
        inCtxRef.current = inCtx;
        const src = inCtx.createMediaStreamSource(stream);
        const proc = inCtx.createScriptProcessor(4096, 1, 1);
        procRef.current = proc;
        proc.onaudioprocess = (e) => {
          const ws = wsRef.current;
          if (!ws || ws.readyState !== WebSocket.OPEN) return;
          ws.send(floatTo16(e.inputBuffer.getChannelData(0)).buffer);
        };
        const mute = inCtx.createGain(); mute.gain.value = 0;
        src.connect(proc); proc.connect(mute); mute.connect(inCtx.destination);
        if (!closed) setStatus('recording');
      } catch (e) {
        setError(e.name === 'NotAllowedError'
          ? 'Microphone access denied — allow it to record the visit.'
          : (e.message || 'Mic error'));
        setStatus('error');
      }
    }

    try {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        if (typeof ev.data !== 'string') return; // scribe is silent — no audio frames
        let msg; try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type === 'ready') startMic();
        else if (msg.type === 'error') { setError(msg.message || 'Recording error'); setStatus('error'); }
        else if (msg.type === 'transcript' && msg.text) {
          transcriptRef.current = `${transcriptRef.current} ${msg.text}`.trim();
          setTranscript(transcriptRef.current);
        }
      };
      ws.onerror = () => { if (!closed) { setError('Could not connect to the recorder.'); setStatus('error'); } };
    } catch (e) {
      setError(e.message); setStatus('error');
    }

    return () => { closed = true; teardownAudio(); };
  }, []);

  async function stopAndSave() {
    if (savingRef.current) return;
    savingRef.current = true;
    teardownAudio();
    const text = transcriptRef.current.trim();
    if (text.length < 15) {
      setError('The recording was too short to capture anything. Please try again.');
      setStatus('error');
      return;
    }
    setStatus('saving');
    try {
      const out = await saveVisit(userId, {
        profile_id: profile?.id || null,
        patient_name: profile?.name || '',
        hospital: hospitalRef.current.trim(),
        doctor: doctorRef.current.trim(),
        transcript: text,
      });
      setResult(out);
      setStatus('done');
      onSaved && onSaved(out);
    } catch (e) {
      setError(e.message || 'Could not save the visit.');
      setStatus('error');
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-scrim/50 backdrop-blur-sm p-4">
      <div className="w-[min(96vw,560px)] max-h-[90vh] overflow-y-auto bg-surface-container-lowest border border-outline-variant rounded-3xl elev-5 m3-scale-in">
        {/* header */}
        <div className="flex items-center gap-3 p-5 border-b border-outline-variant/50">
          <span className="w-11 h-11 rounded-full intelligence-gradient flex items-center justify-center shrink-0">
            <Sym name="stethoscope" className="text-white text-[22px]" fill />
          </span>
          <div className="flex-1 min-w-0">
            <div className="font-title-lg text-[16px] text-on-surface">Record doctor visit</div>
            <div className="text-[12.5px] text-on-surface-variant">
              {profile?.name ? `For ${profile.name}` : 'Listening to your consultation'}
            </div>
          </div>
          <button onClick={onClose} title="Close"
            className="press w-10 h-10 rounded-full bg-surface-container text-on-surface-variant hover:bg-surface-container-high flex items-center justify-center shrink-0">
            <Sym name="close" className="text-[22px]" />
          </button>
        </div>

        <div className="p-5">
          {(status === 'connecting' || status === 'recording') && (
            <>
              <div className="flex items-center gap-3 mb-4">
                <span className="relative w-3 h-3 shrink-0">
                  <span className={`absolute inset-0 rounded-full ${status === 'recording' ? 'bg-error animate-ping' : 'bg-outline'}`} />
                  <span className={`relative block w-3 h-3 rounded-full ${status === 'recording' ? 'bg-error' : 'bg-outline'}`} />
                </span>
                <span className="text-[14px] font-semibold text-on-surface">
                  {status === 'connecting' ? 'Connecting…' : 'Recording'}
                </span>
                <span className="ml-auto tabular-nums text-[14px] text-on-surface-variant">{mmss(seconds)}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-4">
                <input value={hospital} onChange={(e) => setHospital(e.target.value)}
                  placeholder="Hospital (optional)"
                  className="px-3 py-2 rounded-xl bg-surface-container border border-outline-variant/60 text-[13px] text-on-surface placeholder:text-on-surface-variant/70 outline-none focus:border-primary" />
                <input value={doctor} onChange={(e) => setDoctor(e.target.value)}
                  placeholder="Doctor (optional)"
                  className="px-3 py-2 rounded-xl bg-surface-container border border-outline-variant/60 text-[13px] text-on-surface placeholder:text-on-surface-variant/70 outline-none focus:border-primary" />
              </div>

              <div className="rounded-2xl bg-surface-container p-3.5 min-h-[120px] max-h-[240px] overflow-y-auto text-[13px] leading-relaxed text-on-surface-variant whitespace-pre-wrap">
                {transcript || <span className="italic opacity-70">The conversation will appear here as it’s heard. WithCare only listens — it won’t speak during the visit.</span>}
              </div>

              <button onClick={stopAndSave} disabled={status !== 'recording'}
                className="press mt-4 w-full py-3 rounded-full bg-error text-on-error font-semibold text-[14px] flex items-center justify-center gap-2 disabled:opacity-50">
                <Sym name="stop_circle" className="text-[20px]" fill /> Stop &amp; save summary
              </button>
              <p className="mt-2 text-[11px] text-on-surface-variant text-center">
                Please make sure everyone in the room is okay with being recorded.
              </p>
            </>
          )}

          {status === 'saving' && (
            <div className="py-10 flex flex-col items-center gap-3 text-center">
              <span className="w-12 h-12 rounded-full intelligence-gradient flex items-center justify-center animate-pulse">
                <Sym name="auto_awesome" className="text-white text-[24px]" fill />
              </span>
              <div className="text-[14px] font-semibold text-on-surface">Summarizing the visit…</div>
              <div className="text-[12.5px] text-on-surface-variant">Pulling out medicines, diet and follow-ups.</div>
            </div>
          )}

          {status === 'done' && result && (
            <VisitResult userId={userId} profile={profile} result={result} onClose={onClose} />
          )}

          {status === 'error' && (
            <div className="py-8 flex flex-col items-center gap-3 text-center">
              <span className="w-12 h-12 rounded-full bg-error-container flex items-center justify-center">
                <Sym name="error" className="text-error text-[24px]" fill />
              </span>
              <div className="text-[13.5px] text-on-surface">{error || 'Something went wrong.'}</div>
              <div className="text-[11.5px] text-on-surface-variant">Recording needs a microphone and Chrome/Edge.</div>
              <button onClick={onClose} className="press mt-1 px-5 py-2 rounded-full bg-surface-container text-on-surface text-[13px] font-medium">Close</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// The saved-visit summary with one-tap "add" chips for each extracted medicine / routine.
function VisitResult({ userId, profile, result, onClose }) {
  const v = result.visit || {};
  const meds = v.medications || [];
  const routines = v.routines || [];
  const [added, setAdded] = useState({});   // key -> 'adding' | 'added' | 'error'

  const mark = (key, state) => setAdded((a) => ({ ...a, [key]: state }));

  async function addMed(m, i) {
    const key = `m${i}`;
    if (added[key]) return;
    mark(key, 'adding');
    try {
      await addMedication(userId, {
        profile_id: profile?.id || null,
        person: profile?.name || '',
        email: profile?.email || '',
        name: m.name,
        dose: m.dose || '',
        times: timingToTimes(m.timing || ''),
        per_dose: 1,
        quantity: 0,              // supply unknown from speech — user can set it in Medications
        refill_threshold_days: 5,
      });
      mark(key, 'added');
    } catch { mark(key, 'error'); }
  }

  async function addRt(r, i) {
    const key = `r${i}`;
    if (added[key]) return;
    mark(key, 'adding');
    try {
      await addRoutine(userId, {
        profile_id: profile?.id || null,
        person: profile?.name || '',
        email: profile?.email || '',
        name: r.name,
        category: r.category || 'other',
        content: r.content || '',
        frequency: r.frequency || '',
        remind: false,
      });
      mark(key, 'added');
    } catch { mark(key, 'error'); }
  }

  const chipCls = (state) =>
    `press inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12.5px] font-medium border transition-colors ${
      state === 'added'
        ? 'bg-g-green-tint text-g-green-text border-transparent'
        : state === 'error'
        ? 'bg-error-container text-error border-transparent'
        : 'bg-surface-container text-on-surface border-outline-variant/60 hover:bg-surface-container-high'
    }`;

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Sym name="check_circle" className="text-g-green text-[20px]" fill />
        <span className="text-[13.5px] font-semibold text-on-surface">Saved to Reader</span>
      </div>
      <p className="text-[13px] text-on-surface-variant leading-relaxed mb-4">{v.summary || 'Visit recorded.'}</p>

      {(v.hospital || v.doctor) && (
        <div className="text-[12px] text-on-surface-variant mb-4 flex flex-wrap gap-x-4 gap-y-1">
          {v.hospital && <span className="inline-flex items-center gap-1"><Sym name="local_hospital" className="text-[15px]" /> {v.hospital}</span>}
          {v.doctor && <span className="inline-flex items-center gap-1"><Sym name="person" className="text-[15px]" /> {v.doctor}</span>}
        </div>
      )}

      {meds.length > 0 && (
        <div className="mb-4">
          <div className="text-[11.5px] uppercase tracking-wide text-on-surface-variant mb-2">Medicines mentioned — tap to add</div>
          <div className="flex flex-wrap gap-2">
            {meds.map((m, i) => {
              const st = added[`m${i}`];
              return (
                <button key={i} className={chipCls(st)} onClick={() => addMed(m, i)} disabled={st === 'added' || st === 'adding'}>
                  <Sym name={st === 'added' ? 'check' : st === 'adding' ? 'progress_activity' : 'add'}
                    className={`text-[16px] ${st === 'adding' ? 'animate-spin' : ''}`} />
                  {m.name}{m.dose ? ` ${m.dose}` : ''}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {routines.length > 0 && (
        <div className="mb-4">
          <div className="text-[11.5px] uppercase tracking-wide text-on-surface-variant mb-2">Routines suggested — tap to add</div>
          <div className="flex flex-wrap gap-2">
            {routines.map((r, i) => {
              const st = added[`r${i}`];
              return (
                <button key={i} className={chipCls(st)} onClick={() => addRt(r, i)} disabled={st === 'added' || st === 'adding'}>
                  <Sym name={st === 'added' ? 'check' : st === 'adding' ? 'progress_activity' : 'add'}
                    className={`text-[16px] ${st === 'adding' ? 'animate-spin' : ''}`} />
                  {r.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {(v.diet?.length > 0 || v.workouts?.length > 0 || v.tests?.length > 0 || v.follow_up) && (
        <div className="rounded-2xl bg-surface-container p-3.5 text-[12.5px] text-on-surface-variant space-y-2 mb-4">
          {v.diet?.length > 0 && <div><b className="text-on-surface">Diet:</b> {v.diet.join('; ')}</div>}
          {v.workouts?.length > 0 && <div><b className="text-on-surface">Activity:</b> {v.workouts.join('; ')}</div>}
          {v.tests?.length > 0 && <div><b className="text-on-surface">Tests:</b> {v.tests.join('; ')}</div>}
          {v.follow_up && <div><b className="text-on-surface">Follow-up:</b> {v.follow_up}</div>}
        </div>
      )}

      <button onClick={onClose} className="press w-full py-2.5 rounded-full bg-primary text-on-primary font-semibold text-[14px]">Done</button>
    </div>
  );
}
