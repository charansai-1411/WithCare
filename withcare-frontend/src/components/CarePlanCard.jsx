import React, { useState } from 'react';

const chipStyle = {
  display: 'inline-flex', alignItems: 'center', gap: '4px',
  fontSize: '11px', color: '#7C8479', background: '#F2EEE5',
  border: '1px solid #E8E2D6', padding: '3px 9px', borderRadius: '999px', marginTop: '7px',
};

function Section({ label, children, controls }) {
  return (
    <div style={{ padding: '17px 20px', borderBottom: '1px solid #F0EBE0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '13px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', letterSpacing: '0.08em', fontWeight: 700, textTransform: 'uppercase', color: '#1C7A6A' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#1C7A6A' }} />
          {label}
        </div>
        {controls}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '13px' }}>
        {children}
      </div>
    </div>
  );
}

function Row({ main, detail, badge, badgeColor, source, url }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px', alignItems: 'flex-start' }}>
      <div style={{ minWidth: 0 }}>
        {url
          ? <a href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '14.5px', fontWeight: 600, color: '#1C7A6A', textDecoration: 'none' }}>{main}</a>
          : <div style={{ fontSize: '14.5px', fontWeight: 600, color: '#2C3833' }}>{main}</div>
        }
        <div style={{ fontSize: '13px', color: '#7C8479', marginTop: '2px' }}>{detail}</div>
        <span style={chipStyle}>source: {source}</span>
      </div>
      {badge && (
        <span style={{ fontSize: '12.5px', fontWeight: 600, color: badgeColor || '#2C3833', whiteSpace: 'nowrap', ...( badgeColor === '#1C7A6A' ? { background: '#EEF4F1', padding: '4px 9px', borderRadius: '8px' } : {}) }}>
          {badge}
        </span>
      )}
    </div>
  );
}

// Small pill button for sort/filter controls
function Pill({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: '3px 10px', borderRadius: '999px', border: '1px solid',
      fontSize: '11px', fontWeight: 600, cursor: 'pointer',
      borderColor: active ? '#1C7A6A' : '#E2D9CC',
      background: active ? '#EEF4F1' : 'transparent',
      color: active ? '#1C7A6A' : '#8A9085',
    }}>{label}</button>
  );
}

function FacilitiesSection({ facilities }) {
  const [sortBy,    setSortBy]    = useState('distance'); // 'distance' | 'rating'
  const [filterKm,  setFilterKm]  = useState(null);       // null | 5 | 10

  const sorted = [...facilities].sort((a, b) => {
    if (sortBy === 'distance') {
      const da = a.distance_km ?? Infinity;
      const db = b.distance_km ?? Infinity;
      return da - db;
    }
    return 0; // rating sort: keep original order (backend already ranked by relevance)
  });

  const filtered = filterKm
    ? sorted.filter(f => f.distance_km == null || f.distance_km <= filterKm)
    : sorted;

  const controls = (
    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
      <Pill label="Nearest first" active={sortBy === 'distance'} onClick={() => setSortBy('distance')} />
      <Pill label="< 5 km"  active={filterKm === 5}  onClick={() => setFilterKm(filterKm === 5  ? null : 5)} />
      <Pill label="< 10 km" active={filterKm === 10} onClick={() => setFilterKm(filterKm === 10 ? null : 10)} />
    </div>
  );

  return (
    <Section label="Recommended facilities" controls={controls}>
      {filtered.length === 0
        ? <div style={{ fontSize: '13px', color: '#A39C8C' }}>No facilities within {filterKm} km. Try a larger radius.</div>
        : filtered.map((f, i) => (
            <Row
              key={i}
              main={f.name}
              detail={f.detail}
              badge={f.distance_km != null ? `${f.distance_km.toFixed(1)} km` : f.distance || null}
              badgeColor="#1C7A6A"
              source={f.source}
              url={f.url}
            />
          ))
      }
    </Section>
  );
}

export default function CarePlanCard({ msg }) {
  const { intro, hasFacilities, hasCoverage, hasMedicines, hasSchedule,
          facilities, coverage, medicines, schedule, confirmStyle } = msg;

  return (
    <div style={{ display: 'flex', gap: '13px', alignItems: 'flex-start' }}>
      {/* Avatar */}
      <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: '#1C7A6A', color: '#fff', fontFamily: "'Newsreader', serif", fontSize: '17px', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto', marginTop: '2px' }}>w</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '15.5px', lineHeight: 1.55, color: '#2E3A35' }}>{intro}</div>

        <div style={{ marginTop: '14px', background: '#fff', border: '1px solid #ECE5D9', borderRadius: '18px', overflow: 'hidden', boxShadow: '0 1px 2px rgba(40,30,20,0.03)' }}>

          {hasFacilities && <FacilitiesSection facilities={facilities} />}

          {hasCoverage && (
            <Section label="Government schemes">
              {coverage.map((c, i) => (
                <Row key={i} main={c.name} detail={c.detail} badge={c.value} source={c.source} url={c.url} />
              ))}
            </Section>
          )}

          {hasMedicines && (
            <Section label="Affordable medicines">
              {medicines.map((m, i) => (
                <Row key={i} main={m.name} detail={m.detail} badge={m.value} badgeColor="#C0623F" source={m.source} />
              ))}
            </Section>
          )}

          {hasSchedule && (
            <div style={{ padding: '17px 20px', background: '#F1F6F3' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', letterSpacing: '0.08em', fontWeight: 700, textTransform: 'uppercase', color: '#1C7A6A' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#1C7A6A' }} />
                Follow-ups scheduled
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '13px' }}>
                {schedule.events.map((e, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '11px' }}>
                    <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: '#1C7A6A', marginTop: '5px', flex: '0 0 auto' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: '#2C3833' }}>{e.title}</div>
                      <div style={{ fontSize: '12.5px', color: '#7C8479', marginTop: '1px' }}>
                        {e.when} &middot; <span style={{ color: '#9A9485' }}>source: Google Calendar</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div style={confirmStyle}>
                <div style={{ width: '30px', height: '30px', borderRadius: '50%', background: '#2E8B6F', color: '#fff', fontSize: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>✓</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '14.5px', fontWeight: 700, color: '#1B6E5B' }}>{schedule.confirmText}</div>
                  <div style={{ fontSize: '12px', color: '#5E8377', marginTop: '2px' }}>Everyone stays in sync — no double-booking, nothing forgotten.</div>
                </div>
                {schedule.bothCalendars && (
                  <div style={{ display: 'flex', flex: '0 0 auto' }}>
                    <span style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#CC6A47', color: '#fff', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '2px solid #EAF3EE' }}>Y</span>
                    <span style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#1C7A6A', color: '#fff', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '2px solid #EAF3EE', marginLeft: '-9px' }}>A</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
