const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export async function fetchDocuments(userId) {
  try {
    const r = await fetch(`${BASE}/api/documents`, { headers: { 'x-user-id': userId } });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

export async function uploadDocument(userId, file, label) {
  const form = new FormData();
  form.append('file', file);
  form.append('label', label || '');
  const r = await fetch(`${BASE}/api/documents`, {
    method: 'POST',
    headers: { 'x-user-id': userId },
    body: form,
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(detail.detail || 'Upload failed');
  }
  return r.json();
}

export async function deleteDocument(userId, docId) {
  await fetch(`${BASE}/api/documents/${docId}`, {
    method: 'DELETE',
    headers: { 'x-user-id': userId },
  });
}

export async function askDocuments(userId, question, label) {
  const r = await fetch(`${BASE}/api/documents/ask`, {
    method: 'POST',
    headers: { 'x-user-id': userId, 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, label: label || '' }),
  });
  if (!r.ok) throw new Error('Ask failed');
  return r.json();
}
