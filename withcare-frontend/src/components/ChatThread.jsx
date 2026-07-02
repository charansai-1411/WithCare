// withcare-frontend/src/components/ChatThread.jsx
import React, { useRef, useEffect } from 'react';
import AgentFlowAnimation from './AgentFlowAnimation';
import CarePlanCard from './CarePlanCard';
import { SUGGESTIONS } from '../constants/agents';

export default function ChatThread({ messages, input, setInput, send, onKey, msgVM, accent }) {
  const threadRef = useRef(null);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages]);

  const noMessages = messages.length === 0;

  const sendBtnStyle = {
    width: '40px', height: '40px', borderRadius: '13px', border: 'none', cursor: 'pointer',
    background: accent, color: '#fff', fontSize: '19px', flex: '0 0 auto',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  return (
    <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: '#F6F2EC', overflow: 'hidden' }}>

      {/* Thread scroll area */}
      <div ref={threadRef} style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0 }}>
        <div style={{ maxWidth: '780px', margin: '0 auto', padding: '28px 28px 40px' }}>

          {/* Welcome / empty state */}
          {noMessages && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '64px 12px 24px' }}>
              <div style={{ width: '56px', height: '56px', borderRadius: '16px', background: accent, color: '#fff', fontFamily: "'Newsreader', serif", fontSize: '30px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>w</div>
              <div style={{ fontFamily: "'Newsreader', serif", fontSize: '30px', fontWeight: 500, letterSpacing: '-0.01em', marginTop: '22px', color: '#26322F' }}>How can I help with your care today?</div>
              <div style={{ fontSize: '15px', color: '#8C9087', marginTop: '10px', maxWidth: '440px', lineHeight: 1.5 }}>Ask about schemes, insurance, nearby facilities, affordable medicines, or scheduling — I&rsquo;ll handle the rest.</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center', marginTop: '26px', maxWidth: '560px' }}>
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} onClick={() => send(s.q)} style={{ padding: '11px 16px', borderRadius: '999px', border: '1px solid #E0D8C9', background: '#FBF9F4', color: '#4A554F', fontSize: '13.5px', cursor: 'pointer' }}>{s.label}</button>
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          {messages.map(m => {
            const vm = msgVM(m, accent);
            return (
              <div key={vm.id} style={{ marginBottom: '28px' }}>

                {/* User message */}
                {vm.isUser && (
                  <div style={{ maxWidth: '560px', marginLeft: 'auto', background: '#E7F0EB', border: '1px solid #DBE8E1', borderRadius: '18px 18px 6px 18px', padding: '13px 17px', fontSize: '15px', lineHeight: 1.5, color: '#2A3833' }}>
                    {vm.text}
                  </div>
                )}

                {/* Assistant message */}
                {vm.isAssistant && (
                  <div>
                    {/* LIVE: animating agent flow */}
                    {vm.animating && <AgentFlowAnimation orch={vm.orch} subs={vm.subs} />}

                    {/* CLARIFY: plain question bubble */}
                    {vm.isClarify && (
                      <div style={{ display: 'flex', gap: '13px', alignItems: 'flex-start' }}>
                        <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: '#1C7A6A', color: '#fff', fontFamily: "'Newsreader', serif", fontSize: '17px', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>w</div>
                        <div style={{ background: '#fff', border: '1px solid #ECE5D9', borderRadius: '6px 18px 18px 18px', padding: '14px 18px', fontSize: '15px', lineHeight: 1.6, color: '#2E3A35', maxWidth: '620px' }}>
                          {vm.intro}
                        </div>
                      </div>
                    )}

                    {/* LOADING: thinking dots */}
                    {vm.loading && (
                      <div style={{ display: 'flex', gap: '13px', alignItems: 'center' }}>
                        <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: '#1C7A6A', color: '#fff', fontFamily: "'Newsreader', serif", fontSize: '17px', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>w</div>
                        <div style={{ fontSize: '22px', color: '#1C7A6A', letterSpacing: '3px' }}>···</div>
                      </div>
                    )}

                    {/* DONE: collapsed trace + care plan card */}
                    {vm.showCard && (
                      <div>
                        {/* Trace summary pill */}
                        <button onClick={vm.toggleExpand} style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', padding: '7px 13px 7px 9px', borderRadius: '999px', border: '1px solid #E6DFD2', background: '#FBF9F4', cursor: 'pointer', marginBottom: '14px' }}>
                          <span style={{ display: 'inline-flex' }}>
                            {vm.traceDots.map((d, i) => (
                              <span key={i} style={d.style}>{d.initials}</span>
                            ))}
                          </span>
                          <span style={{ fontSize: '12.5px', fontWeight: 600, color: '#5A655F' }}>{vm.summaryLabel}</span>
                          <span style={{ fontSize: '11px', color: '#A39C8C' }}>{vm.expandIcon}</span>
                        </button>

                        {/* Expanded trace detail */}
                        {vm.expanded && (
                          <div style={{ margin: '-4px 0 16px', padding: '14px 16px', borderRadius: '14px', background: '#FBF9F4', border: '1px solid #EAE3D6', display: 'flex', flexDirection: 'column', gap: '9px' }}>
                            {vm.traceLines.map((t, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '11px' }}>
                                <span style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#EEF4F1', color: '#1C7A6A', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>{t.initials}</span>
                                <span style={{ fontSize: '13px', fontWeight: 600, color: '#2C3833' }}>{t.name}</span>
                                <span style={{ fontSize: '12.5px', color: '#7C8479' }}>&rarr; {t.status}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        <CarePlanCard msg={vm} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Composer */}
      <div style={{ padding: '8px 28px 20px' }}>
        <div style={{ maxWidth: '780px', margin: '0 auto' }}>
          {/* Suggestion chips (shown in composer area too) */}
          {!noMessages && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '11px' }}>
              {SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s.q)} style={{ padding: '8px 14px', borderRadius: '999px', border: '1px solid #E4DCCE', background: '#FBF9F4', color: '#5A655F', fontSize: '12.5px', cursor: 'pointer' }}>{s.label}</button>
              ))}
            </div>
          )}

          {/* Input box */}
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '10px', background: '#fff', border: '1px solid #E2DACB', borderRadius: '18px', padding: '8px 8px 8px 18px', boxShadow: '0 4px 20px rgba(40,30,20,0.05)' }}>
            <input
              value={input}
              onChange={setInput}
              onKeyDown={onKey}
              placeholder="Describe what you need help with…"
              style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: '15px', color: '#26322F', padding: '9px 0' }}
            />
            <button onClick={() => send()} style={sendBtnStyle}>↑</button>
          </div>

          <div style={{ textAlign: 'center', fontSize: '11.5px', color: '#A8A293', marginTop: '9px' }}>
            Withcare can make mistakes. Please verify important medical and financial details.
          </div>
        </div>
      </div>
    </main>
  );
}
