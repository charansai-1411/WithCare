import React from 'react';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const CONNECTED = [
  { name: 'Google Calendar', icon: 'calendar_month', color: '#1a73e8', desc: 'Appointments & reminders sync here.', scopes: ['calendar.events'], synced: 'just now' },
  { name: 'Google Drive',    icon: 'add_to_drive',   color: '#34a853', desc: 'Care plans are saved as Docs.',      scopes: ['drive.file'],       synced: '2h ago' },
  { name: 'Gmail',           icon: 'mail',           color: '#ea4335', desc: 'Reminders can be emailed to family.', scopes: ['gmail.send'],      synced: '1d ago' },
];

const SOON = [
  { name: 'WhatsApp', icon: 'chat' },
  { name: 'SMS',      icon: 'sms' },
  { name: 'Google Fit', icon: 'monitoring' },
];

export default function ConnectorsView() {
  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-4xl mx-auto">
        <h1 className="font-headline-lg text-[24px] text-on-surface">Connectors</h1>
        <p className="text-[14px] text-on-surface-variant mb-6">Connect your Google services so WithCare can act for you.</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CONNECTED.map(c => (
            <div key={c.name} className="bg-surface-container-lowest rounded-card p-5 border border-outline-variant">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" style={{ background: c.color + '18' }}>
                  <Sym name={c.icon} className="text-[24px]" fill style={{ color: c.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-title-lg text-[16px] text-on-surface">{c.name}</h3>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-g-green-text bg-g-green-tint px-2 py-0.5 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-g-green" /> Connected
                    </span>
                  </div>
                  <p className="text-[13px] text-on-surface-variant mt-1">{c.desc}</p>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {c.scopes.map(s => <span key={s} className="text-[10px] font-mono text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">{s}</span>)}
                    <span className="text-[11px] text-on-surface-variant ml-auto">Synced {c.synced}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <h2 className="font-title-lg text-[16px] text-on-surface mt-8 mb-3">Available soon</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SOON.map(s => (
            <div key={s.name} className="bg-surface-container-low rounded-card p-4 border border-outline-variant/60 flex items-center gap-3 opacity-80">
              <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center"><Sym name={s.icon} className="text-on-surface-variant text-[20px]" /></div>
              <span className="flex-1 text-[14px] font-medium text-on-surface">{s.name}</span>
              <button className="text-[12px] font-semibold text-primary hover:underline">Notify me</button>
            </div>
          ))}
        </div>

        <div className="flex items-start gap-3 mt-8 p-4 rounded-card bg-primary-fixed/40 border border-primary/10">
          <Sym name="shield" className="text-primary text-[22px]" fill />
          <p className="text-[13px] text-on-surface-variant">WithCare only uses these to help you navigate care — never to share your data. You can revoke access anytime from your Google account.</p>
        </div>
      </div>
    </div>
  );
}
