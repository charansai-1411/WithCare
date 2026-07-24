import React, { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';

// A guided coach-mark tour: it spotlights each real part of the UI in place
// (Chat, Routines, Connectors…), moving from one to the next and
// explaining it right there. Shown once per user; re-openable from the header “?”.
const KEY = (userId) => `withcare-tutorial-seen-${userId || 'guest'}`;

export function tutorialSeen(userId) {
  try { return localStorage.getItem(KEY(userId)) === '1'; } catch (e) { return true; }
}
export function markTutorialSeen(userId) {
  try { localStorage.setItem(KEY(userId), '1'); } catch (e) {}
}

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Each step points at a real element via its [data-tour] anchor. `view` (optional)
// switches the main content so the user actually sees that section as it's explained.
const STEPS = [
  { sel: '[data-tour="nav-chat"]', view: 'chat', place: 'right', icon: 'chat_bubble',
    title: 'Chat is home',
    body: 'Ask anything about care in plain words — “find a heart hospital near me”, “schemes for my mother’s diabetes”. WithCare works out what to do and does it.' },
  { sel: '[data-tour="new-chat"]', place: 'right', icon: 'add',
    title: 'Start a fresh conversation',
    body: 'Begin a new topic anytime. Your past chats stay listed below under “Recent”.' },
  { sel: '[data-tour="nav-tasks"]', view: 'tasks', place: 'right', icon: 'notifications',
    title: 'Tasks & Reminders',
    body: 'Every reminder and appointment you set shows up here, so nothing slips through.' },
  { sel: '[data-tour="nav-routines"]', view: 'routines', place: 'right', icon: 'event_repeat',
    title: 'Routines',
    body: 'Keep daily care routines — skincare, check-ups, workouts, diet and more — for each person. Add your own or let Gemini draft them, with an optional reminder.' },
  { sel: '[data-tour="nav-reader"]', view: 'reader', place: 'right', icon: 'auto_stories',
    title: 'Reader',
    body: 'Upload an insurance policy, lab report or prescription and get clear, cited answers from your own documents.' },
  { sel: '[data-tour="profiles-section"]', place: 'right', icon: 'groups',
    title: 'Care profiles',
    body: 'Add everyone you look after — parents, kids, even pets — and switch here. The header always shows who you’re managing care for.' },
  { sel: '[data-tour="nav-connectors"]', view: 'connectors', place: 'right', icon: 'hub',
    title: 'Connect Google for real actions',
    body: 'Link Calendar, Gmail, Drive and Fit with your own account. Then reminders, bookings and Health data are real — and nothing happens until you confirm.' },
  { sel: '[data-tour="theme-toggle"]', place: 'bottom', icon: 'dark_mode',
    title: 'Theme & help, anytime',
    body: 'Switch light/dark here, and the “?” next to it reopens this tour whenever you need it.' },
  { sel: '[data-tour="resize"]', place: 'right', icon: 'drag_indicator',
    title: 'Resize the sidebar',
    body: 'Drag this edge to make the sidebar wider or narrower — it remembers your size.' },
];

const PAD = 8;   // spotlight padding around the target
const GAP = 16;  // gap between spotlight and the callout

function placeTip(rect, place, tw, th) {
  const m = 12, vw = window.innerWidth, vh = window.innerHeight;
  let left, top;
  if (place === 'right')      { left = rect.right + GAP;            top = rect.top + rect.height / 2 - th / 2; }
  else if (place === 'left')  { left = rect.left - GAP - tw;        top = rect.top + rect.height / 2 - th / 2; }
  else if (place === 'top')   { left = rect.left + rect.width / 2 - tw / 2; top = rect.top - GAP - th; }
  else /* bottom */           { left = rect.left + rect.width / 2 - tw / 2; top = rect.bottom + GAP; }
  left = Math.max(m, Math.min(left, vw - tw - m));
  top  = Math.max(m, Math.min(top,  vh - th - m));
  return { left, top };
}

export default function Tutorial({ onClose, onNavigate }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const [tip, setTip] = useState(null);
  const tipRef = useRef(null);
  const last = i === STEPS.length - 1;
  const step = STEPS[i];

  const finish = useCallback(() => { onNavigate?.('chat'); onClose(); }, [onNavigate, onClose]);

  // Position the spotlight + callout on the current target; keep it in sync on
  // resize/scroll. Switches the view first so the relevant page is visible.
  useLayoutEffect(() => {
    if (step.view) onNavigate?.(step.view);
    const measure = () => {
      const el = document.querySelector(step.sel);
      if (!el) { setRect(null); return; }
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      const r = el.getBoundingClientRect();
      setRect(r);
      const t = tipRef.current;
      if (t) setTip(placeTip(r, step.place, t.offsetWidth, t.offsetHeight));
    };
    // Measure now, then a few retries so it survives the view switch + layout settling.
    measure();
    const raf = requestAnimationFrame(measure);
    const timers = [setTimeout(measure, 80), setTimeout(measure, 220)];
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    return () => {
      cancelAnimationFrame(raf);
      timers.forEach(clearTimeout);
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [i, step, onNavigate]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') finish();
      else if (e.key === 'ArrowRight') setI((v) => Math.min(STEPS.length - 1, v + 1));
      else if (e.key === 'ArrowLeft') setI((v) => Math.max(0, v - 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [finish]);

  return (
    <div className="fixed inset-0 z-[60]" style={{ pointerEvents: 'none' }}>
      {/* Spotlight: a transparent hole with a giant shadow dimming everything else. */}
      {rect ? (
        <div className="fixed rounded-2xl"
          style={{
            left: rect.left - PAD, top: rect.top - PAD,
            width: rect.width + PAD * 2, height: rect.height + PAD * 2,
            boxShadow: '0 0 0 3px rgb(var(--primary)), 0 0 0 4000px rgb(var(--scrim) / 0.55)',
            transition: 'box-shadow 200ms var(--ease-standard)', pointerEvents: 'none',
          }} />
      ) : (
        // Fallback if a target is missing: just dim the screen.
        <div className="fixed inset-0" style={{ background: 'rgb(var(--scrim) / 0.55)', pointerEvents: 'none' }} />
      )}

      {/* Callout */}
      <div ref={tipRef}
        className="fixed w-[320px] max-w-[calc(100vw-24px)] bg-surface-container-lowest rounded-3xl border border-outline-variant elev-5 p-5 m3-scale-in"
        style={{
          left: tip ? tip.left : '50%', top: tip ? tip.top : '50%',
          transform: tip ? 'none' : 'translate(-50%,-50%)',
          pointerEvents: 'auto', visibility: (tip || !rect) ? 'visible' : 'hidden',
        }}>
        <div className="flex items-center gap-3 mb-2.5">
          <div className="w-10 h-10 rounded-2xl intelligence-gradient flex items-center justify-center shrink-0">
            <Sym name={step.icon} className="text-white text-[22px]" fill />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-semibold text-on-surface-variant tracking-wide">STEP {i + 1} OF {STEPS.length}</div>
            <h2 className="font-title-lg text-[16px] text-on-surface leading-tight truncate">{step.title}</h2>
          </div>
        </div>
        <p className="text-[13.5px] leading-relaxed text-on-surface-variant">{step.body}</p>

        {/* Dots */}
        <div className="flex items-center gap-1.5 mt-4">
          {STEPS.map((_, k) => (
            <button key={k} onClick={() => setI(k)} aria-label={`Step ${k + 1}`}
              className={`h-1.5 rounded-full transition-all duration-300 ${k === i ? 'w-5 bg-primary' : 'w-1.5 bg-outline-variant'}`} />
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between mt-4">
          <button onClick={finish} className="text-[13px] font-medium text-on-surface-variant hover:text-on-surface px-1.5 py-2">
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {i > 0 && (
              <button onClick={() => setI(i - 1)}
                className="press px-4 py-2 rounded-full text-[13px] font-semibold text-on-surface hover:bg-surface-container">
                Back
              </button>
            )}
            <button onClick={() => (last ? finish() : setI(i + 1))}
              className="press px-5 py-2 rounded-full text-[13px] font-semibold bg-primary text-on-primary hover:opacity-90 flex items-center gap-1">
              {last ? 'Done' : 'Next'}
              <Sym name={last ? 'check' : 'arrow_forward'} className="text-[16px]" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
