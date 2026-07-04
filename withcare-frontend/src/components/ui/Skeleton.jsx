import React from 'react';

// A single shimmering placeholder block.
export function Skeleton({ className = '', style }) {
  return <div className={`skeleton ${className}`} style={style} />;
}

// A row that mimics a list card while data loads.
export function SkeletonCard() {
  return (
    <div className="flex items-center gap-4 bg-surface-container-lowest border border-outline-variant rounded-card p-4">
      <Skeleton className="w-11 h-11 rounded-xl shrink-0" />
      <div className="flex-1 min-w-0 space-y-2">
        <Skeleton className="h-3.5 w-1/2" />
        <Skeleton className="h-3 w-3/4" />
        <div className="flex gap-1.5 pt-0.5">
          <Skeleton className="h-4 w-16 rounded-full" />
          <Skeleton className="h-4 w-20 rounded-full" />
        </div>
      </div>
    </div>
  );
}

// A list of skeleton cards.
export function SkeletonList({ count = 3 }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  );
}

export default Skeleton;
