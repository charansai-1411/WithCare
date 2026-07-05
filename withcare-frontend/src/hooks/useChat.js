import { useState, useRef, useEffect, useCallback } from 'react';
import { AGENTS } from '../constants/agents';
import { streamChat } from '../services/api';

const AGENT_KEY = {
  orchestrator:  'orchestrator',
  scheme_agent:  'scheme',
  facility_agent:'facility',
  action_agent:  'action',
  reminder_agent:'reminder',
  workout_agent: 'workout',
  diet_agent:    'diet',
  product_agent: 'product',
  reader:        'reader',
};

// Convert backend ordered_steps → UI plan shape
function stepsToPlan(steps) {
  const facilities = [];
  const coverage   = [];
  const plans      = [];
  const products   = [];
  const schedule   = { events: [], bothCalendars: false, confirmText: 'Added to your calendar' };

  for (const step of steps) {
    const agent = step.agent || '';
    const url   = step.source_url || '';

    if (agent === 'product_agent') {
      const m = step.meta || {};
      products.push({
        name:         step.action,
        platform:     step.source_label || m.platform || '',
        priceDisplay: m.price_display || '',
        price:        m.price_inr ?? null,
        rating:       m.rating || '',
        note:         step.detail || m.note || '',
        url,
        tag:          m.tag || '',
        isMedicine:   !!m.is_medicine,
      });
    } else if (agent === 'diet_agent' || agent === 'workout_agent') {
      // Full multi-day plan text — rendered as an accordion card in chat.
      plans.push({
        kind:  agent === 'diet_agent' ? 'diet' : 'workout',
        title: step.action,
        text:  step.detail || '',
      });
    } else if (agent === 'facility_agent') {
      const isMaps = url.includes('google.com/maps');
      facilities.push({
        name:        step.action.replace(/^Visit /, '').replace(/ \(nearby\)$/, ''),
        detail:      step.detail,
        distance_km: step.distance_km ?? null,
        distance:    step.distance_km != null ? `${step.distance_km.toFixed(1)} km` : null,
        source:      isMaps ? 'Google Maps' : step.source_label,
        url,
      });
    } else if (agent === 'scheme_agent') {
      coverage.push({
        name:   step.action.replace(/^Apply for /, ''),
        detail: step.detail,
        value:  '',
        source: step.source_label,
        url,
      });
    } else if (agent === 'action_agent') {
      if (url.includes('calendar.google.com') || url.includes('google.com/calendar')) {
        schedule.events.push({ title: step.action, when: extractDate(step.detail), url });
        schedule.confirmText = 'Added to your Google Calendar';
      } else if (url.includes('docs.google.com')) {
        schedule.driveUrl  = url;
        schedule.driveNote = step.action;
      }
    }
  }

  return {
    facilities,
    coverage,
    medicines: [],
    plans,
    products,
    schedule: schedule.events.length > 0 ? schedule : null,
  };
}

function extractDate(detail) {
  const m = detail.match(/\d{4}-\d{2}-\d{2}/);
  if (m) {
    const d = new Date(m[0]);
    return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }) + ' · 10:00 AM IST';
  }
  return 'Scheduled — check your Google Calendar';
}

function buildAgentTrace(thinkingChunks) {
  const seen = new Set();
  const trace = [];
  for (const c of thinkingChunks) {
    const key = AGENT_KEY[c.agent] || c.agent || 'orchestrator';
    if (!seen.has(key)) {
      seen.add(key);
      trace.push({ id: key, status: c.content });
    } else {
      const existing = trace.find(t => t.id === key);
      if (existing) existing.status = c.content;
    }
  }
  return trace.length > 0 ? trace : [{ id: 'orchestrator', status: 'Processing your request...' }];
}

// Convert a DB message record → UI message shape
export function dbMsgToUiMsg(dbMsg) {
  if (dbMsg.role === 'user') {
    return { id: dbMsg.id, role: 'user', text: dbMsg.content };
  }
  // assistant
  const carePlan = dbMsg.care_plan;
  const hasPlan  = carePlan && carePlan.ordered_steps && carePlan.ordered_steps.length > 0;
  const plan     = hasPlan ? stepsToPlan(carePlan.ordered_steps) : null;
  const agentCount = hasPlan
    ? new Set(carePlan.ordered_steps.map(s => s.agent).filter(Boolean)).size
    : 1;
  const intro = (hasPlan && carePlan.message)
    ? carePlan.message
    : hasPlan
      ? `Here's your care plan — I consulted ${agentCount} specialist${agentCount !== 1 ? 's' : ''} to find the best options for you.`
      : dbMsg.content;
  return {
    id: dbMsg.id,
    role: 'assistant',
    loading: false,
    isClarify: !hasPlan,
    intro,
    plan,
    trace: [{ id: 'orchestrator', status: hasPlan ? 'Care plan ready' : 'Clarified' }],
    error: null,
    expanded: false,
  };
}

function generateSessionId() {
  return 'sess-' + Math.random().toString(36).slice(2, 10) + '-' + Date.now();
}

