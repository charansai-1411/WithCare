import React from 'react';

/**
 * The official Google Gemini spark logo (public/gemini-logo.svg).
 * Trademark of Google; used here for the Google Gen AI Hackathon only.
 */
export default function GeminiLogo({ size = 24, className = '', style }) {
  return (
    <img src="/gemini-logo.svg" width={size} height={size} alt="Gemini"
         draggable={false} className={className} style={style} />
  );
}
