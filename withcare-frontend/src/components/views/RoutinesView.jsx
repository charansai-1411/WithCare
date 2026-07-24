import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchRoutines, draftRoutine, addRoutine, deleteRoutine } from '../../services/routineApi';
import AskBar from '../AskBar';
import PlanCards from '../PlanCards';
import { SkeletonList } from '../ui/Skeleton';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Category → label, icon, and tint (kept in sync with routine_service.CATEGORIES on the backend).
const CATS = {
  workout:   { label: 'Workout',          icon: 'directions_run',     tint: 'bg-g-green-tint',       fg: 'text-g-green' },
  diet:      { label: 'Diet',             icon: 'nutrition',          tint: 'bg-tertiary-fixed',     fg: 'text-tertiary' },
  skincare:  { label: 'Skincare',         icon: 'spa',                tint: 'bg-g-blue/15',          fg: 'text-g-blue' },
  checkup:   { label: 'Health check-ups', icon: 'stethoscope',        tint: 'bg-error-container/50', fg: 'text-error' },
  sleep:     { label: 'Sleep',            icon: 'bedtime',            tint: 'bg-secondary-container', fg: 'text-secondary' },
  hydration: { label: 'Hydration',        icon: 'water_drop',         tint: 'bg-g-blue/15',          fg: 'text-g-blue' },
  eyecare:   { label: 'Eye care',         icon: 'visibility',         tint: 'bg-primary-fixed',      fg: 'text-primary' },
  physio:    { label: 'Physiotherapy',    icon: 'accessibility_new',  tint: 'bg-g-yellow/20',        fg: 'text-on-surface' },
  other:     { label: 'Routine',          icon: 'event_repeat',       tint: 'bg-surface-container-high', fg: 'text-on-surface-variant' },
};
const catOf = (c) => CATS[c] || CATS.other;

// Categories offered in the manual add form (workout/diet keep their dedicated chat plan tools,
// but a user can still add a simple one here).
const FORM_CATS = ['skincare', 'checkup', 'sleep', 'hydration', 'eyecare', 'physio', 'diet', 'workout', 'other'];
const FREQS = ['Daily', 'Twice daily (AM & PM)', 'Every morning', 'Every night', 'Weekly', 'Monthly', 'As needed'];

const BLANK = {
  category: 'skincare', name: '', profileId: '', frequency: 'Twice daily (AM & PM)',
  content: '', focus: '', remind: false, time: '08:00', recurrence: 'daily',
};

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

const inputCls = 'mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none';

