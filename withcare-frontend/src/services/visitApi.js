const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Send a recorded consultation transcript to be extracted (one Gemini call) and stored in the
// Reader as a structured visit record. Returns { doc_id, label, visit: {summary, medications[], …} }.
export async function saveVisit(userId, body) {
  const res = await fetch(`${BASE}/api/visits/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId || '' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

// Best-effort map a doctor's spoken timing ("every morning after breakfast", "twice daily
// morning and night") to clock times, so a one-tap medication add gets sensible dose reminders.
export function timingToTimes(timing = '') {
  const t = timing.toLowerCase();
  const times = [];
  const has = (...w) => w.some((x) => t.includes(x));
  if (has('morning', 'breakfast', 'am', 'sunrise', 'wake')) times.push('09:00');
  if (has('noon', 'afternoon', 'lunch', 'midday')) times.push('13:00');
  if (has('evening', 'night', 'dinner', 'bed', 'pm')) times.push('21:00');
  if (!times.length) {
    if (has('twice', 'two times', 'bd', '2 times')) return ['09:00', '21:00'];
    if (has('thrice', 'three times', 'tds', '3 times')) return ['09:00', '13:00', '21:00'];
    return ['09:00'];
  }
  return Array.from(new Set(times));
}
