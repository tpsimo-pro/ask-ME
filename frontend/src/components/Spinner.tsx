interface SpinnerProps {
  label?: string;
  className?: string;
}

/**
 * Small "scanning" indicator used for async/loading states. Reads as a
 * diagnostic sweep rather than a generic spinner, and respects
 * prefers-reduced-motion (see .scan-sweep in index.css).
 */
export function Spinner({ label, className = "" }: SpinnerProps) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`} role="status" aria-live="polite">
      <span className="relative h-3.5 w-8 overflow-hidden rounded-[2px] border border-signal/40 bg-signal/10">
        <span className="scan-sweep absolute inset-y-0 left-0 w-1/3 bg-signal" />
      </span>
      {label && <span className="font-mono text-xs uppercase tracking-wide text-ink-muted">{label}</span>}
    </span>
  );
}
