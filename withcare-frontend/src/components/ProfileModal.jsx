import React, { useState } from 'react';

const ACCENT = '#1C7A6A';
const GENDERS = ['', 'Female', 'Male', 'Other', 'Prefer not to say'];

const inputStyle = {
  width: '100%', padding: '10px 12px', borderRadius: 10, border: '1px solid #E2DACB',
  background: '#FBF9F4', fontSize: 14, color: '#26322F', boxSizing: 'border-box',
  fontFamily: 'inherit',
};
const labelStyle = { fontSize: 12.5, fontWeight: 600, color: '#6E7872', marginBottom: 5, display: 'block' };

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
    conditions: initial?.conditions || '',
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
      await onSave({ ...f, name: f.name.trim(), age: f.age === '' ? null : Number(f.age) });
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
      style={{ flex: 1, padding: '9px', borderRadius: 10, cursor: 'pointer', fontSize: 13.5, fontWeight: 600,
        border: f.kind === value ? `1px solid ${ACCENT}` : '1px solid #E2DACB',
        background: f.kind === value ? '#EEF4F1' : '#fff',
        color: f.kind === value ? ACCENT : '#8A8273' }}>
      {icon} {label}
    </button>
  );

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(30,24,16,0.42)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
      fontFamily: "'Hanken Grotesk', system-ui, sans-serif" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 460, maxHeight: '88vh', overflowY: 'auto',
        background: '#fff', borderRadius: 20, border: '1px solid #E6DFD2', padding: '26px 28px',
        boxShadow: '0 20px 60px rgba(40,30,20,0.18)' }}>
        <div style={{ fontFamily: "'Newsreader', serif", fontSize: 21, fontWeight: 600, color: '#26322F', marginBottom: 4 }}>
          {title}
        </div>
        <div style={{ fontSize: 13, color: '#9A9485', marginBottom: 18 }}>
          These details help WithCare tailor guidance for {isPet ? 'this pet' : 'this person'}.
        </div>

        {/* Person / Pet toggle — hidden for the self profile */}
        {!isSelf && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
            <KindTab value="person" label="Person" icon="🧑" />
            <KindTab value="pet" label="Pet" icon="🐾" />
          </div>
        )}

        {/* Photo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 18 }}>
          <div style={{ width: 60, height: 60, borderRadius: '50%', flex: '0 0 auto', overflow: 'hidden',
            background: f.photo ? 'transparent' : '#EDE7DB', color: '#8A8273', display: 'flex',
            alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 700 }}>
            {f.photo ? <img src={f.photo} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : (isPet ? '🐾' : initials)}
          </div>
          <label style={{ ...labelStyle, cursor: 'pointer', color: ACCENT, marginBottom: 0 }}>
            {f.photo ? 'Change photo' : 'Add photo'}
            <input type="file" accept="image/*" onChange={onPhoto} style={{ display: 'none' }} />
          </label>
          {f.photo && (
            <button onClick={() => setF((p) => ({ ...p, photo: '' }))}
              style={{ border: 'none', background: 'none', color: '#B0A797', cursor: 'pointer', fontSize: 12.5 }}>
              Remove
            </button>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div style={{ gridColumn: '1 / 3' }}>
            <label style={labelStyle}>Name *</label>
            <input style={inputStyle} value={f.name} onChange={set('name')} placeholder={isPet ? 'e.g. Bruno' : 'e.g. Amma'} />
          </div>

          {isPet ? (
            <div>
              <label style={labelStyle}>Species / type</label>
              <input style={inputStyle} value={f.species} onChange={set('species')} placeholder="Dog, Cat, Bird…" />
            </div>
          ) : (
            <div>
              <label style={labelStyle}>Relation</label>
              <input style={inputStyle} value={f.relation} onChange={set('relation')} placeholder="Mother, Father…" disabled={isSelf} />
            </div>
          )}

          <div>
            <label style={labelStyle}>Age</label>
            <input style={inputStyle} type="number" min="0" max="120" value={f.age} onChange={set('age')} placeholder={isPet ? '4' : '68'} />
          </div>
          <div style={{ gridColumn: '1 / 3' }}>
            <label style={labelStyle}>{isPet ? 'Sex' : 'Gender'}</label>
            <select style={inputStyle} value={f.gender} onChange={set('gender')}>
              {GENDERS.map((g) => <option key={g} value={g}>{g || 'Select…'}</option>)}
            </select>
          </div>
          <div style={{ gridColumn: '1 / 3' }}>
            <label style={labelStyle}>
              {isPet ? "Owner's Gmail" : 'Gmail'} <span style={{ fontWeight: 400, color: '#B0A797' }}>— for calendar sync & sharing the plan</span>
            </label>
            <input style={inputStyle} type="email" value={f.email} onChange={set('email')}
              placeholder="name@gmail.com" />
            {f.email && (
              <div style={{ fontSize: 11.5, color: '#9A9485', marginTop: 5 }}>
                Appointments will be added to this Google Calendar and the care plan shared with them.
              </div>
            )}
          </div>
          <div style={{ gridColumn: '1 / 3' }}>
            <label style={labelStyle}>Health conditions / problems</label>
            <textarea style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }} value={f.conditions}
              onChange={set('conditions')} placeholder={isPet ? 'e.g. allergies, arthritis, vaccinations due' : 'e.g. Type 2 diabetes, hypertension, cataract'} />
          </div>
          <div style={{ gridColumn: '1 / 3' }}>
            <label style={labelStyle}>Other important details</label>
            <textarea style={{ ...inputStyle, minHeight: 50, resize: 'vertical' }} value={f.notes}
              onChange={set('notes')} placeholder={isPet ? 'Breed, vet clinic, microchip, diet…' : 'Allergies, insurance/scheme, preferred hospital, mobility…'} />
          </div>
        </div>

        {err && <div style={{ color: '#C0492E', fontSize: 12.5, marginTop: 12 }}>{err}</div>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 22 }}>
          <button onClick={onClose} style={{ padding: '10px 18px', borderRadius: 11, border: '1px solid #E2DACB',
            background: '#fff', color: '#6E7872', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
            Cancel
          </button>
          <button onClick={submit} disabled={busy} style={{ padding: '10px 20px', borderRadius: 11, border: 'none',
            background: ACCENT, color: '#fff', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Add profile'}
          </button>
        </div>
      </div>
    </div>
  );
}
