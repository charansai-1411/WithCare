import React, { useRef, useEffect } from 'react';
import AgentFlowAnimation from './AgentFlowAnimation';
import CarePlanCard from './CarePlanCard';
import PlanCards, { hasPlanStructure } from './PlanCards';
import GeminiLogo from './ui/GeminiLogo';
import M3Loader from './ui/M3Loader';
import RichText from './ui/RichText';
import { SUGGESTIONS } from '../constants/agents';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const CHIP_ICON = ['medical_services', 'visibility', 'description', 'fitness_center'];

function AiAvatar({ size = 40 }) {
  return (
    <div className="rounded-full bg-surface-container-lowest border border-outline-variant shrink-0 flex items-center justify-center elev-1"
         style={{ width: size, height: size }}>
      <GeminiLogo size={size * 0.58} />
    </div>
  );
}

export default function ChatThread({ messages, input, setInput, send, onKey, msgVM }) {
  const threadRef = useRef(null);
  useEffect(() => { if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight; }, [messages]);
  const noMessages = messages.length === 0;

  return (
    <main className="flex-1 flex flex-col min-w-0 bg-background overflow-hidden relative">
      <div ref={threadRef} className="flex-1 overflow-y-auto px-6 pt-6 pb-40">

        {/* Empty state */}
        {noMessages && (
          <div className="max-w-3xl mx-auto flex flex-col items-center text-center space-y-5 pt-16">
            <div className="w-20 h-20 rounded-[24px] bg-surface-container-lowest border border-outline-variant flex items-center justify-center elev-3 m3-pop m3-breathe">
              <GeminiLogo size={48} />
            </div>
            <h3 className="font-headline-lg text-[28px] text-on-surface m3-enter" style={{ animationDelay: '.08s' }}>How can I help with your care today?</h3>
            <p className="text-[15px] text-on-surface-variant max-w-md m3-enter" style={{ animationDelay: '.14s' }}>Ask about schemes, insurance, nearby facilities, affordable medicines, reminders, or plans — I’ll handle the rest.</p>
            <div className="flex flex-wrap justify-center gap-3 pt-2 m3-stagger">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s.q)}
                  className="press lift px-5 py-2.5 rounded-full border border-outline-variant bg-surface-container-lowest hover:bg-surface-container transition-colors text-sm font-medium flex items-center gap-2 elev-1">
                  <Sym name={CHIP_ICON[i % CHIP_ICON.length]} className="text-primary text-[18px]" />
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="max-w-3xl mx-auto space-y-7 mt-2">
          {messages.map(m => {
            const vm = msgVM(m);
            if (vm.isUser) {
              return (
                <div key={vm.id} className="flex justify-end m3-enter">
                  <div className="max-w-[80%] bg-secondary-fixed text-on-secondary-fixed px-5 py-3 rounded-action rounded-tr-md elev-1">
                    <p className="text-[15px] leading-relaxed">{vm.text}</p>
                  </div>
                </div>
              );
            }
            return (
              <div key={vm.id} className="m3-enter">
                {vm.animating && <AgentFlowAnimation orch={vm.orch} subs={vm.subs} />}

                {vm.isClarify && (
                  <div className="flex gap-4">
                    <AiAvatar />
                    {hasPlanStructure(vm.intro)
                      ? <div className="flex-1 min-w-0"><PlanCards text={vm.intro} variant="accordion" /></div>
                      : <div className="flex-1 max-w-[85%] bg-surface-container-lowest border border-outline-variant rounded-card rounded-tl-md px-5 py-3.5">
                          <RichText text={vm.intro} />
                        </div>}
                  </div>
                )}

                {vm.loading && (
                  <div className="flex gap-3 items-center">
                    <M3Loader size={44} />
                    <span className="text-[13.5px] font-semibold gemini-text gemini-sweep">Thinking…</span>
                  </div>
                )}

                {vm.showCard && (
                  <div className="flex gap-4">
                    <AiAvatar />
                    <div className="flex-1 min-w-0 space-y-3">
                      {vm.intro && (hasPlanStructure(vm.intro)
                        ? <PlanCards text={vm.intro} variant="accordion" />
                        : <RichText text={vm.intro} />)}
                      {/* workout / diet plans (full multi-day text rendered as cards) */}
                      {vm.plans?.map((p, i) => (
                        <PlanCards key={i} text={p.text} variant="accordion" />
                      ))}
                      {/* trace pill */}
                      <button onClick={vm.toggleExpand}
                        className="inline-flex items-center gap-2 pl-1 pr-3 py-1 rounded-full border border-outline-variant bg-surface-container-lowest hover:bg-surface-container">
                        <span className="flex">{vm.traceDots.map((d, i) => (
                          <span key={i} className="w-6 h-6 -ml-1.5 first:ml-0 rounded-full intelligence-gradient text-white text-[9px] font-bold flex items-center justify-center border-2 border-surface">{d.initials}</span>
                        ))}</span>
                        <span className="text-[12px] font-semibold text-on-surface-variant">{vm.summaryLabel}</span>
                        <span className="text-[11px] text-on-surface-variant">{vm.expandIcon}</span>
                      </button>
                      {vm.expanded && (
                        <div className="p-3.5 rounded-card bg-surface-container-lowest border border-outline-variant space-y-2">
                          {vm.traceLines.map((t, i) => (
                            <div key={i} className="flex items-center gap-2.5 text-[13px]">
                              <span className="w-6 h-6 rounded-full bg-primary-fixed text-primary text-[10px] font-bold flex items-center justify-center">{t.initials}</span>
                              <span className="font-semibold text-on-surface">{t.name}</span>
                              <span className="text-on-surface-variant">→ {t.status}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      <CarePlanCard msg={vm} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Composer */}
      <div className="absolute bottom-0 left-0 w-full px-6 pb-5 pt-8 bg-gradient-to-t from-background via-background to-transparent pointer-events-none">
        <div className="max-w-3xl mx-auto pointer-events-auto">
          {!noMessages && (
            <div className="flex flex-wrap gap-2 mb-3 justify-center">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s.q)}
                  className="px-3.5 py-1.5 rounded-full border border-outline-variant bg-surface-container-lowest hover:bg-surface-container text-[12.5px] text-on-surface-variant transition-colors">
                  {s.label}
                </button>
              ))}
            </div>
          )}
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <input value={input} onChange={setInput} onKeyDown={onKey}
                placeholder="Describe what you need help with…"
                className="w-full bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-4 focus:ring-primary/10 rounded-action px-6 py-4 shadow-xl text-on-surface outline-none transition-all placeholder:text-on-surface-variant/50" />
            </div>
            <button onClick={() => send()}
              className="w-14 h-14 rounded-full intelligence-gradient text-white flex items-center justify-center shadow-lg shadow-primary/30 hover:scale-105 active:scale-95 transition-transform shrink-0">
              <Sym name="send" className="text-[26px]" fill />
            </button>
          </div>
          <p className="text-center text-[11px] text-on-surface-variant mt-3">WithCare can make mistakes. Please verify important medical and financial details.</p>
        </div>
      </div>
    </main>
  );
}
