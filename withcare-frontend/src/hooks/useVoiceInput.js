import { useState, useRef, useCallback, useEffect } from 'react';
import { transcribeAudio } from '../services/voiceApi';

// Pick an audio format the browser can actually record (Chrome→webm/opus, Safari→mp4, etc.).
function pickMime() {
  if (typeof MediaRecorder === 'undefined') return '';
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) || '';
}

const SUPPORTED =
  typeof navigator !== 'undefined' &&
  !!navigator.mediaDevices?.getUserMedia &&
  typeof MediaRecorder !== 'undefined';

/**
 * Records mic audio and transcribes it via the backend (Gemini).
 * onResult(text) fires with the transcript so the caller can drop it into the input box.
 */
export function useVoiceInput({ userId, language = '', onResult }) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState('');

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => cleanupStream(), [cleanupStream]); // stop mic on unmount

  const start = useCallback(async () => {
    setError('');
    if (!SUPPORTED) { setError('Voice input isn’t supported in this browser.'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickMime();
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        cleanupStream();
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || mimeType || 'audio/webm' });
        chunksRef.current = [];
        if (!blob.size) { setTranscribing(false); return; }
        try {
          setTranscribing(true);
          const text = await transcribeAudio(userId, blob, language);
          if (text) onResult?.(text);
          else setError('Didn’t catch that — please try again.');
        } catch (ex) {
          setError(ex.message || 'Couldn’t transcribe — please try again.');
        } finally {
          setTranscribing(false);
        }
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch (ex) {
      cleanupStream();
      setError(ex.name === 'NotAllowedError'
        ? 'Microphone access denied. Allow it in your browser to use voice.'
        : (ex.message || 'Could not start recording.'));
    }
  }, [userId, language, onResult, cleanupStream]);

  const stop = useCallback(() => {
    setRecording(false);
    const rec = recorderRef.current;
    if (rec && rec.state !== 'inactive') rec.stop();
  }, []);

  const toggle = useCallback(() => { (recording ? stop : start)(); }, [recording, start, stop]);

  return { supported: SUPPORTED, recording, transcribing, error, toggle, clearError: () => setError('') };
}
