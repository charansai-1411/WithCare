import React from 'react';

// Inline **bold** (no HTML injection).
function Inline({ text }) {
  const parts = (text || '').split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    const m = p.match(/^\*\*([^*]+)\*\*$/);
    return m ? <strong key={i} className="font-semibold">{m[1]}</strong> : <span key={i}>{p}</span>;
  });
}

/**
 * Lightweight, safe markdown for assistant prose so raw `**` / `* ` never show.
 * Handles: **bold**, `* ` / `- ` bullets, and blank-line paragraph breaks.
 */
export default function RichText({ text, className = '' }) {
  const lines = (text || '').split('\n');
  const blocks = [];
  let list = null;
  for (const raw of lines) {
    const line = raw.trim();
    const bullet = line.match(/^[*\-]\s+(.*)$/);
    if (bullet) {
      if (!list) { list = []; blocks.push({ type: 'ul', items: list }); }
      list.push(bullet[1]);
    } else {
      list = null;
      if (line) blocks.push({ type: 'p', text: line.replace(/^#+\s*/, '') });
    }
  }
  return (
    <div className={`text-[15px] leading-relaxed text-on-surface space-y-2 ${className}`}>
      {blocks.map((b, i) =>
        b.type === 'ul' ? (
          <ul key={i} className="space-y-1">
            {b.items.map((it, j) => (
              <li key={j} className="flex items-start gap-2">
                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                <span><Inline text={it} /></span>
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}><Inline text={b.text} /></p>
        )
      )}
    </div>
  );
}
