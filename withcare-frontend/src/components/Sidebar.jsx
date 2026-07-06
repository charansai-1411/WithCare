import React, { useState } from 'react';
import Button from './ui/Button';

const NAV = [
  { key: 'chat',    label: 'Chat',              icon: 'chat_bubble' },
  { key: 'tasks',   label: 'Tasks & Reminders', icon: 'notifications' },
  { key: 'plans',   label: 'Workout & Diet',    icon: 'fitness_center' },
  { key: 'health',  label: 'Health',            icon: 'monitoring', needs: 'health' },
  { key: 'reader',  label: 'Reader',            icon: 'auto_stories' },
  { key: 'profiles',label: 'Profiles',          icon: 'groups' },
  { key: 'connectors', label: 'Connectors',     icon: 'hub' },
  { key: 'settings',label: 'Settings',          icon: 'settings' },
];

function Sym({ name, className = '', fill = false, style }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`} style={style}>{name}</span>;
}

function timeAgo(iso) {
  if (!iso) return '';
  const d = new Date(iso.replace(' ', 'T') + (iso.includes('T') ? '' : 'Z'));
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}

function Avatar({ photo, initials, size = 34, ring = false }) {
  return (
    <div
      className={`rounded-full shrink-0 overflow-hidden flex items-center justify-center font-bold text-white ${ring ? 'ring-2 ring-primary ring-offset-2 ring-offset-surface' : ''}`}
      style={{ width: size, height: size, fontSize: size * 0.4, background: photo ? 'transparent' : undefined }}
    >
      {photo ? <img src={photo} alt="" className="w-full h-full object-cover" />
             : <span className="intelligence-gradient w-full h-full flex items-center justify-center">{initials}</span>}
    </div>
  );
}

export default function Sidebar({
  profiles, onAddProfile, conversations, activeConvId, onConvClick, onConvDelete,
  onNewChat, activeView, onSelectView, healthConnected, user, onSignOut,
}) {
  const [hoverConv, setHoverConv] = useState(null);
  const [hoverProf, setHoverProf] = useState(null);
  const nav = NAV.filter(item => item.needs !== 'health' || healthConnected);

  return (
    <div className="h-full w-full bg-surface flex flex-col p-4 font-body-md text-on-surface">
      {/* Logo */}
      <div className="mb-5 px-2 flex items-center gap-2.5 m3-enter">
        <div className="w-9 h-9 rounded-full bg-white border border-outline-variant/60 elev-1 overflow-hidden shrink-0 flex items-center justify-center">
          <img src="/withcare-logo.png" alt="WithCare" className="w-full h-full object-cover" style={{ transformOrigin: '51% 33%', transform: 'scale(1.9)' }} draggable={false} />
        </div>
        <span className="text-[20px] font-bold tracking-tight leading-none select-none">
          <span className="text-on-surface">with</span><span className="text-primary">care</span>
        </span>
      </div>

      {/* New conversation */}
      <div data-tour="new-chat" className="mb-4">
        <Button variant="tonal" full icon="add" onClick={onNewChat}>New conversation</Button>
      </div>

      {/* Primary nav */}
      <nav className="space-y-0.5 m3-stagger">
        {nav.map(item => {
          const active = activeView === item.key;
          return (
            <button key={item.key} onClick={() => onSelectView(item.key)} data-tour={`nav-${item.key}`}
              className={`press relative flex items-center gap-3 w-full px-4 py-2.5 rounded-full transition-all duration-300 text-[14px]
                ${active ? 'bg-secondary-fixed text-on-secondary-fixed font-semibold' : 'text-on-surface-variant hover:bg-surface-container-high'}`}
              style={active ? { transitionTimingFunction: 'cubic-bezier(0.05,0.7,0.1,1)' } : undefined}>
              {active && <span className="absolute left-1.5 top-1/2 -translate-y-1/2 w-1 h-5 rounded-full bg-secondary origin-center"
                               style={{ animation: 'm3-indicator var(--dur-medium) var(--ease-emph-decel)' }} />}
              <Sym key={active ? 'on' : 'off'} name={item.icon}
                   className={`text-[20px] ${active ? 'm3-pop' : ''}`} fill={active} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="flex-1 overflow-y-auto -mx-1 px-1 mt-3">
        {/* Care profiles quick-switch */}
        <p className="text-[11px] font-bold text-outline uppercase tracking-wider px-3 pt-3 pb-1.5">Care profiles</p>
        <div className="space-y-2 m3-stagger" data-tour="profiles-section">
          {profiles.map(p => (
            <div key={p.id} className="relative group"
                 onMouseEnter={() => setHoverProf(p.id)} onMouseLeave={() => setHoverProf(null)}>
              <button onClick={p.onClick}
                className={`press flex items-center gap-3 w-full px-3 py-2.5 rounded-2xl text-left bg-surface-container-lowest text-on-surface transition-all duration-200
                  ${p.active ? 'elev-2 ring-1 ring-primary' : 'elev-1 hover:elev-2'}`}>
                <Avatar photo={p.photo} initials={p.initials} size={30} />
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold truncate flex items-center gap-1">
                    {p.isPet && <span>🐾</span>}{p.name}
                  </div>
                  <div className="text-[11px] text-on-surface-variant truncate">{p.relation}</div>
                </div>
                {p.active && !(hoverProf === p.id) && <Sym name="check_circle" className="text-primary text-[16px]" fill />}
              </button>
              {hoverProf === p.id && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                  {p.canEdit && <button onClick={(e) => { e.stopPropagation(); p.onEdit(); }} className="w-6 h-6 rounded-full bg-surface-container-highest hover:bg-outline-variant text-on-surface-variant flex items-center justify-center"><Sym name="edit" className="text-[14px]" /></button>}
                  {p.canDelete && <button onClick={(e) => { e.stopPropagation(); p.onDelete(); }} className="w-6 h-6 rounded-full bg-surface-container-highest hover:bg-error-container text-on-surface-variant flex items-center justify-center"><Sym name="close" className="text-[14px]" /></button>}
                </div>
              )}
            </div>
          ))}
          <button onClick={onAddProfile}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-full border border-dashed border-outline-variant text-primary hover:bg-primary-fixed/40 transition-colors">
            <span className="w-[30px] h-[30px] rounded-full bg-primary-fixed flex items-center justify-center"><Sym name="add" className="text-[18px] text-primary" /></span>
            <span className="text-[13px] font-semibold">Add care profile</span>
          </button>
        </div>

        {/* Recent conversations */}
        <p className="text-[11px] font-bold text-outline uppercase tracking-wider px-3 pt-5 pb-1.5">Recent</p>
        {conversations.length === 0 ? (
          <p className="text-[12.5px] text-on-surface-variant px-3 py-1">No conversations yet</p>
        ) : (
          <div className="space-y-0.5">
            {conversations.map(c => {
              const active = activeConvId === c.id;
              return (
                <div key={c.id} className="relative" onMouseEnter={() => setHoverConv(c.id)} onMouseLeave={() => setHoverConv(null)}>
                  <button onClick={() => onConvClick(c.id)}
                    className={`flex items-start gap-3 w-full px-4 py-2 rounded-full text-left transition-colors
                      ${active ? 'bg-secondary-container text-on-secondary-container' : 'text-on-surface-variant hover:bg-surface-container-high'}`}>
                    <Sym name="chat_bubble" className="text-[18px] mt-0.5 shrink-0" />
                    <span className="flex-1 min-w-0">
                      <span className="block truncate text-[13px] font-medium">{c.title}</span>
                      <span className="block text-[11px] opacity-70">{c.profile_name && c.profile_name !== 'You' ? `${c.profile_name} · ` : ''}{timeAgo(c.updated_at)}</span>
                    </span>
                  </button>
                  {hoverConv === c.id && (
                    <button onClick={(e) => { e.stopPropagation(); onConvDelete(c.id); }} title="Delete"
                      className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface-container-highest hover:bg-error-container text-on-surface-variant flex items-center justify-center">
                      <Sym name="close" className="text-[14px]" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* User card */}
      <div className="mt-2 pt-3 border-t border-outline-variant/50">
        <div className="flex items-center gap-3 px-2 py-2 rounded-xl bg-surface-container-low">
          <div className="w-9 h-9 rounded-full overflow-hidden flex items-center justify-center intelligence-gradient text-white font-bold shrink-0">
            {user?.picture ? <img src={user.picture} alt="" className="w-full h-full object-cover" /> : (user?.name || '?').trim().charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-[13px] truncate text-on-surface">{user?.name || 'Signed in'}</p>
            {user?.email && <p className="text-[11px] text-on-surface-variant truncate">{user.email}</p>}
          </div>
          <button onClick={onSignOut} title="Sign out" className="p-1.5 rounded-full hover:bg-surface-container-highest text-on-surface-variant">
            <Sym name="logout" className="text-[18px]" />
          </button>
        </div>
      </div>
    </div>
  );
}
