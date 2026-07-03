import React, { useEffect, useState } from 'react';
import { fetchKgItems } from '../../services/kgApi';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function chips(text) {
  return (text || '').replace(/;/g, ',').split(',').map(s => s.trim()).filter(Boolean);
}

function Card({ icon, iconClass, title, children }) {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-card shadow-sm p-5">
      <div className="flex items-center gap-2 font-title-lg text-[14px] text-on-surface mb-3">
        <Sym name={icon} className={`text-[18px] ${iconClass}`} fill /> {title}
      </div>
      {children}
    </div>
  );
}

function ListRows({ items, empty, render }) {
  if (!items.length) return <div className="text-[13px] text-on-surface-variant/70">{empty}</div>;
  return (
    <div className="flex flex-col">
      {items.map((it, i) => (
        <div key={it.id || i} className="text-[13px] py-2 border-b border-outline-variant/50 last:border-0">
          {render(it)}
        </div>
      ))}
    </div>
  );
}

export default function ProfileDetailView({ userId, profile, onBack, onEdit, onUseForChat }) {
  const [tasks, setTasks] = useState(null);
  const [plans, setPlans] = useState(null);

  useEffect(() => {
    if (!userId) return;
    fetchKgItems(userId, 'tasks').then(setTasks);
    fetchKgItems(userId, 'plans').then(setPlans);
  }, [userId]);

  if (!profile) {
    return <div className="flex-1 flex items-center justify-center text-on-surface-variant text-sm">Profile not found.</div>;
  }

  const isPet = profile.kind === 'pet';
  const mine = (arr) => (arr || []).filter(it => (it.profile_name || '').toLowerCase() === (profile.name || '').toLowerCase());
  const appts = mine(tasks).filter(t => t.type === 'appointment');
  const rems  = mine(tasks).filter(t => t.type === 'reminder');
  const myPlans = mine(plans);
  const conds = chips(profile.conditions);
  const initial = (profile.name || '?').trim().charAt(0).toUpperCase();
  const sub = isPet ? (profile.species || 'Pet') : (profile.relation || (profile.is_self ? 'Your own care' : ''));
  const meta = [sub, profile.age ? `${profile.age}` : '', profile.gender,
    profile.weight ? `${profile.weight} kg` : '', profile.height ? `${profile.height} cm` : '']
    .filter(Boolean).join(' · ');

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-4xl mx-auto">
        <button onClick={onBack}
          className="inline-flex items-center gap-1.5 text-primary text-[13px] font-semibold px-3 py-1.5 rounded-full hover:bg-primary-fixed/40 mb-4 transition-colors">
          <Sym name="arrow_back" className="text-[18px]" /> All profiles
        </button>

        {/* Header */}
        <div className="flex items-center gap-5 bg-surface-container-lowest border border-outline-variant rounded-card shadow-sm p-6 mb-4 flex-wrap">
          <div className="w-16 h-16 rounded-full overflow-hidden flex items-center justify-center intelligence-gradient text-white text-2xl font-bold shrink-0">
            {profile.photo ? <img src={profile.photo} alt="" className="w-full h-full object-cover" /> : initial}
          </div>
          <div className="flex-1 min-w-[200px]">
            <div className="flex items-center gap-2">
              <h1 className="font-headline-lg text-[22px] text-on-surface">{isPet && '🐾 '}{profile.name}</h1>
              {!!profile.is_self && <span className="text-[10px] font-bold text-primary bg-primary-fixed px-2 py-0.5 rounded-full">YOU</span>}
            </div>
            <div className="text-[13.5px] text-on-surface-variant mt-0.5">{meta}</div>
            {profile.email && (
              <div className="flex items-center gap-1.5 text-[12.5px] text-on-surface-variant mt-1">
                <Sym name="mail" className="text-g-red text-[15px]" />{profile.email}
              </div>
            )}
          </div>
          <div className="flex gap-2">
            {!profile.is_self && (
              <button onClick={() => onUseForChat(profile.id)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-full intelligence-gradient text-white text-[13px] font-semibold shadow-sm hover:brightness-105 active:scale-95 transition">
                <Sym name="chat" className="text-[17px]" /> Chat
              </button>
            )}
            <button onClick={() => onEdit(profile)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-outline-variant text-primary text-[13px] font-semibold hover:bg-surface-container">
              <Sym name="edit" className="text-[17px]" /> Edit
            </button>
          </div>
        </div>

        {/* Cards grid */}
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
          <Card icon="badge" iconClass="text-g-yellow" title="About">
            {conds.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2.5">
                {conds.map((c, i) => <span key={i} className="px-3 py-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-[12px]">{c}</span>)}
              </div>
            )}
            <div className="text-[13px] text-on-surface-variant leading-relaxed">{profile.notes || 'No additional details yet.'}</div>
          </Card>

          <Card icon="event" iconClass="text-primary" title="Appointments">
            <ListRows items={appts} empty="No upcoming appointments."
              render={(a) => (<>
                <div className="font-medium text-on-surface">{a.name}</div>
                <div className="text-on-surface-variant mt-0.5">{[a.data?.when, a.data?.hospital].filter(Boolean).join(' · ') || '—'}</div>
              </>)} />
          </Card>

          <Card icon="alarm" iconClass="text-g-red" title="Reminders">
            <ListRows items={rems} empty="No active reminders."
              render={(r) => (<>
                <div className="font-medium text-on-surface">{r.name}</div>
                <div className="text-on-surface-variant mt-0.5">
                  {[r.data?.recurrence && r.data.recurrence !== 'none' ? r.data.recurrence : 'one-time', r.data?.time && `at ${r.data.time}`].filter(Boolean).join(' · ')}
                </div>
              </>)} />
          </Card>

          <Card icon="directions_run" iconClass="text-g-green" title="Workout & Diet plans">
            <ListRows items={myPlans} empty="No plans yet."
              render={(p) => (<>
                <div className="font-medium text-on-surface">{p.name}</div>
                <div className="text-on-surface-variant mt-0.5">{p.type === 'diet_plan' ? 'Diet plan' : 'Workout plan'}</div>
              </>)} />
          </Card>

          <Card icon="shield" iconClass="text-primary" title="Coverage">
            <div className="text-[13px] text-on-surface-variant/70">Schemes &amp; insurance appear here once WithCare finds coverage for {profile.name} in chat.</div>
          </Card>
        </div>
      </div>
    </div>
  );
}
