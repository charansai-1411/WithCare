import React from 'react';
import { GeminiBadge, GeminiDisclaimer } from '../ui/GeminiBadge';
import GeminiLogo from '../ui/GeminiLogo';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function Card({ title, children }) {
  return (
    <section className="bg-surface-container-lowest rounded-card border border-outline-variant p-5">
      <h2 className="font-title-lg text-[16px] text-on-surface mb-4">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, sub, children }) {
  return (
    <div className="flex items-center gap-4 py-2.5 border-b border-outline-variant/40 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="text-[14px] text-on-surface">{label}</div>
        {sub && <div className="text-[12px] text-on-surface-variant">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

export default function SettingsView({ user, location, onEditLocation, onSignOut }) {
  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-3xl mx-auto space-y-5 m3-stagger">
        <h1 className="font-headline-lg text-[24px] text-on-surface mb-1">Settings</h1>

        <Card title="Account">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full overflow-hidden flex items-center justify-center intelligence-gradient text-white text-xl font-bold">
              {user?.picture ? <img src={user.picture} alt="" className="w-full h-full object-cover" /> : (user?.name || '?').trim().charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-title-lg text-[17px] text-on-surface">{user?.name || 'You'}</div>
              <div className="text-[13px] text-on-surface-variant truncate">{user?.email || ''}</div>
              <span className="inline-flex items-center gap-1 mt-1 text-[11px] font-medium text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
                <Sym name="account_circle" className="text-[14px]" /> Signed in with {user?.auth_provider === 'google' ? 'Google' : 'WithCare'}
              </span>
            </div>
            <button onClick={onSignOut} className="px-4 py-2 rounded-full border border-outline-variant text-on-surface font-medium text-[13px] hover:bg-surface-container">Sign out</button>
          </div>
        </Card>

        <Card title="Preferences">
          <Row label="Location" sub="Used for “near me” facility searches">
            <button onClick={onEditLocation} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container text-on-surface-variant text-[13px] hover:bg-surface-container-high">
              <Sym name="location_on" className="text-[16px]" />{location?.city || 'Set location'}
            </button>
          </Row>
          <Row label="Reminder emails" sub="Send reminders to family via Gmail">
            <span className="w-11 h-6 rounded-full bg-primary flex items-center px-0.5 justify-end"><span className="w-5 h-5 rounded-full bg-white" /></span>
          </Row>
        </Card>

        <Card title="AI">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-surface-container border border-outline-variant flex items-center justify-center"><GeminiLogo size={22} /></div>
            <div className="flex-1">
              <div className="text-[14px] font-semibold text-on-surface">Powered by Gemini</div>
              <div className="text-[12.5px] text-on-surface-variant">WithCare navigates care — it never gives medical diagnoses or treatment advice.</div>
            </div>
          </div>
        </Card>

        <Card title="Privacy & Data">
          <Row label="Memory" sub="What WithCare remembers about each profile">
            <button className="text-[13px] font-semibold text-primary hover:underline">Manage</button>
          </Row>
          <Row label="Export my data"><button className="text-[13px] font-semibold text-primary hover:underline">Export</button></Row>
          <Row label="Delete account" sub="Permanently remove your data">
            <button className="px-3 py-1.5 rounded-full border border-error text-error text-[13px] font-semibold hover:bg-error-container/40">Delete</button>
          </Row>
        </Card>

        <div className="flex flex-col items-center gap-2.5 py-4">
          <div className="text-[12px] text-on-surface-variant">WithCare v1.0 · Made for the Google Gen AI Hackathon</div>
          <GeminiBadge />
          <GeminiDisclaimer className="text-center max-w-md" />
        </div>
      </div>
    </div>
  );
}
