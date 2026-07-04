import React, { useId } from 'react';

/**
 * Gemini-style four-point spark (concave-sided star), filled with the official Gemini
 * gradient (#4796E3 → #9177C7 → #CA6673) or a solid color.
 *
 * NOTE: The Gemini mark is Google's trademark; used here for a Google Gen AI hackathon only.
 */
export default function GeminiSpark({ size = 24, fill = 'gradient', className = '', style }) {
  const id = useId().replace(/:/g, '');
  const paint = fill === 'gradient' ? `url(#gm-${id})` : fill;
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className={className} style={style}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      {fill === 'gradient' && (
        <defs>
          <linearGradient id={`gm-${id}`} x1="2" y1="3" x2="22" y2="21" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#4796E3" />
            <stop offset="50%" stopColor="#9177C7" />
            <stop offset="100%" stopColor="#CA6673" />
          </linearGradient>
        </defs>
      )}
      {/* 4-point star with concave sides (the Gemini spark silhouette) */}
      <path fill={paint}
        d="M12 1
           C12.7 6.6 13.8 9.2 15.3 10.7 16.8 12.2 19.4 13.3 23 12
           19.4 12.7 16.8 13.8 15.3 15.3 13.8 16.8 12.7 19.4 12 23
           11.3 19.4 10.2 16.8 8.7 15.3 7.2 13.8 4.6 12.7 1 12
           4.6 11.3 7.2 10.2 8.7 8.7 10.2 7.2 11.3 4.6 12 1 Z" />
    </svg>
  );
}
