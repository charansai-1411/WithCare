import React from 'react';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

// Material 3 button variants. Ripple is added globally (index.html) to every <button>.
const VARIANTS = {
  filled:   'bg-primary text-on-primary elev-1 hover:elev-2',
  gradient: 'intelligence-gradient text-white elev-2 hover:brightness-105',
  tonal:    'bg-secondary-fixed text-on-secondary-fixed hover:brightness-95',
  outlined: 'border border-outline-variant text-primary hover:bg-primary-fixed/40',
  text:     'text-primary hover:bg-primary-fixed/40',
  elevated: 'bg-surface-container-lowest text-primary elev-1 hover:elev-2',
};

const SIZES = {
  sm: 'h-9 px-4 text-[13px]',
  md: 'h-11 px-6 text-[14px]',
  lg: 'h-12 px-7 text-[15px]',
};

export default function Button({
  variant = 'filled', size = 'md', icon, trailingIcon, iconFill = false,
  full = false, className = '', children, ...props
}) {
  return (
    <button
      {...props}
      className={`press inline-flex items-center justify-center gap-2 rounded-full font-button-text
        transition-[filter,box-shadow,background-color] duration-200 disabled:opacity-50 disabled:pointer-events-none
        ${VARIANTS[variant] || VARIANTS.filled} ${SIZES[size] || SIZES.md} ${full ? 'w-full' : ''} ${className}`}>
      {icon && <Sym name={icon} className="text-[20px]" fill={iconFill} />}
      {children}
      {trailingIcon && <Sym name={trailingIcon} className="text-[20px]" fill={iconFill} />}
    </button>
  );
}
