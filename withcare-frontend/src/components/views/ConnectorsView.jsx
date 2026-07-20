import React from 'react';

function Sym({ name, className = '', fill = false, style }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`} style={style}>{name}</span>;
}

// All connectors start DISCONNECTED for every user. Connecting requests real Google consent.
const CONNECTORS = [
  { key: 'calendar', name: 'Google Calendar', icon: 'calendar_month', color: '#1a73e8',
    desc: 'Book appointments & set reminders on your calendar.', scopes: ['calendar.events'] },
  { key: 'gmail', name: 'Gmail', icon: 'mail', color: '#ea4335',
    desc: 'Email reminders to you and your family.', scopes: ['gmail.send'] },
  { key: 'drive', name: 'Google Drive', icon: 'add_to_drive', color: '#34a853',
    desc: 'Save care plans as Google Docs.', scopes: ['drive.file'] },
  { key: 'fit', name: 'Google Fit', icon: 'monitoring', color: '#4285f4',
    desc: 'Sync steps, heart rate, blood pressure, sleep & calories into a Health dashboard.',
    scopes: ['fitness.activity.read', 'fitness.heart_rate.read', 'fitness.blood_pressure.read'] },
];

const SOON = [
  { name: 'WhatsApp', icon: 'chat' },
  { name: 'SMS',      icon: 'sms' },
];

export default function ConnectorsView({ connections = {}, clientId, onConnect, onDisconnect, onOpenHealth }) {
  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-4xl mx-auto">
        <h1 className="font-headline-lg text-[24px] text-on-surface">Connectors</h1>
        <p className="text-[14px] text-on-surface-variant mb-2">Connect your Google services so WithCare can act for you.</p>
        <div className="flex items-start gap-2 text-[12.5px] text-on-surface-variant bg-g-green-tint/60 rounded-lg px-3 py-2 mb-4 w-fit max-w-2xl">
          <Sym name="diversity_1" className="text-[16px] text-g-green-text mt-0.5 shrink-0" fill />
          <span>You connect <b>your own</b> account here. When you set a reminder or book an appointment for a family member, WithCare adds it to <b>your</b> calendar and sends <b>them</b> a calendar invite and email — so they’re covered without having to sign in themselves.</span>
        </div>
        {!clientId && (
          <div className="flex items-center gap-2 text-[12.5px] text-on-surface-variant bg-surface-container rounded-lg px-3 py-2 mb-5 w-fit">
            <Sym name="info" className="text-[16px] text-primary" /> Sign in with Google to grant real permissions (dev mode connects instantly).
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 m3-stagger">
          {CONNECTORS.map((c) => {
            const connected = !!connections[c.key];
            return (
              <div key={c.key} className="bg-surface-container-lowest rounded-card p-5 border border-outline-variant">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" style={{ background: c.color + '18' }}>
                    <Sym name={c.icon} className="text-[24px]" fill style={{ color: c.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-title-lg text-[16px] text-on-surface">{c.name}</h3>
                      {connected
                        ? <span className="flex items-center gap-1 text-[11px] font-semibold text-g-green-text bg-g-green-tint px-2 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-g-green" /> Connected</span>
                        : <span className="text-[11px] font-semibold text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">Not connected</span>}
                    </div>
                    <p className="text-[13px] text-on-surface-variant mt-1">{c.desc}</p>
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {c.scopes.map((s) => <span key={s} className="text-[10px] font-mono text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">{s}</span>)}
                    </div>
                    <div className="flex items-center gap-2 mt-4">
                      {connected ? (
                        <>
                          {c.key === 'fit' && (
                            <button onClick={onOpenHealth}
                              className="px-4 py-2 rounded-full bg-primary text-on-primary text-[13px] font-semibold hover:brightness-110 flex items-center gap-1.5">
                              <Sym name="open_in_new" className="text-[16px]" /> Open Health
                            </button>
                          )}
                          <button onClick={() => onDisconnect(c.key)}
                            className="px-4 py-2 rounded-full border border-outline-variant text-on-surface text-[13px] font-medium hover:bg-surface-container">Disconnect</button>
                        </>
                      ) : (
                        <button onClick={() => onConnect(c.key)}
                          className="px-5 py-2 rounded-full bg-primary text-on-primary text-[13px] font-semibold hover:brightness-110 flex items-center gap-1.5">
                          <Sym name="link" className="text-[16px]" /> Connect
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <h2 className="font-title-lg text-[16px] text-on-surface mt-8 mb-3">Available soon</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SOON.map((s) => (
            <div key={s.name} className="bg-surface-container-low rounded-card p-4 border border-outline-variant/60 flex items-center gap-3 opacity-80">
              <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center"><Sym name={s.icon} className="text-on-surface-variant text-[20px]" /></div>
              <span className="flex-1 text-[14px] font-medium text-on-surface">{s.name}</span>
              <button className="text-[12px] font-semibold text-primary hover:underline">Notify me</button>
            </div>
          ))}
        </div>

        <div className="flex items-start gap-3 mt-8 p-4 rounded-card bg-primary-fixed/40 border border-primary/10">
          <Sym name="shield" className="text-primary text-[22px]" fill />
          <p className="text-[13px] text-on-surface-variant">WithCare only uses these to help you navigate care — never to share your data. You can revoke access anytime from your Google account or by disconnecting here.</p>
        </div>
      </div>
    </div>
  );
}
