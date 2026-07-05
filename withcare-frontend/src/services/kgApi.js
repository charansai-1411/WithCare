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

// Delete any KG item (reminder, appointment, plan, memory fact). For reminders/appointments the
// backend also removes the linked Google Calendar event.
export async function deleteKgItem(userId, nodeId) {
  try {
    const r = await fetch(`${BASE}/api/kg/items/${nodeId}`, {
      method: 'DELETE',
      headers: { 'x-user-id': userId },
    });
    return r.ok;
  } catch {
    return false;
  }
}
