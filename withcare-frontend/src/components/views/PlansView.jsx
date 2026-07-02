import React, { useEffect, useState, useCallback } from 'react';
import { fetchKgItems } from '../../services/kgApi';

const ACCENT = '#1C7A6A';

// Light, safe render of the plan text: bold **headings**, keep line breaks. No HTML injection.
function PlanText({ text }) {
  const lines = (text || '').split('\n');
  return (
    <div style={{ fontSize: 13.5, color: '#3A4641', lineHeight: 1.6 }}>
      {lines.map((ln, i) => {
        const t = ln.trim();
        const h = t.match(/^\*\*(.+?)\*\*:?$/);
        if (h) return <div key={i} style={{ fontWeight: 700, color: '#26322F', marginTop: i ? 10 : 0 }}>{h[1]}</div>;
        if (!t) return <div key={i} style={{ height: 6 }} />;
        // strip inline ** markers
        return <div key={i}>{ln.replace(/\*\*/g, '')}</div>;
      })}
    </div>
  );
}

export default function PlansView({ userId }) {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState({});

  const load = useCallback(() => { fetchKgItems(userId, 'plans').then(setItems); }, [userId]);
  useEffect(() => { load(); }, [load]);

  const list = items || [];
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '28px 40px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Newsreader', serif", fontSize: 24, fontWeight: 600, color: '#26322F' }}>Workout & Diet Plans</div>
          <div style={{ fontSize: 13.5, color: '#9A9485' }}>Plans WithCare created, tailored to each person’s health.</div>
        </div>
        <button onClick={load} style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid #E2DACB', background: '#fff', color: '#6E7872', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>Refresh</button>
      </div>

      {items === null ? (
        <div style={{ color: '#9A9485', fontSize: 14 }}>Loading…</div>
      ) : list.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: '#B0A797', border: '1px dashed #DDD4C5', borderRadius: 16, background: '#FBF9F4' }}>
          No plans yet. In chat, try “create a diet plan for my mother” or “make a workout plan for my father”.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {list.map((it) => {
            const isDiet = it.type === 'diet_plan';
            const expanded = open[it.id];
            return (
              <div key={it.id} style={{ background: '#fff', border: '1px solid #E6DFD2', borderRadius: 16, overflow: 'hidden' }}>
                <button onClick={() => setOpen((o) => ({ ...o, [it.id]: !o[it.id] }))}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
                  <span style={{ fontSize: 20 }}>{isDiet ? '🥗' : '🏃'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15.5, fontWeight: 600, color: '#2C3833' }}>{it.name}</div>
                    <div style={{ fontSize: 12, color: '#A39C8C', marginTop: 2 }}>
                      {isDiet ? 'Diet plan' : 'Workout plan'}{it.profile_name ? ` · ${it.profile_name}` : ''}
                    </div>
                  </div>
                  <span style={{ color: '#A39C8C', fontSize: 13 }}>{expanded ? '▲' : '▼'}</span>
                </button>
                {expanded && (
                  <div style={{ padding: '4px 18px 18px', borderTop: '1px solid #F0EBE1' }}>
                    <PlanText text={it.data?.plan} />
                    <div style={{ fontSize: 11.5, color: '#B0A797', marginTop: 12 }}>General wellness guidance — not medical treatment.</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
