import React, { useEffect, useRef, useState } from 'react';

// Counts up to `value` on mount (M3 emphasized easing). Respects reduced-motion.
export default function Counter({ value = 0, duration = 700, className = '' }) {
  const target = Number(value) || 0;
  const [n, setN] = useState(0);
  const raf = useRef(0);

  useEffect(() => {
    const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || target === 0) { setN(target); return; }
    const start = performance.now();
    const ease = (t) => 1 - Math.pow(1 - t, 3); // emphasized-ish decelerate
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      setN(Math.round(ease(p) * target));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    // Safety net: guarantee the final value even if rAF is throttled (e.g. background tab).
    const done = setTimeout(() => setN(target), duration + 80);
    return () => { cancelAnimationFrame(raf.current); clearTimeout(done); };
  }, [target, duration]);

  return <span className={className}>{n}</span>;
}
