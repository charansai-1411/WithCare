import React from 'react';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const VARIANTS = {
  standard: 'text-on-surface-variant hover:bg-surface-container-high',
  filled:   'bg-primary text-on-primary elev-1 hover:elev-2',
  tonal:    'bg-secondary-fixed text-on-secondary-fixed hover:brightness-95',
  gradient: 'intelligence-gradient text-white elev-2 hover:brightness-105',
  outlined: 'border border-outline-variant text-on-surface-variant hover:bg-surface-container',
};

const SIZES = { sm: 'w-9 h-9 text-[18px]', md: 'w-10 h-10 text-[20px]', lg: 'w-12 h-12 text-[24px]' };

export default function IconButton({ icon, variant = 'standard', size = 'md', fill = false, className = '', ...props }) {
  return (
    <button {...props}
      className={`press inline-flex items-center justify-center rounded-full shrink-0
        transition-[filter,box-shadow,background-color] duration-200 disabled:opacity-50 disabled:pointer-events-none
        ${VARIANTS[variant] || VARIANTS.standard} ${SIZES[size] || SIZES.md} ${className}`}>
      <Sym name={icon} fill={fill} />
    </button>
  );
}