export default function RoutinesView({ userId, onAsk, profiles = [], activeProfileId }) {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState({});
  const [cat, setCat] = useState('all');
  const [person, setPerson] = useState('__all');
  const [busy, setBusy] = useState({});

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(() => {
    fetchRoutines(userId).then(setItems).catch(() => setItems([]));
  }, [userId]);
  useEffect(() => { load(); }, [load]);

  const openForm = () => {
    setForm({ ...BLANK, profileId: activeProfileId || (profiles[0] && profiles[0].id) || '' });
    setErr(''); setShowForm(true);
  };

  async function draft() {
    setDrafting(true); setErr('');
    try {
      const d = await draftRoutine(userId, {
        profile_id: form.profileId || null, category: form.category, note: form.focus.trim(),
      });
      setForm((f) => ({
        ...f,
        name: f.name.trim() || d.name || `${catOf(f.category).label} routine`,
        content: d.content || f.content,
        frequency: d.frequency || f.frequency,
      }));
      if (!d.content) setErr('Gemini couldn’t draft it just now — write the steps manually or try again.');
    } catch (e) {
      setErr(e.message || 'Could not draft the routine.');
    } finally {
      setDrafting(false);
    }
  }

  async function save() {
    if (!form.name.trim()) { setErr('Give the routine a name.'); return; }
    if (!form.content.trim()) { setErr('Add the routine steps (or draft them with Gemini).'); return; }
    if (form.remind && !form.time) { setErr('Pick a reminder time.'); return; }
    const prof = profiles.find((p) => p.id === form.profileId) || {};
    setSaving(true); setErr('');
    try {
      await addRoutine(userId, {
        profile_id: form.profileId || null,
        person: prof.name || '',
        email: prof.email || '',
        name: form.name.trim(),
        category: form.category,
        content: form.content.trim(),
        frequency: form.frequency,
        times: form.remind ? [form.time] : [],
        recurrence: form.recurrence,
        remind: form.remind,
      });
      setShowForm(false);
      load();
    } catch (e) {
      setErr(e.message || 'Could not save the routine.');
    } finally {
      setSaving(false);
    }
  }

  async function remove(it) {
    if (!window.confirm(`Delete this routine?\n\n“${it.name}”${it.reminds ? '\n\nIts reminder will be removed too.' : ''}`)) return;
    setBusy((b) => ({ ...b, [it.id]: true }));
    try {
      await deleteRoutine(userId, it.id);
      setItems((prev) => (prev || []).filter((x) => x.id !== it.id));
    } catch {
      setBusy((b) => ({ ...b, [it.id]: false }));
    }
  }

  const list = items || [];
  const persons = useMemo(() => [...new Set(list.map((i) => i.profile_name).filter(Boolean))], [list]);
  const cats = useMemo(() => [...new Set(list.map((i) => i.category))], [list]);

  const filtered = list.filter((it) => {
    if (cat !== 'all' && it.category !== cat) return false;
    if (person !== '__all' && it.profile_name !== person) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background">
      <div className="flex-1 overflow-y-auto px-8 py-7">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-start gap-4 mb-6">
            <div className="flex-1">
              <h1 className="font-headline-lg text-[24px] text-on-surface">Routines</h1>
              <p className="text-[14px] text-on-surface-variant mt-0.5">
                Daily care routines for each person — add your own or let Gemini draft them.
              </p>
            </div>
            <button onClick={openForm}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-primary text-on-primary text-[13px] font-semibold hover:brightness-110 shrink-0">
              <Sym name="add" className="text-[18px]" /> Add routine
            </button>
          </div>

          {/* Add / draft form */}
          {showForm && (
            <div className="bg-surface-container-lowest border border-outline-variant rounded-card p-4 mb-4 m3-scale-in">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="text-[12px] text-on-surface-variant">Type
                  <select value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })} className={inputCls}>
                    {FORM_CATS.map((c) => <option key={c} value={c}>{catOf(c).label}</option>)}
                  </select>
                </label>
                <label className="text-[12px] text-on-surface-variant">For
                  <select value={form.profileId}
                    onChange={(e) => setForm({ ...form, profileId: e.target.value })} className={inputCls}>
                    {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </label>
              </div>

              {/* Draft with Gemini */}
              <div className="mt-3 flex flex-col sm:flex-row gap-2 sm:items-end">
                <label className="flex-1 text-[12px] text-on-surface-variant">Focus for Gemini (optional)
                  <input value={form.focus} onChange={(e) => setForm({ ...form, focus: e.target.value })}
                    placeholder="e.g. oily skin, morning only, diabetic foot care" className={inputCls} />
                </label>
                <button onClick={draft} disabled={drafting}
                  className="shrink-0 flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl intelligence-gradient text-white text-[13px] font-semibold hover:brightness-110 disabled:opacity-60 h-[42px]">
                  <Sym name={drafting ? 'progress_activity' : 'auto_awesome'} className={`text-[17px] ${drafting ? 'animate-spin' : ''}`} fill />
                  {drafting ? 'Drafting…' : 'Draft with Gemini'}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                <label className="text-[12px] text-on-surface-variant">Name
                  <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g. Morning skincare" className={inputCls} />
                </label>
                <label className="text-[12px] text-on-surface-variant">How often
                  <select value={form.frequency}
                    onChange={(e) => setForm({ ...form, frequency: e.target.value })} className={inputCls}>
                    {FREQS.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                </label>
              </div>

              <label className="block text-[12px] text-on-surface-variant mt-3">Steps
                <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                  rows={5} placeholder={'One step per line, e.g.\n**Cleanse:** gentle face wash\n**Moisturise:** SPF 30 in the morning'}
                  className={`${inputCls} resize-y leading-relaxed`} />
              </label>

              {/* Optional reminder */}
              <div className="mt-3 rounded-xl bg-surface-container-low border border-outline-variant/70 p-3">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input type="checkbox" checked={form.remind}
                    onChange={(e) => setForm({ ...form, remind: e.target.checked })}
                    className="w-4 h-4 accent-primary" />
                  <span className="text-[13px] font-medium text-on-surface flex items-center gap-1.5">
                    <Sym name="notifications" className="text-[17px] text-primary" fill /> Remind on Google Calendar
                  </span>
                </label>
                {form.remind && (
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <label className="text-[12px] text-on-surface-variant">Time
                      <input type="time" value={form.time}
                        onChange={(e) => setForm({ ...form, time: e.target.value })} className={inputCls} />
                    </label>
                    <label className="text-[12px] text-on-surface-variant">Repeat
                      <select value={form.recurrence}
                        onChange={(e) => setForm({ ...form, recurrence: e.target.value })} className={inputCls}>
                        <option value="daily">Every day</option>
                        <option value="weekly">Every week</option>
                        <option value="monthly">Every month</option>
                      </select>
                    </label>
                  </div>
                )}
              </div>

              {err && <div className="text-error text-[12.5px] mt-2">{err}</div>}
              <div className="flex justify-end gap-2 mt-3">
                <button onClick={() => setShowForm(false)}
                  className="px-4 py-2 rounded-full text-[13px] font-medium text-on-surface-variant hover:bg-surface-container">Cancel</button>
                <button onClick={save} disabled={saving}
                  className="px-5 py-2 rounded-full text-[13px] font-semibold bg-primary text-on-primary hover:brightness-110 disabled:opacity-60 flex items-center gap-1.5">
                  {saving ? <Sym name="progress_activity" className="text-[16px] animate-spin" /> : <Sym name="check" className="text-[16px]" />}
                  Save routine
                </button>
              </div>
            </div>
          )}

          {/* Filters */}
          {list.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap mb-4">
              <div className="flex gap-2 flex-wrap">
                {['all', ...cats].map((c) => {
                  const on = cat === c;
                  const info = c === 'all' ? { label: 'All', icon: 'apps' } : catOf(c);
                  return (
                    <button key={c} onClick={() => setCat(c)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12.5px] font-medium border transition-colors
                        ${on ? 'border-primary bg-primary text-on-primary' : 'border-outline-variant text-on-surface-variant hover:bg-surface-container'}`}>
                      <Sym name={info.icon} className="text-[15px]" /> {info.label}
                    </button>
                  );
                })}
              </div>
              <PersonChips persons={persons} value={person} onChange={setPerson} />
            </div>
          )}

          {/* List */}
          {items === null ? (
            <SkeletonList count={2} />
          ) : filtered.length === 0 ? (
            <div className="rounded-card border border-dashed border-outline-variant bg-surface-container-low p-10 text-center text-on-surface-variant">
              <Sym name="event_repeat" className="text-[32px] text-on-surface-variant/60 mb-2" />
              <p className="text-[14px]">
                {list.length === 0
                  ? <>No routines yet. Click <span className="text-on-surface font-medium">Add routine</span> — or in chat, try <span className="text-on-surface font-medium">“make a skincare routine for my mother”.</span></>
                  : 'No routines match this filter.'}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3.5">
              {filtered.map((it) => {
                const info = catOf(it.category);
                const expanded = open[it.id];
                return (
                  <div key={it.id} className="bg-surface-container-lowest border border-outline-variant rounded-card shadow-sm overflow-hidden">
                    <div className="w-full flex items-center gap-1 pr-3">
                      <button onClick={() => setOpen((o) => ({ ...o, [it.id]: !o[it.id] }))}
                        className="flex-1 min-w-0 flex items-center gap-3.5 px-5 py-4 text-left hover:bg-surface-container/40 transition-colors">
                        <div className={`w-11 h-11 rounded-xl shrink-0 flex items-center justify-center ${info.tint}`}>
                          <Sym name={info.icon} className={`text-[22px] ${info.fg}`} fill />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[15.5px] font-semibold text-on-surface truncate">{it.name}</div>
                          <div className="flex gap-1.5 mt-1.5 flex-wrap items-center">
                            {it.profile_name && <span className="px-2.5 py-0.5 bg-primary-fixed text-on-primary-fixed rounded-full text-[11.5px] font-medium">{it.profile_name}</span>}
                            <span className={`px-2.5 py-0.5 rounded-full text-[11.5px] font-medium ${info.tint} ${info.fg}`}>{info.label}</span>
                            {it.frequency && <span className="inline-flex items-center gap-1 text-[11.5px] text-on-surface-variant"><Sym name="schedule" className="text-[13px]" />{it.frequency}</span>}
                            {it.reminds && <span className="inline-flex items-center gap-1 text-[11.5px] text-primary"><Sym name="notifications_active" className="text-[13px]" fill />Reminder on</span>}
                          </div>
                        </div>
                        <Sym name={expanded ? 'expand_less' : 'expand_more'} className="text-on-surface-variant text-[22px]" />
                      </button>
                      <button onClick={() => remove(it)} disabled={busy[it.id]} title="Delete routine"
                        className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-on-surface-variant hover:bg-error-container/50 hover:text-error transition-colors disabled:opacity-40">
                        <Sym name={busy[it.id] ? 'hourglass_empty' : 'delete'} className="text-[19px]" />
                      </button>
                    </div>
                    {expanded && (
                      <div className="px-5 pb-5 pt-3 border-t border-outline-variant/60">
                        <PlanCards text={it.content} variant="tabs" />
                        <div className="text-[11.5px] text-on-surface-variant/70 mt-3">General wellbeing guidance — not medical treatment.</div>
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
        placeholder="Ask WithCare to build a routine…"
        suggestions={[
          { icon: 'spa', label: 'Skincare routine for my mother', q: 'Make a skincare routine for my mother' },
          { icon: 'stethoscope', label: 'Check-up routine for my father', q: 'Create a health check-up routine for my father' },
        ]}
        onAsk={onAsk}
      />
    </div>
  );
}
