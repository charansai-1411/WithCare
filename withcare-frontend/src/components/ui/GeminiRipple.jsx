import React from 'react';

/** Low-opacity Gemini ripple background (public/gemini-ripple.gif), shown behind AI "thinking"
 *  moments only. Decorative + non-interactive. Google trademark; hackathon use only. */
export default function GeminiRipple({ className = '', style }) {
  return (
    <img
      src="/gemini-ripple.gif"
      alt="" aria-hidden="true" draggable={false}
      className={`pointer-events-none select-none ${className}`}
      style={style}
    />
  );
}
