// withcare-frontend/src/components/AgentFlowAnimation.jsx
import React from 'react';
import GeminiLogo from './ui/GeminiLogo';
import GeminiRipple from './ui/GeminiRipple';

/** Gemini-style "thinking" visualization shown while specialists are coordinated. */
export default function AgentFlowAnimation({ orch, subs }) {
  return (
    <div className="relative bg-surface-container-lowest border border-outline-variant rounded-card p-5 elev-2 m3-scale-in overflow-hidden">
      {/* Gemini ripple background — the "thinking" moment */}
      <GeminiRipple className="absolute inset-0 w-full h-full object-cover opacity-[0.18] mix-blend-screen dark:opacity-25" />
      <div className="pointer-events-none absolute -top-20 -right-16 w-52 h-52 rounded-full gemini-gradient opacity-[0.10] blur-3xl gemini-sweep"
           style={{ backgroundSize: '200% 200%' }} />

      {/* Header: spark + radial ripples + sweeping gradient title */}
      <div className="relative flex items-center gap-3.5 mb-5">
        <div className="relative w-11 h-11 flex items-center justify-center shrink-0">
          <span className="absolute inset-0 rounded-full gemini-gradient opacity-25" style={{ animation: 'gemini-ripple 1.9s var(--ease-standard) infinite' }} />
          <span className="absolute inset-0 rounded-full gemini-gradient opacity-25" style={{ animation: 'gemini-ripple 1.9s var(--ease-standard) .95s infinite' }} />
          <GeminiLogo size={30} className="relative m3-breathe" />
        </div>
        <div className="min-w-0">
          <div className="text-[14.5px] font-bold gemini-text gemini-sweep">Gemini is coordinating specialists…</div>
          <div className="text-[12px] text-on-surface-variant mt-0.5">
            {(orch && orch.showStatus && orch.status) ? orch.status : 'Understanding your request and routing to the right experts'}
          </div>
        </div>
      </div>

      {/* Sub-agents: pulsing gradient orbs that light up as consulted */}
      <div className="relative flex flex-col gap-2.5 pl-1">
        {subs.map((ag, i) => (
          <div key={ag.id} className="flex items-center gap-3">
            <span className="relative shrink-0 w-8 h-8 rounded-full gemini-gradient text-white text-[11px] font-bold flex items-center justify-center elev-1"
                  style={{ animation: `gemini-orb 1.7s var(--ease-standard) ${i * 0.16}s infinite` }}>
              {ag.initials}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold text-on-surface leading-tight">{ag.name}</div>
              <div className="text-[11.5px] text-on-surface-variant">{ag.status}</div>
            </div>
            <span className="flex gap-1 shrink-0">
              {[0, 1, 2].map(d => (
                <span key={d} className="w-1.5 h-1.5 rounded-full gemini-gradient"
                      style={{ animation: `gemini-orb 1.1s var(--ease-standard) ${d * 0.18 + i * 0.1}s infinite` }} />
              ))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
