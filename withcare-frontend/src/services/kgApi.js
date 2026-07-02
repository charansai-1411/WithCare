const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export async function fetchKgItems(userId, kind) {
  try {
    const r = await fetch(`${BASE}/api/kg/items?kind=${kind}`, {
      headers: { 'x-user-id': userId },
    });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}