export function useChat({ onSave, location = {}, profile = null, userId = '', connectors = [] } = {}) {
  const [messages,  setMessages]  = useState([]);
  const [input,     setInputRaw]  = useState('');
  const [animMsgId, setAnimMsgId] = useState(null);
  const [animStep,  setAnimStep]  = useState(999);

  const sessionId   = useRef(generateSessionId());
  const timerRef    = useRef(null);
  const thinkingRef = useRef([]);

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  function setInput(e) { setInputRaw(typeof e === 'string' ? e : e.target.value); }

  // Reset chat to a pre-loaded set of messages (when switching conversations)
  const reset = useCallback((preloaded = [], convSessionId = null) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setMessages(preloaded);
    setInputRaw('');
    setAnimMsgId(null);
    setAnimStep(999);
    thinkingRef.current = [];
    sessionId.current = convSessionId || generateSessionId();
  }, []);

  function runAnim(aid, traceLen) {
    if (timerRef.current) clearTimeout(timerRef.current);
    let step = 0;
    const STEP_MS = 700;
    const tick = () => {
      step++;
      if (step <= traceLen) {
        setAnimStep(step);
        timerRef.current = setTimeout(tick, STEP_MS);
      } else {
        timerRef.current = setTimeout(() => {
          setAnimMsgId(prev => prev === aid ? null : prev);
          setAnimStep(999);
        }, 600);
      }
    };
    timerRef.current = setTimeout(tick, 400);
  }

  function send(textArg, attachments) {
    const raw = (typeof textArg === 'string' ? textArg : input).trim();
    const atts = Array.isArray(attachments) ? attachments : [];
    if (!raw && atts.length === 0) return;
    // What we send to the agent — if the user only attached a file, prompt it to read the doc.
    const outgoing = raw || 'I’ve attached a document — please read it and answer from it.';

    const now = Date.now();
    const uid = 'u' + now;
    const aid = 'a' + now;

    thinkingRef.current = [];

    // Snapshot history BEFORE adding the new user message
    const history = messages.flatMap(m => {
      if (m.role === 'user') return [{ role: 'user', content: m.text }];
      if (m.role === 'assistant' && !m.loading && m.intro && !m.isClarify) {
        return [{ role: 'assistant', content: m.intro }];
      }
      if (m.role === 'assistant' && m.isClarify && m.intro) {
        return [{ role: 'assistant', content: m.intro }];
      }
      return [];
    });

    setMessages(prev => [
      ...prev,
      { id: uid, role: 'user', text: raw, attachments: atts },
      { id: aid, role: 'assistant', loading: true, trace: [], intro: '', plan: null, error: null, expanded: false },
    ]);
    setInputRaw('');
    setAnimMsgId(aid);
    setAnimStep(0);

    // Save user message to DB
    onSave?.({ role: 'user', content: raw || '(document attached)', title: raw || 'Document' });

    function handleClarify(question) {
      setMessages(prev => prev.map(m =>
        m.id === aid
          ? { ...m, loading: false, isClarify: true, intro: question, trace: [{ id: 'orchestrator', status: 'Need a few more details' }], plan: null, expanded: false }
          : m
      ));
      setAnimMsgId(null);
      // Save clarify as assistant message with no care plan
      onSave?.({ role: 'assistant', content: question, carePlan: null });
    }

    const familyProfile = profile ? [{
      id: profile.id,
      name: profile.name,
      relation: profile.relation || (profile.is_self ? 'self' : ''),
      kind: profile.kind || 'person',
      species: profile.species || '',
      email: profile.email || '',
      // Their Gmail is their primary calendar id; providing it implies consent to sync/share.
      calendar_id: profile.email || null,
      consent_given: !!profile.email,
      age: profile.age ?? null,
      gender: profile.gender || '',
      weight: profile.weight ?? null,
      height: profile.height ?? null,
      conditions: profile.conditions || '',
      notes: profile.notes || '',
    }] : [];
    const forMember = profile ? (profile.is_self ? 'self' : profile.name) : 'self';

    streamChat(
      {
        message: outgoing,
        sessionId: sessionId.current,
        userId,
        history,
        location: location.city || '',
        coordinates: (location.lat && location.lng) ? { lat: location.lat, lng: location.lng } : null,
        familyProfile,
        forMember,
        attachmentDocIds: atts.map(a => a.docId).filter(Boolean),
        connectors,
      },
      {
        onChunk(chunk) {
          if (chunk.type === 'clarify') { handleClarify(chunk.content); return; }
          if (chunk.type === 'thinking') {
            thinkingRef.current.push(chunk);
            const trace = buildAgentTrace(thinkingRef.current);
            setMessages(prev => prev.map(m => m.id === aid ? { ...m, trace } : m));
            setAnimStep(trace.length);
          }
        },

        onDone(carePlan) {
          const steps = carePlan.ordered_steps || [];
          const trace = buildAgentTrace(thinkingRef.current);
          const plan  = stepsToPlan(steps);

          const agentCount = new Set(steps.map(s => s.agent).filter(Boolean)).size;
          // Prefer the Writer's natural message; fall back to the canned line.
          const intro = carePlan.message
            ? carePlan.message
            : carePlan.intent_summary
              ? `Here's your care plan — I consulted ${agentCount} specialist${agentCount !== 1 ? 's' : ''} to find the best options for you.`
              : "Here's what I found for you.";

          setMessages(prev => prev.map(m =>
            m.id === aid ? { ...m, loading: false, trace, intro, plan, expanded: false } : m
          ));
          runAnim(aid, trace.length);

          // Save assistant message with the full care plan
          onSave?.({ role: 'assistant', content: intro, carePlan });
        },

        onError(errMsg) {
          setMessages(prev => prev.map(m =>
            m.id === aid
              ? { ...m, loading: false, error: errMsg, intro: errMsg, trace: [{ id: 'orchestrator', status: 'Error' }] }
              : m
          ));
          setAnimMsgId(null);
        },
      }
    );
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function msgVM(m, accent) {
    if (m.role === 'user') return { id: m.id, isUser: true, isAssistant: false, text: m.text, attachments: m.attachments || [] };

    const animating = animMsgId === m.id;
    const step      = animating ? animStep : 999;
    const trace     = m.trace || [];

    const orchT = trace[0] || { status: 'Routing your request...' };
    const orch = {
      status: orchT.status,
      showStatus: !animating || step >= 1,
      circleStyle: {
        width: '56px', height: '56px', borderRadius: '50%', display: 'flex',
        alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 700,
        background: '#1C7A6A', color: '#fff', letterSpacing: '0.02em',
        animation: animating ? 'wpulse 1.6s ease-out infinite' : 'none',
      },
    };

    const subs = trace.slice(1).map((t, j) => {
      const ag     = AGENTS[t.id] || { name: t.id, initials: '?' };
      const idx    = j + 1;
      const lit    = animating ? step >= idx : true;
      const active = animating && step === idx;
      return {
        id: t.id, name: ag.name, initials: ag.initials, status: t.status,
        rowStyle: {
          display: 'flex', alignItems: 'center', gap: '13px',
          opacity: lit ? 1 : 0.34,
          transform: lit ? 'none' : 'translateX(8px)',
          transition: 'opacity .45s ease, transform .45s ease',
        },
        lineStyle: {
          height: '2px', width: '30px', borderRadius: '2px', flex: '0 0 auto',
          background: lit ? '#1C7A6A' : '#DBD3C6',
          transform: lit ? 'scaleX(1)' : 'scaleX(0)', transformOrigin: 'left',
          transition: 'transform .5s ease, background .4s ease',
        },
        dotStyle: {
          width: '40px', height: '40px', borderRadius: '50%', flex: '0 0 auto',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '12px', fontWeight: 700, transition: 'all .4s ease',
          background: lit ? '#1C7A6A' : '#ECE7DE',
          color: lit ? '#fff' : '#B0A797',
          boxShadow: active ? '0 0 0 4px rgba(28,122,106,0.18)' : 'none',
        },
      };
    });

    const traceLines = trace.map(t => ({
      id: t.id,
      initials: (AGENTS[t.id] || {}).initials || '?',
      name:     (AGENTS[t.id] || {}).name     || t.id,
      status:   t.status,
    }));

    const traceDots = trace.map((t, i) => ({
      initials: (AGENTS[t.id] || {}).initials || '?',
      style: {
        width: '24px', height: '24px', borderRadius: '50%', background: '#1C7A6A',
        color: '#fff', fontSize: '9px', fontWeight: 700,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        border: '2px solid #FBF9F4', marginLeft: i === 0 ? '0' : '-8px',
      },
    }));

    const plan  = m.plan  || {};
    const sched = plan.schedule;

    return {
      id: m.id, isUser: false, isAssistant: true,
      animating,
      showCard: !animating && !m.loading && !m.isClarify,
      isClarify: !!m.isClarify,
      loading: !!m.loading,
      orch, subs,
      intro:  m.error ? m.error : (m.intro || ''),
      isError: !!m.error,
      expanded: !!m.expanded,
      expandIcon: m.expanded ? '▲' : '▼',
      toggleExpand: () => setMessages(prev => prev.map(x => x.id === m.id ? { ...x, expanded: !x.expanded } : x)),
      summaryLabel: trace.length + ' specialists consulted',
      traceLines, traceDots,
      plans:      plan.plans || [],
      products:   plan.products || [],
      hasFacilities: !!(plan.facilities && plan.facilities.length),
      hasCoverage:   !!(plan.coverage   && plan.coverage.length),
      hasMedicines:  !!(plan.medicines  && plan.medicines.length),
      hasSchedule:   !!sched,
      facilities: plan.facilities || [],
      coverage:   plan.coverage   || [],
      medicines:  plan.medicines  || [],
      schedule:   sched || { events: [] },
      confirmStyle: {
        display: 'flex', alignItems: 'center', gap: '12px', marginTop: '15px',
        padding: '13px 15px', borderRadius: '13px', background: '#FFFFFF',
        border: '1px solid #BFE0D2', boxShadow: '0 3px 14px rgba(46,139,111,0.14)',
      },
    };
  }

  return { messages, input, setInput, send, reset, onKey, msgVM };
}
