import React, { useState } from 'react';
import Button from './ui/Button';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const GENDERS = ['', 'Female', 'Male', 'Other', 'Prefer not to say'];

const inputCls = 'w-full px-3 py-2.5 rounded-xl border border-outline-variant bg-surface-container-low text-[14px] text-on-surface outline-none focus:border-primary focus:ring-4 focus:ring-primary/10 transition-all box-border';
const labelCls = 'block text-[12.5px] font-semibold text-on-surface-variant mb-1.5';

export default function ProfileModal({ initial, onClose, onSave }) {
  const editing = !!initial?.id;
  const isSelf = !!initial?.is_self;
  const [f, setF] = useState({
    kind: initial?.kind || 'person',
    name: initial?.name || '',
    relation: initial?.relation || '',
    species: initial?.species || '',
    email: initial?.email || '',
    age: initial?.age ?? '',
    gender: initial?.gender || '',
    weight: initial?.weight ?? '',
    height: initial?.height ?? '',
    conditions: initial?.conditions || '',
    blood_group: initial?.blood_group || '',
    allergies: initial?.allergies || '',
    notes: initial?.notes || '',
    photo: initial?.photo || '',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const isPet = f.kind === 'pet';
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  function onPhoto(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1.5 * 1024 * 1024) { setErr('Image too large (max ~1.5 MB).'); return; }
    const reader = new FileReader();
    reader.onload = () => setF((p) => ({ ...p, photo: reader.result }));
    reader.readAsDataURL(file);
  }

  async function submit() {
    if (!f.name.trim()) { setErr('Name is required.'); return; }
    setBusy(true); setErr('');
    try {
      await onSave({
        ...f, name: f.name.trim(),
        age: f.age === '' ? null : Number(f.age),
        weight: f.weight === '' ? null : Number(f.weight),
        height: f.height === '' ? null : Number(f.height),
      });
    } catch {
      setErr('Could not save. Try again.');
      setBusy(false);
    }
  }

  const initials = (f.name || '?').trim().charAt(0).toUpperCase();
  const title = editing ? (isSelf ? 'Edit your profile' : `Edit ${isPet ? 'pet' : 'care'} profile`)
                        : `Add a ${isPet ? 'pet' : 'care'} profile`;

  const KindTab = ({ value, label, icon }) => (
    <button onClick={() => setF((p) => ({ ...p, kind: value }))}
      className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-[13.5px] font-semibold border transition-colors
        ${f.kind === value ? 'border-primary bg-primary-fixed text-primary' : 'border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container'}`}>
      <Sym name={icon} className="text-[18px]" /> {label}
    </button>
  );

  return (
    <div onClick={onClose} className="fixed inset-0 bg-scrim/50 flex items-center justify-center z-50 p-4 font-body-md m3-enter">
      <div onClick={(e) => e.stopPropagation()}
        className="w-[460px] max-h-[88vh] overflow-y-auto bg-surface-container-lowest rounded-[28px] border border-outline-variant elev-5 p-7 m3-scale-in">
        <div className="flex items-start gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl intelligence-gradient flex items-center justify-center shrink-0">
            <Sym name={isPet ? 'pets' : 'person'} className="text-white text-[22px]" fill />
          </div>
          <div>
            <h2 className="font-headline-lg text-[21px] text-on-surface leading-tight">{title}</h2>
            <p className="text-[13px] text-on-surface-variant">These details help WithCare tailor guidance for {isPet ? 'this pet' : 'this person'}.</p>
          </div>
        </div>

        {!isSelf && (
          <div className="flex gap-2 my-4">
            <KindTab value="person" label="Person" icon="person" />
            <KindTab value="pet" label="Pet" icon="pets" />
          </div>
        )}

        {/* Photo */}
        <div className="flex items-center gap-4 my-5">
          <div className="w-16 h-16 rounded-full shrink-0 overflow-hidden flex items-center justify-center intelligence-gradient text-white text-2xl font-bold">
            {f.photo ? <img src={f.photo} alt="" className="w-full h-full object-cover" /> : (isPet ? <Sym name="pets" className="text-[26px]" fill /> : initials)}
          </div>
          <label className="text-[13px] font-semibold text-primary cursor-pointer hover:underline">
            {f.photo ? 'Change photo' : 'Add photo'}
            <input type="file" accept="image/*" onChange={onPhoto} className="hidden" />
          </label>
          {f.photo && (
            <button onClick={() => setF((p) => ({ ...p, photo: '' }))} className="text-[12.5px] text-on-surface-variant hover:text-error">Remove</button>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3.5">
          <div className="col-span-2">
            <label className={labelCls}>Name *</label>
            <input className={inputCls} value={f.name} onChange={set('name')} placeholder={isPet ? 'e.g. Bruno' : 'e.g. Amma'} />
          </div>

          {isPet ? (
            <div>
              <label className={labelCls}>Species / type</label>
              <input className={inputCls} value={f.species} onChange={set('species')} placeholder="Dog, Cat, Bird…" />
            </div>
          ) : (
            <div>
              <label className={labelCls}>Relation</label>
              <input className={inputCls} value={f.relation} onChange={set('relation')} placeholder="Mother, Father…" disabled={isSelf} />
            </div>
          )}

          <div>
            <label className={labelCls}>Age</label>
            <input className={inputCls} type="number" min="0" max="120" value={f.age} onChange={set('age')} placeholder={isPet ? '4' : '68'} />
          </div>
          <div className="col-span-2">
            <label className={labelCls}>{isPet ? 'Sex' : 'Gender'}</label>
            <select className={inputCls} value={f.gender} onChange={set('gender')}>
              {GENDERS.map((g) => <option key={g} value={g}>{g || 'Select…'}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>Weight <span className="font-normal text-on-surface-variant/70">(kg)</span></label>
            <input className={inputCls} type="number" min="0" max="500" step="0.1" value={f.weight} onChange={set('weight')} placeholder={isPet ? '12' : '70'} />
          </div>
          <div>
            <label className={labelCls}>Height <span className="font-normal text-on-surface-variant/70">(cm)</span></label>
            <input className={inputCls} type="number" min="0" max="300" step="0.1" value={f.height} onChange={set('height')} placeholder={isPet ? '40' : '165'} />
          </div>
          <div className="col-span-2">
            <label className={labelCls}>
              {isPet ? "Owner's Gmail" : 'Gmail'} <span className="font-normal text-on-surface-variant/70">— for calendar sync &amp; sharing the plan</span>
            </label>
            <input className={inputCls} type="email" value={f.email} onChange={set('email')} placeholder="name@gmail.com" />
            {f.email && (
              <div className="text-[11.5px] text-on-surface-variant mt-1.5">Appointments will be added to this Google Calendar and the care plan shared with them.</div>
            )}
          </div>
          <div className="col-span-2">
            <label className={labelCls}>Health conditions / problems</label>
            <textarea className={`${inputCls} min-h-[60px] resize-y`} value={f.conditions} onChange={set('conditions')}
              placeholder={isPet ? 'e.g. allergies, arthritis, vaccinations due' : 'e.g. Type 2 diabetes, hypertension, cataract'} />
          </div>
          <div>
            <label className={labelCls}>Blood group <span className="font-normal text-on-surface-variant/70">— for emergencies</span></label>
            <select className={inputCls} value={f.blood_group} onChange={set('blood_group')}>
              {['', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map((g) => <option key={g} value={g}>{g || 'Select…'}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>Allergies <span className="font-normal text-on-surface-variant/70">— for emergencies</span></label>
            <input className={inputCls} value={f.allergies} onChange={set('allergies')} placeholder="e.g. Penicillin, peanuts" />
          </div>
          <div className="col-span-2">
            <label className={labelCls}>Other important details</label>
            <textarea className={`${inputCls} min-h-[50px] resize-y`} value={f.notes} onChange={set('notes')}
              placeholder={isPet ? 'Breed, vet clinic, microchip, diet…' : 'Allergies, insurance/scheme, preferred hospital, mobility…'} />
          </div>
        </div>

        {err && <div className="text-error text-[12.5px] mt-3">{err}</div>}

        <div className="flex justify-end gap-2.5 mt-6">
          <Button variant="text" onClick={onClose}>Cancel</Button>
          <Button variant="gradient" onClick={submit} disabled={busy}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Add profile'}
          </Button>
        </div>
      </div>
    </div>
  );
}
