import React from 'react';
import GeminiLogo from './GeminiLogo';

// "Built with Gemini" attribution chip.
export function GeminiBadge({ label = 'Built with Gemini', className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-outline-variant bg-surface-container-lowest text-[11px] font-medium text-on-surface-variant ${className}`}>
      <GeminiLogo size={14} /> {label}
    </span>
  );
}

// Trademark disclaimer for the Gemini mark (hackathon use).
export function GeminiDisclaimer({ className = '' }) {
  return (
    <p className={`text-[10.5px] leading-relaxed text-on-surface-variant/70 ${className}`}>
      The Gemini name and spark are trademarks of Google. WithCare is an independent project built
      for the Google Gen AI Hackathon and is not affiliated with or endorsed by Google.
    </p>
  );
}

export default GeminiBadge;
