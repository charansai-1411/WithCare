import React, { useEffect, useRef, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const WS_URL = API.replace(/^http/, 'ws') + '/ws/live';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Float32 [-1,1] -> Int16 PCM
function floatTo16(f32) {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

/**
 * A full-screen "call" with WithCare over Gemini Live: mic (16 kHz PCM) → backend WS →
 * Gemini → reply audio (24 kHz PCM) played back, with barge-in.
 */
export default function LiveVoice({ onClose }) {
  const [status, setStatus] = useState('connecting'); // connecting | listening | speaking | error | ended
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');

  const wsRef = useRef(null);
  const inCtxRef = useRef(null);
  const outCtxRef = useRef(null);
  const streamRef = useRef(null);
  const procRef = useRef(null);
  const playHeadRef = useRef(0);
  const sourcesRef = useRef([]);

  useEffect(() => {
    let closed = false;

    function stopPlayback() {
      sourcesRef.current.forEach((s) => { try { s.stop(); } catch { /* noop */ } });
      sourcesRef.current = [];
      if (outCtxRef.current) playHeadRef.current = outCtxRef.current.currentTime;
    }

    function playPcm(int16) {
      const ctx = outCtxRef.current;
      if (!ctx) return;
      const f32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) f32[i] = int16[i] / 32768;
      const buf = ctx.createBuffer(1, f32.length, 24000);
      buf.getChannelData(0).set(f32);
      const s = ctx.createBufferSource();
      s.buffer = buf; s.connect(ctx.destination);
      const now = ctx.currentTime;
      if (playHeadRef.current < now) playHeadRef.current = now;
      s.start(playHeadRef.current);
      playHeadRef.current += buf.duration;
      s.onended = () => {
        sourcesRef.current = sourcesRef.current.filter((x) => x !== s);
        if (!sourcesRef.current.length && !closed) setStatus('listening');
      };
      sourcesRef.current.push(s);
    }

    async function startMic() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        });
        streamRef.current = stream;
        const AC = window.AudioContext || window.webkitAudioContext;
        const inCtx = new AC({ sampleRate: 16000 });
        inCtxRef.current = inCtx;
        outCtxRef.current = new AC({ sampleRate: 24000 });
        const src = inCtx.createMediaStreamSource(stream);
        const proc = inCtx.createScriptProcessor(4096, 1, 1);
        procRef.current = proc;
        proc.onaudioprocess = (e) => {
          const ws = wsRef.current;
          if (!ws || ws.readyState !== WebSocket.OPEN) return;
          ws.send(floatTo16(e.inputBuffer.getChannelData(0)).buffer);
        };
        // Route through a muted gain so the processor runs without echoing the mic to the speakers.
        const mute = inCtx.createGain(); mute.gain.value = 0;
        src.connect(proc); proc.connect(mute); mute.connect(inCtx.destination);
        if (!closed) setStatus('listening');
      } catch (e) {
        setError(e.name === 'NotAllowedError' ? 'Microphone access denied — allow it to talk.' : (e.message || 'Mic error'));
        setStatus('error');
      }
    }

    try {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        if (typeof ev.data === 'string') {
          let msg; try { msg = JSON.parse(ev.data); } catch { return; }
          if (msg.type === 'ready') startMic();
          else if (msg.type === 'error') { setError(msg.message || 'Live voice error'); setStatus('error'); }
          else if (msg.type === 'text') setTranscript((t) => `${t} ${msg.text}`.trim().slice(-400));
          else if (msg.type === 'interrupted') stopPlayback();
          else if (msg.type === 'turn_complete') { if (!sourcesRef.current.length && !closed) setStatus('listening'); }
        } else {
          playPcm(new Int16Array(ev.data));
          if (!closed) setStatus('speaking');
        }
      };
      ws.onerror = () => { if (!closed) { setError('Could not connect to the live service.'); setStatus('error'); } };
      ws.onclose = () => { if (!closed) setStatus((s) => (s === 'error' ? s : 'ended')); };
    } catch (e) {
      setError(e.message); setStatus('error');
    }

    return () => {
      closed = true;
      try { wsRef.current?.send(JSON.stringify({ type: 'end' })); } catch { /* noop */ }
      try { wsRef.current?.close(); } catch { /* noop */ }
      try { procRef.current?.disconnect(); } catch { /* noop */ }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      try { inCtxRef.current?.close(); } catch { /* noop */ }
      try { outCtxRef.current?.close(); } catch { /* noop */ }
    };
  }, []);

  const speaking = status === 'speaking';
  const label = {
    connecting: 'Connecting…', listening: 'Listening — just speak', speaking: 'WithCare is speaking…',
    error: 'Couldn’t start voice chat', ended: 'Voice chat ended',
  }[status];

  // A compact voice bar docked above the composer — a normal spoken conversation, not a call.
  return (
    <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[70] w-[min(92vw,440px)]">
      <div className="bg-surface-container-lowest border border-outline-variant rounded-3xl elev-5 p-4 m3-scale-in">
        <div className="flex items-center gap-3">
          <div className="relative w-11 h-11 shrink-0 flex items-center justify-center">
            {status !== 'error' && <span className="absolute inset-0 rounded-full intelligence-gradient animate-ping" style={{ opacity: 0.25 }} />}
            <span className="relative w-11 h-11 rounded-full intelligence-gradient flex items-center justify-center">
              <Sym name={status === 'error' ? 'error' : speaking ? 'graphic_eq' : 'mic'} className="text-white text-[22px]" fill />
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-semibold text-on-surface">Voice chat</div>
            <div className="text-[12.5px] text-on-surface-variant truncate">{error || label}</div>
          </div>
          <button onClick={onClose} title="Stop voice chat"
            className="press w-10 h-10 rounded-full bg-surface-container text-on-surface-variant hover:bg-error-container hover:text-error flex items-center justify-center shrink-0">
            <Sym name="close" className="text-[22px]" />
          </button>
        </div>
        {transcript && <p className="mt-2.5 text-[12.5px] text-on-surface-variant italic line-clamp-2">{transcript}</p>}
        {status === 'error' && (
          <p className="mt-2 text-[11.5px] text-on-surface-variant">Needs a microphone and a supported browser (Chrome/Edge).</p>
        )}
      </div>
    </div>
  );
}
