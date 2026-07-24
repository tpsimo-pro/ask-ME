interface LogoProps {
  className?: string;
  showWordmark?: boolean;
}

/**
 * ask-ME wordmark. Purely presentational — the mark reads as a terminal
 * prompt ("> _") to ground the brand in the product's subject (code).
 */
export function Logo({ className = "", showWordmark = true }: LogoProps) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true" className="shrink-0">
        {/* Fixed dark navy, not the `ink` token: the mark is a brand
            constant and should not invert when the app switches theme. */}
        <rect x="1" y="1" width="24" height="24" rx="6" fill="#14181d" />
        <path
          d="M7.5 9.5L11 13L7.5 16.5"
          stroke="#3DE0D6"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <line x1="13" y1="16.5" x2="18.5" y2="16.5" stroke="#3DE0D6" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      {showWordmark && (
        <span className="font-display text-lg font-semibold tracking-tight text-ink">
          ask<span className="text-signal">-ME</span>
        </span>
      )}
    </span>
  );
}
