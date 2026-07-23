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
    connecting: 'Connecting…', listening: 'Listening — go ahead', speaking: 'WithCare is speaking…',
    error: 'Couldn’t start the call', ended: 'Call ended',
  }[status];

  return (
    <div className="fixed inset-0 z-[70] flex flex-col items-center justify-center p-6"
         style={{ background: 'rgb(var(--scrim) / 0.72)', backdropFilter: 'blur(6px)' }}>
      <div className="text-center">
        {/* Orb */}
        <div className="relative mx-auto mb-8 flex items-center justify-center" style={{ width: 160, height: 160 }}>
          <div className={`absolute inset-0 rounded-full intelligence-gradient ${status === 'error' ? '' : 'animate-ping'}`}
               style={{ opacity: 0.25 }} />
          <div className="relative rounded-full intelligence-gradient flex items-center justify-center"
               style={{ width: speaking ? 132 : 116, height: speaking ? 132 : 116, transition: 'all .25s ease' }}>
            <Sym name={status === 'error' ? 'error' : speaking ? 'graphic_eq' : 'mic'} className="text-white text-[46px]" fill />
          </div>
        </div>

        <h2 className="font-headline-lg text-[22px] text-white">Talk to WithCare</h2>
        <p className="text-[14px] text-white/80 mt-1 min-h-[20px]">{error || label}</p>

        {transcript && (
          <p className="mt-4 max-w-md mx-auto text-[13px] text-white/70 italic line-clamp-3">{transcript}</p>
        )}

        {status === 'error' && (
          <p className="mt-3 max-w-sm mx-auto text-[12px] text-white/60">
            Live voice needs the Gemini Live model enabled on your Vertex project/region, a microphone, and a supported browser (Chrome/Edge).
          </p>
        )}

        {/* End call */}
        <button onClick={onClose}
          className="press mt-9 w-16 h-16 rounded-full bg-error text-on-error flex items-center justify-center mx-auto shadow-lg shadow-error/40 hover:brightness-110">
          <Sym name="call_end" className="text-[30px]" fill />
        </button>
        <div className="text-[12px] text-white/60 mt-2">End call</div>
      </div>
    </div>
  );
}
