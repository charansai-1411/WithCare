import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchKgItems, deleteKgItem } from '../../services/kgApi';
import AskBar from '../AskBar';
import PlanCards from '../PlanCards';
import { SkeletonList } from '../ui/Skeleton';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
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

export default function PlansView({ userId, onAsk }) {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState({});
  const [tab, setTab] = useState('all');
  const [person, setPerson] = useState('__all');

  const [busy, setBusy] = useState({});

  const load = useCallback(() => { fetchKgItems(userId, 'plans').then(setItems); }, [userId]);
  useEffect(() => { load(); }, [load]);

  async function remove(it) {
    if (!window.confirm(`Delete this plan?\n\n“${it.name}”`)) return;
    setBusy((b) => ({ ...b, [it.id]: true }));
    const ok = await deleteKgItem(userId, it.id);
    if (ok) setItems((prev) => (prev || []).filter((x) => x.id !== it.id));
    else setBusy((b) => ({ ...b, [it.id]: false }));
  }

  const list = items || [];
  const persons = useMemo(() => [...new Set(list.map(i => i.profile_name).filter(Boolean))], [list]);

  const filtered = list.filter((it) => {
    if (tab === 'workout' && it.type !== 'workout_plan') return false;
    if (tab === 'diet' && it.type !== 'diet_plan') return false;
    if (person !== '__all' && it.profile_name !== person) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background">
      <div className="flex-1 overflow-y-auto px-8 py-7">
        <div className="max-w-4xl mx-auto">
        <div className="flex items-start gap-4 mb-6">
          <div className="flex-1">
            <h1 className="font-headline-lg text-[24px] text-on-surface">Workout &amp; Diet</h1>
            <p className="text-[14px] text-on-surface-variant mt-0.5">Plans tailored to each person’s health conditions.</p>
          </div>
          <button onClick={load}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-outline-variant text-on-surface-variant text-[13px] font-medium hover:bg-surface-container shrink-0">
            <Sym name="refresh" className="text-[18px]" /> Refresh
          </button>
        </div>

        {list.length > 0 && (
          <>
            <div className="flex items-center gap-4 flex-wrap mb-4">
              <SegTabs value={tab} onChange={setTab}
                tabs={[{ k: 'all', label: 'All' }, { k: 'workout', label: 'Workout' }, { k: 'diet', label: 'Diet' }]} />
              <PersonChips persons={persons} value={person} onChange={setPerson} />
            </div>
            <div className="flex items-center gap-2 bg-g-green-tint text-g-green-text rounded-xl px-4 py-2.5 mb-4 text-[12.5px]">
              <Sym name="trending_up" className="text-[17px]" /> Plans adapt as health improves.
            </div>
          </>
        )}

        {items === null ? (
          <SkeletonList count={2} />
        ) : filtered.length === 0 ? (
          <div className="rounded-card border border-dashed border-outline-variant bg-surface-container-low p-10 text-center text-on-surface-variant">
            <Sym name="exercise" className="text-[32px] text-on-surface-variant/60 mb-2" />
            <p className="text-[14px]">No plans yet. In chat, try <span className="text-on-surface font-medium">“create a diet plan for my mother”</span> or <span className="text-on-surface font-medium">“make a workout plan for my father”.</span></p>
          </div>
        ) : (
          <div className="flex flex-col gap-3.5">
            {filtered.map((it) => {
              const isDiet = it.type === 'diet_plan';
              const expanded = open[it.id];
              return (
                <div key={it.id} className="bg-surface-container-lowest border border-outline-variant rounded-card shadow-sm overflow-hidden">
                  <div className="w-full flex items-center gap-1 pr-3">
                    <button onClick={() => setOpen((o) => ({ ...o, [it.id]: !o[it.id] }))}
                      className="flex-1 min-w-0 flex items-center gap-3.5 px-5 py-4 text-left hover:bg-surface-container/40 transition-colors">
                      <div className={`w-11 h-11 rounded-xl shrink-0 flex items-center justify-center ${isDiet ? 'bg-tertiary-fixed' : 'bg-g-green-tint'}`}>
                        <Sym name={isDiet ? 'nutrition' : 'directions_run'} className={`text-[22px] ${isDiet ? 'text-tertiary' : 'text-g-green'}`} fill />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[15.5px] font-semibold text-on-surface truncate">{it.name}</div>
                        <div className="flex gap-1.5 mt-1.5">
                          {it.profile_name && <span className="px-2.5 py-0.5 bg-primary-fixed text-on-primary-fixed rounded-full text-[11.5px] font-medium">{it.profile_name}</span>}
                          <span className="px-2.5 py-0.5 bg-g-green-tint text-g-green-text rounded-full text-[11.5px] font-medium">{isDiet ? 'Diet plan' : 'Workout plan'}</span>
                        </div>
                      </div>
                      <Sym name={expanded ? 'expand_less' : 'expand_more'} className="text-on-surface-variant text-[22px]" />
                    </button>
                    <button onClick={() => remove(it)} disabled={busy[it.id]} title="Delete plan"
                      className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-on-surface-variant hover:bg-error-container/50 hover:text-error transition-colors disabled:opacity-40">
                      <Sym name={busy[it.id] ? 'hourglass_empty' : 'delete'} className="text-[19px]" />
                    </button>
                  </div>
                  {expanded && (
                    <div className="px-5 pb-5 pt-3 border-t border-outline-variant/60">
                      <PlanCards text={it.data?.plan} variant="tabs" />
                      <div className="text-[11.5px] text-on-surface-variant/70 mt-3">General wellness guidance — not medical treatment.</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        </div>
      </div>
      <AskBar
        userId={userId}
        placeholder="Ask for a workout or diet plan…"
        suggestions={[
          { icon: 'nutrition', label: 'Diet plan for my mother', q: 'Create a diet plan for my mother' },
          { icon: 'directions_run', label: 'Workout plan for my father', q: 'Make a workout plan for my father' },
        ]}
        onAsk={onAsk}
      />
    </div>
  );
}
