const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Send a recorded audio blob to the backend for Gemini transcription.
// `language` is an optional hint (e.g. "Hindi"); the model auto-detects otherwise.
export async function transcribeAudio(userId, blob, language = '') {
  const form = new FormData();
  const ext = (blob.type || '').includes('ogg') ? 'ogg' : (blob.type || '').includes('mp4') ? 'mp4' : 'webm';
  form.append('file', blob, `speech.${ext}`);
  if (language) form.append('language', language);

  const res = await fetch(`${BASE}/api/voice/transcribe`, {
    method: 'POST',
    headers: { 'x-user-id': userId || '' },
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Transcription failed (${res.status})`);
  }
  const data = await res.json();
  return (data.text || '').trim();
}
