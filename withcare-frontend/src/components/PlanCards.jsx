import React, { useState } from 'react';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const dayLabel = (num) => WEEKDAYS[num - 1] || `Day ${num}`;

// Rotating Google colors, applied as LIGHT tints across the whole element so text stays readable.
const DAY_STYLES = [
  { fill: 'bg-g-yellow/15', head: 'bg-g-yellow/25', on: 'bg-g-yellow/30', ring: 'border-g-yellow/40', text: 'text-g-yellow', dot: 'bg-g-yellow' },
  { fill: 'bg-g-blue/15',   head: 'bg-g-blue/25',   on: 'bg-g-blue/30',   ring: 'border-g-blue/40',   text: 'text-g-blue',   dot: 'bg-g-blue' },
  { fill: 'bg-g-red/15',    head: 'bg-g-red/25',    on: 'bg-g-red/30',    ring: 'border-g-red/40',    text: 'text-g-red',    dot: 'bg-g-red' },
  { fill: 'bg-g-green/15',  head: 'bg-g-green/25',  on: 'bg-g-green/30',  ring: 'border-g-green/40',  text: 'text-g-green',  dot: 'bg-g-green' },
];
const styleFor = (num) => DAY_STYLES[(num - 1) % DAY_STYLES.length];

const DAY_RE = /^\*{0,2}\s*Day\s+(\d+)\b\s*[:\-–—]?\s*(.*?)\s*\*{0,2}$/i;
const FOOTER_RE = /^\*{0,2}\s*(Adaptivity Note|Disclaimer|Note|Important|General)\b/i;

// Split plan text into { intro, days[], footer } by "Day N" headers.
export function parsePlan(text) {
  const lines = (text || '').split('\n').map((l) => l.trim());
  const intro = [], days = [], footer = [];
  let cur = null, inFooter = false;
  for (const line of lines) {
    if (!line || /^-{2,}$/.test(line) || line === '—') continue;
    const dm = line.match(DAY_RE);
    if (dm) {
      inFooter = false;
      cur = { num: parseInt(dm[1], 10), title: dm[2].replace(/\*+/g, '').trim(), lines: [] };
      days.push(cur);
      continue;
    }
    if (FOOTER_RE.test(line)) inFooter = true;
    if (inFooter) footer.push(line);
    else if (cur) cur.lines.push(line);
    else intro.push(line);
  }
  return { intro: intro.join(' ').replace(/\*\*/g, '').trim(), days, footer: footer.join('\n') };
}

// True when the text is a real multi-day plan (used to decide chat rendering).
export function hasPlanStructure(text) {
  return parsePlan(text).days.length >= 2;
}

// ── inline **bold** (no HTML injection) ──
function Inline({ text }) {
  const parts = (text || '').split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    const m = p.match(/^\*\*([^*]+)\*\*$/);
    return m
      ? <strong key={i} className="font-semibold text-on-surface">{m[1]}</strong>
      : <span key={i}>{p}</span>;
  });
}

// Group a day's raw lines into labeled sub-sections + a rationale note.
function buildSections(lines) {
  const sections = [];
  let cur = null, rationale = '';
  for (const raw of lines) {
    const line = raw.trim().replace(/^[*\-]\s+/, '');
    if (!line) continue;
    if (/^\**\s*Rationale\b/i.test(line)) {
      rationale = line.replace(/^\**\s*Rationale\s*\**\s*:?\s*\**\s*/i, '');
      cur = null;
      continue;
    }
    // "**Label:** value"  or  "**Heading:**"
    const labeled = line.match(/^\*\*([^*]+?):?\*\*\s*(.*)$/);
    if (labeled) {
      cur = { label: labeled[1].trim(), value: labeled[2].trim(), items: [] };
      sections.push(cur);
      continue;
    }
    // otherwise it's an item (exercise/food) belonging to the current section
    if (cur) cur.items.push(line);
    else { cur = { label: '', value: line, items: [] }; sections.push(cur); }
  }
  return { sections, rationale };
}

// "Name: detail" → bold the name; else render inline.
function Item({ text }) {
  const m = text.match(/^([^:]{2,44}):\s*(.+)$/);
  if (m) return <><strong className="font-medium text-on-surface">{m[1]}:</strong> <Inline text={m[2]} /></>;
  return <Inline text={text} />;
}

