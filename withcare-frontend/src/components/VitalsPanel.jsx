import React, { useEffect, useState, useCallback } from 'react';
import { fetchVitals, logVital, deleteVital } from '../services/vitalsApi';
import { LineChart } from './ui/Charts';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const METRICS = {
  blood_sugar:    { label: 'Blood sugar', unit: 'mg/dL', color: '#ea4335', bp: false, icon: 'water_drop' },
  blood_pressure: { label: 'Blood pressure', unit: 'mmHg', color: '#a142f4', bp: true, icon: 'ecg_heart' },
  weight:         { label: 'Weight', unit: 'kg', color: '#1a73e8', bp: false, icon: 'monitor_weight' },
  heart_rate:     { label: 'Heart rate', unit: 'bpm', color: '#ea4335', bp: false, icon: 'favorite' },
  spo2:           { label: 'SpO₂', unit: '%', color: '#34a853', bp: false, icon: 'spo2' },
  temperature:    { label: 'Temperature', unit: '°F', color: '#f9ab00', bp: false, icon: 'thermometer' },
};
const ORDER = ['blood_sugar', 'blood_pressure', 'weight', 'heart_rate', 'spo2', 'temperature'];

const fmtDay = (at) => {
  const d = new Date(at);
  return isNaN(d) ? '' : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
};

export default function VitalsPanel({ userId, profile }) {
  const [vitals, setVitals] = useState(null);
  const [metric, setMetric] = useState('blood_sugar');
  const [value, setValue] = useState('');
  const [sys, setSys] = useState('');
  const [dia, setDia] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const pid = profile?.id;
  const load = useCallback(() => { fetchVitals(userId, pid).then(setVitals); }, [userId, pid]);
  useEffect(() => { load(); }, [load]);

  const m = METRICS[metric];

  async function submit() {
    setErr('');
    const payload = { profile_id: pid || null, metric };
    if (m.bp) {
      if (!sys || !dia) { setErr('Enter both systolic and diastolic.'); return; }
      payload.systolic = sys; payload.diastolic = dia;
    } else {
      if (!value) { setErr('Enter a value.'); return; }
      payload.value = value;
    }
    setSaving(true);
    try {
      await logVital(userId, payload);
      setValue(''); setSys(''); setDia('');
      load();
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  }

  async function remove(id) {
    await deleteVital(userId, id);
    setVitals((v) => (v || []).filter((x) => x.id !== id));
  }

  const list = vitals || [];
  const byMetric = {};
  for (const r of list) (byMetric[r.metric] ||= []).push(r);

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="font-title-lg text-[17px] text-on-surface flex items-center gap-2">
          <Sym name="vital_signs" className="text-primary text-[20px]" fill /> Vitals
        </h2>
        <span className="text-[12.5px] text-on-surface-variant">Log {profile?.name || 'their'} readings and watch the trend</span>
      </div>

      {/* Log form */}
      <div className="bg-surface-container-lowest border border-outline-variant rounded-card p-4 mb-4 flex flex-wrap items-end gap-3">
        <label className="text-[12px] text-on-surface-variant">Reading
          <select value={metric} onChange={(e) => { setMetric(e.target.value); setErr(''); }}
            className="mt-1 block bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none">
            {ORDER.map((k) => <option key={k} value={k}>{METRICS[k].label}</option>)}
          </select>
        </label>
        {m.bp ? (
          <>
            <label className="text-[12px] text-on-surface-variant">Systolic
              <input type="number" value={sys} onChange={(e) => setSys(e.target.value)} placeholder="120"
                className="mt-1 block w-24 bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
            <label className="text-[12px] text-on-surface-variant">Diastolic
              <input type="number" value={dia} onChange={(e) => setDia(e.target.value)} placeholder="80"
                className="mt-1 block w-24 bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
            </label>
          </>
        ) : (
          <label className="text-[12px] text-on-surface-variant">Value <span className="text-on-surface-variant/60">({m.unit})</span>
            <input type="number" step="any" value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. 140"
              className="mt-1 block w-32 bg-surface-container-low border border-outline-variant focus:border-primary rounded-xl px-3 py-2 text-[14px] text-on-surface outline-none" />
          </label>
        )}
        <button onClick={submit} disabled={saving}
          className="px-5 py-2.5 rounded-full bg-primary text-on-primary text-[13.5px] font-semibold hover:brightness-110 disabled:opacity-60 flex items-center gap-1.5">
          {saving ? <Sym name="progress_activity" className="text-[17px] animate-spin" /> : <Sym name="add" className="text-[17px]" />} Log reading
        </button>
        {err && <div className="text-error text-[12.5px] w-full">{err}</div>}
      </div>

      {/* Trends */}
      {vitals === null ? (
        <div className="h-40 rounded-card skeleton" />
      ) : list.length === 0 ? (
        <div className="rounded-card border border-dashed border-outline-variant bg-surface-container-low p-6 text-center text-on-surface-variant text-[13px]">
          No readings yet. Log a blood-sugar, BP or weight reading above — the trend appears here.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {ORDER.filter((k) => byMetric[k]?.length).map((k) => {
            const meta = METRICS[k];
            const rows = byMetric[k];
            const latest = rows[rows.length - 1];
            const data = rows.map((r) => ({ day: fmtDay(r.at), value: r.value, sys: r.systolic, dia: r.diastolic }));
            const series = meta.bp
              ? [{ key: 'sys', color: meta.color, label: 'Systolic' }, { key: 'dia', color: '#1a73e8', label: 'Diastolic' }]
              : [{ key: 'value', color: meta.color, label: meta.label }];
            const latestLabel = meta.bp ? `${latest.systolic}/${latest.diastolic}` : `${latest.value}`;
            return (
              <section key={k} className="bg-surface-container-lowest rounded-card border border-outline-variant p-5 elev-1">
                <div className="flex items-center gap-2.5 mb-2">
                  <span className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: meta.color + '1F' }}>
                    <Sym name={meta.icon} className="text-[18px]" fill /></span>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-title-lg text-[15px] text-on-surface leading-tight">{meta.label}</h3>
                    <div className="text-[12px] text-on-surface-variant">Latest <b className="text-on-surface">{latestLabel}</b> {meta.unit} · {fmtDay(latest.at)}</div>
                  </div>
                  <button onClick={() => remove(latest.id)} title="Delete latest reading"
                    className="w-8 h-8 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-error-container/50 hover:text-error">
                    <Sym name="delete" className="text-[17px]" />
                  </button>
                </div>
                {rows.length > 1
                  ? <LineChart data={data} series={series} unit={` ${meta.unit}`} />
                  : <div className="text-[12.5px] text-on-surface-variant py-4 text-center">Log another reading to see the trend line.</div>}
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}
