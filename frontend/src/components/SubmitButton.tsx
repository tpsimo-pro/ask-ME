import { ReactNode } from "react";

interface SubmitButtonProps {
  submitting: boolean;
  submittingLabel: string;
  children: ReactNode;
}

export function SubmitButton({ submitting, submittingLabel, children }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={submitting}
      className="cursor-pointer rounded-[3px] border border-ink bg-ink px-6 py-3 font-sans text-base font-medium text-paper transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
    >
      {submitting ? submittingLabel : children}
    </button>
  );
}