function DayBody({ day, styleObj }) {
  const { sections, rationale } = buildSections(day.lines);
  return (
    <div className="flex flex-col gap-2.5">
      {sections.map((s, i) => (
        <div key={i}>
          {s.label && (
            <div className="flex items-center gap-1.5 text-[13px] font-semibold text-on-surface mb-0.5">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${styleObj.dot}`} />{s.label}
            </div>
          )}
          {s.value && <div className={`text-[13px] text-on-surface-variant leading-relaxed ${s.label ? 'pl-3' : ''}`}><Inline text={s.value} /></div>}
          {s.items.length > 0 && (
            <div className={`flex flex-col gap-0.5 mt-0.5 ${s.label ? 'pl-3' : ''}`}>
              {s.items.map((it, j) => (
                <div key={j} className="flex items-start gap-1.5 text-[12.5px] text-on-surface-variant leading-relaxed">
                  <span className="mt-1.5 w-1 h-1 rounded-full bg-on-surface-variant/40 shrink-0" />
                  <span><Item text={it} /></span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {rationale && (
        <div className="text-[12.5px] text-on-surface-variant bg-surface-container-lowest/70 rounded-lg px-3 py-2 leading-relaxed">
          <span className="font-semibold">Why: </span><Inline text={rationale} />
        </div>
      )}
    </div>
  );
}

// ── Variant: accordion (stacked collapsible horizontal bars) — used in chat ──
function Accordion({ intro, days, footer }) {
  const [open, setOpen] = useState({});
  return (
    <div className="space-y-2">
      {intro && <p className="text-[14px] text-on-surface leading-relaxed mb-1">{intro}</p>}
      {days.map((d) => {
        const s = styleFor(d.num);
        const isOpen = !!open[d.num];
        return (
          <div key={d.num} className={`rounded-xl border ${s.ring} overflow-hidden`}>
            <button onClick={() => setOpen((o) => ({ ...o, [d.num]: !o[d.num] }))}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left ${s.head} hover:brightness-[0.98] transition`}>
              <span className={`w-7 h-7 rounded-full bg-surface-container-lowest flex items-center justify-center text-[12px] font-bold shrink-0 ${s.text}`}>{d.num}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-semibold text-on-surface leading-tight">{dayLabel(d.num)}</div>
                {d.title && <div className="text-[12px] text-on-surface/60 truncate">{d.title}</div>}
              </div>
              <Sym name={isOpen ? 'expand_less' : 'expand_more'} className="text-on-surface-variant text-[20px]" />
            </button>
            {isOpen && (
              <div className={`px-4 py-3 border-t ${s.ring} ${s.fill}`}>
                <DayBody day={d} styleObj={s} />
              </div>
            )}
          </div>
        );
      })}
      {footer && <div className="text-[12px] text-on-surface-variant/80 leading-relaxed whitespace-pre-line pt-1">{footer.replace(/\*\*/g, '')}</div>}
    </div>
  );
}

// ── Variant: tabs (horizontal day pills + detail panel) — used in the Plans tab ──
function Tabs({ intro, days, footer }) {
  const [active, setActive] = useState(days[0]?.num ?? 1);
  const cur = days.find((d) => d.num === active) || days[0];
  const cs = styleFor(cur.num);
  return (
    <div>
      {intro && <p className="text-[13.5px] text-on-surface-variant leading-relaxed mb-3">{intro}</p>}

      <div className="flex gap-2 overflow-x-auto pb-1.5 mb-3">
        {days.map((d) => {
          const s = styleFor(d.num);
          const on = d.num === active;
          return (
            <button key={d.num} onClick={() => setActive(d.num)}
              className={`shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[13px] font-medium border transition-colors
                ${on ? `${s.on} ${s.ring} text-on-surface` : 'border-outline-variant text-on-surface-variant hover:bg-surface-container'}`}>
              <span className={`w-2 h-2 rounded-full ${s.dot}`} />{dayLabel(d.num)}
            </button>
          );
        })}
      </div>

      <div className={`rounded-xl border ${cs.ring} ${cs.fill} p-4`}>
        <div className="flex items-center gap-2.5 mb-2.5">
          <span className={`w-8 h-8 rounded-lg bg-surface-container-lowest flex items-center justify-center text-[14px] font-bold shrink-0 ${cs.text}`}>{cur.num}</span>
          <div className="min-w-0">
            <div className="text-[15px] font-semibold text-on-surface leading-tight">{dayLabel(cur.num)}</div>
            {cur.title && <div className="text-[12.5px] text-on-surface/60 truncate">{cur.title}</div>}
          </div>
        </div>
        <DayBody day={cur} styleObj={cs} />
      </div>

      {footer && <div className="mt-3 text-[12px] text-on-surface-variant/80 leading-relaxed whitespace-pre-line border-t border-outline-variant/50 pt-3">{footer.replace(/\*\*/g, '')}</div>}
    </div>
  );
}

export default function PlanCards({ text, variant = 'tabs' }) {
  const parsed = parsePlan(text);
  if (parsed.days.length < 2) {
    // Not a real plan (e.g. an old truncated one) — show the text so nothing is lost.
    return (
      <div className="text-[13.5px] text-on-surface-variant leading-relaxed whitespace-pre-line">
        {(text || '')
          .replace(/\*\*/g, '')
          .replace(/^#{1,6}\s*/gm, '')   // strip markdown heading markers (##, ###) if the model used them
          .replace(/\n-{2,}\n/g, '\n')}
      </div>
    );
  }
  return variant === 'accordion' ? <Accordion {...parsed} /> : <Tabs {...parsed} />;
}
