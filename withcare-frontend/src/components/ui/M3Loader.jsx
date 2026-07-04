import React from 'react';
import { M3LoadingIndicator } from '@alerix/m3-loading-indicator/react';

// Reads an M3 color token (space-separated "r g b") into a usable CSS color.
function token(name, alpha) {
  if (typeof window === 'undefined') return alpha ? `rgba(26,115,232,${alpha})` : '#1a73e8';
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!raw) return alpha ? `rgba(26,115,232,${alpha})` : '#1a73e8';
  const rgb = raw.split(/\s+/).join(',');
  return alpha != null ? `rgba(${rgb},${alpha})` : `rgb(${rgb})`;
}

/**
 * Material 3 Expressive *contained* loading indicator — the 7-shape spring morph inside a
 * tonal circular container. Theme-aware (reads the current primary tokens).
 */
export default function M3Loader({ size = 44, speed = 1 }) {
  return (
    <M3LoadingIndicator
      size={size}
      speed={speed}
      color={token('--primary')}
      contained
      containerColor={token('--primary-fixed', 0.55)}
    />
  );
}
