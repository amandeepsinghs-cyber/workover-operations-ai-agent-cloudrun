import React, { useId } from 'react';

/**
 * Urvi mark (D-42): a bold "U" with a well-pulse line through it, on the blue → indigo tile.
 * Pure SVG so it stays crisp at every size (header 40 px, panel 28 px, chat avatar 24 px, favicon).
 * The favicon in index.html uses the same paths; keep them in sync.
 */
export const UrviMark: React.FC<{ size?: number; className?: string; title?: string }> = ({
  size = 32,
  className = '',
  title = 'Urvi',
}) => {
  const gid = `urvi-g-${useId().replace(/:/g, '')}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={`shrink-0 ${className}`}
      role="img"
      aria-label={title}
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="32" height="32" rx="8" fill={`url(#${gid})`} />
      {/* The "U" */}
      <path
        d="M9.5 7v9.5a6.5 6.5 0 0 0 13 0V7"
        fill="none"
        stroke="#ffffff"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Well pulse through the D */}
      <polyline
        points="5,16 10.5,16 12.6,12 15.4,21 17.8,13.5 19.6,16 27,16"
        fill="none"
        stroke="#5eead4"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};
