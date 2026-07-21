import React, { useEffect, useState, useCallback } from 'react';
import { fetchEmergencySummary, sendSos } from '../../services/emergencyApi';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function Field({ icon, label, value, muted }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-outline-variant/40 last:border-0">
      <Sym name={icon} className="text-on-surface-variant text-[19px] mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-[11.5px] text-on-surface-variant uppercase tracking-wide">{label}</div>
        <div className={`text-[14.5px] ${muted ? 'text-on-surface-variant italic' : 'text-on-surface font-medium'}`}>{value}</div>
      </div>
    </div>
  );
}

export default function EmergencyView({ userId, profile, location, onEditProfile, onAsk }) {
  const [data, setData] = useState(null);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState('');

  const pid = profile?.id;
  const load = useCallback(() => { fetchEmergencySummary(userId, pid).then(setData); }, [userId, pid]);
  useEffect(() => { setResult(null); setErr(''); load(); }, [load]);

  async function triggerSos() {
    const who = data?.person || profile?.name || 'this person';
    const n = data?.contacts?.length || 0;
    if (!window.confirm(`Send an EMERGENCY alert about ${who} to ${n > 0 ? `${n} family contact${n !== 1 ? 's' : ''}` : 'your family'} now?`)) return;
    setSending(true); setErr(''); setResult(null);
    try {
      const coords = (location?.lat && location?.lng) ? { lat: location.lat, lng: location.lng } : null;
      const r = await sendSos(userId, pid, location?.city || '', coords);
      setResult(r);
    } catch (e) { setErr(e.message); }
    finally { setSending(false); }
  }

  const who = profile?.name || 'this person';
  const dash = (v) => (v == null || v === '') ? '—' : v;
  const meds = data?.medications || [];
  const contacts = data?.contacts || [];

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-start gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-error-container flex items-center justify-center shrink-0">
            <Sym name="emergency" className="text-error text-[22px]" fill />
          </div>
          <div>
            <h1 className="font-headline-lg text-[24px] text-on-surface">Emergency</h1>
            <p className="text-[14px] text-on-surface-variant">Critical info for {who}, and a one-tap SOS to their family.</p>
          </div>
        </div>

        {/* SOS button */}
        <button onClick={triggerSos} disabled={sending || !pid}
          className="mt-5 w-full rounded-3xl bg-error text-on-error py-6 flex flex-col items-center justify-center gap-1 shadow-lg shadow-error/30 hover:brightness-110 active:scale-[0.99] transition disabled:opacity-60">
          <Sym name={sending ? 'progress_activity' : 'sos'} className={`text-[40px] ${sending ? 'animate-spin' : ''}`} fill />
          <span className="text-[18px] font-bold tracking-wide">{sending ? 'Sending alert…' : 'SEND SOS ALERT'}</span>
          <span className="text-[12px] opacity-90">Emails {who}’s medical info to family members</span>
        </button>

        {/* Result / error */}
        {result && (
          <div className="mt-3 rounded-card border border-g-green/40 bg-g-green-tint p-4 text-g-green-text text-[13.5px] flex items-start gap-2">
            <Sym name="mark_email_read" className="text-[19px] mt-0.5" fill />
            <div>
              {result.emailed
                ? <>Alert sent to <b>{result.notified.length}</b> {result.notified.length === 1 ? 'person' : 'people'}{result.contact_names?.length ? ` (${result.contact_names.join(', ')} + you)` : ''}.</>
                : <>Couldn’t email anyone — connect <b>Gmail</b> on the Connectors page and make sure family profiles have email addresses.</>}
            </div>
          </div>
        )}
        {err && <div className="mt-3 text-error text-[13px]">{err}</div>}

        {/* Quick actions */}
        <div className="mt-3 flex flex-wrap gap-2.5">
          <a href="tel:108"
            className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-outline-variant text-on-surface text-[13px] font-medium hover:bg-surface-container">
            <Sym name="call" className="text-g-red text-[17px]" fill /> Call 108 (ambulance)
          </a>
          {onAsk && (
            <button onClick={() => onAsk('find the nearest hospital to me right now')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-outline-variant text-on-surface text-[13px] font-medium hover:bg-surface-container">
              <Sym name="local_hospital" className="text-primary text-[17px]" fill /> Nearest hospital
            </button>
          )}
        </div>

        {/* Emergency info sheet */}
        <div className="mt-6 bg-surface-container-lowest border border-outline-variant rounded-card p-5">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-title-lg text-[16px] text-on-surface flex items-center gap-2">
              <Sym name="medical_information" className="text-primary text-[20px]" fill /> {who}’s emergency sheet
            </h2>
            {onEditProfile && profile && (
              <button onClick={() => onEditProfile(profile)} className="text-[12.5px] font-semibold text-primary hover:underline">Edit</button>
            )}
          </div>
          <Field icon="cake" label="Age" value={dash(data?.age)} muted={!data?.age} />
          <Field icon="bloodtype" label="Blood group" value={dash(data?.blood_group)} muted={!data?.blood_group} />
          <Field icon="warning" label="Allergies" value={dash(data?.allergies)} muted={!data?.allergies} />
          <Field icon="clinical_notes" label="Conditions" value={dash(data?.conditions)} muted={!data?.conditions} />
          <Field icon="medication" label="Current medicines"
            value={meds.length ? meds.map((m) => m.replace(/^.*?:\s*/, '')).join(', ') : '—'} muted={!meds.length} />
          <Field icon="diversity_1" label="Family contacts"
            value={contacts.length ? contacts.map((c) => `${c.name}${c.relation ? ` (${c.relation})` : ''}`).join(', ') : 'No family emails on file'} muted={!contacts.length} />
        </div>

        {(!data?.blood_group || !data?.allergies) && (
          <p className="mt-3 text-[12.5px] text-on-surface-variant flex items-center gap-1.5">
            <Sym name="info" className="text-[15px] text-primary" /> Add {who}’s blood group and allergies in their profile so responders have them.
          </p>
        )}
      </div>
    </div>
  );
}
