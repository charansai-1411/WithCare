import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchKgItems, deleteKgItem } from '../../services/kgApi';
import AskBar from '../AskBar';
import { SkeletonList } from '../ui/Skeleton';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s.replace(' ', 'T') + (s.includes('T') ? '' : 'Z'));
  return isNaN(d) ? s : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function SegTabs({ tabs, value, onChange }) {
  return (
    <div className="flex border border-outline-variant rounded-full overflow-hidden">
      {tabs.map((t) => (
        <button key={t.k} onClick={() => onChange(t.k)}
          className={`px-4 py-1.5 text-[13px] font-medium transition-colors ${value === t.k ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container'}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

function PersonChips({ persons, value, onChange }) {
  if (persons.length <= 1) return null;
  const all = ['__all', ...persons];
  return (
    <div className="flex gap-2 flex-wrap">
      {all.map((p) => (
        <button key={p} onClick={() => onChange(p)}
          className={`px-3 py-1.5 rounded-full text-[12.5px] font-medium border transition-colors
            ${value === p ? 'border-primary bg-primary-fixed text-primary' : 'border-outline-variant text-on-surface-variant hover:bg-surface-container'}`}>
          {p === '__all' ? 'Everyone' : p}
        </button>
      ))}
    </div>
  );
}

function Toggle({ on, onClick }) {
  return (
    <button onClick={onClick} title={on ? 'Pause reminder' : 'Resume reminder'}
      className={`w-11 h-6 rounded-full flex items-center px-0.5 transition-colors shrink-0 ${on ? 'bg-primary justify-end' : 'bg-surface-container-highest justify-start'}`}>
      <span className="w-5 h-5 rounded-full bg-white shadow-sm" />
    </button>
  );
}

export default function TasksView({ userId, onAsk }) {
  const [items, setItems] = useState(null);
  const [tab, setTab] = useState('all');
  const [person, setPerson] = useState('__all');
  const [paused, setPaused] = useState({});

  const [busy, setBusy] = useState({});

  const load = useCallback(() => { fetchKgItems(userId, 'tasks').then(setItems); }, [userId]);
  useEffect(() => { load(); }, [load]);

  async function remove(it) {
    const label = it.type === 'reminder' ? 'reminder' : 'appointment';
    if (!window.confirm(`Delete this ${label}${it.type !== 'diet_plan' ? ' and its calendar event' : ''}?\n\n“${it.name}”`)) return;
    setBusy((b) => ({ ...b, [it.id]: true }));
    const ok = await deleteKgItem(userId, it.id);
    if (ok) setItems((prev) => (prev || []).filter((x) => x.id !== it.id));
    else setBusy((b) => ({ ...b, [it.id]: false }));
  }

  const list = items || [];
  const persons = useMemo(() => [...new Set(list.map(i => i.profile_name).filter(Boolean))], [list]);

  const filtered = list.filter((it) => {
    if (tab === 'reminders' && it.type !== 'reminder') return false;
    if (tab === 'appointments' && it.type !== 'appointment') return false;
    if (person !== '__all' && it.profile_name !== person) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background">
      <div className="flex-1 overflow-y-auto px-8 py-7">
        <div className="max-w-4xl mx-auto">
        <div className="flex items-start gap-4 mb-6">
          <div className="flex-1">
            <h1 className="font-headline-lg text-[24px] text-on-surface">Tasks &amp; Reminders</h1>
            <p className="text-[14px] text-on-surface-variant mt-0.5">Appointments and medication reminders, delivered where you’ll see them.</p>
          </div>
          <button onClick={load}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-outline-variant text-on-surface-variant text-[13px] font-medium hover:bg-surface-container shrink-0">
            <Sym name="refresh" className="text-[18px]" /> Refresh
          </button>
        </div>

        {list.length > 0 && (
          <div className="flex items-center gap-4 flex-wrap mb-5">
            <SegTabs value={tab} onChange={setTab}
              tabs={[{ k: 'all', label: 'All' }, { k: 'reminders', label: 'Reminders' }, { k: 'appointments', label: 'Appointments' }]} />
            <PersonChips persons={persons} value={person} onChange={setPerson} />
          </div>
        )}

        {items === null ? (
          <SkeletonList count={3} />
        ) : filtered.length === 0 ? (
          <div className="rounded-card border border-dashed border-outline-variant bg-surface-container-low p-10 text-center">
            <Sym name="alarm_add" className="text-[32px] text-on-surface-variant/60" />
            <div className="text-[14.5px] font-medium text-on-surface mt-2.5">Nothing here yet</div>
            <div className="text-[13px] text-on-surface-variant mt-1">Try: “remind my mother to take her tablet at 1pm daily”</div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {filtered.map((it) => {
              const d = it.data || {};
              const isReminder = it.type === 'reminder';
              const on = paused[it.id] !== true;
              return (
                <div key={it.id} className="flex items-center gap-4 bg-surface-container-lowest border border-outline-variant rounded-card shadow-sm p-4 hover:shadow-md transition-shadow">
                  <div className={`w-11 h-11 rounded-xl shrink-0 flex items-center justify-center ${isReminder ? 'bg-tertiary-fixed' : 'bg-primary-fixed'}`}>
                    <Sym name={isReminder ? 'alarm' : 'event'} className={`text-[22px] ${isReminder ? 'text-tertiary' : 'text-primary'}`} fill />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[15px] font-semibold text-on-surface">{it.name}</div>
                    <div className="flex items-center gap-2 flex-wrap mt-1.5 text-[12.5px] text-on-surface-variant">
                      {isReminder ? (<>
                        <span className="px-2.5 py-0.5 bg-surface-container rounded-full">{d.recurrence && d.recurrence !== 'none' ? d.recurrence : 'one-time'}</span>
                        {d.time && <span>at {d.time}</span>}
                        {d.lead_minutes != null && <><span className="text-on-surface-variant/60">·</span><span>{d.lead_minutes} min before</span></>}
                      </>) : (
                        <span>{[d.when, d.hospital].filter(Boolean).join(' · ') || fmtDate(it.updated_at)}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 border border-outline-variant rounded-full text-[11.5px] text-on-surface-variant"><Sym name="calendar_month" className="text-primary text-[13px]" />Calendar</span>
                      {isReminder && <span className="inline-flex items-center gap-1 px-2.5 py-0.5 border border-outline-variant rounded-full text-[11.5px] text-on-surface-variant"><Sym name="mail" className="text-g-red text-[13px]" />Gmail</span>}
                      {it.profile_name && <span className="px-2.5 py-0.5 bg-g-green-tint text-g-green-text rounded-full text-[11.5px] font-medium">For {it.profile_name}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {isReminder
                      ? <Toggle on={on} onClick={() => setPaused((p) => ({ ...p, [it.id]: on }))} />
                      : <span className="text-[11px] text-on-surface-variant/70">{fmtDate(it.updated_at)}</span>}
                    <button onClick={() => remove(it)} disabled={busy[it.id]} title="Delete"
                      className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-error-container/50 hover:text-error transition-colors disabled:opacity-40">
                      <Sym name={busy[it.id] ? 'hourglass_empty' : 'delete'} className="text-[19px]" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        </div>
      </div>
      <AskBar
        placeholder="Set a reminder or schedule an appointment…"
        suggestions={[
          { icon: 'notifications_active', label: 'Remind mother at 1pm daily', q: 'Remind my mother to take her tablet at 1pm daily' },
          { icon: 'event', label: 'Schedule an eye check-up', q: 'Please schedule an eye check-up' },
        ]}
        onAsk={onAsk}
      />
    </div>
  );
}
