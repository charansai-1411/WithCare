// withcare-frontend/src/components/AgentFlowAnimation.jsx
import React from 'react';

/** Live agent-coordination animation shown while the system is "thinking" */
export default function AgentFlowAnimation({ orch, subs }) {
  return (
    <div style={{ background: '#FFFFFF', border: '1px solid #ECE5D9', borderRadius: '18px', padding: '18px 20px', animation: 'wfade .4s ease', boxShadow: '0 4px 18px rgba(40,30,20,0.05)' }}>
      {/* Header dots */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '9px', marginBottom: '18px' }}>
        <span style={{ display: 'inline-flex', gap: '3px' }}>
          {[0, 0.18, 0.36].map((delay, i) => (
            <span key={i} style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#1C7A6A', animation: `wdot 1.1s infinite ${delay}s` }} />
          ))}
        </span>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#5A655F' }}>Coordinating specialists for this question&hellip;</span>
      </div>

      <div style={{ display: 'flex', gap: '26px', alignItems: 'flex-start' }}>
        {/* Orchestrator */}
        <div style={{ width: '128px', flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <div style={orch.circleStyle}>OR</div>
          <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '10px', color: '#2C3833' }}>Orchestrator</div>
          <div style={{ fontSize: '11px', color: '#9A9485', marginTop: '1px' }}>Coordinator</div>
          {orch.showStatus && (
            <div style={{ fontSize: '11.5px', color: '#1C7A6A', marginTop: '6px', lineHeight: 1.35 }}>{orch.status}</div>
          )}
        </div>

        {/* Sub-agents */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '11px', paddingTop: '4px' }}>
          {subs.map(ag => (
            <div key={ag.id} style={ag.rowStyle}>
              <div style={ag.lineStyle} />
              <div style={ag.dotStyle}>{ag.initials}</div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#2C3833' }}>{ag.name}</div>
                <div style={{ fontSize: '11.5px', color: '#7C8479' }}>{ag.status}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
