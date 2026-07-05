import React from 'react';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Rotating Google colors — filled as a light tint across each card so text stays readable.
const CARD_STYLES = [
  { fill: 'bg-g-blue/10',   ring: 'border-g-blue/40',   chip: 'bg-g-blue text-white',   accent: 'text-g-blue',   icon: 'shopping_bag' },
  { fill: 'bg-g-red/10',    ring: 'border-g-red/40',    chip: 'bg-g-red text-white',    accent: 'text-g-red',    icon: 'storefront' },
  { fill: 'bg-g-yellow/12', ring: 'border-g-yellow/50', chip: 'bg-g-yellow text-white', accent: 'text-g-yellow', icon: 'local_mall' },
  { fill: 'bg-g-green/10',  ring: 'border-g-green/40',  chip: 'bg-g-green text-white',  accent: 'text-g-green',  icon: 'medical_services' },
];
const styleFor = (i) => CARD_STYLES[i % CARD_STYLES.length];

function ProductCard({ p, i }) {
  const s = styleFor(i);
  return (
    <div className={`relative flex flex-col rounded-2xl border ${s.ring} ${s.fill} p-4 min-h-[172px] press lift`}>
      {/* platform + cheapest tag */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-1 rounded-full ${s.chip}`}>
          <Sym name={s.icon} className="text-[13px]" fill />{p.platform || 'Store'}
        </span>
        {p.tag && (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-container-lowest border border-outline-variant text-on-surface uppercase tracking-wide">
            {p.tag}
          </span>
        )}
      </div>

      {/* name */}
      <div className="text-[13.5px] font-semibold text-on-surface leading-snug line-clamp-2">{p.name}</div>

      {/* price */}
      <div className="flex items-baseline gap-2 mt-2">
        <span className={`text-[22px] font-extrabold leading-none ${s.accent}`}>{p.priceDisplay || '—'}</span>
        {p.rating && <span className="text-[11.5px] font-medium text-on-surface-variant">{p.rating}</span>}
      </div>

      {/* suggestion / note */}
      {p.note && (
        <div className="text-[12px] text-on-surface-variant mt-1.5 leading-snug line-clamp-2 flex items-start gap-1">
          <Sym name="lightbulb" className={`text-[13px] mt-0.5 ${s.accent}`} fill />
          <span>{p.note}</span>
        </div>
      )}

      {/* buy link */}
      <div className="mt-auto pt-3">
        {p.url ? (
          <a href={p.url} target="_blank" rel="noopener noreferrer"
            className={`inline-flex items-center gap-1.5 text-[12.5px] font-bold ${s.accent} hover:underline`}>
            View & buy <Sym name="open_in_new" className="text-[15px]" />
          </a>
        ) : (
          <span className="text-[12px] text-on-surface-variant/70">Link unavailable</span>
        )}
      </div>
    </div>
  );
}

export default function ProductCards({ products }) {
  if (!products || products.length === 0) return null;
  const anyMedicine = products.some((p) => p.isMedicine);
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-primary">
        <Sym name="sell" className="text-[15px]" fill /> Price comparison · cheapest first
      </div>
      {/* rectangular cards, side by side, max 3 per row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {products.map((p, i) => <ProductCard key={i} p={p} i={i} />)}
      </div>
      {anyMedicine && (
        <div className="flex items-start gap-1.5 text-[11.5px] text-on-surface-variant/90 bg-surface-container-low border border-outline-variant/60 rounded-xl px-3 py-2 mt-1">
          <Sym name="info" className="text-[15px] text-primary mt-0.5" />
          <span>Prices are indicative and can change. For a medicine, confirm the exact product and dose with your doctor or pharmacist before buying.</span>
        </div>
      )}
    </div>
  );
}
