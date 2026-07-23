import React, { useRef, useEffect, useState } from 'react';
import AgentFlowAnimation from './AgentFlowAnimation';
import CarePlanCard from './CarePlanCard';
import PlanCards, { hasPlanStructure } from './PlanCards';
import ProductCards from './ProductCards';
import GeminiLogo from './ui/GeminiLogo';
import M3Loader from './ui/M3Loader';
import RichText from './ui/RichText';
import { SUGGESTIONS } from '../constants/agents';
import { uploadDocument } from '../services/readerApi';
import VoiceButton from './VoiceButton';
import LiveVoice from './LiveVoice';

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

const needsConnect = (t) => /\bConnectors\b|connect (your |the )?(google )?(calendar|gmail|drive|fit)/i.test(t || '');

export default function ChatThread({ messages, input, setInput, send, onKey, msgVM, userId, onUploaded, onOpenConnectors }) {
  const threadRef = useRef(null);
  const fileRef = useRef(null);
  // Pending attachments — shown as previews, uploaded to the Reader library, and attached to the
  // next message the user sends. { id, name, type, url(objectURL for images), status, error, docId }
  const [attachments, setAttachments] = useState([]);
  const [live, setLive] = useState(false);   // live voice call overlay
  // Keep the latest input value so a voice transcript (which resolves async) appends to
  // whatever is currently typed rather than a stale snapshot.
  const inputRef = useRef(input);
  inputRef.current = input;
  useEffect(() => { if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight; }, [messages]);
  const noMessages = messages.length === 0;

  async function onPickFile(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const id = 'att' + Date.now();
    const isImage = (file.type || '').startsWith('image/');
    const url = isImage ? URL.createObjectURL(file) : '';
    setAttachments((a) => [...a, { id, name: file.name, type: file.type, url, status: 'uploading' }]);
    try {
      const doc = await uploadDocument(userId, file, '');   // → lands in the Reader library
      setAttachments((a) => a.map((x) => x.id === id ? { ...x, status: 'ready', docId: doc?.id } : x));
      onUploaded?.();   // let the Reader refresh if it's open
    } catch (ex) {
      setAttachments((a) => a.map((x) => x.id === id ? { ...x, status: 'error', error: ex.message } : x));
    }
  }
  const dropAttachment = (id) => setAttachments((a) => a.filter((x) => x.id !== id));

  // Send text + any attachments together, then clear the pending attachments.
  // Attachments always show in the message (display doesn't depend on OCR ingest succeeding).
  function submit(text) {
    const payload = attachments.map((a) => ({ name: a.name, type: a.type, url: a.url, docId: a.docId }));
    send(typeof text === 'string' ? text : undefined, payload);
    setAttachments([]);
  }
  function onKeyLocal(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  }

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
                  <div className="max-w-[80%] flex flex-col items-end gap-2">
                    {vm.attachments?.length > 0 && (
                      <div className="flex flex-wrap gap-2 justify-end">
                        {vm.attachments.map((a, i) => (a.url && (a.type || '').startsWith('image/'))
                          ? <img key={i} src={a.url} alt={a.name} title={a.name}
                              className="w-32 h-32 object-cover rounded-2xl border border-outline-variant elev-1" />
                          : <span key={i} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface-container border border-outline-variant text-[12.5px] text-on-surface">
                              <Sym name="description" className="text-primary text-[16px]" fill />{a.name}
                            </span>)}
                      </div>
                    )}
                    {vm.text && (
                      <div className="bg-secondary-fixed text-on-secondary-fixed px-5 py-3 rounded-action rounded-tr-md elev-1">
                        <p className="text-[15px] leading-relaxed">{vm.text}</p>
                      </div>
                    )}
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
                          {onOpenConnectors && needsConnect(vm.intro) && (
                            <button onClick={onOpenConnectors}
                              className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-primary text-on-primary text-[13px] font-semibold hover:brightness-110">
                              <Sym name="hub" className="text-[16px]" /> Open Connectors
                            </button>
                          )}
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
                      {/* product price-comparison cards */}
                      {vm.products?.length > 0 && <ProductCards products={vm.products} />}
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
          {/* Pending attachment previews (image thumbnails / file chips) */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2.5">
              {attachments.map((a) => (
                <div key={a.id}
                  className={`relative flex items-center gap-2 pl-1.5 pr-2 py-1.5 rounded-2xl border bg-surface-container-lowest
                    ${a.status === 'error' ? 'border-error/50' : 'border-outline-variant'}`}>
                  {a.url && (a.type || '').startsWith('image/')
                    ? <img src={a.url} alt={a.name} className="w-10 h-10 rounded-xl object-cover" />
                    : <span className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center"><Sym name="description" className="text-primary text-[20px]" fill /></span>}
                  <div className="min-w-0 max-w-[150px]">
                    <div className="text-[12.5px] text-on-surface truncate">{a.name}</div>
                    <div className={`text-[11px] flex items-center gap-1 ${a.status === 'error' ? 'text-error' : 'text-on-surface-variant'}`}>
                      {a.status === 'uploading' && <><Sym name="progress_activity" className="text-[13px] animate-spin" />Reading…</>}
                      {a.status === 'ready' && <><Sym name="check_circle" className="text-[13px] text-primary" />Ready</>}
                      {a.status === 'error' && <span title={a.error}>Couldn’t read</span>}
                    </div>
                  </div>
                  <button onClick={() => dropAttachment(a.id)} title="Remove"
                    className="w-6 h-6 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high shrink-0">
                    <Sym name="close" className="text-[15px]" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-end gap-3">
            <input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg,image/webp"
              onChange={onPickFile} className="hidden" />
            <button onClick={() => fileRef.current?.click()} title="Attach an image or document (PDF/PNG/JPG)"
              className="w-14 h-14 rounded-full border border-outline-variant bg-surface-container-lowest text-on-surface-variant flex items-center justify-center shadow-sm hover:bg-surface-container active:scale-95 transition shrink-0">
              <Sym name="add" className="text-[26px]" />
            </button>
            <button onClick={() => setLive(true)} title="Talk live with WithCare"
              className="w-14 h-14 rounded-full bg-g-green-tint text-g-green-text border border-g-green/30 flex items-center justify-center shadow-sm hover:brightness-105 active:scale-95 transition shrink-0">
              <Sym name="phone_in_talk" className="text-[24px]" fill />
            </button>
            <div className="flex-1 relative">
              <input value={input} onChange={setInput} onKeyDown={onKeyLocal}
                placeholder="Describe what you need help with, or tap the mic to speak…"
                className="w-full bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-4 focus:ring-primary/10 rounded-action pl-6 pr-28 py-4 shadow-xl text-on-surface outline-none transition-all placeholder:text-on-surface-variant/50" />
              <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
                <VoiceButton userId={userId}
                  onTranscript={(t) => setInput(inputRef.current ? `${inputRef.current} ${t}` : t)} />
              </div>
            </div>
            <button onClick={() => submit()}
              className="w-14 h-14 rounded-full intelligence-gradient text-white flex items-center justify-center shadow-lg shadow-primary/30 hover:scale-105 active:scale-95 transition-transform shrink-0">
              <Sym name="send" className="text-[26px]" fill />
            </button>
          </div>
          <p className="text-center text-[11px] text-on-surface-variant mt-3">WithCare can make mistakes. Please verify important medical and financial details.</p>
        </div>
      </div>

      {live && <LiveVoice onClose={() => setLive(false)} />}
    </main>
  );
}
