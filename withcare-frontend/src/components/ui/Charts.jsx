import React from 'react';

// Lightweight Material 3-styled SVG charts (no chart library). Google palette, rounded bars,
// soft gridlines, tonal area fills. All sized in a fixed viewBox and scaled to 100% width.

const W = 340, H = 176;
const PAD = { l: 30, r: 12, t: 14, b: 24 };
const iw = W - PAD.l - PAD.r;
const ih = H - PAD.t - PAD.b;

const grid = 'rgb(var(--outline-variant))';
const axis = 'rgb(var(--on-surface-variant))';

function niceMax(v) {
  if (v <= 10) return Math.ceil(v);
  const pow = Math.pow(10, Math.floor(Math.log10(v)));
  return Math.ceil(v / pow) * pow;
}

function Grid({ min, max, ticks = 3 }) {
  const lines = [];
  for (let i = 0; i <= ticks; i++) {
    const t = i / ticks;
    const y = PAD.t + ih * (1 - t);
    const val = Math.round(min + (max - min) * t);
    lines.push(
      <g key={i}>
        <line x1={PAD.l} y1={y} x2={W - PAD.r} y2={y} stroke={grid} strokeWidth="1" strokeDasharray={i === 0 ? '' : '3 4'} opacity={i === 0 ? 0.8 : 0.5} />
        <text x={PAD.l - 6} y={y + 3} textAnchor="end" style={{ fontSize: 9, fill: axis }}>{val}</text>
      </g>,
    );
  }
  return <>{lines}</>;
}

function DayLabels({ data }) {
  const bw = iw / data.length;
  return data.map((d, i) => (
    <text key={i} x={PAD.l + bw * i + bw / 2} y={H - 8} textAnchor="middle" style={{ fontSize: 9, fill: axis }}>{d.day}</text>
  ));
}

export function BarChart({ data, valueKey = 'value', color = '#1a73e8', unit = '', goal }) {
  const vals = data.map((d) => d[valueKey]);
  const max = niceMax(Math.max(goal || 0, ...vals) * 1.1);
  const bw = iw / data.length;
  const barW = Math.min(26, bw * 0.5);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" preserveAspectRatio="xMidYMid meet">
      <Grid min={0} max={max} />
      {goal != null && (
        <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + ih * (1 - goal / max)} y2={PAD.t + ih * (1 - goal / max)}
          stroke={color} strokeWidth="1.5" strokeDasharray="4 3" opacity="0.55" />
      )}
      {data.map((d, i) => {
        const v = d[valueKey];
        const bh = Math.max(2, ih * (v / max));
        const x = PAD.l + bw * i + (bw - barW) / 2;
        const y = PAD.t + ih - bh;
        return (
          <g key={i}>
            <title>{`${d.day}: ${v}${unit}`}</title>
            <rect x={x} y={y} width={barW} height={bh} rx={barW / 2} fill={color}
              opacity={i === data.length - 1 ? 1 : 0.78} />
          </g>
        );
      })}
      <DayLabels data={data} />
    </svg>
  );
}

export function LineChart({ data, series, unit = '', minPad = 6 }) {
  const allVals = data.flatMap((d) => series.map((s) => d[s.key]));
  const rawMin = Math.min(...allVals), rawMax = Math.max(...allVals);
  const min = Math.max(0, Math.floor(rawMin - minPad));
  const max = Math.ceil(rawMax + minPad);
  const bw = iw / data.length;
  const px = (i) => PAD.l + bw * i + bw / 2;
  const py = (v) => PAD.t + ih * (1 - (v - min) / (max - min || 1));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" preserveAspectRatio="xMidYMid meet">
      <Grid min={min} max={max} />
      {series.map((s) => {
        const pts = data.map((d, i) => `${px(i)},${py(d[s.key])}`).join(' ');
        const area = `M ${px(0)},${PAD.t + ih} L ${data.map((d, i) => `${px(i)},${py(d[s.key])}`).join(' L ')} L ${px(data.length - 1)},${PAD.t + ih} Z`;
        return (
          <g key={s.key}>
            <path d={area} fill={s.color} opacity="0.10" />
            <polyline points={pts} fill="none" stroke={s.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
            {data.map((d, i) => (
              <g key={i}>
                <title>{`${d.day} — ${s.label || s.key}: ${d[s.key]}${unit}`}</title>
                <circle cx={px(i)} cy={py(d[s.key])} r={i === data.length - 1 ? 4 : 2.8} fill="rgb(var(--surface))" stroke={s.color} strokeWidth="2" />
              </g>
            ))}
          </g>
        );
      })}
      <DayLabels data={data} />
    </svg>
  );
}

// Circular progress ring (today's goal), M3 style.
export function Ring({ value, goal, color = '#1a73e8', size = 96, stroke = 10, children }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, goal ? value / goal : 0));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} opacity="0.16" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset .8s var(--ease-emph-decel, ease)' }} />
      {children && (
        <foreignObject x="0" y="0" width={size} height={size}>
          <div style={{ width: size, height: size }} className="flex flex-col items-center justify-center text-center">{children}</div>
        </foreignObject>
      )}
    </svg>
  );
}
