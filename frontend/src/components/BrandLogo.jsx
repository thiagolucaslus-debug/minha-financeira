import React, { useId } from 'react';

export function BrandLogo({ size = 'md', showSubtitle = false, compact = false }) {
  const uid = useId().replace(/:/g, '');
  const bgId = `mf-bg-${uid}`;
  const goldId = `mf-gold-${uid}`;
  const emId = `mf-em-${uid}`;

  const iconBox =
    size === 'lg'
      ? 'w-12 h-12 rounded-2xl'
      : size === 'sm'
      ? 'w-9 h-9 rounded-xl'
      : 'w-10 h-10 rounded-xl';

  return (
    <div className="inline-flex items-center gap-3 select-none">
      <div
        className={`${iconBox} relative flex-shrink-0 overflow-hidden shadow-goldGlow ring-1 ring-gold-500/40`}
      >
        <svg viewBox="0 0 512 512" fill="none" className="w-full h-full">
          <defs>
            <linearGradient id={bgId} x1="32" y1="24" x2="480" y2="488" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#1B202E" />
              <stop offset="55%" stopColor="#0D1017" />
              <stop offset="100%" stopColor="#06070A" />
            </linearGradient>
            <linearGradient id={goldId} x1="72" y1="68" x2="436" y2="444" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#F3E1AF" />
              <stop offset="50%" stopColor="#C9A45C" />
              <stop offset="100%" stopColor="#8E6C2A" />
            </linearGradient>
            <linearGradient id={emId} x1="312" y1="292" x2="418" y2="394" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#34D399" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
          </defs>
          <rect width="512" height="512" fill={`url(#${bgId})`} />
          <rect
            x="26"
            y="26"
            width="460"
            height="460"
            rx="102"
            stroke={`url(#${goldId})`}
            strokeWidth="12"
            strokeOpacity="0.78"
          />
          <path
            d="M112 366V150H152L214 252L276 150H316V366H274V224L222 310H206L154 224V366H112Z"
            fill={`url(#${goldId})`}
          />
          <path
            d="M338 150H408V188H376V242H402V278H376V366H338V150Z"
            fill={`url(#${goldId})`}
          />
          <path d="M338 332L376 294L414 332L376 370L338 332Z" fill={`url(#${emId})`} />
        </svg>
      </div>
      {!compact && (
        <div className="leading-tight">
          <div
            className={`font-bold tracking-tight ${
              size === 'lg' ? 'text-xl' : size === 'sm' ? 'text-sm' : 'text-base'
            }`}
          >
            <span className="text-[var(--text-primary)]">Minha </span>
            <span className="bg-gradient-to-r from-gold-600 via-gold-500 to-emerald-500 dark:from-gold-300 dark:via-gold-500 dark:to-emerald-400 bg-clip-text text-transparent">
              Financeira
            </span>
          </div>
          {showSubtitle && (
            <div className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)] font-semibold">
              Private Cloud 24/7
            </div>
          )}
        </div>
      )}
    </div>
  );
}
