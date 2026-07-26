import { ReactNode } from "react";

import { Logo } from "./Logo";

interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-paper px-4 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(var(--color-line)_1px,transparent_1px),linear-gradient(90deg,var(--color-line)_1px,transparent_1px)] [background-size:36px_36px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent)]"
      />

      <div className="relative flex w-full max-w-sm flex-col items-center gap-8">
        <Logo className="scale-125" />

        <div className="text-center">
          <h1 className="font-display text-2xl font-semibold text-ink sm:text-3xl">{title}</h1>
          {subtitle && <p className="mt-2 text-sm leading-relaxed text-ink-muted">{subtitle}</p>}
        </div>

        <div className="w-full">{children}</div>

        {footer && <div className="text-center font-mono text-xs text-ink-muted">{footer}</div>}
      </div>
    </div>
  );
}
