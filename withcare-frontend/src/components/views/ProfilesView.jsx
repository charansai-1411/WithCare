import React from 'react';
import Button from '../ui/Button';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function chips(text) {
  return (text || '').replace(/;/g, ',').split(',').map(s => s.trim()).filter(Boolean);
}

export default function ProfilesView({ profiles, activeProfileId, onSelect, onAdd, onEdit, onDelete }) {
  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1">
            <h1 className="font-headline-lg text-[24px] text-on-surface">Care Profiles</h1>
            <p className="text-[14px] text-on-surface-variant">Everyone you manage care for — people and pets.</p>
          </div>
          <Button variant="gradient" icon="add" onClick={onAdd}>Add profile</Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 m3-stagger">
          {profiles.map(p => {
            const isPet = p.kind === 'pet';
            const active = p.id === activeProfileId;
            const conds = chips(p.conditions);
            return (
              <div key={p.id}
                className={`ripple lift relative bg-surface-container-lowest rounded-card p-5 border cursor-pointer group
                  ${active ? 'border-primary elev-2' : 'border-outline-variant elev-1'}`}
                onClick={() => onSelect(p.id)}>
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 rounded-full overflow-hidden flex items-center justify-center intelligence-gradient text-white text-xl font-bold shrink-0">
                    {p.photo ? <img src={p.photo} alt="" className="w-full h-full object-cover" /> : (p.name || '?').trim().charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-title-lg text-[17px] text-on-surface truncate">{isPet && '🐾 '}{p.name}</h3>
                      {!!p.is_self && <span className="text-[10px] font-bold text-primary bg-primary-fixed px-2 py-0.5 rounded-full">YOU</span>}
                    </div>
                    <p className="text-[13px] text-on-surface-variant">
                      {isPet ? (p.species || 'Pet') : (p.relation || 'Self')}{p.age ? ` · ${p.age}` : ''}{p.gender ? ` · ${p.gender}` : ''}
                    </p>
                    {p.email && <p className="text-[12px] text-on-surface-variant truncate mt-0.5 flex items-center gap-1"><Sym name="mail" className="text-[14px]" />{p.email}</p>}
                  </div>
                </div>

                {conds.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-4">
                    {conds.map((c, i) => (
                      <span key={i} className="px-2.5 py-1 rounded-full bg-tertiary-fixed text-on-tertiary-fixed text-[11px] font-medium">{c}</span>
                    ))}
                  </div>
                )}
                {p.notes && <p className="text-[12.5px] text-on-surface-variant mt-3 line-clamp-2">{p.notes}</p>}

                <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={(e) => { e.stopPropagation(); onEdit(p); }} className="w-8 h-8 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface-variant flex items-center justify-center"><Sym name="edit" className="text-[16px]" /></button>
                  {!p.is_self && <button onClick={(e) => { e.stopPropagation(); onDelete(p.id); }} className="w-8 h-8 rounded-full bg-surface-container hover:bg-error-container text-on-surface-variant flex items-center justify-center"><Sym name="delete" className="text-[16px]" /></button>}
                </div>
              </div>
            );
          })}

          <button onClick={onAdd}
            className="rounded-card p-5 border border-dashed border-outline-variant text-on-surface-variant hover:border-primary hover:text-primary hover:bg-primary-fixed/30 transition flex flex-col items-center justify-center gap-2 min-h-[140px]">
            <span className="w-12 h-12 rounded-full bg-primary-fixed flex items-center justify-center"><Sym name="add" className="text-primary text-[26px]" /></span>
            <span className="font-semibold text-[14px]">Add a care profile</span>
          </button>
        </div>
      </div>
    </div>
  );
}
