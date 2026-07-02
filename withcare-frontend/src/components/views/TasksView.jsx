import React, { useEffect, useState, useCallback } from 'react';
import { fetchKgItems } from '../../services/kgApi';

const ACCENT = '#1C7A6A';

function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T') + (s.includes('T') ? '' : 'Z'));
  return isNaN(d) ? s : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function Icon({ type }) {
  const map = { appointment: '📅', reminder: '⏰', task: '✅' };
  return (
    <div style={{ width: 40, height: 40, borderRadius: 10, flex: '0 0 auto', background: '#EEF4F1',
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
      {map[type] || '•'}
    </div>
  );
}

export default function TasksView({ userId }) {
  const [items, setItems] = useState(null);

  const load = useCallback(() => {
    fetchKgItems(userId, 'tasks').then(setItems);
  }, [userId]);
  useEffect(() => { load(); }, [load]);

  const list = items || [];
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '28px 40px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Newsreader', serif", fontSize: 24, fontWeight: 600, color: '#26322F' }}>Tasks & Reminders</div>
          <div style={{ fontSize: 13.5, color: '#9A9485' }}>Appointments and reminders you've set through WithCare.</div>
        </div>
        <button onClick={load} style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid #E2DACB', background: '#fff', color: '#6E7872', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>Refresh</button>
      </div>

      {items === null ? (
        <div style={{ color: '#9A9485', fontSize: 14 }}>Loading…</div>
      ) : list.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: '#B0A797', border: '1px dashed #DDD4C5', borderRadius: 16, background: '#FBF9F4' }}>
          Nothing yet. In chat, try “schedule an eye check-up” or “remind my mother to take her tablet at 1pm daily”.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {list.map((it) => {
            const d = it.data || {};
            const meta = it.type === 'reminder'
              ? [d.recurrence && d.recurrence !== 'none' ? d.recurrence : 'one-time', d.time && `at ${d.time}`, d.lead_minutes != null && `${d.lead_minutes} min before`].filter(Boolean).join(' · ')
              : [d.when, d.hospital].filter(Boolean).join(' · ');
            return (
              <div key={it.id} style={{ display: 'flex', gap: 14, alignItems: 'flex-start', background: '#fff', border: '1px solid #E6DFD2', borderRadius: 14, padding: '14px 16px' }}>
                <Icon type={it.type} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: '#2C3833' }}>{it.name}</div>
                  {meta && <div style={{ fontSize: 13, color: '#6E7872', marginTop: 3 }}>{meta}</div>}
                  <div style={{ fontSize: 12, color: '#A39C8C', marginTop: 5 }}>
                    {it.profile_name ? `For ${it.profile_name} · ` : ''}{it.type} · updated {fmtDate(it.updated_at)}
                  </div>
                </div>
                <span style={{ fontSize: 11, fontWeight: 600, color: ACCENT, background: '#EDF3F0', border: '1px solid #DCE8E2', borderRadius: 999, padding: '3px 9px', flex: '0 0 auto' }}>
                  {it.type === 'reminder' ? 'Reminder' : 'Task'}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
