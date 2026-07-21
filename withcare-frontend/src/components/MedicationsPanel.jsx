import React, { useEffect, useState, useCallback } from 'react';
import { fetchMedications, addMedication, refillMedication, deleteMedication } from '../services/medicationApi';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Status → badge styling + label.
function statusBadge(m) {
  if (m.status === 'out')
    return { cls: 'text-error bg-error-container/50', icon: 'error', label: 'Out — refill now' };
  if (m.status === 'refill_soon')
    return { cls: 'text-on-surface bg-g-yellow/25', icon: 'warning',
             label: `Refill soon · ${m.days_left}d left` };
  if (m.days_left != null)
    return { cls: 'text-g-green-text bg-g-green-tint', icon: 'check_circle',
             label: `${m.days_left} days left` };
  return { cls: 'text-on-surface-variant bg-surface-container', icon: 'schedule', label: 'Tracking' };
}

const FREQ = [
  { label: 'Once a day', times: '09:00' },
  { label: 'Twice a day', times: '09:00, 21:00' },
  { label: 'Three times a day', times: '08:00, 14:00, 20:00' },
];

const BLANK = { name: '', dose: '', profileId: '', times: '09:00', per_dose: 1, quantity: 30, threshold: 5 };

export default function MedicationsPanel({ userId, profiles = [], activeProfileId }) {
  const [meds, setMeds] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState({});
  const [err, setErr] = useState('');

  const load = useCallback(() => { fetchMedications(userId).then(setMeds).catch(() => setMeds([])); }, [userId]);
  useEffect(() => { load(); }, [load]);

  const openForm = () => {
    setForm({ ...BLANK, profileId: activeProfileId || (profiles[0] && profiles[0].id) || '' });
    setErr(''); setShowForm(true);
  };

  async function save() {
    if (!form.name.trim()) { setErr('Enter the medicine name.'); return; }
    const prof = profiles.find((p) => p.id === form.profileId) || {};
    setSaving(true); setErr('');
    try {
      await addMedication(userId, {
        profile_id: form.profileId || null,
        person: prof.name || '',
        email: prof.email || '',
        name: form.name.trim(),
        dose: form.dose.trim(),
        times: form.times.split(',').map((t) => t.trim()).filter(Boolean),
        per_dose: Number(form.per_dose) || 1,
        quantity: Number(form.quantity) || 0,
        refill_threshold_days: Number(form.threshold) || 5,
      });
      setShowForm(false);
      load();
    } catch (e) {
      setErr(e.message || 'Could not add the medicine.');
    } finally {
      setSaving(false);
    }
  }

  async function refill(m) {
    const q = window.prompt(`How many ${m.name} do you now have in stock?`, m.quantity || 30);
    if (q == null) return;
    setBusy((b) => ({ ...b, [m.id]: true }));
    try { await refillMedication(userId, m.id, Number(q) || 0); load(); }
    finally { setBusy((b) => ({ ...b, [m.id]: false })); }
  }

  async function remove(m) {
    if (!window.confirm(`Remove "${m.name}" and its dose reminders?`)) return;
    setBusy((b) => ({ ...b, [m.id]: true }));
    try { await deleteMedication(userId, m.id); setMeds((x) => (x || []).filter((y) => y.id !== m.id)); }
    finally { setBusy((b) => ({ ...b, [m.id]: false })); }
  }

  const list = meds || [];

  return (
    <section className="mb-8">
      <div className="flex items-center gap-3 mb-3">
        <h2 className="font-title-lg text-[17px] text-on-surface flex items-center gap-2">
          <Sym name="medication" className="text-primary text-[20px]" fill /> Medications
        </h2>
        <span className="text-[12.5px] text-on-surface-variant">Tracked with dose reminders & refill alerts</span>
        <button onClick={openForm}
          className="ml-auto flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-primary text-on-primary text-[13px] font-semibold hover:brightness-110 shrink-0">
          <Sym name="add" className="text-[17px]" /> Add medicine
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="bg-surface-container-lowest border border-outline-variant rounded-card p-4 mb-3 m3-scale-in">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-[12px] text-on-surface-variant">Medicine
              <input autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Metformin"
                className="mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
            <label className="text-[12px] text-on-surface-variant">Dose
              <input value={form.dose} onChange={(e) => setForm({ ...form, dose: e.target.value })}
                placeholder="e.g. 500mg"
                className="mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
            <label className="text-[12px] text-on-surface-variant">For
              <select value={form.profileId} onChange={(e) => setForm({ ...form, profileId: e.target.value })}
                className="mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none">
                {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="text-[12px] text-on-surface-variant">Schedule
              <select value={form.times}
                onChange={(e) => setForm({ ...form, times: e.target.value, per_dose: form.per_dose })}
                className="mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none">
                {FREQ.map((f) => <option key={f.label} value={f.times}>{f.label} ({f.times})</option>)}
              </select>
            </label>
            <label className="text-[12px] text-on-surface-variant">Pills per dose
              <input type="number" min="1" value={form.per_dose} onChange={(e) => setForm({ ...form, per_dose: e.target.value })}
                className="mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
            <label className="text-[12px] text-on-surface-variant">Quantity in stock
              <input type="number" min="0" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                className="mt-1 w-full bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
            <label className="text-[12px] text-on-surface-variant sm:col-span-2">Alert me when this many days of supply are left
              <input type="number" min="1" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })}
                className="mt-1 w-32 bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
          </div>
          {err && <div className="text-error text-[12.5px] mt-2">{err}</div>}
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowForm(false)} className="px-4 py-2 rounded-full text-[13px] font-medium text-on-surface-variant hover:bg-surface-container">Cancel</button>
            <button onClick={save} disabled={saving}
              className="px-5 py-2 rounded-full text-[13px] font-semibold bg-primary text-on-primary hover:brightness-110 disabled:opacity-60 flex items-center gap-1.5">
              {saving ? <Sym name="progress_activity" className="text-[16px] animate-spin" /> : <Sym name="check" className="text-[16px]" />}
              Save & set reminders
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {meds === null ? (
        <div className="h-16 rounded-card skeleton" />
      ) : list.length === 0 && !showForm ? (
        <div className="rounded-card border border-dashed border-outline-variant bg-surface-container-low p-6 text-center text-on-surface-variant text-[13px]">
          No medicines tracked yet. Add one to get automatic dose reminders and a refill alert before it runs out.
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {list.map((m) => {
            const b = statusBadge(m);
            return (
              <div key={m.id} className="flex items-center gap-3.5 bg-surface-container-lowest border border-outline-variant rounded-card p-3.5">
                <div className="w-11 h-11 rounded-xl bg-primary-fixed shrink-0 flex items-center justify-center">
                  <Sym name="medication" className="text-primary text-[22px]" fill />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14.5px] font-semibold text-on-surface truncate">
                    {m.name}{m.dose ? <span className="text-on-surface-variant font-normal"> · {m.dose}</span> : null}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap mt-1 text-[12px] text-on-surface-variant">
                    <span className="inline-flex items-center gap-1"><Sym name="schedule" className="text-[14px]" />{(m.times || []).join(', ')}</span>
                    {m.recipient && <span className="px-2 py-0.5 bg-g-green-tint text-g-green-text rounded-full text-[11px] font-medium">For {m.recipient}</span>}
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11.5px] font-semibold shrink-0 ${b.cls}`}>
                  <Sym name={b.icon} className="text-[14px]" fill /> {b.label}
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => refill(m)} disabled={busy[m.id]} title="I restocked this"
                    className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container disabled:opacity-40">
                    <Sym name="refresh" className="text-[19px]" />
                  </button>
                  <button onClick={() => remove(m)} disabled={busy[m.id]} title="Remove"
                    className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-error-container/50 hover:text-error disabled:opacity-40">
                    <Sym name={busy[m.id] ? 'hourglass_empty' : 'delete'} className="text-[19px]" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
