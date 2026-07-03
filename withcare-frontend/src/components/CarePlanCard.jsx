import React, { useState } from 'react';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

function Section({ icon, label, controls, children }) {
  return (
    <div className="px-5 py-4 border-b border-outline-variant/60 last:border-b-0">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-primary">
          <Sym name={icon} className="text-[16px]" fill />
          {label}
        </div>
        {controls}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}

function Row({ main, detail, badge, badgeTone, source, url }) {
  const badgeCls = badgeTone === 'tertiary'
    ? 'bg-tertiary-fixed text-on-tertiary-fixed'
    : 'bg-primary-fixed text-on-primary-fixed';
  return (
    <div className="flex justify-between gap-4 items-start">
      <div className="min-w-0">
        {url
          ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-[14.5px] font-semibold text-primary hover:underline">{main}</a>
          : <div className="text-[14.5px] font-semibold text-on-surface">{main}</div>}
        <div className="text-[13px] text-on-surface-variant mt-0.5">{detail}</div>
        {source && (
          <span className="inline-flex items-center gap-1 text-[11px] text-on-surface-variant bg-surface-container border border-outline-variant/60 px-2 py-0.5 rounded-full mt-1.5">
            <Sym name="link" className="text-[12px]" /> {source}
          </span>
        )}
      </div>
      {badge && (
        <span className={`text-[12px] font-semibold whitespace-nowrap px-2.5 py-1 rounded-full ${badgeCls}`}>{badge}</span>
      )}
    </div>
  );
}

function Pill({ label, active, onClick }) {
  return (
    <button onClick={onClick}
      className={`px-2.5 py-1 rounded-full border text-[11px] font-semibold transition-colors
        ${active ? 'border-primary bg-primary-fixed text-primary' : 'border-outline-variant text-on-surface-variant hover:bg-surface-container'}`}>
      {label}
    </button>
  );
}

function FacilitiesSection({ facilities }) {
  const [sortBy, setSortBy] = useState('distance');
  const [filterKm, setFilterKm] = useState(null);

  const sorted = [...facilities].sort((a, b) =>
    sortBy === 'distance' ? (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity) : 0);
  const filtered = filterKm ? sorted.filter(f => f.distance_km == null || f.distance_km <= filterKm) : sorted;

  const controls = (
    <div className="flex gap-1.5 flex-wrap">
      <Pill label="Nearest first" active={sortBy === 'distance'} onClick={() => setSortBy('distance')} />
      <Pill label="< 5 km" active={filterKm === 5} onClick={() => setFilterKm(filterKm === 5 ? null : 5)} />
      <Pill label="< 10 km" active={filterKm === 10} onClick={() => setFilterKm(filterKm === 10 ? null : 10)} />
    </div>
  );

  return (
    <Section icon="location_on" label="Recommended facilities" controls={controls}>
      {filtered.length === 0
        ? <div className="text-[13px] text-on-surface-variant">No facilities within {filterKm} km. Try a larger radius.</div>
        : filtered.map((f, i) => (
            <Row key={i} main={f.name} detail={f.detail}
              badge={f.distance_km != null ? `${f.distance_km.toFixed(1)} km` : f.distance || null}
              badgeTone="primary" source={f.source} url={f.url} />
          ))}
    </Section>
  );
}

export default function CarePlanCard({ msg }) {
  const { hasFacilities, hasCoverage, hasMedicines, hasSchedule,
          facilities, coverage, medicines, schedule } = msg;

  if (!hasFacilities && !hasCoverage && !hasMedicines && !hasSchedule) return null;

  return (
    <div className="bg-surface-container-lowest border border-outline-variant rounded-card overflow-hidden shadow-sm">
      {hasFacilities && <FacilitiesSection facilities={facilities} />}

      {hasCoverage && (
        <Section icon="verified" label="Government schemes">
          {coverage.map((c, i) => (
            <Row key={i} main={c.name} detail={c.detail} badge={c.value} badgeTone="primary" source={c.source} url={c.url} />
          ))}
        </Section>
      )}

      {hasMedicines && (
        <Section icon="medication" label="Affordable medicines">
          {medicines.map((m, i) => (
            <Row key={i} main={m.name} detail={m.detail} badge={m.value} badgeTone="tertiary" source={m.source} />
          ))}
        </Section>
      )}

      {hasSchedule && (
        <div className="px-5 py-4 bg-primary-fixed/40">
          <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-primary">
            <Sym name="event_available" className="text-[16px]" fill />
            Follow-ups scheduled
          </div>
          <div className="flex flex-col gap-2.5 mt-3">
            {schedule.events.map((e, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-semibold text-on-surface">{e.title}</div>
                  <div className="text-[12.5px] text-on-surface-variant mt-0.5">
                    {e.when} · <span className="text-on-surface-variant/70">Google Calendar</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-4 p-3 rounded-2xl bg-surface-container-lowest border border-outline-variant/60">
            <div className="w-8 h-8 rounded-full bg-g-green text-white flex items-center justify-center shrink-0">
              <Sym name="check" className="text-[18px]" />
            </div>
            <div className="flex-1">
              <div className="text-[14px] font-bold text-on-surface">{schedule.confirmText}</div>
              <div className="text-[12px] text-on-surface-variant mt-0.5">Everyone stays in sync — no double-booking, nothing forgotten.</div>
            </div>
            {schedule.bothCalendars && (
              <div className="flex shrink-0">
                <span className="w-7 h-7 rounded-full intelligence-gradient text-white text-[11px] font-bold flex items-center justify-center border-2 border-surface">Y</span>
                <span className="w-7 h-7 rounded-full bg-secondary text-white text-[11px] font-bold flex items-center justify-center border-2 border-surface -ml-2">A</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
